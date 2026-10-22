"""Okumayı dondurur: esleme.py + ids.json özetini ve zamanı DONDURMA.json'a yazar.

readout_sha256 = SHA-256( esleme.py baytları  ||  ids.json baytları )
Kabukta doğrulama:  cat esleme.py ids.json | shasum -a 256

Kullanım: .venv/bin/python -I dondur.py          (yalnızca ilk kez; varsa üzerine yazmaz)
          .venv/bin/python -I dondur.py --kontrol (şu anki dosyalar donmuş özetle aynı mı?)
"""
import sys
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

BEYIN = Path(__file__).resolve().parent
DOSYALAR = ['esleme.py', 'ids.json']
KAYIT = BEYIN / 'DONDURMA.json'


def ozet():
    h = hashlib.sha256()
    tek = {}
    for ad in DOSYALAR:
        b = (BEYIN / ad).read_bytes()
        h.update(b)
        tek[ad] = hashlib.sha256(b).hexdigest()
    return h.hexdigest(), tek


def kontrol():
    """(donmus_mu, kayit) döndürür. Kayıt yoksa (False, None)."""
    if not KAYIT.exists():
        return False, None
    k = json.loads(KAYIT.read_text())
    s, _ = ozet()
    return s == k['readout_sha256'], k


def main():
    if '--kontrol' in sys.argv:
        ok, k = kontrol()
        print('DONMUŞ VE AYNI' if ok else 'UYUŞMUYOR / KAYIT YOK', k and k['readout_sha256'])
        sys.exit(0 if ok else 1)
    if KAYIT.exists():
        print('DONDURMA.json zaten var, üzerine yazılmadı:', json.loads(KAYIT.read_text())['readout_sha256'])
        sys.exit(1)
    s, tek = ozet()
    k = {
        'readout_sha256': s,
        'definition': 'SHA-256 of the bytes of esleme.py followed by the bytes of ids.json '
                      '(cat esleme.py ids.json | shasum -a 256)',
        'files_sha256': tek,
        'readout_frozen_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'note': 'Frozen after the direction-blind pilot (veri/pilot.json) and BEFORE calibration.',
    }
    KAYIT.write_text(json.dumps(k, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(k, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
