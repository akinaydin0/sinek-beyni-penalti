# -*- coding: utf-8 -*-
"""[tur3b 2026-10-22] ADIM 4: bir taahhüdü doğrula: oyun/verify.py'yi DEĞİŞTİRMEDEN, sinek beyninin yeniden
koşusuyla birlikte çalıştırır ve sonucu düz dille özetler.

Prova5 (varsayılan; bu depodaki tatbikat, beklenen sonuç "PROVA DOĞRULANDI"):
    Windows (PowerShell):  py -3.12 -I araclar\\dogrula.py
    macOS / Linux:         python3.12 -I araclar/dogrula.py

Final (deney günü; --kod, --duyuru-sha ve --yayin-utc değerlerini KENDİN dış kaynaktan oku:
sabitlenmiş gönderi, bir gün önceki duyuru, GitHub commit saati / OpenTimestamps):
    python3.12 -I araclar/dogrula.py --taahhut veri/taahhut.json --config oyun/config_final.json \\
        --log veri/penalty_log.json --karar veri/beyin_kararlari.json --beacon-dosya veri/beacon.json \\
        --kod <TAM 64 karakter SHA-256> --duyuru-sha <duyuru özeti> --yayin-utc <2026-10-23T12:04:00Z>

Ne yapar:
  - verify.py'yi '-I -X utf8' ile çalıştırır (Windows'ta Türkçe çıktı ve Node kontrolü için UTF-8 şart).
  - Beyin Python'unu işletim sistemine göre verir (--beyin-python): Windows beyin\\.venv\\Scripts\\python.exe.
  - verify.py'nin çıktısından her şut için "spike'lar Mac referansıyla bit bit aynı mı" sonucunu çıkarır.
    (Karar dosyası Mac'te üretildi; verify beyni yeniden koşturup spike özetini ona karşı kontrol eder.)
  - Prova5'te çıktıyı Mac'in kendi verify çıktısıyla (veri/prova5/prova5_verify_cikti.txt) satır satır karşılaştırır.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import sys
import time

sys.dont_write_bytecode = True  # depoya __pycache__ yazma
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ortak  # noqa: E402

BEYIN_SATIR = re.compile(r"^(TAMAM|HATA)\s+şut (\d+): beyin taahhüt \+ beacon'daki tohum \((\d+)\) ve yerle "
                         r"\(([-+0-9.]+)\) yeniden koşturuldu, çıktı birebir aynı(.*)$")
RASTER_SATIR = re.compile(r"^(TAMAM|HATA)\s+şut (\d+): raster dosyası \(npz\) yeniden koşuyla aynı")
# Mac çıktısıyla karşılaştırırken platforma göre değişmesi BEKLENEN satırlar
DEGISKEN = ("beyin ortamı",)


def satir_kumesi(metin):
    out = []
    for s in metin.splitlines():
        if s[:7] in ("TAMAM  ", "HATA   ", "UYARI  ", "EKSİK  ", "bilgi  ") or s.startswith(("SONUÇ:", "SKOR")):
            if not any(d in s for d in DEGISKEN):
                out.append(s.rstrip())
    return out


def main():
    ortak.utf8_cikti()
    ap = argparse.ArgumentParser(description="Taahhüdü beyin yeniden koşusuyla doğrula (oyun/verify.py)")
    ap.add_argument("--taahhut")
    ap.add_argument("--config")
    ap.add_argument("--log")
    ap.add_argument("--karar")
    ap.add_argument("--beacon-dosya")
    ap.add_argument("--kod", help="TAM 64 karakter taahhüt SHA-256 (sabitlenmiş gönderiden)")
    ap.add_argument("--duyuru-sha", help="bir gün önce duyurulan DUYURU ÖZETİ")
    ap.add_argument("--yayin-utc", help="taahhüdün herkese açık yerde ilk görüldüğü an (UTC, dış kaynaktan)")
    ap.add_argument("--beyin-python", help="beyin ortamının Python'u (varsayılan beyin/.venv)")
    ap.add_argument("--cevrimdisi", action="store_true", help="drand relay'lerine sorma (BLS yine zorunlu)")
    ap.add_argument("--beklenen", choices=["prova", "final"],
                    help="CI için: çıkış kodu 0 = beklenen sonuç ve 5 şutun 5'inde beyin bit bit aynı")
    ap.add_argument("--cikti", help="verify.py'nin tam çıktısını bu dosyaya yaz")
    ap.add_argument("--json", help="özet JSON")
    a = ap.parse_args()
    ortak.python_kontrol()

    dosyalar = [a.taahhut, a.config, a.log, a.karar, a.beacon_dosya]
    prova5 = not any(dosyalar)
    if prova5:
        p = ortak.PROVA5
        args = ["--taahhut", p["taahhut"], "--config", p["config"], "--log", p["log"], "--karar", p["karar"],
                "--beacon-dosya", p["beacon"], "--kod", a.kod or p["kod"],
                "--duyuru-sha", a.duyuru_sha or p["duyuru_sha"], "--yayin-utc", a.yayin_utc or p["yayin_utc"]]
        print("PROVA5 doğrulanıyor (tatbikat). --kod / --duyuru-sha / --yayin-utc değerleri _tur3/YENI_AKIS.md'den;")
        print("finalde bunları doğrulayan KENDİSİ dış kaynaktan okur.")
    else:
        if not all(dosyalar):
            sys.exit("HATA: final için --taahhut, --config, --log, --karar ve --beacon-dosya birlikte verilmeli.")
        args = ["--taahhut", a.taahhut, "--config", a.config, "--log", a.log, "--karar", a.karar,
                "--beacon-dosya", a.beacon_dosya]
        for ad, v in (("--kod", a.kod), ("--duyuru-sha", a.duyuru_sha), ("--yayin-utc", a.yayin_utc)):
            if v:
                args += [ad, v]
    bpy = a.beyin_python or ortak.dogrulama_beyin_python()
    print(f"beyin Python'u: {bpy}")
    if not os.path.exists(bpy):
        print(f"UYARI: beyin Python'u yok ({bpy}); önce araclar/kur.py. verify beyni yeniden KOŞTURAMAZ.")
    args += ["--beyin-python", bpy]
    if a.cevrimdisi:
        args.append("--cevrimdisi")

    ortak.baslik("oyun/verify.py (beyin yeniden koşusu dahil; ~20 s Mac'te, ilk seferde derleme ile daha uzun)")
    cmd = [sys.executable, "-I", "-X", "utf8", "-B", os.path.join(ortak.OYUN, "verify.py")] + args
    kod, cikti, sure = ortak.kos(cmd, cwd=ortak.KOK)
    if a.cikti:
        with open(a.cikti, "w", encoding="utf-8", newline="\n") as f:
            f.write(cikti + "\n")

    beyin = {}
    for s in cikti.splitlines():
        m = BEYIN_SATIR.match(s)
        if m:
            beyin[int(m.group(2))] = {"ayni": m.group(1) == "TAMAM", "tohum": int(m.group(3)),
                                      "keeper_x": float(m.group(4)), "not": m.group(5).strip()}
        m = RASTER_SATIR.match(s)
        if m and int(m.group(2)) in beyin:
            beyin[int(m.group(2))]["raster_ayni"] = m.group(1) == "TAMAM"
    etiket = next((s[len("SONUÇ:"):].strip() for s in reversed(cikti.splitlines()) if s.startswith("SONUÇ:")), None)
    hatalar = [s[7:] for s in cikti.splitlines() if s.startswith("HATA   ")]
    uyarilar = [s[7:] for s in cikti.splitlines() if s.startswith("UYARI  ")]

    mac_farki = None
    if prova5 and os.path.isfile(ortak.PROVA5["mac_cikti"]):
        with open(ortak.PROVA5["mac_cikti"], encoding="utf-8") as f:
            ref = satir_kumesi(f.read())
        bu = satir_kumesi(cikti)
        mac_farki = {"yalniz_mac": [s for s in ref if s not in bu], "yalniz_bu": [s for s in bu if s not in ref]}

    ortak.baslik("ÖZET (düz dille)")
    print(f"makine: {platform.platform()} | Python {sys.version.split()[0]} | verify süresi {sure:.1f} s")
    print(f"verify.py sonucu: {etiket} (çıkış {kod})")
    if beyin:
        n_ayni = sum(1 for v in beyin.values() if v["ayni"])
        print(f"sinek beyni: {len(beyin)} şutun {n_ayni}'inde spike'lar Mac referansıyla BİT BİT AYNI")
        for n in sorted(beyin):
            v = beyin[n]
            print(f"   şut {n}: {'AYNI' if v['ayni'] else 'FARKLI'}  (tohum {v['tohum']}, kaleci x {v['keeper_x']:+.3f}) "
                  f"{v['not']}" + ("" if v.get("raster_ayni", True) else "  [raster FARKLI]"))
    else:
        print("sinek beyni: yeniden koşu satırı YOK (beyin koşturulamadı; yukarıdaki HATA satırlarına bak)")
    for h in hatalar:
        print(f"   HATA: {h}")
    for u in uyarilar:
        print(f"   UYARI: {u}")
    if mac_farki is not None:
        if not mac_farki["yalniz_mac"] and not mac_farki["yalniz_bu"]:
            print("Mac'in kendi verify çıktısıyla karşılaştırma: bütün kontrol satırları AYNI "
                  "(yalnız 'beyin ortamı' satırı platforma göre değişir)")
        else:
            print("Mac'in kendi verify çıktısıyla karşılaştırma: FARKLI satırlar var")
            for s in mac_farki["yalniz_mac"]:
                print("   yalnız Mac'te: " + s)
            for s in mac_farki["yalniz_bu"]:
                print("   yalnız burada: " + s)

    tamam_beyin = len(beyin) == 5 and all(v["ayni"] and v.get("raster_ayni", True) for v in beyin.values())
    ozet = {"zaman_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "platform": platform.platform(),
            "makine": platform.machine(), "python": sys.version.split()[0], "verify_cikis": kod, "etiket": etiket,
            "verify_sure_s": round(sure, 1), "beyin": {str(k): v for k, v in sorted(beyin.items())},
            "beyin_5_te_5_ayni": tamam_beyin, "beyin_python": bpy, "hatalar": hatalar, "uyarilar": uyarilar, "mac_farki": mac_farki,
            "prova5": prova5}
    if a.json:
        with open(a.json, "w", encoding="utf-8", newline="\n") as f:
            json.dump(ozet, f, ensure_ascii=False, indent=1)
            f.write("\n")
    if a.beklenen == "prova":
        sys.exit(0 if (kod == 3 and tamam_beyin) else 1)
    if a.beklenen == "final":
        sys.exit(0 if (kod == 0 and tamam_beyin) else 1)
    sys.exit(kod)


if __name__ == "__main__":
    main()
