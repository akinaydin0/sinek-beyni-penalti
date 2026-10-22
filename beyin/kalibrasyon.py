"""Kalibrasyon: kaleci solda / sağda / ortada, her sahne 30 x 1 s beyin denemesi.

Okuma ve eşleme DONMUŞ esleme.py'den gelir (DONDURMA.json ile doğrulanır).
Soru: sineğin steer'i kalecinin tarafıyla birlikte dönüyor mu?

Önceden yazılmış test (koşmadan önce):
- reacts_to_keeper_side: kaleci-sağ ve kaleci-sol sahnelerinin steer ortalamaları
  arasındaki fark Welch t-testinde p < 0.01 ise True.
- flips_sign: iki sahnenin ortalama steer'inin işareti farklıysa True.
- direction: kaleci sağdayken steer daha sağdaysa 'toward_keeper', değilse
  'away_from_keeper'.

Tohumlar: 1_000_001'den başlar, sahneler sırayla (sol, sağ, orta) dönüşümlü.
Kullanım: .venv/bin/python -I kalibrasyon.py [--n 30]   (grafik için: --sadece-ciz)
Çıktı: ../veri/kalibrasyon.json, ../cikti/kalibrasyon.png
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
from beyin_model import SinekBeyni  # noqa: E402

TOHUM0 = 1_000_001
SAHNELER = [('keeper_left', -esleme.CAL_KEEPER_X_M), ('keeper_right', esleme.CAL_KEEPER_X_M), ('centre', 0.0)]


def deneme_kaydi(beyin, grup_ids, keeper_x, seed, ids):
    rates = esleme.girdi_hizlari(keeper_x, ids)
    i, t, d = beyin.deneme(rates, seed, esleme.T_TRIAL_S)
    c = np.bincount(i, minlength=len(beyin.root_ids))
    counts = {k: int(sum(c[beyin.f2i[x]] for x in v)) for k, v in grup_ids.items()}
    steer, power, rt, lt = esleme.oku(counts)
    ax, ay, v = esleme.esle(steer, power)
    steer_idx = np.array([beyin.f2i[x] for k in esleme.STEER_NEURONS for x in grup_ids[k]])
    st = t[np.isin(i, steer_idx)]
    return {'trial_seed': seed, 'keeper_x': keeper_x, 'counts': counts, 'Rturn': rt, 'Lturn': lt,
            'steer': round(steer, 4), 'power_spikes': power, 'aim': {'x': ax, 'y': ay}, 'speed_mps': v,
            'decision_ms': esleme.karar_ms(st.tolist()), 'brain_spikes': int(len(i)),
            'runtime_s': round(d, 2)}, (i, t)


def ozet(rows):
    s = np.array([r['steer'] for r in rows])
    n = len(s)
    sem = s.std(ddof=1) / np.sqrt(n)
    out = {
        'n_trials': n,
        'steer_mean': round(float(s.mean()), 4), 'steer_sd': round(float(s.std(ddof=1)), 4),
        'steer_ci95': [round(float(s.mean() - 1.96 * sem), 4), round(float(s.mean() + 1.96 * sem), 4)],
        'frac_steer_right': round(float((s > 0).mean()), 3), 'frac_steer_left': round(float((s < 0).mean()), 3),
        'aim_x_mean_m': round(float(np.mean([r['aim']['x'] for r in rows])), 3),
        'power_mean': round(float(np.mean([r['power_spikes'] for r in rows])), 2),
        'speed_mean_mps': round(float(np.mean([r['speed_mps'] for r in rows])), 2),
        'aim_y_mean_m': round(float(np.mean([r['aim']['y'] for r in rows])), 3),
        'Rturn_mean': round(float(np.mean([r['Rturn'] for r in rows])), 2),
        'Lturn_mean': round(float(np.mean([r['Lturn'] for r in rows])), 2),
        'decision_ms_median': float(np.median([r['decision_ms'] for r in rows])),
        'counts_mean': {k: round(float(np.mean([r['counts'][k] for r in rows])), 2) for k in esleme.COUNT_KEYS},
    }
    return out


def ciz(res, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    SURF, T1, T2, GRID = '#1a1a19', '#f0efec', '#c3c2b7', '#3a3a37'
    COL = {'keeper_left': '#3987e5', 'keeper_right': '#d95926', 'centre': '#199e70'}
    ETK = {'keeper_left': 'Kaleci solda (x = -1.83 m)', 'keeper_right': 'Kaleci sağda (x = +1.83 m)',
           'centre': 'Kaleci ortada (x = 0)'}
    plt.rcParams.update({'font.family': 'Helvetica', 'font.size': 11, 'text.color': T1,
                         'axes.labelcolor': T2, 'xtick.color': T2, 'ytick.color': T2,
                         'axes.edgecolor': GRID, 'axes.facecolor': SURF, 'figure.facecolor': SURF})
    fig = plt.figure(figsize=(12, 7.6), dpi=150)
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1], width_ratios=[1, 1.25], hspace=0.45, wspace=0.32)

    # 1) steer dağılımı
    ax = fig.add_subplot(gs[:, 0])
    rng = np.random.default_rng(0)  # yalnızca noktaları yatayda dağıtmak için (veriyi etkilemez)
    for k, (ad, _) in enumerate(SAHNELER):
        s = np.array([r['steer'] for r in res['trials'][ad]])
        ax.scatter(s, k + rng.uniform(-0.18, 0.18, len(s)), s=22, color=COL[ad], alpha=0.8,
                   edgecolors=SURF, linewidths=0.8, zorder=3)
        o = res['summary'][ad]
        ax.plot(o['steer_ci95'], [k, k], color=T1, lw=2, zorder=4, solid_capstyle='round')
        ax.scatter([o['steer_mean']], [k], s=60, color=T1, zorder=5)
        xm = max(-0.8, min(0.8, o['steer_mean']))
        ax.text(xm, k - 0.3, f"ort. {o['steer_mean']:+.2f}", va='bottom', ha='center', color=T2, fontsize=10)
    ax.axvline(0, color=GRID, lw=1, zorder=1)
    ax.set_yticks(range(3), [ETK[a] for a, _ in SAHNELER])
    ax.set_ylim(-0.6, 2.6)
    ax.invert_yaxis()
    ax.set_xlim(-1, 1)
    ax.set_xlabel('steer  (- sola, + sağa)')
    ax.set_title('Sineğin dönüş kararı, 30 deneme / sahne', color=T1, loc='left', fontsize=12, pad=10)
    for sp in ['top', 'right']:
        ax.spines[sp].set_visible(False)
    ax.grid(axis='x', color=GRID, lw=0.6, zorder=0)

    # 2) sola / sağa döndüren nöronların toplam spike'ı (sahne başına ortalama)
    ax2 = fig.add_subplot(gs[0, 1])
    xs = np.arange(3)
    w = 0.34
    CL, CR = '#6f6e69', '#c3c2b7'
    for k, (ad, _) in enumerate(SAHNELER):
        o = res['summary'][ad]
        for dx, val, c in [(-w / 2 - 0.01, o['Lturn_mean'], CL), (w / 2 + 0.01, o['Rturn_mean'], CR)]:
            ax2.bar(k + dx, val, w, color=c, edgecolor=SURF, linewidth=1)
            ax2.text(k + dx, val + 2, f'{val:.0f}', ha='center', va='bottom', color=T2, fontsize=9.5)
    ax2.set_xticks(xs, ['Kaleci solda', 'Kaleci sağda', 'Kaleci ortada'])
    ax2.set_ylabel('spike / 1 s (ortalama)')
    ax2.set_ylim(0, max(res['summary'][a]['Lturn_mean'] for a, _ in SAHNELER) * 1.25)
    ax2.set_title('Sola döndüren (koyu) ve sağa döndüren (açık) 5 nöronun toplamı', color=T1, loc='left',
                  fontsize=12, pad=10)
    for sp in ['top', 'right']:
        ax2.spines[sp].set_visible(False)
    ax2.grid(axis='y', color=GRID, lw=0.6)
    ax2.set_axisbelow(True)

    # 3) nişan noktaları kale çerçevesinde
    ax3 = fig.add_subplot(gs[1, 1])
    ax3.plot([-3.66, -3.66, 3.66, 3.66], [0, 2.44, 2.44, 0], color=T2, lw=2.5, solid_capstyle='round')
    ax3.axhline(0, color=GRID, lw=1)
    for ad, _ in SAHNELER:
        xx = [r['aim']['x'] for r in res['trials'][ad]]
        yy = [r['aim']['y'] for r in res['trials'][ad]]
        ax3.scatter(xx, yy, s=24, color=COL[ad], alpha=0.85, edgecolors=SURF, linewidths=0.8, label=ETK[ad])
    for ad, x in SAHNELER[:2]:
        ax3.plot([x, x], [0, 1.91], color=COL[ad], lw=1, ls=(0, (2, 3)), alpha=0.9)
    ax3.set_xlim(-4.2, 4.2)
    ax3.set_ylim(-0.1, 2.8)
    ax3.set_aspect('equal')
    ax3.set_xlabel('x (m), şutörün bakışından')
    ax3.set_ylabel('y (m)')
    ax3.set_title('Eşlenen nişan noktaları (kesikli = kalecinin yeri)', color=T1, loc='left', fontsize=12, pad=10)
    for sp in ['top', 'right']:
        ax3.spines[sp].set_visible(False)
    leg = ax3.legend(loc='upper center', bbox_to_anchor=(0.5, -0.32), ncol=3, frameon=False, fontsize=9)
    for tx in leg.get_texts():
        tx.set_color(T2)
    t = res['test']
    fig.suptitle(f"Kalibrasyon (Shiu et al. 2024 LIF, FlyWire v783)  |  sağ - sol farkı {t['steer_diff_right_minus_left']:+.2f}, "
                 f"Welch p = {t['welch_p']:.2g}  |  yön: {'kaleciye doğru' if t['direction'] == 'toward_keeper' else 'kaleciden uzağa'}",
                 color=T1, fontsize=12.5, x=0.02, ha='left', y=0.985)
    fig.savefig(path, facecolor=SURF, bbox_inches='tight', pad_inches=0.3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=30)
    ap.add_argument('--sadece-ciz', action='store_true', help='simülasyon yok; var olan kalibrasyon.json\'dan grafiği yeniden çiz')
    a = ap.parse_args()
    if a.sadece_ciz:
        ciz(json.loads((ortam.VERI / 'kalibrasyon.json').read_text()), ortam.CIKTI / 'kalibrasyon.png')
        return
    ok, kayit = dondur.kontrol()
    if not ok:
        sys.exit('esleme.py/ids.json donmuş özetle uyuşmuyor: kalibrasyon yapılmadı.')
    ids = json.load(open(ortam.BEYIN / 'ids.json'))
    beyin = SinekBeyni(esleme.tum_girdi_kimlikleri(ids))
    grup_ids = {k: [int(r) for r in ids['groups'][k]['root_ids_v783']] for k in esleme.COUNT_KEYS}
    trials = {ad: [] for ad, _ in SAHNELER}
    seed = TOHUM0
    t0 = time.time()
    for n in range(a.n):
        for ad, kx in SAHNELER:
            row, _ = deneme_kaydi(beyin, grup_ids, kx, seed, ids)
            seed += 1
            trials[ad].append(row)
        print(f'{n + 1}/{a.n}', {ad: trials[ad][-1]['steer'] for ad, _ in SAHNELER}, flush=True)
    wall = time.time() - t0
    from scipy import stats
    sL = np.array([r['steer'] for r in trials['keeper_left']])
    sR = np.array([r['steer'] for r in trials['keeper_right']])
    w = stats.ttest_ind(sR, sL, equal_var=False)
    mw = stats.mannwhitneyu(sR, sL, alternative='two-sided')
    diff = float(sR.mean() - sL.mean())
    summ = {ad: ozet(trials[ad]) for ad, _ in SAHNELER}
    test = {
        'steer_diff_right_minus_left': round(diff, 4),
        'welch_t': round(float(w.statistic), 3), 'welch_p': float(w.pvalue),
        'mannwhitney_p': float(mw.pvalue),
        'reacts_to_keeper_side': bool(w.pvalue < 0.01),
        'flips_sign': bool(np.sign(sR.mean()) != np.sign(sL.mean())),
        'direction': 'toward_keeper' if diff > 0 else 'away_from_keeper',
        'rule': 'reacts = Welch p < 0.01 (keeper_right vs keeper_left steer); flips = mean signs differ; '
                'direction = toward_keeper if mean steer(right) > mean steer(left)',
    }
    rt = [r['runtime_s'] for ad in trials for r in trials[ad]]
    res = {
        'what': 'calibration of the frozen readout (keeper left / right / centre)',
        'prova': False, 'note': 'calibration only; these are not kicks',
        'model': 'Shiu et al. 2024 LIF (Brian2), FlyWire v783',
        'readout': esleme.READOUT, 'readout_sha256': kayit['readout_sha256'],
        'readout_frozen_at': kayit['readout_frozen_at'],
        'constants': esleme.sabitler(),
        'scenes': {ad: {'keeper_x': kx} for ad, kx in SAHNELER},
        'seeds': f'{TOHUM0}..{seed - 1} (interleaved left, right, centre)',
        'summary': summ, 'test': test,
        'runtime': {'per_trial_s_mean': round(float(np.mean(rt[1:])), 2), 'per_trial_s_max': round(float(max(rt)), 2),
                    'network_build_s': round(beyin.build_s, 1), 'total_wall_s': round(wall, 1),
                    'machine': 'Apple M2 Pro, 16 GB, Brian2 runtime (Cython), 1 process'},
        'code_sha256': {f: hashlib.sha256((ortam.BEYIN / f).read_bytes()).hexdigest()
                        for f in ['beyin_model.py', 'kalibrasyon.py', 'ortam.py']},
        'run_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'trials': trials,
    }
    ortam.VERI.mkdir(exist_ok=True)
    ortam.CIKTI.mkdir(exist_ok=True)
    with open(ortam.VERI / 'kalibrasyon.json', 'w') as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    ciz(res, ortam.CIKTI / 'kalibrasyon.png')
    print(json.dumps({'summary': {k: {kk: v[kk] for kk in ['steer_mean', 'steer_ci95', 'frac_steer_right', 'power_mean', 'Rturn_mean', 'Lturn_mean']} for k, v in summ.items()}, 'test': test, 'runtime': res['runtime']}, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
