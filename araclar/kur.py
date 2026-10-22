# -*- coding: utf-8 -*-
"""[tur3b 2026-10-22] ADIM 1: sinek beyni ortamını kurar (beyin/.venv), birebir sürümlerle.

    Windows (PowerShell):  py -3.12 -I araclar\\kur.py
    macOS / Linux:         python3.12 -I araclar/kur.py

Ne yapar:
  1. Python 3.12 mi diye bakar (referans 3.12.10).
  2. beyin/.venv'i bu Python ile kurar; pip==26.2.2 ve beyin/requirements.txt'teki 24 paketi birebir sürümle yükler.
  3. Windows: taahhüde giren kod (oyun/commit.py, tests.py) beyin Python'unu beyin/.venv/bin/python yolunda arar;
     Windows venv'i ise Scripts\\python.exe kullanır. Kod değiştirilmesin diye beyin/.venv/bin/ içine
     Scripts\\python.exe'nin bir KOPYASI konur (python ve python.exe adlarıyla). Spike'ları etkilemez.
     Ayrıca beyin/.venv/python_utf8.cmd yazılır: aynı Python'u '-X utf8' ile başlatır. verify.py beyin alt sürecinin
     çıktısını UTF-8 çözer; Türkçe Windows'ta (cp1254) alt süreç 'ş' harfini 0xFE yazar ve çözüm patlar. dogrula.py
     Windows'ta bu .cmd'yi --beyin-python olarak verir. Yalnız metin kodlamasını değiştirir.
  4. Brian2'nin Cython derlemesini 1 ms'lik küçük bir ağla dener. beyin_model.py hedefi 'cython' olarak sabitler;
     derleyici yoksa Brian2 numpy'ye GEÇMEZ, beyin koşusu hata verir. Gerekenler:
       Windows: "Build Tools for Visual Studio 2022" -> "Desktop development with C++" (MSVC)
       macOS:   xcode-select --install   (Xcode Command Line Tools, clang)
       Linux:   sudo apt install build-essential python3.12-dev python3.12-venv  (g++ ve Python başlıkları)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

sys.dont_write_bytecode = True  # depoya __pycache__ yazma
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ortak  # noqa: E402

PIP_SURUM = "pip==26.2.2"
DERLEME_DENEMESI = (
    "import time; t=time.time()\n"
    "from brian2 import NeuronGroup, run, ms, prefs\n"
    "prefs.codegen.target='cython'\n"
    "G=NeuronGroup(2,'dv/dt=-v/(10*ms):1', threshold='v>1', reset='v=0', method='exact')\n"
    "run(1*ms)\n"
    "print('DERLEME TAMAM', round(time.time()-t,1), 's')\n"
)


def main():
    ortak.utf8_cikti()
    ap = argparse.ArgumentParser(description="Sinek beyni ortamını kur (beyin/.venv)")
    ap.add_argument("--temiz", action="store_true", help="var olan beyin/.venv'i silip baştan kur")
    ap.add_argument("--derleyici-atla", action="store_true", help="Cython derleme denemesini atla")
    a = ap.parse_args()
    ortak.python_kontrol("3.12.10")
    ortak.baslik(f"1/4 Python {sys.version.split()[0]} ({sys.executable})")
    if a.temiz and os.path.isdir(ortak.VENV):
        shutil.rmtree(ortak.VENV)
    py = ortak.venv_python()
    if not os.path.exists(py):
        kod, _, s = ortak.kos([sys.executable, "-m", "venv", ortak.VENV])
        if kod != 0:
            sys.exit("HATA: venv kurulamadı (Linux'ta: sudo apt install python3.12-venv).")
        print(f"beyin/.venv kuruldu ({s:.1f} s)")
    else:
        print("beyin/.venv zaten var (baştan kurmak için --temiz)")

    ortak.baslik("2/4 paketler (birebir sürümler)")
    kod, _, s1 = ortak.kos([py, "-m", "pip", "install", "--disable-pip-version-check", "-q", PIP_SURUM])
    if kod != 0:
        sys.exit("HATA: pip güncellenemedi.")
    req = os.path.join(ortak.BEYIN, "requirements.txt")
    kod, _, s2 = ortak.kos([py, "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", req])
    if kod != 0:
        sys.exit("HATA: paketler kurulamadı (yukarıdaki pip çıktısına bak).")
    print(f"paketler kuruldu ({s1 + s2:.0f} s)")
    ref = ortak.json_oku(ortak.PROVA5["config"])["ortam"]["paketler"]
    kod, cikti, _ = ortak.kos([py, "-I", "-B", "-c",
                               "import importlib.metadata as m;print('\\n'.join(sorted(d.metadata['Name']+'=='+d.version "
                               "for d in m.distributions())))"], gizle=True)
    simdi = [x for x in cikti.splitlines() if "==" in x]
    eksik = sorted(set(ref) - set(simdi))
    fazla = sorted(set(simdi) - set(ref))
    print(f"paket listesi Mac referansıyla {'AYNI' if not eksik and not fazla else 'FARKLI'} "
          f"({len(simdi)} paket; eksik {eksik or '-'}; fazla {fazla or '-'})")

    if ortak.WINDOWS:
        ortak.baslik("3/4 Windows: beyin/.venv/bin/python kopyası (taahhüt kodu bu yolu bekliyor)")
        bin_dir = os.path.join(ortak.VENV, "bin")
        os.makedirs(bin_dir, exist_ok=True)
        for ad in ("python.exe", "python"):
            shutil.copy2(py, os.path.join(bin_dir, ad))
        # Alt süreç yolu cp1252 ile yazar ('ç' bozulur): yolu ASCII-güvenli JSON olarak al
        kod_json = "import sys,json;print(json.dumps([sys.flags.utf8_mode, sys.prefix]))"
        try:
            kod, cikti, _ = ortak.kos([os.path.join(bin_dir, "python"), "-I", "-c", kod_json], gizle=True)
            utf8, prefix = json.loads(cikti.strip().splitlines()[-1])
        except (OSError, ValueError, IndexError) as e:
            kod, utf8, prefix = -1, 0, f"çalışmadı: {e}"
        print(f"beyin/.venv/bin/python -> {prefix} (çıkış {kod})")
        if kod != 0 or os.path.normcase(os.path.abspath(prefix)) != os.path.normcase(os.path.abspath(ortak.VENV)):
            sys.exit("HATA: beyin/.venv/bin/python kopyası venv'i bulamadı.")
        with open(ortak.UTF8_CMD, "w", encoding="ascii", newline="") as f:
            f.write(ortak.UTF8_CMD_ICERIK)
        try:
            kod, cikti, _ = ortak.kos([ortak.UTF8_CMD, "-I", "-B", "-c", kod_json], gizle=True)
            utf8, prefix = json.loads(cikti.strip().splitlines()[-1])
        except (OSError, ValueError, IndexError) as e:
            kod, utf8, prefix = -1, 0, f"çalışmadı: {e}"
        print(f"beyin/.venv/python_utf8.cmd -> utf8_mode {utf8}, prefix {prefix} (çıkış {kod})")
        if kod != 0 or utf8 != 1 or \
                os.path.normcase(os.path.abspath(prefix)) != os.path.normcase(os.path.abspath(ortak.VENV)):
            os.remove(ortak.UTF8_CMD)
            print("UYARI: python_utf8.cmd çalışmadı ve silindi; dogrula.py düz python.exe kullanacak. Türkçe kod "
                  "sayfalı (cp1254) Windows'ta beyin yeniden koşusu bu yüzden 'UnicodeDecodeError' ile düşebilir.")
    else:
        ortak.baslik("3/4 (yalnız Windows'ta gerekli adım: atlandı)")

    ortak.baslik("4/4 Brian2 Cython derleme denemesi")
    if a.derleyici_atla:
        print("atlandı (--derleyici-atla)")
        return
    kod, cikti, s = ortak.kos([py, "-I", "-B", "-c",
                               "import sys; sys.path.insert(0, " + repr(ortak.BEYIN) + "); import ortam; "
                               "ortam.derleyici_ayarla(); exec(" + repr(DERLEME_DENEMESI) + ")"], gizle=True)
    if kod == 0 and "DERLEME TAMAM" in cikti:
        print(f"Cython derlemesi çalışıyor ({s:.1f} s).")
    else:
        print(cikti[-1500:])
        print("\nHATA: Brian2 Cython ile derleyemedi. beyin_model.py hedefi 'cython' olarak sabitler ve Brian2 bu "
              "durumda numpy'ye GEÇMEZ: beyin yeniden koşusu, dolayısıyla doğrulama, hata verir. Derleyiciyi kur:")
        print("  Windows: Build Tools for Visual Studio 2022 -> 'Desktop development with C++'")
        print("  macOS:   xcode-select --install")
        print("  Linux:   sudo apt install build-essential python3.12-dev")
        sys.exit(2)


if __name__ == "__main__":
    main()
