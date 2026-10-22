#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
olasilik.py - [tur3 2026-10-22] TAHMİN, SONUÇ DEĞİL: yeni kurallarla 5 şutluk seride kim kazanır?

Senaryo için bir beklenti hesabı. Gerçek seri tek seferliktir ve bu tahminden farklı çıkabilir.
Hiçbir taahhüdün parçası değildir; final koşuda kullanılmaz.

Girdi:
  - Donmuş sinek beyninin GERÇEK nişan dağılımı: kayma taramaları (beyin denemeleri; her biri bir
    (aim_x, aim_y, hız) üretir). Kalecinin x'i ±0,30, ±0,35, ±0,40, ±0,45, ±0,50 m.
  - Yeni motor kuralları: config_sablon.json (Hunter menzil-içi model AÇIK, merkeze çekilme 0).
Her şut (i.i.d., gerçek akıştaki gibi):
  1) kayma: büyüklük U[0,30; 0,50], yön %50/%50, mm'ye yuvarlanır (keeper_shift kuralının dağılımı);
  2) beynin cevabı: kaymanın iki yanındaki tarama noktasından biri (yakınlıkla orantılı olasılıkla),
     o noktanın denemelerinden biri rastgele (beyin her x için ayrı koşturulmadı: yaklaşık);
  3) kaleci: draw_plan(cfg, rastgele 62 bit seed, n) = gerçek seed dağılımı (yön Bar-Eli, çıkış Hunter);
  4) motor: simulate_kick(..., keeper_x = kayma).
Seri: 5 şut; SİNEK = gol sayısı; gol dışı her sonuç (kurtarış, direk, aut, üstten aut) ÇAKIR'a.

  python3.12 -I olasilik.py --tarama ../veri/kalibrasyon_kayma_tarama.json ../veri/kalibrasyon_kayma_tarama_tur3.json \
      --config config_sablon.json --seri 20000 --cikti ../veri/olasilik_tahmini.json
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import random
import sys
import time
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import penalty_model as pm  # noqa: E402

GRID = [0.30, 0.35, 0.40, 0.45, 0.50]
_CFG = _KP = None


def _init(cfg_path):
    global _CFG, _KP
    _CFG = pm.load_json(cfg_path)
    _KP = pm.keeper_params(_CFG)


def _one(task):
    x, ax, ay, v, kseed, n = task
    plan = pm.draw_plan(_CFG, kseed, n)
    r = pm.simulate_kick(_CFG, _KP, {"x": ax, "y": ay}, v, plan, x)
    c = r["contact"]
    return (r["outcome"], c is not None, bool(c and c.get("beaten")), plan["dive_dir"])


def load_pools(paths):
    pools = {}
    srcs = {}
    for p in paths:
        d = pm.load_json(p)
        for key, rows in d["trials"].items():
            x = round(float(key), 2)
            if round(abs(x), 2) not in GRID:
                continue
            for r in rows:
                pools.setdefault(x, []).append((float(r["aim_x"]), float(r["aim_y"]), float(r["speed"]), int(r["seed"])))
            srcs.setdefault(x, []).append(f"{os.path.basename(p)}: {len(rows)}")
    for x in pools:  # tekrar eden tohum olmasın
        assert len({t[3] for t in pools[x]}) == len(pools[x]), x
    return pools, srcs


