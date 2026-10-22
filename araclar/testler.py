# -*- coding: utf-8 -*-
"""[tur3b 2026-10-22] ADIM 3: testler.

    Windows (PowerShell):  py -3.12 -I araclar\\testler.py
    macOS / Linux:         python3.12 -I araclar/testler.py

Üç kontrol:
  A. Dosyalar taahhütteki gibi mi? Taahhüde giren 21 dosyanın (11 oyun + 10 beyin) SHA-256'sı
     veri/prova5/config_prova5.json -> kod_ozetleri ile aynı mı. Tutmazsa en sık sebep Windows'ta git'in satır
     sonlarını CRLF'ye çevirmesidir (.gitattributes bunu kapatır; ZIP yerine 'git clone' kullan).
  B. Duyuru özeti: oyun/commit.py kurallar -> 572bbd8a… (veri/duyuru.json ile aynı olmalı).
  C. oyun/tests.py: 22 test (ağa çıkmaz; beyin koşusu burada taklit edilir, gerçeği dogrula.py'de).
"""
from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True  # depoya __pycache__ yazma
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ortak  # noqa: E402


def dosya_kontrol():
    ko = ortak.json_oku(ortak.PROVA5["config"])["kod_ozetleri"]
    kotu = []
    for anahtar, sha in sorted(ko.items()):
        p = os.path.join(ortak.KOK, *anahtar.split("/"))
        if not os.path.isfile(p):
            kotu.append(f"{anahtar}: YOK" + (" (önce araclar/veri_indir.py)" if "indirilen" in anahtar else ""))
            continue
        s = ortak.sha256_dosya(p)
        if s != sha:
            with open(p, "rb") as f:
                crlf = b"\r\n" in f.read()
            kotu.append(f"{anahtar}: FARKLI ({s[:12]}… ≠ {sha[:12]}…)" + (" — dosyada CRLF var: satır sonları "
                                                                          "değişmiş" if crlf else ""))
    for k in kotu:
        print("HATA   " + k)
    print(("TAMAM  " if not kotu else "HATA   ") + f"taahhüde giren {len(ko)} dosyanın SHA-256'sı "
          f"{'taahhüttekiyle aynı' if not kotu else 'TUTMUYOR'}")
    return not kotu


def main():
    ortak.utf8_cikti()
    ortak.python_kontrol()
    sonuc = {}
    ortak.baslik("A. dosyalar taahhütteki gibi mi?")
    sonuc["A"] = dosya_kontrol()

    ortak.baslik("B. duyuru özeti (oyun/commit.py kurallar)")
    kod, cikti, s = ortak.kos([sys.executable, "-I", "-X", "utf8", "-B", os.path.join(ortak.OYUN, "commit.py"),
                               "kurallar"])
    beklenen = ortak.json_oku(os.path.join(ortak.VERI, "duyuru.json"))["duyuru_ozeti_sha256"]
    sonuc["B"] = kod == 0 and beklenen in cikti and beklenen == ortak.PROVA5["duyuru_sha"]
    print(("TAMAM  " if sonuc["B"] else "HATA   ") + f"duyuru özeti {beklenen[:12]}… "
          f"{'tutuyor' if sonuc['B'] else 'TUTMUYOR'} ({s:.1f} s)")

    ortak.baslik("C. oyun/tests.py")
    kod, cikti, s = ortak.kos([sys.executable, "-I", "-X", "utf8", "-B", os.path.join(ortak.OYUN, "tests.py")])
    son = [x for x in cikti.splitlines() if "test geçti" in x]
    sonuc["C"] = kod == 0 and bool(son) and son[-1].split()[0] in ("22/22",)
    print(("TAMAM  " if sonuc["C"] else "HATA   ") + f"oyun/tests.py: {son[-1] if son else 'sonuç satırı yok'} "
          f"(çıkış {kod}, {s:.1f} s)")

    print("\nÖZET: " + "  ".join(f"{k}={'TAMAM' if v else 'HATA'}" for k, v in sonuc.items()))
    sys.exit(0 if all(sonuc.values()) else 1)


if __name__ == "__main__":
    main()
