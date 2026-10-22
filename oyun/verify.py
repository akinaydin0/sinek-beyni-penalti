#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify.py - [tur3 2026-10-22] taahhüdü, kuralları, kodu, drand beacon'ını, sinek beynini ve motoru BAŞTAN kontrol eder.

  python3.12 -I verify.py --taahhut T --config C --log L --karar K --beacon-dosya B \
      --kod <TAM 64 karakter SHA-256, story/sabitlenmiş gönderiden> \
      --duyuru-sha <bir gün önce duyurulan DUYURU ÖZETİ: kurallar + kod> \
      --yayin-utc <taahhüdün herkese açık yerde görüldüğü en erken an, UTC, dış kaynaktan>
      [--beyin-dizin ../beyin] [--beyin-python ../beyin/.venv/bin/python] [--beyin-atla] [--cevrimdisi]

ÇIKIŞ (ilk satır MOD'u basar):
  SONUÇ: DOĞRULANDI                      (çıkış 0) yalnız mod = final, taahhüt prova = false, HİÇBİR HATA yok ve
                                          --kod, --duyuru-sha, --yayin-utc verildi ve beyin yeniden koşturuldu
  SONUÇ: PROVA DOĞRULANDI                (çıkış 3) aynı kontrollerin hepsi tuttu ama bu bir prova
  SONUÇ: TAAHHÜT STORY'YE BAĞLANMADI     (çıkış 2) --kod (tam SHA) verilmedi
  SONUÇ: KURALLAR VE KOD DUYURUYLA KARŞILAŞTIRILMADI / ZAMAN KANITI VERİLMEDİ / BEYİN YENİDEN KOŞTURULMADI (çıkış 2)
  SONUÇ: DOĞRULANAMADI                   (çıkış 1) en az bir HATA

Kontroller (her biri TAMAM / HATA satırı basar):
  taahhüt: config + motor + readout özeti; story'deki TAM SHA (--kod, 64 karakter zorunlu)
  kurallar: drand zincir bilgileri SABİT (quicknet); Akın'ın 22 Ekim kararları; şablonla alan alan aynı;
            duyuru özeti (kurallar + kod) = bir gün önce duyurulan (--duyuru-sha); readout = donmuş e0ff656d…;
            kayma / tohum formülleri bilinen cevaplarla (KAT) ve bağımsız JS uygulamasıyla aynı
  kod: oyun/*.py, beyin kodu ve bağlantı verisinin SHA-256'ları taahhüttekiyle aynı; karar dosyasındaki
       code_sha256 / data_sha256 de aynı (eksik alan = HATA)
  beacon: tur N; randomness = SHA-256(imza); BLS imzası quicknet açık anahtarıyla GEÇERLİ (bls12381.py);
          relay'ler (çevrimiçiyse): hiçbiri farklı değer vermiyor, /info sabitlerle aynı
  zaman: taahhüdün kendi saati turdan önce (kanıt değil); dış kanıt (--yayin-utc) turdan en az
         beacon.min_gecikme_dk önce
  beyin: tohum tabanı beacon'dan; sahne = kaymalar; nişan/hız = esle(oku(spike sayıları));
         YENİDEN KOŞU (beynin kendi ortamıyla): her şutta spike sayıları, steer, nişan, hız, decision_ms ve
         spikes_sha256 birebir aynı; raster (npz) varsa onun özeti de
  motor: log'daki start_x = kaymalar; kaleci seed'leri; beacon; koşu baştan üretilip bayt bayt aynı
Bu programın verdiği sonuç yalnız ONU ÇALIŞTIRAN makinede geçerlidir: başkasının ekran görüntüsü kanıt değildir.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import penalty_model as pm  # noqa: E402
import beacon as bcn  # noqa: E402
import commit as cm  # noqa: E402

# [tur3 2026-10-22, delik 3] quicknet sabitlerinin üçüncü, ELLE yazılmış kopyası
QUICKNET_SABIT = {
    "network": "drand quicknet",
    "chain_hash": "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971",
    "public_key": "83cf0f2896adee7eb8b5f01fcad3912212c437e0073e911fb90022d3e760183c8c4b450b6a0a6c3ac6a5776a2d1064510d1fec758c921cc22b0e17e63aaf4bcb5ed66304de9cf809bd274ca73bab4af5a6e9c76a4bc09e76eae8991ef5ece45a",
    "scheme": "bls-unchained-g1-rfc9380",
    "genesis_time": 1692803367,
    "period_s": 3,
    "relays": ["https://api.drand.sh", "https://api2.drand.sh", "https://drand.cloudflare.com"],
}
READOUT_DONDURMA = "e0ff656deddd74430262a8b5b272ca9842ae75a2f9b8a806562cc4e42cdcaa27"
SHIU_COMMIT = "91bdd1e7dcf193f3e7ca5a8933497fcef63b7960"
if QUICKNET_SABIT != bcn.QUICKNET or QUICKNET_SABIT != cm.QUICKNET_SABIT or READOUT_DONDURMA != cm.READOUT_DONDURMA:
    raise SystemExit("HATA: verify.py, beacon.py ve commit.py'deki sabitler birbirinden farklı.")

CAKIR_SAYILIR = ("save", "post", "wide", "over")  # skor kuralı (config.skor_kurali)
EKSIK_KOD = "TAAHHÜT STORY'YE BAĞLANMADI"
EKSIK_KURAL = "KURALLAR VE KOD DUYURUYLA KARŞILAŞTIRILMADI"
# [tur3 2026-10-22] bilinen cevap testi (KAT): belgedeki formüllerle elle hesaplandı (tests.py _u_bagimsiz ile aynı)
KAT = {"randomness": "64a2d5d2d5f83225d0c7223321bcdbd8f6bf0850d5260a2f1842e815fb868716", "sha": "ab" * 32,
       "kaymalar": [0.404, 0.336, -0.472, -0.437, 0.317], "seed_base": 2568652039,
       "kaleci_seed_1_2": [182150181063851154, 25846298794819660]}
KAT_CFG = {"keeper_shift": {"min_m": 0.30, "max_m": 0.50, "p_positive": 0.5, "round_decimals": 3},
           "beacon_rule": "KAT"}
EKSIK_ZAMAN = "ZAMAN KANITI VERİLMEDİ"
EKSIK_BEYIN = "BEYİN YENİDEN KOŞTURULMADI"
BEYIN_KOD = ("kick.py", "beyin_model.py", "ortam.py", "esleme.py", "dondur.py")
BEYIN_VERI = {"Completeness_783.csv": "beyin/indirilen/shiu_model/Completeness_783.csv",
              "Connectivity_783.parquet": "beyin/indirilen/shiu_model/Connectivity_783.parquet",
              "shiu_model.py": "beyin/indirilen/shiu_model/model.py"}
YENIDEN_ALANLAR = ("counts", "steer", "power_spikes", "aim", "speed_mps", "decision_ms", "Rturn", "Lturn",
                   "brain_spikes", "spikes_sha256")


def skor(log):
    """(SİNEK golleri, ÇAKIR puanı). Gol dışındaki her sonuç (kurtarış, direk, aut, üstten aut) ÇAKIR'a."""
    g = sum(1 for k in log["kicks"] if k["outcome"] == "goal")
    c = sum(1 for k in log["kicks"] if k["outcome"] in CAKIR_SAYILIR)
    return g, c


class Rapor:
    def __init__(self, out):
        self.out = out
        self.hata = []
        self.eksik = []
        self.uyari = []

    def check(self, cond, msg):
        self.out(("TAMAM  " if cond else "HATA   ") + msg)
        if not cond:
            self.hata.append(msg)
        return bool(cond)

    def bilgi(self, msg):
        self.out("bilgi  " + msg)

    def uyar(self, msg):
        self.out("UYARI  " + msg)
        self.uyari.append(msg)

    def eksik_ekle(self, etiket, msg):
        self.out("EKSİK  " + msg)
        if etiket not in self.eksik:
            self.eksik.append(etiket)


def esleme_yukle(beyin_dir, beklenen_sha):
    """beyin/esleme.py'yi, özeti taahhüttekiyle aynıysa, dosya yazmadan (pycache yok) yükler. Yalnız math kullanır."""
    p = os.path.join(beyin_dir, "esleme.py")
    if not os.path.isfile(p):
        return None, "esleme.py bulunamadı"
    src = open(p, "rb").read()
    if hashlib.sha256(src).hexdigest() != beklenen_sha:
        return None, "esleme.py taahhütteki özetle aynı değil"
    ns = {"__name__": "esleme_dondurulmus"}
    exec(compile(src, p, "exec"), ns)  # noqa: S102 (özeti taahhütle doğrulanmış, kendi kodumuz)
    return ns, None


def beyin_kos_alt_surec(beyin_python, beyin_dir, timeout=1800):
    """Beyni beynin kendi ortamıyla (beyin_yeniden.py) yeniden koşturan fonksiyon döndürür."""
    def kos(isler):
        p = subprocess.run([beyin_python, "-I", "-B", os.path.join(HERE, "beyin_yeniden.py"), "--beyin", beyin_dir],
                           input=json.dumps({"isler": isler}), capture_output=True, text=True, timeout=timeout)
        satir = [x for x in p.stdout.splitlines() if x.startswith("SONUC_JSON ")]
        if not satir:
            raise RuntimeError(f"beyin yeniden koşusu çıktı vermedi (çıkış {p.returncode}): {p.stderr.strip()[-300:]}")
        d = json.loads(satir[-1][len("SONUC_JSON "):])
        if d.get("hata") or p.returncode != 0:
            raise RuntimeError(d.get("hata") or f"çıkış {p.returncode}")
        if d.get("readout_sha256") != READOUT_DONDURMA:
            raise RuntimeError("yeniden koşu başka bir okuma özetiyle yapıldı")
        return d["sonuc"]
    return kos


def dogrula(t, cfg, *, kod=None, kural_sha=None, yayin_utc=None, log=None, dec=None, beacon_dosya=None,
            sablon=None, beyin_dir=None, beyin_kos=None, ortam_simdi=None, fetch=None, info_fetch=None,
            cevrimdisi=False, out=print):
    """Bütün kontroller. Rapor döner (hata / eksik / uyarı listeleri + 'final', 'tam')."""
    rp = Rapor(out)
    beyin_dir = cm.beyin_dizini(beyin_dir)
    mod = cfg.get("mod")
    t_prova = t.get("prova")
    final = mod == "final" and t_prova is False
    out(f"MOD: {'FINAL' if final else 'PROVA'}  (config.mod = {mod!r}, taahhüt prova = {t_prova!r})")
    rp.final = final
    rp.tam = False
    rp.check((mod == "final") == (t_prova is False), "config.mod ile taahhüdün prova bayrağı tutarlı")

    # ------------------------------------------------------------ taahhüt
    readout = t["payload"].get("readout_sha256")
    payload, sha = cm.commit_digest(cfg, readout)
    out(f"yeniden hesaplanan TAM SHA-256: {sha}")
    rp.check(sha == t.get("sha256"), "config + motor + readout, taahhüt dosyasındaki özetle aynı")
    rp.check(payload["engine_sha256"] == t["payload"].get("engine_sha256"), "penalty_model.py taahhütten beri değişmemiş")
    if kod is None:
        rp.eksik_ekle(EKSIK_KOD, "--kod verilmedi: story/sabitlenmiş gönderideki TAM SHA-256 ile karşılaştırılmadı")
    else:
        k = kod.strip().lower()
        if len(k) != 64:
            rp.check(False, f"--kod tam 64 karakter olmalı (verilen {len(k)} karakter); kısa kod kabul edilmez")
        else:
            rp.check(k == sha, "story/sabitlenmiş gönderideki TAM SHA-256 bu özetle aynı")
    rp.check(readout == READOUT_DONDURMA, f"taahhütteki readout_sha256 donmuş okuma (DONDURMA.json, {READOUT_DONDURMA[:12]}…)")

    # ------------------------------------------------------------ kurallar
    zf = bcn.zincir_farklari(cfg.get("beacon"))
    rp.check(not zf, "drand zincir bilgileri quicknet SABİTLERİYLE aynı (chain_hash, public_key, şema, genesis, "
                     "period, relay'ler)" + (f": FARKLI {zf}" if zf else ""))
    kf = cm.karar_farklari(cfg)
    rp.check(not kf, "Akın'ın 22 Ekim kararları: Hunter a=-0.0447 b=1.72, kayma 0,30-0,50 m %50/%50, merkeze çekilme 0, "
                     "FC 27 reytingleri, 5 şut, beyin tohumu beacon'dan" + (f": FARKLI {kf}" if kf else ""))
    if sablon is not None:
        sf = cm.kural_farklari(cfg, sablon)
        rp.check(not sf, "config, şablonla (duyurulan kurallar) alan alan aynı" + (": " + "; ".join(sf[:4]) if sf else ""))
    else:
        rp.check(False, "şablon (config_sablon.json) bulunamadı; kurallar karşılaştırılamadı")
    ko = cfg.get("kod_ozetleri")
    ds_ = cm.duyuru_ozeti(cfg, ko)
    out(f"DUYURU ÖZETİ (kurallar + kod): {ds_}")
    if kural_sha is None:
        rp.eksik_ekle(EKSIK_KURAL, "--duyuru-sha verilmedi: kurallar ve kod bir gün önceki duyuruyla karşılaştırılmadı")
    else:
        rp.check(kural_sha.strip().lower() == ds_, "kurallar ve kod özetleri, önceden duyurulanla aynı (duyuru özeti)")
    kat_ok = (bcn.kaymalar(KAT_CFG, KAT["sha"], KAT["randomness"], 5) == KAT["kaymalar"]
              and bcn.beyin_tohum_tabani(KAT["sha"], KAT["randomness"]) == KAT["seed_base"]
              and pm.effective_seeds(KAT_CFG, [1, 2], KAT["randomness"]) == KAT["kaleci_seed_1_2"])
    rp.check(kat_ok, "kayma, beyin tohumu ve kaleci seed formülleri belgedeki bilinen cevaplarla aynı (KAT)")

    # ------------------------------------------------------------ kod
    if not isinstance(ko, dict):
        rp.check(False, "config'te kod_ozetleri yok (eski biçim taahhüt): kod taahhüde girmemiş")
        ko = {}
    else:
        df = cm.kod_farklari(cfg, HERE, beyin_dir)
        n_oyun = sum(1 for x in ko if x.startswith("oyun/"))
        n_beyin = sum(1 for x in ko if x.startswith("beyin/"))
        rp.check(not df, f"kod ve veri özetleri taahhüttekiyle aynı ({n_oyun} oyun, {n_beyin} beyin dosyası)"
                 + (": " + "; ".join(df[:4]) if df else ""))
        rp.check(ko.get("oyun/penalty_model.py") == payload["engine_sha256"], "kod özetindeki motor = taahhütteki motor")
    eo = cfg.get("ortam")
    if isinstance(eo, dict) and ortam_simdi is not None:
        if ortam_simdi == eo:
            rp.bilgi(f"beyin ortamı taahhüttekiyle aynı (Python {eo.get('python')}, {len(eo.get('paketler', []))} paket)")
        else:
            fark = sorted(set(eo.get("paketler", [])) ^ set(ortam_simdi.get("paketler", [])))[:6]
            rp.uyar(f"beyin ortamı taahhüttekinden farklı (Python {ortam_simdi.get('python')} / {eo.get('python')}; "
                    f"paket farkı {fark}); yeniden koşu bu yüzden tutmayabilir")
    elif not isinstance(eo, dict):
        rp.check(False, "config'te beyin ortamı (paket listesi) yok")

    if not (log and dec):
        return rp

    # ------------------------------------------------------------ beacon
    b = cfg.get("beacon") or {}
    bc = beacon_dosya
    if not bc:
        rp.check(False, "beacon dosyası verilmedi (--beacon-dosya); beacon'sız koşu doğrulanamaz")
        return rp
    N = int(b.get("round") or -1)
    randomness = str(bc.get("randomness", "")).lower()
    rp.check(int(bc.get("round", -2)) == N and bc.get("chain_hash", QUICKNET_SABIT["chain_hash"]) == QUICKNET_SABIT["chain_hash"],
             f"beacon dosyası: drand quicknet turu {N}, taahhütteki turla aynı")
    rp.check(bcn.imza_ozeti_tutuyor(bc), "beacon: randomness = SHA-256(signature)")
    bls_ok, bls_msg = bcn.bls_dogrula(bc)
    rp.check(bls_ok, f"beacon: BLS imzası quicknet açık anahtarıyla GEÇERLİ ({bls_msg})")
    if cevrimdisi:
        rp.uyar("relay karşılaştırması atlandı (--cevrimdisi); beacon yalnız BLS imzasıyla doğrulandı")
    else:
        rr = bcn.relay_karsilastir(bc, fetch=fetch, info_fetch=info_fetch)
        for ln in rr["satirlar"]:
            out(ln)
        rp.check(rr["farkli"] == 0, "ulaşılan hiçbir relay farklı değer vermiyor")
        rp.check(not rr["info_farkli"], "relay'lerin zincir bilgisi (/info) sabitlerle aynı")
        if rr["ulasilan"] == 0:
            rp.uyar("hiçbir relay'e ulaşılamadı; beacon yalnız BLS imzasıyla doğrulandı")
        elif rr["ayni"] < 2:
            rp.uyar(f"yalnız {rr['ayni']} relay teyit etti")
        else:
            rp.bilgi(f"{rr['ayni']} relay aynı değeri verdi")

    # ------------------------------------------------------------ zaman
    t_r = bcn.round_time(N)
    min_dk = float(b.get("min_gecikme_dk", 120))
    out(f"       drand turu {N} yayın saati: {bcn.iso_utc(t_r)} UTC (quicknet sabitlerinden)")
    ca = t.get("created_at_utc")
    if not ca:
        rp.check(False, "taahhüt dosyasında created_at_utc yok")
    else:
        rp.check(bcn.parse_utc(ca) < t_r, f"taahhüdün kendi saati ({ca}) turdan önce (dosyanın beyanı, KANIT DEĞİL)")
    if yayin_utc is None:
        rp.eksik_ekle(EKSIK_ZAMAN, "--yayin-utc verilmedi: taahhüdün tur yayınlanmadan önce herkese açık olduğu dış "
                                   "kaynaktan (sabitlenmiş gönderi, açık depo commit'i, OpenTimestamps) kontrol edilmedi")
    else:
        ts = bcn.parse_utc(yayin_utc)
        rp.check(ts < t_r, f"taahhüt, tur yayınlanmadan ÖNCE herkese açık yerde (dış kanıt {bcn.iso_utc(ts)} < "
                           f"{bcn.iso_utc(t_r)})")
        fark_dk = (t_r - ts) / 60.0
        if final:
            rp.check(fark_dk >= min_dk, f"taahhüt turdan en az {min_dk:.0f} dk önce açık yerde ({fark_dk:.0f} dk)")
        elif fark_dk < min_dk:
            rp.uyar(f"(prova) taahhüt turdan yalnız {fark_dk:.0f} dk önce; finalde en az {min_dk:.0f} dk gerekir")

    # ------------------------------------------------------------ dosyalar arası
    rp.check(log.get("commit_sha256") == sha, "penalty_log.json'daki commit_sha256 taahhütle aynı")
    rp.check(dec.get("commit_sha256") == sha, "beyin dosyasındaki commit_sha256 taahhütle aynı")
    rp.check(dec.get("readout_sha256") == READOUT_DONDURMA, "beyin dosyasının readout_sha256'sı donmuş okuma (eksikse HATA)")
    rp.check(log.get("decisions_sha256") == pm.sha256_hex(pm.canonical_json(dec)), "log, bu karar dosyasından üretilmiş")
    rp.check(bool(dec.get("prova")) == (not final) and bool(log.get("prova")) == (not final)
             and not dec.get("stub") and not log.get("stub"),
             "karar dosyası ve log'un prova/stub bayrakları moda uygun")
    kicks = dec.get("kicks") or []
    lkicks = log.get("kicks") or []
    by = cfg.get("beyin") or {}
    nn = int(by.get("n", 5))
    rp.check([int(k.get("n", -1)) for k in kicks] == list(range(1, nn + 1)) and
             [int(k.get("n", -1)) for k in lkicks] == list(range(1, nn + 1)),
             f"şutlar 1..{nn} eksiksiz, beyin dosyasında ve log'da (yeniden deneme yok)")

    # karar dosyasındaki beyin kod/veri özetleri
    cs = dec.get("code_sha256") or {}
    ds = dec.get("data_sha256") or {}
    kotu = [f for f in BEYIN_KOD if not cs.get(f) or cs.get(f) != ko.get(f"beyin/{f}")]
    kotu += [f for f, key in BEYIN_VERI.items() if not ds.get(f) or ds.get(f) != ko.get(key)]
    if ds.get("shiu_commit") != SHIU_COMMIT:
        kotu.append("shiu_commit")
    rp.check(not kotu, "karar dosyasındaki code_sha256 / data_sha256 taahhütteki beyin kodu ve verisiyle aynı"
             + (f": FARKLI ya da eksik {kotu}" if kotu else ""))

    # tohum ve sahne (beacon'dan)
    sb = bcn.beyin_tohum_tabani(sha, randomness)
    rp.check(dec.get("seed_base") == sb and [k.get("trial_seed") for k in kicks] == [sb + i for i in range(1, nn + 1)],
             f"beyin tohumları beacon'dan (seed_base {sb}, trial_seed = seed_base + n)")
    beklenen = bcn.kaymalar(cfg, sha, randomness, nn)
    out("       beklenen kaymalar (m): " + ", ".join(f"{x:+.3f}" for x in beklenen))
    scene = [(k.get("scene") or {}).get("keeper_x") for k in kicks]
    rp.check(scene == beklenen, "beyin sahnesi (scene.keeper_x) beacon'dan hesaplanan kaymalarla birebir aynı")
    si = dec.get("scene_input")
    if si is not None:
        rp.check([x.get("keeper_x") for x in si] == beklenen, "beyin girdi kaydı (scene_input) aynı kaymalar")
    start = [(k.get("keeper") or {}).get("start_x") for k in lkicks]
    rp.check(start == beklenen, "motorun kaleci başlangıcı (log keeper.start_x) aynı kaymalar: beyin ile motor aynı yeri görüyor")

    # ucuz beyin kontrolü: nişan ve hız spike sayılarından mı çıkıyor?
    es, err = esleme_yukle(beyin_dir, ko.get("beyin/esleme.py"))
    if es is None:
        rp.check(False, f"donmuş eşleme (esleme.py) yüklenemedi: {err}")
    else:
        bozuk = []
        for k in kicks:
            try:
                s, pw, rt, lt = es["oku"](k["counts"])
                ax, ay, v = es["esle"](s, pw)
                if (round(s, 4), int(pw), rt, lt, {"x": ax, "y": ay}, v) != \
                        (k.get("steer"), k.get("power_spikes"), k.get("Rturn"), k.get("Lturn"), k.get("aim"), k.get("speed_mps")):
                    bozuk.append(k.get("n"))
            except (KeyError, TypeError):
                bozuk.append(k.get("n"))
        rp.check(not bozuk, "her şutta steer, nişan ve hız spike sayılarından donmuş eşlemeyle çıkıyor "
                            "(esle(oku(counts)))" + (f": TUTMAYAN şut {bozuk}" if bozuk else ""))
        rp.check(dec.get("constants") == json.loads(json.dumps(es["sabitler"]())) and dec.get("readout") == es["READOUT"],
                 "karar dosyasındaki okuma formülü ve sabitler donmuş esleme.py ile aynı")

    # beyin yeniden koşusu
    if beyin_kos is None:
        rp.eksik_ekle(EKSIK_BEYIN, "beyin yeniden koşturulmadı (--beyin-atla ya da beyin ortamı yok): spike'lar "
                                   "yalnız kendi içinde tutarlılık açısından kontrol edildi")
    else:
        proje = os.path.dirname(beyin_dir)
        isler = []
        for i, k in enumerate(kicks):
            rpth = k.get("raster_npz")
            isler.append({"n": i + 1, "trial_seed": sb + i + 1, "keeper_x": beklenen[i] if i < len(beklenen) else 0.0,
                          "raster": os.path.join(proje, rpth) if rpth else None})
        try:
            res = beyin_kos(isler)
        except Exception as e:  # noqa: BLE001
            res = None
            rp.check(False, f"beyin yeniden koşusu başarısız: {e}")
        if res is not None:
            rp.check(len(res) == len(kicks) == nn, f"beyin yeniden koşusu {len(res)} şut verdi")
            for k, r in zip(kicks, res):
                fark = [f for f in YENIDEN_ALANLAR if k.get(f) != r.get(f)]
                rp.check(not fark, f"şut {r['n']}: beyin taahhüt + beacon'daki tohum ({r['trial_seed']}) ve yerle "
                                   f"({r['keeper_x']:+.3f}) yeniden koşturuldu, çıktı birebir aynı"
                         + (f": FARKLI {fark}" if fark else f" (spikes {r['spikes_sha256'][:12]})"))
                if r.get("raster") == "yok":
                    rp.bilgi(f"şut {r['n']}: spike raster dosyası (npz) yok; yalnız yeniden koşuyla karşılaştırıldı")
                else:
                    rp.check(r.get("raster") == "aynı", f"şut {r['n']}: raster dosyası (npz) yeniden koşuyla aynı ({r.get('raster')})")

    # ------------------------------------------------------------ motor
    lb = log.get("beacon") or {}
    rp.check(lb.get("value") == randomness and lb.get("rule") == cfg.get("beacon_rule"), "log'daki beacon (kural + değer) bu beacon")
    seeds = pm.effective_seeds(cfg, pm.kick_seeds(cfg, nn), randomness)
    rp.check(log.get("keeper_seeds") == seeds, "kaleci seed'leri = taahhütteki seed'ler + bu beacon")
    try:
        rerun = pm.run(cfg, dec, sha, beacon=randomness)
        rp.check(pm.dumps_readable(rerun) == pm.dumps_readable(log), "motor koşusu baştan üretildi: log bayt bayt aynı")
    except (SystemExit, Exception) as e:  # noqa: BLE001
        rp.check(False, f"motor koşusu yeniden üretilemedi: {e}")
    g, c = skor(log)
    out(f"SKOR   SİNEK {g} – {c} ÇAKIR  (" + " ".join(k.get("outcome", "?") for k in lkicks)
        + "; gol dışı her sonuç ÇAKIR'a)")
    rp.tam = True
    return rp


def sonuc_etiketi(rp):
    if rp.hata:
        return "DOĞRULANAMADI", 1
    if not rp.tam:
        return "TAAHHÜT TUTUYOR (koşu kontrol edilmedi: --log, --karar ve --beacon-dosya gerekli)", 2
    if rp.eksik:
        return " + ".join(rp.eksik), 2
    if not rp.final:
        return "PROVA DOĞRULANDI (final sonuç DEĞİL)", 3
    return "DOĞRULANDI", 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Taahhüt, beacon, beyin ve motor doğrulama")
    ap.add_argument("--taahhut", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--kod", help="story/sabitlenmiş gönderideki TAM SHA-256 (64 karakter)")
    ap.add_argument("--duyuru-sha", "--kural-sha", dest="kural_sha",
                    help="bir gün önce duyurulan DUYURU ÖZETİ (kurallar + kod; commit.py kurallar)")
    ap.add_argument("--yayin-utc", help="taahhüdün herkese açık yerde görüldüğü en erken an (UTC, dış kaynaktan), "
                                        "örn. 2026-10-23T12:00:00Z")
    ap.add_argument("--log")
    ap.add_argument("--karar")
    ap.add_argument("--beacon-dosya")
    ap.add_argument("--sablon", default=os.path.join(HERE, "config_sablon.json"))
    ap.add_argument("--beyin-dizin")
    ap.add_argument("--beyin-python")
    ap.add_argument("--beyin-atla", action="store_true", help="beyni yeniden koşturma (sonuç DOĞRULANDI olamaz)")
    ap.add_argument("--cevrimdisi", action="store_true", help="relay'lere sorma (BLS yine zorunlu)")
    a = ap.parse_args(argv)
    t = pm.load_json(a.taahhut)
    cfg = pm.load_json(a.config)
    log = pm.load_json(a.log) if a.log else None
    dec = pm.load_json(a.karar) if a.karar else None
    bd = pm.load_json(a.beacon_dosya) if a.beacon_dosya else None
    sablon = pm.load_json(a.sablon) if os.path.exists(a.sablon) else None
    bdir = cm.beyin_dizini(a.beyin_dizin)
    py = cm.beyin_python(bdir, a.beyin_python)
    kos = None
    ortam_simdi = None
    if os.path.exists(py):
        try:
            ortam_simdi = cm.ortam_bilgisi(bdir, py)
        except Exception:  # noqa: BLE001
            ortam_simdi = None
        if not a.beyin_atla and log and dec:
            kos = beyin_kos_alt_surec(py, bdir)
    rp = dogrula(t, cfg, kod=a.kod, kural_sha=a.kural_sha, yayin_utc=a.yayin_utc, log=log, dec=dec, beacon_dosya=bd,
                 sablon=sablon, beyin_dir=bdir, beyin_kos=kos, ortam_simdi=ortam_simdi, cevrimdisi=a.cevrimdisi)
    if rp.tam:
        # [tur3 2026-10-22, delik 4] ikinci, bağımsız uygulama (JavaScript, yalnız Node'un crypto modülü)
        import shutil
        node = shutil.which("node")
        js = os.path.join(HERE, "bagimsiz", "kontrol.mjs")
        if node:
            p = subprocess.run([node, js, a.beacon_dosya, a.taahhut, a.log, a.karar], capture_output=True, text=True,
                               timeout=120)
            rp.check(p.returncode == 0 and "BAĞIMSIZ KONTROL: TUTUYOR" in p.stdout,
                     "bağımsız JS uygulaması (bagimsiz/kontrol.mjs) kaymaları, beyin tohumunu ve kaleci seed'lerini "
                     "aynı hesaplıyor")
        else:
            rp.bilgi("node yok: bağımsız JS kontrolü atlandı (elle: node bagimsiz/kontrol.mjs ...)")
    if rp.tam and log:
        log_sha = hashlib.sha256(open(a.log, "rb").read()).hexdigest()
        print("\nVİDEO AÇIKLAMASI VE EKRAN İÇİN (her şutta ekranda: taahhüt, run_id, keeper_x, nişan, sonuç):")
        print(f"   taahhüt SHA-256 : {t.get('sha256')}")
        print(f"   log SHA-256     : {log_sha}   ({os.path.basename(a.log)}, dosya baytları)")
        print(f"   drand turu      : {cfg['beacon']['round']} | run_id: {log.get('run_id')}")
        for k in log["kicks"]:
            print(f"   şut {k['n']}: keeper_x {k['keeper']['start_x']:+.3f} | nişan ({k['shot']['aim']['x']:+.2f}, "
                  f"{k['shot']['aim']['y']:.2f}) {k['shot']['speed_mps']} m/s | {k['outcome']}")
    etiket, kod = sonuc_etiketi(rp)
    print(f"\nözet: {len(rp.hata)} HATA, {len(rp.eksik)} EKSİK, {len(rp.uyari)} UYARI")
    print("NOT: bu sonuç yalnız bu programı KENDİ makinesinde, kendi indirdiği dosyalarla çalıştıran için geçerlidir.")
    print("SONUÇ:", etiket)
    sys.exit(kod)


if __name__ == "__main__":
    main()