def binom_ge(n, p, k):
    return sum(math.comb(n, j) * p ** j * (1 - p) ** (n - j) for j in range(k, n + 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tarama", nargs="+", required=True)
    ap.add_argument("--config", default=os.path.join(HERE, "config_sablon.json"))
    ap.add_argument("--seri", type=int, default=20000)
    ap.add_argument("--tohum", type=int, default=20261022)
    ap.add_argument("--is", dest="isci", type=int, default=8)
    ap.add_argument("--bootstrap", type=int, default=2000)
    ap.add_argument("--cikti", required=True)
    a = ap.parse_args()
    cfg = pm.load_json(a.config)
    pools, srcs = load_pools(a.tarama)
    for s in (-1, 1):
        for g in GRID:
            assert round(s * g, 2) in pools, f"tarama noktası eksik: {s * g}"
    rng = random.Random(a.tohum)
    tasks, meta = [], []
    ks = cfg["keeper_shift"]
    for s in range(a.seri):
        for n in range(1, 6):
            mag = ks["min_m"] + (ks["max_m"] - ks["min_m"]) * rng.random()
            sign = 1.0 if rng.random() < ks["p_positive"] else -1.0
            x = round(sign * mag, ks["round_decimals"])
            m = abs(x)
            i_lo = min(int((m - 0.30) / 0.05 + 1e-9), len(GRID) - 2)
            g_lo, g_hi = GRID[i_lo], GRID[i_lo + 1]
            w = (m - g_lo) / (g_hi - g_lo)
            g = g_hi if rng.random() < w else g_lo
            key = round(sign * g, 2)
            j = rng.randrange(len(pools[key]))
            ax, ay, v, bseed = pools[key][j]
            kseed = rng.getrandbits(62)
            tasks.append((x, ax, ay, v, kseed, n))
            meta.append((s, key, j))
    t0 = time.time()
    with Pool(a.isci, initializer=_init, initargs=(a.config,)) as pool:
        res = pool.map(_one, tasks, chunksize=500)
    wall = time.time() - t0

    N = len(res)
    cnt = {}
    cnt_off = {}
    goals = [0] * a.seri
    goals_off = [0] * a.seri
    contacts = beaten = 0
    side = {"sol": {"n": 0, "goal": 0}, "sag": {"n": 0, "goal": 0}}  # kalecinin yeri: şutörün solu (x<0) / sağı
    aim_same_side = 0
    per_trial = {}
    for (o, has_c, bt, dive), (x, ax, ay, v, kseed, n), (s, key, j) in zip(res, tasks, meta):
        cnt[o] = cnt.get(o, 0) + 1
        o_off = "save" if has_c else o  # Hunter kapalı olsaydı: her temas kurtarış
        cnt_off[o_off] = cnt_off.get(o_off, 0) + 1
        goals[s] += o == "goal"
        goals_off[s] += o_off == "goal"
        contacts += has_c
        beaten += bt
        sd = "sol" if x < 0 else "sag"
        side[sd]["n"] += 1
        side[sd]["goal"] += o == "goal"
        aim_same_side += (ax < 0) == (x < 0)
        pt = per_trial.setdefault((key, j), [0, 0])
        pt[0] += 1
        pt[1] += o == "goal"

    def dist(gl):
        d = [0] * 6
        for g in gl:
            d[g] += 1
        return [round(c / len(gl), 4) for c in d]

    def rates(c):
        on = c.get("goal", 0) + c.get("save", 0)
        return {"gol": round(c.get("goal", 0) / N, 4), "kurtaris": round(c.get("save", 0) / N, 4),
                "direk": round(c.get("post", 0) / N, 4), "aut_wide": round(c.get("wide", 0) / N, 4),
                "ust_aut_over": round(c.get("over", 0) / N, 4),
                "aut_toplam_wide_over": round((c.get("wide", 0) + c.get("over", 0)) / N, 4),
                "isabetli_sut_orani": round(on / N, 4),
                "isabetli_sutlarda_kurtaris": round(c.get("save", 0) / on, 4) if on else None}

    d_on, d_off = dist(goals), dist(goals_off)
    p_goal = cnt.get("goal", 0) / N
    # belirsizlik: beyin denemeleri sınırlı (nokta başına 20-35). Denemeler üzerinde bootstrap
    # (her denemenin gol oranı simülasyondan; havuzlar yeniden örneklenir, kullanım ağırlıkları sabit).
    brng = random.Random(a.tohum + 1)
    usage = {}
    for (key, j), (nk, ng) in per_trial.items():
        usage.setdefault(key, {})[j] = (nk, ng)
    key_w = {key: sum(nk for nk, _ in d.values()) / N for key, d in usage.items()}
    boots = []
    for _ in range(a.bootstrap):
        p = 0.0
        for key, d in usage.items():
            L = len(pools[key])
            rates_k = [(d[j][1] / d[j][0]) if j in d else None for j in range(L)]
            have = [r for r in rates_k if r is not None]
            samp = [have[brng.randrange(len(have))] for _ in range(L)]
            p += key_w[key] * sum(samp) / L
        boots.append(binom_ge(5, p, 3))
    boots.sort()
    ci = [round(boots[int(0.025 * len(boots))], 3), round(boots[int(0.975 * len(boots)) - 1], 3)]

    out = {
        "UYARI": "TAHMİN (senaryo için), SONUÇ DEĞİL. Gerçek seri tek seferlik; beacon ve tohumlar açıklanınca belli olur.",
        "ne": "[tur3 2026-10-22] yeni kurallarla (Hunter açık, kaleci ±30-50 cm kayık, beyin gerçek yeri görüyor) "
              "5 şutluk serinin Monte Carlo tahmini",
        "olusturuldu_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "girdi": {
            "config": os.path.basename(a.config), "config_sha256": pm.sha256_hex(pm.canonical_json(cfg)),
            "motor_sha256": pm.engine_sha256(),
            "beyin_taramalari": [os.path.basename(p) for p in a.tarama],
            "beyin_deneme_sayisi": {str(k): len(v) for k, v in sorted(pools.items())},
            "beyin_kaynaklari": {str(k): v for k, v in sorted(srcs.items())},
            "seri": a.seri, "sut": N, "mc_tohum": a.tohum, "sure_s": round(wall, 1),
        },
        "yontem": ("Her şut: kayma U[0,30;0,50]·(±1) -> beynin cevabı komşu tarama noktasından (yakınlık ağırlıklı) "
                   "rastgele bir gerçek deneme -> kaleci planı rastgele seed'den (draw_plan) -> simulate_kick(keeper_x = kayma). "
                   "Şutlar bağımsız; seri gol sayısı Binom(5, p) ile de kontrol edildi."),
        "sonuc_hunter_acik": {
            "sinek_gol_dagilimi_0_5": d_on,
            "P_sinek_kazanir_en_az_3_gol": round(sum(d_on[3:]), 4),
            "P_cakir_kazanir": round(sum(d_on[:3]), 4),
            "P_sinek_kazanir_binom_kontrol": round(binom_ge(5, p_goal, 3), 4),
            "P_sinek_kazanir_95_guven_beyin_bootstrap": ci,
            "beklenen_sinek_golu": round(5 * p_goal, 3),
            "sut_basina": rates(cnt),
            "temas_orani": round(contacts / N, 4),
            "temas_olup_gol_hunter": round(beaten / N, 4),
            "kalecinin_yerine_gore_gol": {k: round(v["goal"] / v["n"], 4) for k, v in side.items()},
            "nisan_kalecinin_oldugu_tarafta": round(aim_same_side / N, 4),
        },
        "karsilastirma_hunter_kapali_ayni_cekilisler": {
            "sinek_gol_dagilimi_0_5": d_off,
            "P_sinek_kazanir_en_az_3_gol": round(sum(d_off[3:]), 4),
            "sut_basina": rates(cnt_off),
        },
        "sinirlar": [
            "Beyin her kayma değeri için ayrı koşturulmadı: 10 tarama noktası (nokta başına 20-35 deneme) arasında komşu nokta seçildi.",
            "Beyin taramalarının tohumları finaldeki tohumlar değil; finalde beyin yeni tohumlarla bir kez koşar.",
            "Kalecinin tepki, dalış, erişim sayıları FC reytinglerinden varsayımla türetildi (MODEL.md).",
            "Bootstrap aralığı yalnız beyin örnekleminin belirsizliğidir; motor modelinin hatası buna dahil değil.",
        ],
    }
    pm.write_json(a.cikti, out)
    print(json.dumps({k: out[k] for k in ("sonuc_hunter_acik", "karsilastirma_hunter_kapali_ayni_cekilisler")},
                     ensure_ascii=False, indent=1))
    print(f"yazıldı: {a.cikti}  ({N} şut, {wall:.0f} s)")


if __name__ == "__main__":
    main()
