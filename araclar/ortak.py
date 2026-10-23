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

# [tur4 2026-10-23] Depodaki doğrulanan tatbikat artık PROVA7B (tur3b kodu, seçenek B: şut sapması açık; bugünkü
# oyun/ ile birebir aynı kod). Değerler _tur3/DEGISIKLIK.md "PROVA7B" satırından. Provada açık gönderi olmadığı için
# --kod ve --yayin-utc dış kaynaktan değil, belgeden gelir (finalde doğrulayan bunları KENDİSİ dış kaynaktan okur).
# Eski PROVA5 dosyaları veri/prova5/ içinde duruyor; eski motorla yapıldığı için bugünkü verify.py ile bilerek
# DOĞRULANAMADI alır ("her taahhüt yayınlanır" kuralı gereği depoda).
PROVA = {
    "ad": "PROVA7B",
    "taahhut": os.path.join(VERI, "prova7B", "taahhut_prova7B.json"),
    "config": os.path.join(VERI, "prova7B", "config_prova7B.json"),
    "log": os.path.join(VERI, "prova7B", "prova7B_penalty_log.json"),
    "karar": os.path.join(VERI, "prova7B", "prova7B_beyin_kararlari.json"),
    "beacon": os.path.join(VERI, "prova7B", "beacon_prova7B.json"),
    "kod": "95d11f1736b19ac9e78c77b09f79f9d5f0122b3702dd4bf2e73fd2b182e210ed",
    "duyuru_sha": "ab65e95be6b8ff29b9713e8481f4c8a93a1f4af5dcf2e00902bdfce687b51cf2",
    "yayin_utc": "2026-10-22T20:44:44Z",
    "mac_cikti": os.path.join(VERI, "prova7B", "prova7B_verify_cikti.txt"),
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


# [tur4 2026-10-23] macOS / Linux eşi. Aynı sorun 8-bit yerel ayarlı (ör. tr_TR.ISO-8859-9) Linux'ta da var: CI'da
# ölçüldü, kalkansız "'utf-8' codec can't decode byte 0xfe" -> DOĞRULANAMADI. Bu sh betiği venv'in kendi python'unu
# '-X utf8' ile başlatır (yol betiğin kendi yerinden bulunur, boşluk ve Türkçe karakter sorun olmaz). UTF-8 yerel
# ayarda (macOS ve bugünkü Linux'ların hepsi) zaten aynı kodlamadır; hiçbir şeyi değiştirmez.
UTF8_SH = os.path.join(VENV, "bin", "python_utf8")
UTF8_SH_ICERIK = ("#!/bin/sh\n"
                  "# [tur4 2026-10-23] Runs the brain venv Python in UTF-8 mode (-X utf8). Text encoding only.\n"
                  "exec \"$(dirname \"$0\")/python\" -X utf8 \"$@\"\n")
# [tur4 2026-10-23] yol, BAYT olarak (hex) karşılaştırılır: 8-bit yerel ayarlı Linux'ta bu süreç yolu ISO-8859-9 ile,
# -X utf8'li alt süreç UTF-8 ile çözer ("ç" -> "Ã§"); metin olarak karşılaştırmak kalkanı yanlışlıkla reddediyordu
# (CI 39884328955, Linux Latin-5 benzetimi). Diskteki baytlar ikisinde de aynıdır.
KALKAN_KONTROL = ("import sys,os,json;print(json.dumps([sys.flags.utf8_mode, "
                  "os.fsencode(os.path.realpath(sys.prefix)).hex()]))")


def utf8_kalkani():
    """İşletim sistemine göre UTF-8 kalkanının yolu (Windows .cmd, ötekiler sh)."""
    return UTF8_CMD if WINDOWS else UTF8_SH


def utf8_kalkan_kur():
    """[tur4 2026-10-23] macOS/Linux: beyin/.venv/bin/python_utf8 yazar ve dener. (yol | None, açıklama) döner.
    Windows'ta .cmd'yi kur.py yazar (orada ek kontroller var); burada yalnız varlığı bildirilir."""
    if WINDOWS:
        return (UTF8_CMD if os.path.isfile(UTF8_CMD) else None), "Windows: python_utf8.cmd (kur.py yazar)"
    if not os.path.exists(venv_python()):
        return None, "beyin/.venv yok"
    try:
        with open(UTF8_SH, "w", encoding="ascii", newline="\n") as f:
            f.write(UTF8_SH_ICERIK)
        os.chmod(UTF8_SH, 0o755)
        p = subprocess.run([UTF8_SH, "-I", "-B", "-c", KALKAN_KONTROL], capture_output=True, timeout=60)
        utf8, prefix = json.loads(p.stdout.decode("utf-8").strip().splitlines()[-1])
    except (OSError, ValueError, IndexError, subprocess.SubprocessError) as e:
        return None, f"python_utf8 çalışmadı: {e}"
    if p.returncode != 0 or utf8 != 1 or prefix != os.fsencode(os.path.realpath(VENV)).hex():
        return None, (f"python_utf8 beklenen ortamı vermedi (utf8_mode {utf8}, prefix "
                      f"{bytes.fromhex(prefix).decode('utf-8', 'replace') if prefix else prefix})")
    return UTF8_SH, "tamam (utf8_mode 1, prefix beyin/.venv)"


def dogrulama_beyin_python():
    """dogrula.py'nin verify.py'ye verdiği beyin Python'u: UTF-8 kalkanı (Windows .cmd, macOS/Linux sh), yoksa
    düz venv python. [tur4 2026-10-23] macOS/Linux'ta da kalkan: kur.py yazmadıysa burada yazılır ve denenir."""
    if WINDOWS:
        return UTF8_CMD if os.path.isfile(UTF8_CMD) else venv_python()
    yol, _ = utf8_kalkan_kur()
    return yol or venv_python()


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
