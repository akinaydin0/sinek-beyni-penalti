# -*- coding: utf-8 -*-
"""[tur3b 2026-10-22] araclar/ ortak yardımcıları: yollar, işletim sistemine göre beyin Python'u, UTF-8 çıktı,
alt süreç çalıştırma. Yalnız standart kütüphane.

Bu klasördeki betikler (kur.py, veri_indir.py, testler.py, dogrula.py) taahhüde GİRMEZ; yalnız kurulum ve
çalıştırma kolaylığıdır. Doğrulamanın kendisi oyun/verify.py'dir ve bu betikler onu DEĞİŞTİRMEDEN çağırır.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time

ARACLAR = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(ARACLAR)
OYUN = os.path.join(KOK, "oyun")
BEYIN = os.path.join(KOK, "beyin")
VERI = os.path.join(KOK, "veri")
VENV = os.path.join(BEYIN, ".venv")
WINDOWS = os.name == "nt"

# prova5: _tur3/YENI_AKIS.md "PROVA5" bölümündeki değerler. Provada açık gönderi olmadığı için --kod ve
# --yayin-utc dış kaynaktan değil, belgeden gelir (finalde doğrulayan bunları KENDİSİ dış kaynaktan okur).
PROVA5 = {
    "taahhut": os.path.join(VERI, "prova5", "taahhut_prova5.json"),
    "config": os.path.join(VERI, "prova5", "config_prova5.json"),
    "log": os.path.join(VERI, "prova5", "prova5_penalty_log.json"),
    "karar": os.path.join(VERI, "prova5", "prova5_beyin_kararlari.json"),
    "beacon": os.path.join(VERI, "prova5", "beacon_prova5.json"),
    "kod": "71a3c84e932d435d52b14731eb717f82f880f52404412d4c94e82315aaec5a31",
    "duyuru_sha": "572bbd8a487ac49c87020e760b695e9afc930517ce92e1063c9f9e39bb0fe775",
    "yayin_utc": "2026-10-22T19:13:20Z",
    "mac_cikti": os.path.join(VERI, "prova5", "prova5_verify_cikti.txt"),
}
READOUT_DONDURMA = "e0ff656deddd74430262a8b5b272ca9842ae75a2f9b8a806562cc4e42cdcaa27"


def utf8_cikti():
    """Windows'ta konsol/boru kodlaması cp1252/cp1254 olabilir: Türkçe karakterler için çıktıyı UTF-8 yap."""
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            try:
                s.reconfigure(encoding="utf-8", errors="backslashreplace")
            except (ValueError, OSError):
                pass


def python_kontrol(tam=None):
    v = sys.version_info
    if (v.major, v.minor) != (3, 12):
        komut = "py -3.12" if WINDOWS else "python3.12"
        sys.exit(f"HATA: Python 3.12 gerekli (bu {v.major}.{v.minor}.{v.micro}). Komutu '{komut} ...' ile çalıştır.")
    if tam and ".".join(map(str, v[:3])) != tam:
        print(f"UYARI: Mac referansı Python {tam} ile koşturuldu; bu {v.major}.{v.minor}.{v.micro}. "
              "verify.py bunu UYARI olarak gösterir; spike'lar yine de aynı çıkmalı.")


def venv_python():
    """Beyin ortamının Python'u (Windows: Scripts\\python.exe, diğerleri: bin/python)."""
    if WINDOWS:
        return os.path.join(VENV, "Scripts", "python.exe")
    return os.path.join(VENV, "bin", "python")


# [tur3b 2026-10-22] Windows: verify.py beyin alt sürecini '-I -B' ile çağırır ve çıktısını kendi (UTF-8) kodlamasıyla
# çözer. Alt süreç ise sistemin kod sayfasıyla yazar: cp1254 (Türkçe Windows) 'ş' harfini 0xFE olarak yazar ve
# UTF-8 çözümü patlar -> "beyin yeniden koşusu başarısız". Bu küçük .cmd, aynı Python'u '-X utf8' ile başlatır;
# yalnız metin kodlamasını değiştirir (spike'ları değil). kur.py yazar; dogrula.py Windows'ta bunu kullanır.
UTF8_CMD = os.path.join(VENV, "python_utf8.cmd")
UTF8_CMD_ICERIK = ("@echo off\r\n"
                   "rem [tur3b 2026-10-22] Runs the brain venv Python in UTF-8 mode (-X utf8). Text encoding only.\r\n"
                   "\"%~dp0Scripts\\python.exe\" -X utf8 %*\r\n")


def dogrulama_beyin_python():
    """dogrula.py'nin verify.py'ye verdiği beyin Python'u (Windows'ta UTF-8 .cmd, diğerlerinde venv python)."""
    if WINDOWS and os.path.isfile(UTF8_CMD):
        return UTF8_CMD
    return venv_python()


def sha256_dosya(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def json_oku(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def kos(cmd, *, cwd=None, girdi=None, gizle=False, zaman_asimi=None):
    """Komutu çalıştırır, çıktısını (UTF-8 çözülerek) canlı basar ve toplar. (çıkış kodu, metin, süre_s) döner."""
    t0 = time.time()
    p = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.PIPE if girdi is not None else None,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if girdi is not None:
        p.stdin.write(girdi.encode("utf-8"))
        p.stdin.close()
    satirlar = []
    for ham in iter(p.stdout.readline, b""):
        s = ham.decode("utf-8", errors="replace").rstrip("\r\n")
        satirlar.append(s)
        if not gizle:
            print(s, flush=True)
    p.wait(timeout=zaman_asimi)
    return p.returncode, "\n".join(satirlar), time.time() - t0


def baslik(s):
    print("\n" + "=" * 78 + f"\n{s}\n" + "=" * 78, flush=True)
