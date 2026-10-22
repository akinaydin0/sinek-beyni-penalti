# -*- coding: utf-8 -*-
"""[tur3b 2026-10-22] ADIM 2: Shiu et al. (2024) modelinin dosyalarını SABİT commit'ten indirir ve SHA-256'larını
kontrol eder. Tutmayan dosya diske YAZILMAZ (geçici .part dosyası silinir).

    Windows (PowerShell):  py -3.12 -I araclar\\veri_indir.py
    macOS / Linux:         python3.12 -I araclar/veri_indir.py
    İnternetsiz / ayna:    ... araclar/veri_indir.py --kaynak-dizin <bu dosyaların durduğu klasör>
    Ek (isteğe bağlı):     ... araclar/veri_indir.py --ek     (FlyWire açıklama dosyası, 31 MB; kimlikler.py için)

Kaynak: https://github.com/philshiu/Drosophila_brain_model, commit 91bdd1e7dcf193f3e7ca5a8933497fcef63b7960 (MIT).
Beklenen SHA-256'lar: Completeness/Connectivity için beyin/ids.json -> model_data (dondurulmuş, taahhüde girer);
model.py için veri/prova5/config_prova5.json -> kod_ozetleri (taahhüde girer). Hepsi ayrıca aşağıda elle yazılı;
iki kaynak birbirini tutmazsa betik durur.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import time
import urllib.request

sys.dont_write_bytecode = True  # depoya __pycache__ yazma
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ortak  # noqa: E402

SHIU_COMMIT = "91bdd1e7dcf193f3e7ca5a8933497fcef63b7960"
SHIU_URL = f"https://raw.githubusercontent.com/philshiu/Drosophila_brain_model/{SHIU_COMMIT}/"
HEDEF = os.path.join(ortak.BEYIN, "indirilen", "shiu_model")
# ad -> (sha256, bayt); elle yazılı kopya, ids.json / config ile karşılaştırılır
DOSYALAR = {
    "model.py": ("fc45837d7122c6ce2a7f3f2f23c515992e4b232aadb919efabb72337fac88e4e", 11900),
    "Completeness_783.csv": ("bbb847a4cc2caaa7a16349722d220c087317b946d148d4d592d94d250617a311", 3327347),
    "Connectivity_783.parquet": ("efeb23fb99098e9c390f6869969b2a121a2ee92c833cfc45ecb2c1d8e1af0347", 100804642),
    "LICENSE": ("3621f6d6476189190e2960fa43f11b275ba4eca848fdac50a1ba2925de6223e8", 1085),
}
EK_COMMIT = "a83b2776d60d5764cef36b927f5f9679c16c47a2"
EK = {"ad": "Supplemental_file1_neuron_annotations.tsv",
      "url": f"https://raw.githubusercontent.com/flyconnectome/flywire_annotations/{EK_COMMIT}/supplemental_files/"
             "Supplemental_file1_neuron_annotations.tsv",
      "hedef": os.path.join(ortak.BEYIN, "indirilen", "flywire_annotations"),
      "sha": "b214970b55d2fbe0853bba536fdcb9e28730f4eb7ab06f600491df795da683cd", "bayt": 31720298}


def capraz_kontrol():
    ids = ortak.json_oku(os.path.join(ortak.BEYIN, "ids.json"))
    md = ids["model_data"]
    cfg = ortak.json_oku(ortak.PROVA5["config"])["kod_ozetleri"]
    beklenen = {
        "Completeness_783.csv": md["Completeness_783.csv_sha256"],
        "Connectivity_783.parquet": md["Connectivity_783.parquet_sha256"],
        "model.py": cfg["beyin/indirilen/shiu_model/model.py"],
    }
    for ad, sha in beklenen.items():
        if DOSYALAR[ad][0] != sha:
            sys.exit(f"HATA: {ad} için elle yazılı SHA-256 ile ids.json/config farklı. Betik durdu.")
    if md["commit"] != SHIU_COMMIT or ids["annotation_file"]["sha256"] != EK["sha"]:
        sys.exit("HATA: ids.json'daki commit/özet bu betikteki sabitlerle aynı değil.")
    print("beklenen SHA-256'lar: betik = beyin/ids.json = taahhüt config'i (model.py)  [TAMAM]")


def indir(url, hedef, sha, bayt, deneme=4):
    part = hedef + ".part"
    for k in range(1, deneme + 1):
        try:
            h = hashlib.sha256()
            n = 0
            t0 = time.time()
            req = urllib.request.Request(url, headers={"User-Agent": "sinek-beyni-penalti-dogrulama/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r, open(part, "wb") as f:  # noqa: S310 (sabit https)
                son = -1
                for blk in iter(lambda: r.read(1 << 20), b""):
                    f.write(blk)
                    h.update(blk)
                    n += len(blk)
                    yuzde = int(100 * n / bayt) if bayt else 0
                    if yuzde // 20 != son and bayt > 5_000_000:
                        son = yuzde // 20
                        print(f"   {os.path.basename(hedef)}: %{yuzde} ({n / 1e6:.0f} MB)", flush=True)
            if h.hexdigest() != sha or n != bayt:
                os.remove(part)
                raise ValueError(f"SHA-256/boyut TUTMADI ({h.hexdigest()[:12]}…, {n} bayt; beklenen {sha[:12]}…, {bayt})")
            os.replace(part, hedef)
            return time.time() - t0
        except Exception as e:  # noqa: BLE001
            if os.path.exists(part):
                os.remove(part)
            print(f"   deneme {k}/{deneme} başarısız: {e}", flush=True)
            if k == deneme or isinstance(e, ValueError):
                raise
            time.sleep(3 * k)
    return None


def main():
    ortak.utf8_cikti()
    ap = argparse.ArgumentParser(description="Shiu et al. model dosyalarını indir ve SHA-256 ile kontrol et")
    ap.add_argument("--kaynak-dizin", help="indirmek yerine bu klasörden kopyala (yine SHA-256 kontrol edilir)")
    ap.add_argument("--ek", action="store_true", help="FlyWire açıklama dosyasını da indir (kimlikler.py için)")
    a = ap.parse_args()
    capraz_kontrol()
    os.makedirs(HEDEF, exist_ok=True)
    t_top = time.time()
    hata = 0
    isler = [(ad, SHIU_URL + ad, os.path.join(HEDEF, ad), sha, bayt) for ad, (sha, bayt) in DOSYALAR.items()]
    if a.ek:
        os.makedirs(EK["hedef"], exist_ok=True)
        isler.append((EK["ad"], EK["url"], os.path.join(EK["hedef"], EK["ad"]), EK["sha"], EK["bayt"]))
    for ad, url, hedef, sha, bayt in isler:
        if os.path.isfile(hedef) and ortak.sha256_dosya(hedef) == sha:
            print(f"TAMAM  {ad}: zaten var, SHA-256 tutuyor ({sha[:12]}…)")
            continue
        try:
            if a.kaynak_dizin:
                kaynak = os.path.join(a.kaynak_dizin, ad)
                if not os.path.isfile(kaynak) or ortak.sha256_dosya(kaynak) != sha:
                    raise ValueError(f"{kaynak} yok ya da SHA-256 tutmuyor")
                shutil.copyfile(kaynak, hedef)
                print(f"TAMAM  {ad}: kopyalandı, SHA-256 tutuyor ({sha[:12]}…)")
            else:
                s = indir(url, hedef, sha, bayt)
                print(f"TAMAM  {ad}: indirildi, SHA-256 tutuyor ({sha[:12]}…, {bayt / 1e6:.1f} MB, {s:.1f} s)")
        except Exception as e:  # noqa: BLE001
            hata += 1
            print(f"HATA   {ad}: {e}")
    print(f"\nsüre {time.time() - t_top:.1f} s; hedef klasör: {HEDEF}")
    if hata:
        sys.exit(f"SONUÇ: {hata} dosya alınamadı ya da SHA-256 tutmadı.")
    print("SONUÇ: bütün dosyalar yerinde ve SHA-256'ları tutuyor.")


if __name__ == "__main__":
    main()
