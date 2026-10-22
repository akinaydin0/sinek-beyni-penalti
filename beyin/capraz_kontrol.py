"""Çapraz kontrol: hızlı sarmalayıcı (beyin_model.py) orijinal Shiu koduyla aynı sonucu veriyor mu?

Aynı uyarım (21 şeker GRN'si, 100 Hz ve 200 Hz, 30 x 1 s) hızlı sarmalayıcıyla koşulur;
MN9 hızı, orijinal run_exp çıktısıyla (smoke_test.py) ve depodaki yayımlanmış örnek
sonuçlarla karşılaştırılır. Ayrıca aynı tohumun aynı spike'ları verdiği (determinizm)
denetlenir. Tohumlar 5_000_001'den başlar.

Kullanım: .venv/bin/python -I capraz_kontrol.py  ->  ../veri/capraz_kontrol.json
"""
import sys
import json
import hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ortam  # noqa: E402
import numpy as np  # noqa: E402
from beyin_model import SinekBeyni  # noqa: E402
from smoke_test import SUGAR_V783, MN9  # noqa: E402


def main():
    b = SinekBeyni(SUGAR_V783)
    mn9 = b.f2i[MN9]
    out = {'what': 'fast wrapper vs original Shiu run_exp, sugar GRN -> MN9, v783', 'conditions': {}}
    seed = 5_000_001
    for hz in (100, 200):
        r, act, sure = [], set(), []
        for _ in range(30):
            i, t, d = b.deneme({s: hz for s in SUGAR_V783}, seed)
            seed += 1
            r.append(int((i == mn9).sum()))
            act |= set(np.unique(i).tolist())
            sure.append(d)
        out['conditions'][f'wrapper_{hz}Hz'] = {'mn9_rate_hz_mean': float(np.mean(r)), 'mn9_rate_hz_sd': float(np.std(r, ddof=1)),
                                                'active_neurons_union': len(act), 'trial_s_mean': float(np.mean(sure[1:]))}
        print(hz, out['conditions'][f'wrapper_{hz}Hz'], flush=True)
    # determinizm
    h = []
    for _ in range(2):
        i, t, _d = b.deneme({s: 100 for s in SUGAR_V783}, 4242)
        h.append(hashlib.sha256(i.tobytes() + t.tobytes()).hexdigest())
    out['determinism_same_seed_same_spikes'] = h[0] == h[1]
    out['determinism_sha256'] = h[0]
    sm = ortam.VERI / 'smoke_test_seker_mn9.json'
    if sm.exists():
        s = json.loads(sm.read_text())
        out['original_run_exp_100Hz'] = s['conditions']['sugarR_783_100Hz']['mn9_rate_hz_mean']
        out['repo_reference_v630'] = {k: v['mn9_rate_hz_mean'] for k, v in s['reference_repo_results_v630'].items()}
    (ortam.VERI / 'capraz_kontrol.json').write_text(json.dumps(out, indent=2) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
