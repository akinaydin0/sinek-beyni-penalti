"""Penaltı kararları: her şut için bir adet 1 s'lik sinek beyni denemesi.

  python -I kick.py --n 5 --seed-base S --keeper-x X --out ../veri/prova_beyin_kararlari.json
  (--keeper-x tek değer ya da şut başına virgüllü liste olabilir)

- Şut n'nin tohumu: trial_seed = S + n (n = 1..N). Tohum ve tüm sayılar JSON'a yazılır;
  aynı tohum aynı spike'ları verir.
- Okuma/eşleme DONMUŞ esleme.py'den gelir; özet DONDURMA.json ile tutmazsa betik çalışmaz.
- Çıktı adı 'prova' ile başlıyorsa PROVA koşusudur ve öyle işaretlenir.
  Başka bir ada (ör. beyin_kararlari.json) yazmak için --final gerekir; final dosya
  zaten varsa üzerine YAZILMAZ (yeniden deneme yok kuralı).
- Her şutun spike'ları npz olarak kaydedilir: veri/beyin_raster/<çıktı adı>/kick_NN.npz
"""
import sys
import json
import time
import hashlib
import argparse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ortam  # noqa: E402
import numpy as np  # noqa: E402
import esleme  # noqa: E402
import dondur  # noqa: E402

