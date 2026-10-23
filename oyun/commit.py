#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
commit.py - taahhüt (commitment) özeti: story'ye, sabitlenmiş gönderiye ve açık depoya TAM SHA-256 yazılır.

Özetlenen şey (kanonik JSON, sıralı anahtarlar, boşluksuz, UTF-8):
  - config'in TAMAMI: kalecinin FC reytingleri ve boyu, fizik sabitleri, kaleci modeli sabitleri, ana seed,
    şut başına kaleci seed listesi, kayma kuralı, drand turu N, beyin kuralı ve
    [tur3 2026-10-22, delik 4] KOD ÖZETLERİ (oyun/*.py, beyin kodu ve bağlantı verisi) + beyin ortamının
    paket listesi (config.kod_ozetleri, config.ortam)
  - penalty_model.py'nin SHA-256'sı ve beyin parçasının readout_sha256'sı (donmuş: e0ff656d…)

Alt komutlar:
  python3.12 -I commit.py kurallar --sablon config_sablon.json [--yaz duyuru.json]
        # DUYURU İÇİN: duyuru özeti = kurallar (seed'ler, mod, not, tur numarası hariç her şey) + bütün kod/veri
        # dosyalarının SHA-256'ları. Bir gün önce herkese açık yayınlanır; sonra kod da kural da değişemez.
  python3.12 -I commit.py yeni    --sablon config_sablon.json --cikti config_final.json [--beacon-gecikme-dk 180]
  python3.12 -I commit.py hesapla --config config_final.json --yaz ../veri/taahhut.json

[tur3 2026-10-22] Kurallar:
  - drand zincir bilgileri SABİT (beacon.QUICKNET; aşağıda elle bir kopyası daha var). Şablon/config farklıysa HATA.
  - Akın'ın 22 Ekim kararları (AKIN_KARARLARI) şablonda/config'te birebir olmalı, yoksa HATA.
  - Final config şablonla alan alan aynı olmalı (kural özeti); değişebilen yalnız seed'ler, tur ve kod özetleri.
  - Beyin tohum tabanı config'te YOK: beacon'dan türetilir (beacon.beyin_tohum_tabani).
  - 'yeni' final için N'yi en az beacon.min_gecikme_dk (120) sonraya koyar; 'hesapla' kalan süre bundan azsa
    taahhüt dosyasını yazmaz. Bunlar KAZAYI önler, hileyi önlemez: asıl güvence taahhüdün N'den önce herkese
    açık yerde olması (YENI_AKIS.md) ve verify.py'nin dış zaman kanıtı (--yayin-utc) istemesidir.
"""
from __future__ import annotations

import argparse
import copy
import datetime
import functools
import hashlib
import json
import os
import secrets
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # -I removes the script dir from sys.path; this folder is our own code
import penalty_model as pm  # noqa: E402
import beacon as bcn  # noqa: E402  [tur3 2026-10-22]

DEFAULT_BEYIN = os.path.join(HERE, "..", "veri", "beyin_kararlari.json")

# [tur3 2026-10-22, delik 3] quicknet sabitlerinin ELLE yazılmış kopyası (beacon.QUICKNET ile aynı olmalı)
QUICKNET_SABIT = {
    "network": "drand quicknet",
    "chain_hash": "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971",
    "public_key": "83cf0f2896adee7eb8b5f01fcad3912212c437e0073e911fb90022d3e760183c8c4b450b6a0a6c3ac6a5776a2d1064510d1fec758c921cc22b0e17e63aaf4bcb5ed66304de9cf809bd274ca73bab4af5a6e9c76a4bc09e76eae8991ef5ece45a",
    "scheme": "bls-unchained-g1-rfc9380",
    "genesis_time": 1692803367,
    "period_s": 3,
    "relays": ["https://api.drand.sh", "https://api2.drand.sh", "https://drand.cloudflare.com"],
}
if QUICKNET_SABIT != bcn.QUICKNET:
    raise SystemExit("HATA: commit.py ve beacon.py'deki quicknet sabitleri farklı.")

# [tur3 2026-10-22, delik 4] beynin donmuş okuma özeti (beyin/DONDURMA.json)
READOUT_DONDURMA = "e0ff656deddd74430262a8b5b272ca9842ae75a2f9b8a806562cc4e42cdcaa27"

# [tur3 2026-10-22, delik 5] Akın'ın 22 Ekim kararları: şablon/config bunlardan sapamaz
AKIN_KARARLARI = {
    "keeper_model.in_reach_save_model.a": -0.0447,
    "keeper_model.in_reach_save_model.b": 1.72,
    "keeper_model.positioning_pull_per_point": 0.0,
    "keeper_shift.surum": "kayma-v1",
    "keeper_shift.min_m": 0.30,
    "keeper_shift.max_m": 0.50,
    "keeper_shift.p_positive": 0.5,
    "keeper_shift.round_decimals": 3,
    "keeper.name": "Uğurcan Çakır",
    "keeper.height_m": 1.91,
    "keeper.ratings.diving": 80,
    "keeper.ratings.handling": 76,
    "keeper.ratings.kicking": 81,
    "keeper.ratings.positioning": 80,
    "keeper.ratings.reflexes": 82,
    "beyin.n": 5,
    "beyin.keeper_x": "beacon_kayma",
    "beyin.tohum": "beyin-tohum-v1",
}

# [tur3b 2026-10-22] motor kuralları (taahhütten ÖNCE kararlaştırıldı): gerçekçi (balistik) kaleci uçuşu ZORUNLU;
# şut sapması (seçenek B) kuralı önceden kayıtlı ve sabit. Açık mı kapalı mı (sut_sapmasi.acik) Akın'ın A/B seçimi:
# şablona yazılır, bir gün önceki duyuru özetine girer. Sabitler sonuç görülmeden kalibre edildi (MODEL.md bölüm 8).
TUR3B_KURALLARI = {
    "keeper_model.ucus.surum": "balistik-v1",
    "sut_sapmasi.surum": "sapma-v1",
    "sut_sapmasi.delta_h": 0.5056909,
    "sut_sapmasi.alpha_h_zemin": 0.123205,
    "sut_sapmasi.alpha_h_yuksek": 0.138678,
    "sut_sapmasi.delta_v": 2.057649,
    "sut_sapmasi.alpha_v_zemin": 0.000594,
    "sut_sapmasi.alpha_v_yuksek": 0.001372,
    "sut_sapmasi.yukseklik_ref_m": 1.6,
    # [tur4 2026-10-23] 0.332 -> 0.432: motor 1.1.1 (direkten gol = gol) ile yeniden kalibrasyon, aynı yöntem ve hedef (%4,78)
    "sut_sapmasi.olcek": 0.432,   # kalibrasyon: kalibrasyon.py --sapma-kalibre (MODEL.md 8)
}

# kural özetine GİRMEYEN (koşudan koşuya değişen) alanlar
KURAL_DISI_UST = ("mod", "not", "seed", "keeper_seeds", "beacon_rule", "kod_ozetleri", "ortam")
KURAL_DISI_BEACON = ("round", "round_time_utc")

# [tur3 2026-10-22, delik 4] taahhüde giren dosyalar (anahtar = sinek-penalti/ köküne göre yol)
OYUN_DOSYALARI = ["penalty_model.py", "commit.py", "beacon.py", "verify.py", "bls12381.py", "beyin_yeniden.py",
                  "tests.py", "olasilik.py", "kalibrasyon.py", "config_sablon.json", "bagimsiz/kontrol.mjs"]
BEYIN_DOSYALARI = ["kick.py", "beyin_model.py", "ortam.py", "esleme.py", "dondur.py", "ids.json", "DONDURMA.json",
                   "indirilen/shiu_model/model.py", "indirilen/shiu_model/Completeness_783.csv",
                   "indirilen/shiu_model/Connectivity_783.parquet"]

ORTAM_KODU = ("import json,sys,platform,importlib.metadata as m;"
              "print(json.dumps({'python':sys.version.split()[0],'platform':platform.platform(),"
              "'paketler':sorted(d.metadata['Name']+'=='+d.version for d in m.distributions())}))")


# --------------------------------------------------------------------------- taahhüt
def build_payload(cfg, readout_sha):
    return {
        # [tur3 2026-10-22] kod özetli config'ler v2; eski provaların özeti değişmesin diye v1 korunur
        "kind": "sinek-penalti-taahhut-v2" if "kod_ozetleri" in cfg else "sinek-penalti-taahhut-v1",
        "config": cfg,
        "keeper_seeds": cfg.get("keeper_seeds"),
        "engine_sha256": pm.engine_sha256(),
        "readout_sha256": readout_sha,
    }


def commit_digest(cfg, readout_sha):
    payload = build_payload(cfg, readout_sha)
    sha = pm.sha256_hex(pm.canonical_json(payload))
    return payload, sha


def short_code(sha):
    return sha[:12]


# --------------------------------------------------------------------------- kurallar
def _get(d, path):
    for k in path.split("."):
        if not isinstance(d, dict) or k not in d:
            return "(yok)"
        d = d[k]
    return d


def karar_farklari(cfg):
    """Akın'ın kararlarından ve [tur3b 2026-10-22] motor kurallarından sapan alanlar: [(alan, beklenen, bulunan)]."""
    out = []
    for path, want in list(AKIN_KARARLARI.items()) + list(TUR3B_KURALLARI.items()):
        got = _get(cfg, path)
        if got != want or type(got) is bool:
            out.append((path, want, got))
    acik = _get(cfg, "sut_sapmasi.acik")
    if type(acik) is not bool:   # [tur3b 2026-10-22] A (false) ya da B (true); başka bir değer olamaz
        out.append(("sut_sapmasi.acik", "true/false", acik))
    return out


def secenek(cfg):
    """[tur3b 2026-10-22] 'A' (sapma kapalı) ya da 'B' (sapma açık)."""
    return "B" if _get(cfg, "sut_sapmasi.acik") is True else "A"


def kurallar(cfg):
    """Kural özeti için config'in değişmeyen kısmı (seed'ler, mod, not, tur, kod özetleri hariç)."""
    c = copy.deepcopy(cfg)
    for k in KURAL_DISI_UST:
        c.pop(k, None)
    if isinstance(c.get("beacon"), dict):
        for k in KURAL_DISI_BEACON:
            c["beacon"].pop(k, None)
    return c


def kural_ozeti(cfg):
    return pm.sha256_hex(pm.canonical_json(kurallar(cfg)))


def duyuru(cfg, kod):
    """[tur3 2026-10-22, delik 4-5] Bir gün önce duyurulan şey: kurallar + bütün kod/veri özetleri."""
    return {"kurallar": kurallar(cfg), "kod_ozetleri": kod}


def duyuru_ozeti(cfg, kod):
    """DUYURU ÖZETİ = SHA-256(kanonik JSON({"kurallar": kurallar(cfg), "kod_ozetleri": kod}))."""
    return pm.sha256_hex(pm.canonical_json(duyuru(cfg, kod)))


def _fark(a, b, yol=""):
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            p = f"{yol}.{k}" if yol else k
            if k not in a:
                out.append(f"{p}: şablonda var, config'te yok")
            elif k not in b:
                out.append(f"{p}: config'te var, şablonda yok")
            else:
                out += _fark(a[k], b[k], p)
        return out
    if a != b or type(a) is not type(b):
        return [f"{yol}: config {json.dumps(a, ensure_ascii=False)[:60]} ≠ şablon {json.dumps(b, ensure_ascii=False)[:60]}"]
    return []


def kural_farklari(cfg, sablon):
    """Final config'in şablondan (duyurulan kurallardan) farklı olduğu alanlar."""
    return _fark(kurallar(cfg), kurallar(sablon))


# --------------------------------------------------------------------------- kod özetleri
def beyin_dizini(arg=None):
    if arg:
        return os.path.abspath(arg)
    for c in (os.path.join(HERE, "..", "beyin"), os.path.join(HERE, "..", "..", "beyin")):
        if os.path.exists(os.path.join(c, "kick.py")):
            return os.path.abspath(c)
    return os.path.abspath(os.path.join(HERE, "..", "beyin"))


@functools.lru_cache(maxsize=256)
def _dosya_sha(path, mtime_ns, size):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def dosya_sha(path):
    st = os.stat(path)
    return _dosya_sha(os.path.abspath(path), st.st_mtime_ns, st.st_size)


def kod_ozetleri_hesapla(oyun_dir=HERE, beyin_dir=None):
    """{'oyun/<dosya>': sha | None, 'beyin/<dosya>': sha | None} (None = dosya yok)."""
    beyin_dir = beyin_dizini(beyin_dir)
    out = {}
    for ad, kok, liste in (("oyun", oyun_dir, OYUN_DOSYALARI), ("beyin", beyin_dir, BEYIN_DOSYALARI)):
        for f in liste:
            p = os.path.join(kok, f)
            out[f"{ad}/{f}"] = dosya_sha(p) if os.path.isfile(p) else None
    return out


def kod_farklari(cfg, oyun_dir=HERE, beyin_dir=None):
    ko = cfg.get("kod_ozetleri")
    if not isinstance(ko, dict):
        return ["config'te kod_ozetleri yok (eski biçim)"]
    simdi = kod_ozetleri_hesapla(oyun_dir, beyin_dir)
    out = []
    for k in sorted(set(ko) | set(simdi)):
        if k not in ko:
            out.append(f"{k}: taahhütte yok")
        elif simdi.get(k) is None:
            out.append(f"{k}: dosya bulunamadı")
        elif simdi[k] != ko[k]:
            out.append(f"{k}: değişmiş ({ko[k][:12]} -> {simdi[k][:12]})")
    return out


def beyin_python(beyin_dir=None, arg=None):
    return arg or os.path.join(beyin_dizini(beyin_dir), ".venv", "bin", "python")


def ortam_bilgisi(beyin_dir=None, py=None):
    """Beyin ortamının Python sürümü, platformu ve paket listesi (pip freeze yerine importlib.metadata)."""
    py = beyin_python(beyin_dir, py)
    p = subprocess.run([py, "-I", "-B", "-c", ORTAM_KODU], capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        raise RuntimeError(f"beyin ortamı okunamadı ({py}): {p.stderr.strip()[-200:]}")
    return json.loads(p.stdout.strip().splitlines()[-1])


# --------------------------------------------------------------------------- denetimler
def sablon_denetle(cfg, ne="şablon"):
    fark = bcn.zincir_farklari(cfg.get("beacon"))
    if fark:
        raise SystemExit(f"HATA: {ne} drand zincir bilgileri quicknet sabitleriyle aynı değil: {fark}")
    kf = karar_farklari(cfg)
    if kf:
        raise SystemExit(f"HATA: {ne} Akın'ın 22 Ekim kararlarından sapıyor: {kf}")
    if not isinstance(cfg.get("beyin"), dict) or not isinstance(cfg.get("keeper_shift"), dict):
        raise SystemExit(f"HATA: {ne} 'beyin' ve 'keeper_shift' blokları olmalı (tur3 şablonu).")


def cmd_kurallar(a):
    s = pm.load_json(a.sablon)
    sablon_denetle(s)
    kod = kod_ozetleri_hesapla(HERE, a.beyin_dizin)
    eksik = [k for k, v in kod.items() if v is None]
    if eksik:
        raise SystemExit(f"HATA: duyuruya girecek dosyalar bulunamadı: {eksik}")
    d_sha = duyuru_ozeti(s, kod)
    print("DUYURU ÖZETİ (kurallar + kod; bir gün önce herkese açık duyurulur, SHA-256):", d_sha)
    print("kural özeti (yalnız kurallar):", kural_ozeti(s))
    print("kapsam: config'in seed'ler, mod, not, beacon.round, beacon.round_time_utc, beacon_rule, kod_ozetleri ve "
          f"ortam DIŞINDAKİ bütün alanları + {len(kod)} kod/veri dosyasının SHA-256'sı")
    irm = s["keeper_model"]["in_reach_save_model"]
    print(f"[tur3b] kaleci uçuşu: {s['keeper_model']['ucus']['surum']} | şut sapması: SEÇENEK {secenek(s)} "
          f"({'AÇIK' if secenek(s) == 'B' else 'KAPALI'}; kural {s['sut_sapmasi']['surum']}, olcek {s['sut_sapmasi']['olcek']})")
    print(f"özet: Hunter a={irm['a']} b={irm['b']} | kayma {s['keeper_shift']['min_m']}-{s['keeper_shift']['max_m']} m, "
          f"p+ {s['keeper_shift']['p_positive']} | merkeze çekilme {s['keeper_model']['positioning_pull_per_point']} | "
          f"en az {s['beacon']['min_gecikme_dk']} dk önceden taahhüt | beyin tohumu: {s['beyin']['tohum']}")
    print("Bu andan sonra şablon ya da listelenen dosyalardan biri değişirse duyuru özeti tutmaz: değişiklik yeniden "
          "ve açıkça duyurulmalı.")
    if a.yaz:
        pm.write_json(a.yaz, {"duyuru_ozeti_sha256": d_sha, "kural_ozeti_sha256": kural_ozeti(s),
                              "kurallar": kurallar(s), "kod_ozetleri": kod,
                              "tanim": "duyuru özeti = SHA-256(kanonik JSON({\"kurallar\": ..., \"kod_ozetleri\": ...})); "
                                       "kanonik = sort_keys, ayraç ',' ':', UTF-8 (penalty_model.canonical_json)"})
        print("yazıldı:", a.yaz)


def cmd_yeni(a):
    if os.path.exists(a.cikti):
        raise SystemExit(f"{a.cikti} zaten var. Seed'leri yeniden üretmek YASAK (taahhüt öncesi bile bir kez üretilir).")
    cfg = pm.load_json(a.sablon)
    sablon_denetle(cfg)
    n = int(cfg["beyin"]["n"])
    b = cfg["beacon"]
    cfg["mod"] = "prova" if a.prova else "final"
    cfg["not"] = ("PROVA config (tatbikat, story'de PAYLAŞILMAZ). " if a.prova else "FINAL config. ") + \
        "Seed'ler secrets.randbits(62) ile bir kez üretildi. Taahhütten sonra DEĞİŞTİRME."
    cfg["seed"] = secrets.randbits(62)
    cfg["keeper_seeds"] = [secrets.randbits(62) for _ in range(n)]
    now = time.time()
    gecikme = a.beacon_gecikme_dk if a.beacon_gecikme_dk is not None else float(b["varsayilan_gecikme_dk"])
    if a.beacon_turu:
        r = int(a.beacon_turu)
    else:
        r = bcn.round_at(now + 60.0 * gecikme) + 1
    t_r = bcn.round_time(r)
    if not a.prova:
        if t_r <= now:
            raise SystemExit(f"HATA: tur {r} zaten yayınlanmış ({bcn.iso_utc(t_r)} UTC). Final için gelecekteki bir tur gerekir.")
        if t_r - now < 60.0 * float(b["min_gecikme_dk"]):
            raise SystemExit(f"HATA: tur {r} yalnız {(t_r - now) / 60:.0f} dk sonra; final için en az "
                             f"{b['min_gecikme_dk']} dk gerekli (taahhüt önce herkese açık yere konacak).")
    b["round"] = r
    b["round_time_utc"] = bcn.iso_utc(t_r)
    cfg["beacon_rule"] = (f"drand quicknet round {r} randomness (chain {bcn.QUICKNET['chain_hash'][:16]}…, "
                          f"yayın {bcn.iso_utc(t_r)})")
    # [tur3 2026-10-22, delik 4] kod + veri özetleri ve beyin ortamı taahhüde girer
    cfg["kod_ozetleri"] = kod_ozetleri_hesapla(HERE, a.beyin_dizin)
    eksik = [k for k, v in cfg["kod_ozetleri"].items() if v is None]
    if eksik:
        raise SystemExit(f"HATA: taahhüde girecek dosyalar bulunamadı: {eksik}")
    cfg["ortam"] = ortam_bilgisi(a.beyin_dizin, a.beyin_python)
    pm.write_json(a.cikti, cfg)
    print(f"yazıldı: {a.cikti} ({n} kaleci seed'i, mod={cfg['mod']})")
    print(f"beacon: drand quicknet turu {r} -> yayın {bcn.iso_utc(t_r)} (UTC) = {bcn.yerel(t_r)} "
          f"[{(t_r - now) / 60:.0f} dk sonra]")
    print("beyin tohumu: config'te YOK; tur yayınlanınca beacon'dan türetilir (beacon.py kaymalar).")
    print(f"[tur3b] şut sapması: SEÇENEK {secenek(cfg)} ({'AÇIK' if secenek(cfg) == 'B' else 'KAPALI'}) | kaleci uçuşu: "
          f"{cfg['keeper_model']['ucus']['surum']}")
    print("DUYURU ÖZETİ:", duyuru_ozeti(cfg, cfg["kod_ozetleri"]), "(bir gün önceki duyuruyla aynı olmalı)")
    print(f"kod özetleri: {len(cfg['kod_ozetleri'])} dosya; beyin ortamı: Python {cfg['ortam']['python']}, "
          f"{len(cfg['ortam']['paketler'])} paket")


def cmd_hesapla(a):
    cfg = pm.load_json(a.config)
    final = cfg.get("mod") == "final"
    sablon_denetle(cfg, "config")
    sablon = pm.load_json(a.sablon)
    kf = kural_farklari(cfg, sablon)
    if kf:
        raise SystemExit("HATA: config duyurulan kurallardan (şablon) farklı: " + "; ".join(kf[:5]))
    df = kod_farklari(cfg, HERE, a.beyin_dizin)
    if df:
        raise SystemExit("HATA: kod/veri dosyaları config'teki özetlerle aynı değil: " + "; ".join(df[:5]))
    readout = (a.readout_sha or READOUT_DONDURMA).strip().lower()
    if readout != READOUT_DONDURMA:
        raise SystemExit(f"HATA: readout_sha256 donmuş değer ({READOUT_DONDURMA[:12]}…) değil.")
    b = cfg.get("beacon") or {}
    if not b.get("round"):
        raise SystemExit("HATA: config'te beacon.round yok (commit.py yeni yazar).")
    payload, sha = commit_digest(cfg, readout)
    t_r = bcn.round_time(b["round"])
    now = time.time()
    print("MOD:", "FINAL" if final else "PROVA (story'de PAYLAŞILMAZ)")
    print("TAM SHA-256 (story, sabitlenmiş gönderi, açık depo ve video açıklamasına TAM olarak yaz):")
    print("   ", sha)
    print("kısa etiket (yalnız göz için; doğrulama TAM SHA ister):", short_code(sha))
    print("DUYURU ÖZETİ (kurallar + kod):", duyuru_ozeti(cfg, cfg.get("kod_ozetleri")),
          "(bir gün önce duyurulanla aynı olmalı)")
    print("motor:", payload["engine_sha256"][:12], "| readout:", readout[:12], "| kod özetleri:",
          len(cfg.get("kod_ozetleri") or {}), "dosya")
    print(f"beacon: drand quicknet turu {b['round']} | yayın {bcn.iso_utc(t_r)} (UTC) = {bcn.yerel(t_r)} "
          "[quicknet sabitlerinden]")
    kalan = t_r - now
    min_dk = float(b["min_gecikme_dk"])
    if kalan > 0:
        print(f"kalan: {kalan / 60:.1f} dk. Taahhüdü (config + taahhüt + kod) bu sürenin içinde, tur yayınlanmadan "
              f"en az {min_dk:.0f} dk önce herkese açık yere koy.")
    if final and kalan < 60.0 * min_dk:
        raise SystemExit(f"HATA: tura {kalan / 60:.1f} dk kaldı (en az {min_dk:.0f} dk gerekli); taahhüt dosyası "
                         "YAZILMADI. Bu config hiçbir yerde paylaşılmadıysa yeni bir config ile baştan başla.")
    if not final and kalan <= 0:
        print("NOT (prova): bu tur zaten yayınlandı; gerçek akışta bu bir HATA olurdu.")
    if a.yaz:
        out = {"sha256": sha, "short": short_code(sha), "payload": payload,
               "duyuru_ozeti_sha256": duyuru_ozeti(cfg, cfg.get("kod_ozetleri")),
               "created_at_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "prova": not final}
        if os.path.exists(a.yaz) and not a.uzerine_yaz:
            old = pm.load_json(a.yaz)
            if old.get("sha256") != sha:
                raise SystemExit(f"{a.yaz} farklı bir taahhüt içeriyor; üzerine yazmak için --uzerine-yaz (yalnız prova).")
        pm.write_json(a.yaz, out)
        # [tur3 2026-10-22, delik 2d] her taahhüt kayda geçer; kayıttaki her taahhüt sonuçlanır ve yayınlanır
        gecmis = os.path.join(os.path.dirname(os.path.abspath(a.yaz)), "taahhut_gecmisi.jsonl")
        with open(gecmis, "a", encoding="utf-8") as f:
            f.write(json.dumps({"sha256": sha, "mod": cfg.get("mod"), "round": b["round"],
                                "created_at_utc": out["created_at_utc"], "dosya": os.path.basename(a.yaz)},
                               ensure_ascii=False) + "\n")
        print("yazıldı:", a.yaz, "| kayıt:", gecmis)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Taahhüt özeti (SHA-256) üret.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("kurallar", help="bir gün önce duyurulacak özeti (kurallar + kod) hesapla")
    k.add_argument("--sablon", default=os.path.join(HERE, "config_sablon.json"))
    k.add_argument("--beyin-dizin")
    k.add_argument("--yaz")
    y = sub.add_parser("yeni", help="taze rastgele seed'lerle config üret")
    y.add_argument("--sablon", default=os.path.join(HERE, "config_sablon.json"))
    y.add_argument("--cikti", required=True)
    y.add_argument("--prova", action="store_true", help="tatbikat config'i (mod=prova; story'de paylaşılmaz)")
    y.add_argument("--beacon-turu", type=int, help="drand quicknet tur numarası N (verilmezse şimdi + gecikme)")
    y.add_argument("--beacon-gecikme-dk", type=float,
                   help="N, şimdiden kaç dakika sonra yayınlanacak (varsayılan şablondaki 180; final için en az 120)")
    y.add_argument("--beyin-dizin")
    y.add_argument("--beyin-python")
    h = sub.add_parser("hesapla", help="config'in taahhüt özetini hesapla")
    h.add_argument("--config", required=True)
    h.add_argument("--sablon", default=os.path.join(HERE, "config_sablon.json"))
    h.add_argument("--readout-sha")
    h.add_argument("--beyin-dizin")
    h.add_argument("--yaz", help="taahhüt dosyasını yaz (örn. ../veri/taahhut.json)")
    h.add_argument("--uzerine-yaz", action="store_true")
    a = ap.parse_args(argv)
    {"kurallar": cmd_kurallar, "yeni": cmd_yeni, "hesapla": cmd_hesapla}[a.cmd](a)


if __name__ == "__main__":
    main()
