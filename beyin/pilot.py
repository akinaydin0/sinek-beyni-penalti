"""Yön-kör pilot: girdi gücünü ve power ölçeğini önceden yazılmış bir kuralla seçer.

KURAL (koşmadan önce yazıldı):
- Sahne: yalnızca kaleci ORTADA (keeper_x = 0). Sol/sağ sahneler pilotta yok.
- Izgara: P9 sürüşü önce kapalı (0), sonra 100 Hz (eonsystemspbc/fly-brain'in P9
  deneyindeki hız); LC10 hızı 5, 10, 20, 40 Hz. Sıra: P9 kapalı + artan LC10.
- Her koşul 5 deneme, pilot tohumları 9_000_001'den başlar (kalibrasyonda ve
  şutlarda hiç kullanılmaz).
- Ölçülen YALNIZCA toplamlar: S = Rturn + Lturn (10 dönüş nöronunun toplam spike'ı),
  POW = oDN1_L + oDN1_R, tüm beyindeki spike sayısı. Sol-sağ farkı hesaplanmaz.
- Seçim: sıradaki ilk koşul, ortalama S >= 10 ve ortalama POW >= 1 ise seçilir.
  (Dönüş nöronları susuyorsa P9 açılır; görev tanımındaki "isteğe bağlı P9".)
- P_SCALE = max(1, seçilen koşuldaki POW medyanı, tam sayıya yuvarlanmış).
- Hiçbir koşul geçmezse: LC10 40 Hz + P9 100 Hz alınır ve "silent" diye işaretlenir.
Seçilen üç sabit esleme.py'ye bu betik tarafından yazılır.

Kullanım: .venv/bin/python -I pilot.py
"""
import sys
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ortam  # noqa: E402
import numpy as np  # noqa: E402
import esleme  # noqa: E402
from beyin_model import SinekBeyni  # noqa: E402

IZGARA_P9 = [0.0, 100.0]
IZGARA_LC10 = [5.0, 10.0, 20.0, 40.0]
N_DENEME = 5
TOHUM0 = 9_000_001


def main():
    ids = json.load(open(ortam.BEYIN / 'ids.json'))
    beyin = SinekBeyni(esleme.tum_girdi_kimlikleri(ids))
    grup_ids = {k: [int(r) for r in ids['groups'][k]['root_ids_v783']] for k in esleme.COUNT_KEYS}
    sonuc = []
    tohum = TOHUM0
    for p9 in IZGARA_P9:
        for r in IZGARA_LC10:
            S, POW, TOT, sure = [], [], [], []
            for _ in range(N_DENEME):
                rates = esleme.girdi_hizlari(0.0, ids, r_lc10=r, p9_hz=p9)
                i, t, d = beyin.deneme(rates, tohum, esleme.T_TRIAL_S)
                tohum += 1
                c = np.bincount(i, minlength=len(beyin.root_ids))
                cnt = {k: int(sum(c[beyin.f2i[x]] for x in v)) for k, v in grup_ids.items()}
                S.append(sum(cnt[k] for k in esleme.RTURN + esleme.LTURN))
                POW.append(sum(cnt[k] for k in esleme.POWER))
                TOT.append(int(len(i)))
                sure.append(d)
            row = {'p9_hz': p9, 'r_lc10_hz': r, 'steer_total_mean': float(np.mean(S)),
                   'power_mean': float(np.mean(POW)), 'power_median': float(np.median(POW)),
                   'brain_spikes_mean': float(np.mean(TOT)), 'trial_s_mean': float(np.mean(sure[1:] or sure))}
            sonuc.append(row)
            print(row, flush=True)
    secim = None
    for row in sonuc:
        if row['steer_total_mean'] >= 10 and row['power_mean'] >= 1:
            secim = dict(row, status='ok')
            break
    if secim is None:
        row = [x for x in sonuc if x['p9_hz'] == 100.0 and x['r_lc10_hz'] == 40.0][0]
        secim = dict(row, status='silent')
    p_scale = max(1, int(round(secim['power_median'])))
    out = {
        'what': 'direction-blind pilot (centred keeper only, totals only)',
        'rule': __doc__.split('KURAL (koşmadan önce yazıldı):')[1].split('Kullanım')[0].strip(),
        'seeds': f'{TOHUM0}..{tohum - 1}', 'n_trials_per_condition': N_DENEME,
        'grid': sonuc,
        'selected': {'R_LC10_HZ': secim['r_lc10_hz'], 'P9_DRIVE_HZ': secim['p9_hz'], 'P_SCALE': p_scale,
                     'status': secim['status']},
        'run_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    }
    with open(ortam.VERI / 'pilot.json', 'w') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    # sabitleri esleme.py'ye yaz
    p = ortam.BEYIN / 'esleme.py'
    s = p.read_text()
    s = re.sub(r'^R_LC10_HZ = None .*$', f"R_LC10_HZ = {secim['r_lc10_hz']}          # pilot.py (veri/pilot.json)", s, flags=re.M)
    s = re.sub(r'^P9_DRIVE_HZ = None .*$', f"P9_DRIVE_HZ = {secim['p9_hz']}        # pilot.py (veri/pilot.json); 0 = kapalı", s, flags=re.M)
    s = re.sub(r'^P_SCALE = None .*$', f"P_SCALE = {p_scale}            # pilot.py (veri/pilot.json): seçilen koşulda power medyanı", s, flags=re.M)
    p.write_text(s)
    print('SEÇİM', out['selected'])


if __name__ == '__main__':
    main()
