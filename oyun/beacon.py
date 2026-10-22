#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
beacon.py - [tur3 2026-10-22] drand quicknet beacon'ı: tur zamanı, açık relay'lerden çekme,
kontroller, kalecinin şut başına yana kayması ve beyin tohumu.

Saf Python 3 (yalnız standart kütüphane + bu klasördeki bls12381.py). Ağ yalnızca 'getir' ve verify.py'nin
relay karşılaştırması için gerekir; BLS imza kontrolü ağsız yapılır.

[tur3 2026-10-22, delik 3] ZİNCİR BİLGİLERİ SABİT: quicknet'in chain_hash, public_key, genesis_time, period ve
şeması bu dosyaya (ve commit.py, verify.py'ye) elle yazılıdır. Config'teki 'beacon' bloğu bunlarla birebir aynı
değilse HATA. Tur saati yalnız bu sabitlerden hesaplanır; config'teki genesis_time'a bakılmaz.

[tur3 2026-10-22, delik 7] BLS İMZASI KONTROL EDİLİR (bls12381.py, bağımlılıksız): e(imza, g2) = e(H(tur), pk).
Geçersiz imzalı beacon kabul edilmez. Relay'ler ek kontroldür: ulaşılan hiçbir relay farklı değer veremez.

Alt komutlar:
  python3.12 -I beacon.py zaman    --config C                      # N turunun yayın saati, kalan süre
  python3.12 -I beacon.py getir    --config C --yaz B [--bekle]    # N'yi relay'lerden çek, BLS + relay kontrolü
  python3.12 -I beacon.py kaymalar --config C --taahhut T --beacon-dosya B [--beyin-cikti YOL]
                                                                    # 5 kayma + beyin tohumu + komutlar

KAYMA KURALI (config.keeper_shift, sürüm 'kayma-v1'):
  anahtar = "<randomness>|<taahhüt SHA-256>"
  u_b = U(anahtar, "kick<n>|kayma_buyukluk"),  u_y = U(anahtar, "kick<n>|kayma_yon")
  U(a, e) = (SHA-256("a|e") ilk 7 bayt, big-endian tamsayı + 0,5) / 2^56     (penalty_model.uniform ile aynı)
  büyüklük = min_m + (max_m - min_m) * u_b ;  işaret = +1 (u_y < p_positive) değilse -1
  keeper_x = round(işaret * büyüklük, round_decimals)
  +x = şutörün sağı = kalecinin SOLU (SOZLESME.md).

BEYİN TOHUMU (delik 6, sürüm 'beyin-tohum-v1'):
  seed_base = int(SHA-256("<randomness>|<taahhüt SHA-256>|beyin|seed_base") onaltılık ilk 8 hane, 16) mod 4 000 000 000
  trial_seed_n = seed_base + n   (kick.py kuralı; Brian2/numpy tohumu 2^32'den küçük olmalı)
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shlex
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # -I removes the script dir from sys.path; this folder is our own code
import penalty_model as pm  # noqa: E402
import bls12381  # noqa: E402

UA = "sinek-penalti-verify/1.1 (+drand quicknet okuyucu)"

# [tur3 2026-10-22] drand quicknet sabitleri (League of Entropy). Kaynak: https://api.drand.sh/<chain>/info,
# 22 Ekim 2026'da üç relay'den aynı okundu. Değiştirmek = başka zincir: HATA.
QUICKNET = {
    "network": "drand quicknet",
    "chain_hash": "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971",
    "public_key": "83cf0f2896adee7eb8b5f01fcad3912212c437e0073e911fb90022d3e760183c8c4b450b6a0a6c3ac6a5776a2d1064510d1fec758c921cc22b0e17e63aaf4bcb5ed66304de9cf809bd274ca73bab4af5a6e9c76a4bc09e76eae8991ef5ece45a",
    "scheme": "bls-unchained-g1-rfc9380",
    "genesis_time": 1692803367,
    "period_s": 3,
    "relays": ["https://api.drand.sh", "https://api2.drand.sh", "https://drand.cloudflare.com"],
}
BEYIN_TOHUM_MOD = 4_000_000_000


# --------------------------------------------------------------------------- sabit zincir
def zincir_farklari(b) -> list:
    """config.beacon bloğu QUICKNET sabitlerinden hangi alanlarda farklı? (boş liste = aynı)"""
    if not isinstance(b, dict):
        return ["beacon bloğu yok"]
    return [k for k, v in QUICKNET.items() if b.get(k) != v]


def round_time(r: int) -> int:
    """N turunun yayın zamanı (unix saniye): genesis + (N - 1) * period, SABİTLERDEN."""
    return QUICKNET["genesis_time"] + (int(r) - 1) * QUICKNET["period_s"]


def round_at(t: float) -> int:
    """t anında yayınlanmış en son tur (ağ gecikmesi hariç), SABİTLERDEN."""
    return int((float(t) - QUICKNET["genesis_time"]) // QUICKNET["period_s"]) + 1


def iso_utc(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(s: str) -> float:
    s = str(s).strip().replace(" ", "T")
    if s.endswith("Z"):
        s = s[:-1]
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.datetime.strptime(s, fmt).replace(tzinfo=datetime.timezone.utc).timestamp()
        except ValueError:
            pass
    raise ValueError(f"UTC zamanı okunamadı: {s!r} (biçim: 2026-10-23T14:05:00Z)")


def yerel(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


# --------------------------------------------------------------------------- kontroller
def imza_ozeti_tutuyor(beacon) -> bool:
    """randomness == SHA-256(signature baytları)."""
    try:
        sig = bytes.fromhex(beacon["signature"])
    except (KeyError, ValueError, TypeError):
        return False
    return hashlib.sha256(sig).hexdigest() == str(beacon.get("randomness", "")).lower()


def bls_dogrula(beacon):
    """(geçerli_mi, açıklama): imza, QUICKNET açık anahtarıyla tur için geçerli mi?"""
    try:
        r = int(beacon["round"])
        sig = str(beacon["signature"]).lower()
    except (KeyError, ValueError, TypeError) as e:
        return False, f"beacon alanları eksik: {e}"
    return bls12381.dogrula_drand(r, sig, QUICKNET["public_key"])


def relay_getir(url: str, chain_hash: str, r: int, timeout: float = 10.0) -> dict:
    """Bir relay'den N turunu çek: {"round", "randomness", "signature"}."""
    req = urllib.request.Request(f"{url.rstrip('/')}/{chain_hash}/public/{int(r)}",
                                 headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (sabit https adresleri)
        d = json.loads(resp.read().decode("utf-8"))
    return {"round": int(d["round"]), "randomness": str(d["randomness"]).lower(),
            "signature": str(d["signature"]).lower()}


def relay_info_getir(url: str, chain_hash: str, timeout: float = 10.0) -> dict:
    """Bir relay'in zincir bilgisi (/info)."""
    req = urllib.request.Request(f"{url.rstrip('/')}/{chain_hash}/info",
                                 headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        d = json.loads(resp.read().decode("utf-8"))
    return {"public_key": str(d.get("public_key", "")).lower(), "period": int(d.get("period", -1)),
            "genesis_time": int(d.get("genesis_time", -1)), "hash": str(d.get("hash", "")).lower(),
            "schemeID": str(d.get("schemeID", ""))}


def info_farklari(info) -> list:
    beklenen = {"public_key": QUICKNET["public_key"], "period": QUICKNET["period_s"],
                "genesis_time": QUICKNET["genesis_time"], "hash": QUICKNET["chain_hash"],
                "schemeID": QUICKNET["scheme"]}
    return [k for k, v in beklenen.items() if info.get(k) != v]


def relaylardan(r: int, fetch=None):
    """Bütün relay'leri dene. [(url, sonuç dict | None, hata str | None)] döner."""
    fetch = fetch or relay_getir
    out = []
    for url in QUICKNET["relays"]:
        try:
            out.append((url, fetch(url, QUICKNET["chain_hash"], r), None))
        except Exception as e:  # ağ yok, zaman aşımı, bozuk yanıt
            out.append((url, None, f"{type(e).__name__}: {e}"))
    return out


def ayni(a, c) -> bool:
    return (int(a["round"]) == int(c["round"]) and a["randomness"].lower() == c["randomness"].lower()
            and a["signature"].lower() == c["signature"].lower())


def relay_karsilastir(beacon, fetch=None, info_fetch=None):
    """Kayıtlı beacon'ı relay'lerle karşılaştır.
    Döner: {"ayni": n, "ulasilan": n, "farkli": n, "info_farkli": [..], "satirlar": [..]}"""
    rows = relaylardan(int(beacon["round"]), fetch)
    info_fetch = info_fetch or relay_info_getir
    res = {"ayni": 0, "ulasilan": 0, "farkli": 0, "info_farkli": [], "satirlar": []}
    for url, got, err in rows:
        if got is None:
            res["satirlar"].append(f"   {url}: ulaşılamadı ({err})")
            continue
        res["ulasilan"] += 1
        try:
            fi = info_farklari(info_fetch(url, QUICKNET["chain_hash"]))
            info_txt = "zincir bilgisi (/info) sabitlerle aynı" if not fi else f"/info FARKLI: {fi}"
            if fi:
                res["info_farkli"].append((url, fi))
        except Exception as e:  # noqa: BLE001
            info_txt = f"/info okunamadı ({type(e).__name__})"
        if ayni(got, beacon):
            res["ayni"] += 1
            res["satirlar"].append(f"   {url}: aynı; {info_txt}")
        else:
            res["farkli"] += 1
            res["satirlar"].append(f"   {url}: FARKLI değer: {got['randomness'][:16]}…; {info_txt}")
    return res


# --------------------------------------------------------------------------- kayma ve beyin tohumu
def kaymalar(cfg, commit_sha: str, randomness: str, n: int):
    """Şut 1..n için kalecinin çizgi üzerindeki x'i (m). Kural: modül başındaki açıklama."""
    ks = cfg["keeper_shift"]
    lo, hi = float(ks["min_m"]), float(ks["max_m"])
    pp = float(ks["p_positive"])
    nd = int(ks["round_decimals"])
    key = f"{str(randomness).lower()}|{str(commit_sha).lower()}"
    out = []
    for k in range(1, int(n) + 1):
        u_b = pm.uniform(key, f"kick{k}|kayma_buyukluk")
        u_y = pm.uniform(key, f"kick{k}|kayma_yon")
        mag = lo + (hi - lo) * u_b
        sign = 1.0 if u_y < pp else -1.0
        out.append(round(sign * mag, nd))
    return out


def beyin_tohum_tabani(commit_sha: str, randomness: str) -> int:
    """[tur3 2026-10-22, delik 6] Beyin tohum tabanı beacon'dan: taahhüt anında kimse bilemez, seçilemez."""
    h = hashlib.sha256(f"{str(randomness).lower()}|{str(commit_sha).lower()}|beyin|seed_base".encode("utf-8"))
    return int(h.hexdigest()[:8], 16) % BEYIN_TOHUM_MOD


def yon_tr(x: float) -> str:
    return "kalecinin soluna = şutörün sağına" if x > 0 else "kalecinin sağına = şutörün soluna"


# --------------------------------------------------------------------------- komutlar
def _cfg_beacon(cfg):
    b = cfg.get("beacon")
    if not isinstance(b, dict) or not b.get("round"):
        raise SystemExit("config'te 'beacon' bloğu ya da beacon.round yok (commit.py yeni yazar).")
    fark = zincir_farklari(b)
    if fark:
        raise SystemExit(f"HATA: config'teki drand zincir bilgileri quicknet sabitleriyle aynı değil: {fark}. "
                         "Başka bir zincir ya da kaydırılmış saat kabul edilmez.")
    return b


def cmd_zaman(a):
    cfg = pm.load_json(a.config)
    b = _cfg_beacon(cfg)
    r = int(b["round"])
    t = round_time(r)
    now = time.time()
    print(f"beacon: {QUICKNET['network']} turu {r}")
    print(f"yayın saati: {iso_utc(t)} (UTC) = {yerel(t)}   [quicknet sabitlerinden]")
    print(f"şu an:       {iso_utc(now)} (UTC); şu anki tur ≈ {round_at(now)}")
    if now < t:
        print(f"kalan: {int(t - now)} s ({(t - now) / 60:.1f} dk)")
    else:
        print(f"bu tur {int(now - t)} s önce yayınlandı.")


def cmd_getir(a):
    cfg = pm.load_json(a.config)
    b = _cfg_beacon(cfg)
    r = int(b["round"])
    t = round_time(r)
    now = time.time()
    if now < t + 1:
        if not a.bekle:
            raise SystemExit(f"tur {r} henüz yayınlanmadı ({iso_utc(t)} UTC, {int(t - now)} s kaldı). "
                             f"Beklemek için --bekle ekle.")
        while time.time() < t + 2:
            kalan = t + 2 - time.time()
            print(f"tur {r} bekleniyor: {int(kalan)} s", flush=True)
            time.sleep(min(30.0, max(0.5, kalan)))
    rows = relaylardan(r)
    oks = [(u, res) for u, res, err in rows if res is not None]
    for u, res, err in rows:
        print(f"  {u}: " + (f"tur {res['round']} randomness {res['randomness'][:16]}…" if res else f"ulaşılamadı ({err})"))
    if not oks:
        raise SystemExit("HATA: hiçbir relay'den yanıt gelmedi; kaydedilmedi. İnternet bağlantısını kontrol edip tekrar dene.")
    ref = oks[0][1]
    if any(not ayni(res, ref) for _, res in oks):
        raise SystemExit("HATA: relay'ler farklı değer veriyor; kaydedilmedi.")
    if int(ref["round"]) != r:
        raise SystemExit(f"HATA: relay tur {ref['round']} döndürdü, beklenen {r}.")
    if not imza_ozeti_tutuyor(ref):
        raise SystemExit("HATA: randomness != SHA-256(signature); kaydedilmedi.")
    bls_ok, bls_msg = bls_dogrula(ref)
    if not bls_ok:
        raise SystemExit(f"HATA: BLS imzası geçersiz ({bls_msg}); kaydedilmedi.")
    out = {"network": QUICKNET["network"], "chain_hash": QUICKNET["chain_hash"], "scheme": QUICKNET["scheme"],
           "round": r, "round_time_utc": iso_utc(t),
           "randomness": ref["randomness"], "signature": ref["signature"],
           "kontrol": {"randomness_eq_sha256_signature": True,
                       "bls_imza": "GEÇERLİ: " + bls_msg + " (bls12381.py, quicknet açık anahtarı)",
                       "ayni_deger_veren_relaylar": [u for u, _ in oks],
                       "ulasilamayan_relaylar": [u for u, res, _ in rows if res is None]},
           "fetched_at_utc": iso_utc(time.time()),
           "prova": cfg.get("mod") != "final"}
    if os.path.exists(a.yaz):
        old = pm.load_json(a.yaz)
        if not ayni(old, ref):
            raise SystemExit(f"{a.yaz} farklı bir beacon içeriyor; üzerine yazılmadı.")
    pm.write_json(a.yaz, out)
    print(f"TAMAM: BLS imzası geçerli; {len(oks)} relay aynı değeri verdi; randomness = SHA-256(signature).")
    print(f"randomness: {ref['randomness']}")
    print(f"yazıldı: {a.yaz}")


def cmd_kaymalar(a):
    cfg = pm.load_json(a.config)
    b = _cfg_beacon(cfg)
    t = pm.load_json(a.taahhut)
    bc = pm.load_json(a.beacon_dosya)
    if int(bc["round"]) != int(b["round"]):
        raise SystemExit(f"HATA: beacon dosyası tur {bc['round']}, config tur {b['round']} istiyor.")
    if not imza_ozeti_tutuyor(bc):
        raise SystemExit("HATA: beacon dosyasında randomness != SHA-256(signature).")
    bls_ok, bls_msg = bls_dogrula(bc)
    if not bls_ok:
        raise SystemExit(f"HATA: beacon dosyasındaki BLS imzası geçersiz ({bls_msg}).")
    sys.path.insert(0, HERE)
    from commit import commit_digest  # our own file in this folder
    _, sha = commit_digest(cfg, t["payload"].get("readout_sha256"))
    if sha != t["sha256"]:
        raise SystemExit("HATA: config taahhüt dosyasıyla uyuşmuyor.")
    by = cfg["beyin"]
    n = int(by["n"])
    xs = kaymalar(cfg, sha, bc["randomness"], n)
    sb = beyin_tohum_tabani(sha, bc["randomness"])
    print(f"taahhüt {sha} + drand turu {bc['round']} (BLS imzası geçerli)")
    print("kalecinin yeri (çizgi üzerinde, metre):")
    for k, x in enumerate(xs, 1):
        print(f"  şut {k}: keeper_x = {x:+.3f}  ({abs(x) * 100:.1f} cm {yon_tr(x)})")
    print(f"beyin tohum tabanı (beacon'dan): {sb}  -> trial_seed = {sb + 1} … {sb + n}")
    kx = ",".join(repr(x) for x in xs)
    final = cfg.get("mod") == "final"
    out = a.beyin_cikti or ("../veri/beyin_kararlari.json" if final else "../veri/prova_beyin_kararlari.json")
    print("\nbeyin (beyin/ klasöründen):")
    print(f"  .venv/bin/python -I kick.py {'--final ' if final else ''}--n {n} --seed-base {sb} "
          f"--keeper-x={kx} --commit-sha256 {sha} --out {shlex.quote(out)}")
    print("\nmotor (oyun/ klasöründen), beacon değeri:")
    print(f"  --beacon {bc['randomness']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="drand quicknet beacon: zaman, çekme, kayma")
    sub = ap.add_subparsers(dest="cmd", required=True)
    z = sub.add_parser("zaman")
    z.add_argument("--config", required=True)
    g = sub.add_parser("getir")
    g.add_argument("--config", required=True)
    g.add_argument("--yaz", required=True)
    g.add_argument("--bekle", action="store_true", help="tur yayınlanana kadar bekle")
    k = sub.add_parser("kaymalar")
    k.add_argument("--config", required=True)
    k.add_argument("--taahhut", required=True)
    k.add_argument("--beacon-dosya", required=True)
    k.add_argument("--beyin-cikti")
    a = ap.parse_args(argv)
    {"zaman": cmd_zaman, "getir": cmd_getir, "kaymalar": cmd_kaymalar}[a.cmd](a)


if __name__ == "__main__":
    main()
