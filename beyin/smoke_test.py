"""Duman testi: makalenin şeker-GRN -> MN9 sonucunu v783 verisiyle yeniden üret.

Shiu et al. (Nature 2024) deposundaki ORİJİNAL run_exp fonksiyonu, hiç
değiştirilmeden çalıştırılır (sabit commit, bkz. ortam.SHIU_COMMIT).
Uyarılan nöronlar: makaledeki 21 sağ-yarım-küre şeker GRN'si, v783 kimlikleriyle
(20'si v630 ile aynı kök kimliği taşıyor; 1 tanesi v783'te değişmiş:
720575940620900446 (v630) -> 720575940639259967 (v783), eonsystemspbc/fly-brain
deposundaki v783 listesinden; v783 açıklama dosyasında LB3c 'sugar' olarak doğrulandı).

Kullanım:  .venv/bin/python -I smoke_test.py [--n-proc 3]
Çıktı:     sonuclar/smoke/*.parquet  ve  ../veri/smoke_test_seker_mn9.json
"""
import sys
import json
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ortam  # noqa: E402

ortam.derleyici_ayarla()

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from brian2 import Hz  # noqa: E402

SUGAR_V783 = [
    720575940624963786, 720575940630233916, 720575940637568838, 720575940638202345,
    720575940617000768, 720575940630797113, 720575940632889389, 720575940621754367,
    720575940621502051, 720575940640649691, 720575940639332736, 720575940616885538,
    720575940639198653, 720575940639259967, 720575940617937543, 720575940632425919,
    720575940633143833, 720575940612670570, 720575940628853239, 720575940629176663,
    720575940611875570,
]
MN9 = 720575940660219265  # Shiu et al. örnek defteri; v630 ve v783'te aynı kök kimliği


def mn9_hiz(df, n_run):
    m = df[df.flywire_id == MN9]
    c = m.groupby('trial').size().reindex(range(n_run), fill_value=0).values
    return c  # 1 s deneme -> sayı = Hz


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n-proc', type=int, default=3)
    ap.add_argument('--n-run', type=int, default=30)
    a = ap.parse_args()

    shiu = ortam.shiu_model_yukle()
    comp = pd.read_csv(ortam.PATH_COMP, index_col=0)
    ann = pd.read_csv(ortam.ANNOT, sep='\t', low_memory=False, usecols=['root_id', 'cell_type', 'cell_sub_class', 'side'])
    eksik = [s for s in SUGAR_V783 + [MN9] if s not in comp.index]
    assert not eksik, f'v783 dosyasında olmayan kimlik: {eksik}'
    assert set(SUGAR_V783) <= set(ann.root_id), 'şeker GRN kimlikleri v783 açıklamasında yok'

    res_dir = ortam.BEYIN / 'sonuclar' / 'smoke'
    res_dir.mkdir(parents=True, exist_ok=True)
    kosullar = [
        ('sugarR_783_100Hz', 100),   # örnek defterde açıkça 100 Hz ile koşulan deney
        ('sugarR_783_default', None),  # model.py varsayılanı (r_poi = 150 Hz)
        ('kontrol_783_uyarimsiz', 0),  # hiç uyarım yok: MN9 sessiz kalmalı
    ]
    out = {
        'what': 'Shiu et al. 2024 sugar GRN -> MN9 smoke test on FlyWire v783',
        'code': f'github.com/philshiu/Drosophila_brain_model @ {ortam.SHIU_COMMIT} (model.run_exp, unmodified)',
        'data': {'completeness': 'Completeness_783.csv', 'connectivity': 'Connectivity_783.parquet'},
        'sugar_grn_v783': [str(s) for s in SUGAR_V783],
        'mn9_root_id': str(MN9),
        'n_run': a.n_run, 't_run_s': 1.0,
        'conditions': {},
    }
    for ad, hz in kosullar:
        p = dict(shiu.default_params)
        p['n_run'] = a.n_run
        if hz is not None:
            p['r_poi'] = hz * Hz
        t0 = time.time()
        if hz == 0:
            # uyarımsız kontrol: aynı ağ, Poisson hızı 0
            shiu.run_exp(exp_name=ad, neu_exc=SUGAR_V783, path_res=res_dir, path_comp=ortam.PATH_COMP,
                         path_con=ortam.PATH_CON, params=p, n_proc=a.n_proc)
        else:
            shiu.run_exp(exp_name=ad, neu_exc=SUGAR_V783, path_res=res_dir, path_comp=ortam.PATH_COMP,
                         path_con=ortam.PATH_CON, params=p, n_proc=a.n_proc)
        wall = time.time() - t0
        df = pd.read_parquet(res_dir / f'{ad}.parquet')
        c = mn9_hiz(df, a.n_run)
        out['conditions'][ad] = {
            'r_poi_hz': float(p['r_poi'] / Hz),
            'mn9_rate_hz_mean': float(c.mean()), 'mn9_rate_hz_sd': float(c.std(ddof=1)) if a.n_run > 1 else 0.0,
            'mn9_rate_per_trial': c.tolist(),
            'active_neurons': int(df.flywire_id.nunique()), 'total_spikes': int(len(df)),
            'wall_s_this_run': round(wall, 1),
        }
        print(ad, out['conditions'][ad]['mn9_rate_hz_mean'], flush=True)

    # Depodaki yayımlanmış örnek sonuçlar (v630 verisi) ile karşılaştırma
    ref = {}
    for ad, f in [('sugarR_630_repo_100Hz', 'sugarR_100Hz.parquet'), ('sugarR_630_repo_default', 'sugarR.parquet')]:
        d = pd.read_parquet(ortam.SHIU_REPO / 'results' / 'example' / f)
        c = mn9_hiz(d, 30)
        ref[ad] = {'mn9_rate_hz_mean': float(c.mean()), 'mn9_rate_hz_sd': float(c.std(ddof=1)),
                   'note': 'published example output in the repo, FlyWire v630; MN9 has the same root id in v630 and v783'}
    out['reference_repo_results_v630'] = ref
    v = out['conditions']['sugarR_783_100Hz']['mn9_rate_hz_mean']
    r = ref['sugarR_630_repo_100Hz']['mn9_rate_hz_mean']
    k = out['conditions']['kontrol_783_uyarimsiz']['mn9_rate_hz_mean']
    out['pass'] = bool(v > 20 and k == 0 and abs(v - r) < 0.35 * r)
    out['verdict'] = (f'MN9 {v:.1f} Hz with sugar GRNs at 100 Hz (v783) vs {r:.1f} Hz in the repo example (v630); '
                      f'{k:.1f} Hz without stimulation.')
    (ortam.VERI).mkdir(exist_ok=True)
    with open(ortam.VERI / 'smoke_test_seker_mn9.json', 'w') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(out['verdict'], 'PASS' if out['pass'] else 'FAIL')


if __name__ == '__main__':
    main()
