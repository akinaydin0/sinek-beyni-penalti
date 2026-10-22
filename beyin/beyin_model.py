"""Shiu et al. (Nature 2024) LIF tüm-beyin modelinin hızlı sarmalayıcısı.

Model AYNI: denklemler, sabitler (v_0, v_th, t_mbr, tau, t_rfc, t_dly, w_syn, f_poi)
ve bağlantı ağırlıkları, Shiu deposundaki model.py'den (sabit commit) okunur ve
create_model() ile birebir aynı şekilde kurulur. Tek fark çalışma biçimi:

* Orijinal kod her denemede ağı baştan kurar (~40 s). Burada ağ bir kez kurulur,
  `Network.store()` ile saklanır, her deneme `restore()` ile sıfırdan başlar.
* Orijinal `PoissonInput(N=1)` yerine tek bir `PoissonGroup` + bire bir sinaps
  kullanılır: her Poisson olayı hedef nöronun v'sine aynı ağırlığı
  (w_syn * f_poi = 68.75 mV) aynı zaman adımında ('synapses' dilimi) ekler.
  Uyarılan nöronların refrakter süresi orijinaldeki gibi 0 yapılır.
  Böylece uyarım hızları her denemede yeniden derleme olmadan değişebilir.
* Rastgelelik yalnızca Poisson girdisinden gelir; model geri kalanıyla
  deterministiktir. Her deneme `brian2.seed(trial_seed)` ile tohumlanır, yani
  aynı tohum aynı spike'ları verir (bkz. determinizm testi, README).
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ortam  # noqa: E402

ortam.derleyici_ayarla()

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from brian2 import (NeuronGroup, Synapses, PoissonGroup, SpikeMonitor, Network,  # noqa: E402
                    Hz, ms, second, prefs, seed as b2_seed, defaultclock)
import brian2  # noqa: E402

prefs.codegen.target = 'cython'
brian2.BrianLogger.suppress_name('resolution_conflict')


class SinekBeyni:
    def __init__(self, input_root_ids, verbose=True):
        t0 = time.time()
        self.shiu = ortam.shiu_model_yukle()
        P = dict(self.shiu.default_params)
        self.P = P
        comp = pd.read_csv(ortam.PATH_COMP, index_col=0)
        con = pd.read_parquet(ortam.PATH_CON, columns=['Presynaptic_Index', 'Postsynaptic_Index',
                                                        'Excitatory x Connectivity'])
        self.root_ids = np.asarray(comp.index, dtype=np.int64)
        self.f2i = {int(r): i for i, r in enumerate(self.root_ids)}
        N = len(comp)

        neu = NeuronGroup(N=N, model=P['eqs'], method='linear', threshold=P['eq_th'],
                          reset=P['eq_rst'], refractory='rfc', name='default_neurons', namespace=P)
        neu.v = P['v_0']
        neu.g = 0
        neu.rfc = P['t_rfc']
        syn = Synapses(neu, neu, 'w : volt', on_pre='g += w', delay=P['t_dly'], name='default_synapses')
        syn.connect(i=con['Presynaptic_Index'].values, j=con['Postsynaptic_Index'].values)
        syn.w = con['Excitatory x Connectivity'].values * P['w_syn']
        del con

        self.input_root_ids = [int(r) for r in input_root_ids]
        self.in_idx = np.array([self.f2i[r] for r in self.input_root_ids], dtype=np.int64)
        assert len(set(self.in_idx.tolist())) == len(self.in_idx), 'girdi listesinde tekrar var'
        pg = PoissonGroup(len(self.in_idx), rates=np.zeros(len(self.in_idx)) * Hz, name='girdi')
        ps = Synapses(pg, neu, on_pre='v += w_poi', namespace={'w_poi': P['w_syn'] * P['f_poi']},
                      name='girdi_sinaps')
        ps.connect(i=np.arange(len(self.in_idx)), j=self.in_idx)
        spk = SpikeMonitor(neu, name='spikes')
        self.neu, self.syn, self.pg, self.ps, self.spk = neu, syn, pg, ps, spk
        self.net = Network(neu, syn, pg, ps, spk)
        self.net.store('bos')
        self.build_s = time.time() - t0
        if verbose:
            print(f'[beyin] ağ kuruldu: {N} nöron, {len(syn)} bağlantı, {self.build_s:.1f} s', flush=True)

    def deneme(self, rates_hz, trial_seed, t_run_s=1.0):
        """Bir deneme koş. rates_hz: {root_id: Hz}. Dönen: (spike_i, spike_t_s, sure_s)."""
        t0 = time.time()
        self.net.restore('bos')
        r = np.zeros(len(self.in_idx))
        pos = {rid: k for k, rid in enumerate(self.input_root_ids)}
        for rid, hz in rates_hz.items():
            r[pos[int(rid)]] = float(hz)
        rfc = np.full(len(self.root_ids), float(self.P['t_rfc'] / ms))
        rfc[self.in_idx[r > 0]] = 0.0  # Shiu: Poisson hedeflerinde refrakter süre yok
        self.neu.rfc = rfc * ms
        self.pg.rates = r * Hz
        b2_seed(int(trial_seed))
        self.net.run(t_run_s * second)
        i = np.asarray(self.spk.i[:], dtype=np.int64)
        t = np.asarray(self.spk.t[:] / second, dtype=np.float64)
        return i, t, time.time() - t0

    def sayilar(self, spike_i, root_ids):
        idx = np.array([self.f2i[int(r)] for r in root_ids])
        c = np.bincount(spike_i, minlength=len(self.root_ids))
        return {int(r): int(c[k]) for r, k in zip(root_ids, idx)}