MODEL = 'Shiu et al. 2024 LIF (Brian2), FlyWire v783'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description='Sinek beyni penaltı kararları')
    ap.add_argument('--n', type=int, default=5)
    ap.add_argument('--seed-base', type=int, required=True)
    ap.add_argument('--keeper-x', default='0.0',
                    help='kalecinin x konumu (m), SOZLESME koordinatı; tek değer ya da şut başına virgüllü liste (ör. --keeper-x=0,0.2,-0.1,0,0; eksiyle başlıyorsa = kullan)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--final', action='store_true', help='prova OLMAYAN gerçek koşu (yalnızca taahhütten sonra)')
    ap.add_argument('--commit-sha256', default=None, help='story\'de paylaşılan taahhüt özeti (final için kayda geçer)')
    a = ap.parse_args()
    kx_list = [float(x) for x in str(a.keeper_x).split(',')]
    if len(kx_list) == 1:
        kx_list = kx_list * a.n
    if len(kx_list) != a.n:
        sys.exit(f'--keeper-x: {len(kx_list)} değer verildi, --n {a.n}')

    out = Path(a.out).expanduser().resolve()
    prova = out.name.lower().startswith('prova')
    if not prova and not a.final:
        sys.exit(f'{out.name}: prova olmayan bir çıktı için --final gerekir. Kurulum aşamasında yalnızca prova koşulur.')
    if not prova and out.exists():
        sys.exit(f'{out} zaten var. Her şut bir kez atılır; final koşu tekrarlanmaz.')
    ok, kayit = dondur.kontrol()
    if not ok:
        sys.exit('esleme.py / ids.json donmuş özetle (DONDURMA.json) uyuşmuyor. Koşu yapılmadı.')
    kal_p = ortam.VERI / 'kalibrasyon.json'
    if not kal_p.exists():
        sys.exit('veri/kalibrasyon.json yok: önce kalibrasyon.py çalıştırılmalı.')
    kal = json.loads(kal_p.read_text())
    if kal.get('readout_sha256') != kayit['readout_sha256']:
        sys.exit('kalibrasyon.json başka bir okuma özetiyle yapılmış. Koşu yapılmadı.')

    ids = json.loads((ortam.BEYIN / 'ids.json').read_text())
    from beyin_model import SinekBeyni
    beyin = SinekBeyni(esleme.tum_girdi_kimlikleri(ids))
    grup_ids = {k: [int(r) for r in ids['groups'][k]['root_ids_v783']] for k in esleme.COUNT_KEYS}
    ro_labels = list(esleme.COUNT_KEYS)
    ro_idx = np.array([beyin.f2i[grup_ids[k][0]] for k in ro_labels])
    steer_idx = np.array([beyin.f2i[x] for k in esleme.STEER_NEURONS for x in grup_ids[k]])

    raster_dir = ortam.VERI / 'beyin_raster' / out.stem
    raster_dir.mkdir(parents=True, exist_ok=True)
    kicks = []
    t_all = time.time()
    for n in range(1, a.n + 1):
        seed = a.seed_base + n
        kx = kx_list[n - 1]
        rates = esleme.girdi_hizlari(kx, ids)
        i, t, dur = beyin.deneme(rates, seed, esleme.T_TRIAL_S)
        c = np.bincount(i, minlength=len(beyin.root_ids))
        counts = {k: int(sum(c[beyin.f2i[x]] for x in v)) for k, v in grup_ids.items()}
        steer, power, rt, lt = esleme.oku(counts)
        ax, ay, v = esleme.esle(steer, power)
        dms = esleme.karar_ms(t[np.isin(i, steer_idx)].tolist())
        # raster: okuma nöronları + tüm beyin
        m = np.isin(i, ro_idx)
        lab_of = {int(ix): k for k, ix in zip(ro_labels, ro_idx)}
        ro_lab = np.array([ro_labels.index(lab_of[int(x)]) for x in i[m]], dtype=np.int16)
        npz = raster_dir / f'kick_{n:02d}.npz'
        all_i = i.astype(np.int32)
        all_t = t.astype(np.float32)
        np.savez_compressed(
            npz, readout_labels=np.array(ro_labels), readout_root_ids=np.array([grup_ids[k][0] for k in ro_labels], dtype=np.int64),
            ro_label_idx=ro_lab, ro_t=t[m].astype(np.float64),
            all_i=all_i, all_t=all_t, all_root=beyin.root_ids[i].astype(np.int64),
            t_run_s=np.float64(esleme.T_TRIAL_S), dt_s=np.float64(1e-4), trial_seed=np.int64(seed),
            keeper_x=np.float64(kx), steer=np.float64(steer), decision_ms=np.int64(dms),
            rturn_labels=np.array(esleme.RTURN), lturn_labels=np.array(esleme.LTURN), prova=np.bool_(prova))
        spike_sha = hashlib.sha256(all_i.tobytes() + all_t.tobytes()).hexdigest()
        k = {'n': n, 'trial_seed': seed, 'scene': {'keeper_x': kx},
             'counts': counts, 'steer': round(steer, 4), 'power_spikes': int(power),
             'aim': {'x': ax, 'y': ay}, 'speed_mps': v, 'decision_ms': dms,
             'Rturn': rt, 'Lturn': lt, 'brain_spikes': int(len(i)), 'runtime_s': round(dur, 2),
             'raster_npz': str(npz.relative_to(ortam.PROJE)), 'spikes_sha256': spike_sha}
        kicks.append(k)
        print(f"şut {n}: seed {seed}  Rturn {rt}  Lturn {lt}  steer {steer:+.3f}  power {power}  "
              f"aim ({ax:+.2f}, {ay:.2f})  {v} m/s  karar {dms} ms  [{dur:.1f} s]", flush=True)
    wall = time.time() - t_all

    cal = {ad: {kk: vv for kk, vv in kal['summary'][ad].items()} for ad in ['keeper_left', 'keeper_right', 'centre']}
    cal['reacts_to_keeper_side'] = kal['test']['reacts_to_keeper_side']
    cal['flips_sign'] = kal['test']['flips_sign']
    cal['direction'] = kal['test']['direction']
    cal['welch_p'] = kal['test']['welch_p']
    cal['source'] = 'veri/kalibrasyon.json'
    res = {
        'prova': prova,
        'status': ('PROVA (dry run, NOT the final kicks; run before any commitment)' if prova
                   else 'FINAL (run after the published commitment)'),
        'model': MODEL,
        'readout_frozen_at': kayit['readout_frozen_at'], 'readout_sha256': kayit['readout_sha256'],
        'readout': esleme.READOUT,
        'calibration': cal,
        'seed_base': a.seed_base, 'seed_rule': 'trial_seed = seed_base + n',
        'commit_sha256': a.commit_sha256,
        'scene_input': [{'n': k['n'], 'keeper_x': k['scene']['keeper_x'], 'bias_b': esleme.sahne_bias(k['scene']['keeper_x']),
                         'lc10_rate_hz': {'L': esleme.R_LC10_HZ * (1 - esleme.K_BIAS * esleme.sahne_bias(k['scene']['keeper_x'])),
                                          'R': esleme.R_LC10_HZ * (1 + esleme.K_BIAS * esleme.sahne_bias(k['scene']['keeper_x']))},
                         'p9_drive_hz': esleme.P9_DRIVE_HZ} for k in kicks],
        'constants': esleme.sabitler(),
        'kicks': kicks,
        'runtime': {'per_trial_s': [k['runtime_s'] for k in kicks], 'network_build_s': round(beyin.build_s, 1),
                    'total_wall_s': round(wall, 1), 'machine': 'Apple M2 Pro, 16 GB, Brian2 runtime (Cython)'},
        'code_sha256': {f: sha(ortam.BEYIN / f) for f in ['kick.py', 'beyin_model.py', 'ortam.py', 'esleme.py', 'dondur.py']},
        'data_sha256': {'Completeness_783.csv': ids['model_data']['Completeness_783.csv_sha256'],
                        'Connectivity_783.parquet': ids['model_data']['Connectivity_783.parquet_sha256'],
                        'shiu_model.py': sha(ortam.SHIU_REPO / 'model.py'), 'shiu_commit': ortam.SHIU_COMMIT},
        'run_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False) + '\n')
    print(f'yazıldı: {out}  ({"PROVA" if prova else "FINAL"})')


if __name__ == '__main__':
    main()
