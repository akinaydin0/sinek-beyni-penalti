#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kalibrasyon.py - modelin gerçek penaltı istatistiklerine ne kadar yakın olduğuna bakan PROVA kontrolü.
Sonuç üretmez; yalnızca kaleci modelinin makul olup olmadığını gösterir.

Kıyas (Bar-Eli ve ark. 2007, Tablo 1-2, isabetli 286 penaltı, yönler KALECİNİN bakışıyla):
  doğru tarafa atlayış: sol/sol %29,6 , sağ/sağ %25,4
  ters tarafa atlayış: %0
  ortaya vuruş + atlayan kaleci: %9,8 (sol) , %3,2 (sağ)
  ortaya vuruş + ortada kalan kaleci: %60 (10 şut) ; yana vuruş + ortada kalan: %0
  genel kurtarış: %14,7   (Hunter 2018, 1278 penaltı: isabetli şutlarda %16,5)

Şut varsayımları: kale üçe bölünür (her biri 2,44 m), bölge içinde x düzgün; y = 0,15 + 2,15·u² (alçağa yatık:
penaltıların çoğu kalenin alt yarısına gider, Opta/Guardian 2023), 
hız N(23,5; 1,9) m/s [16-30] (Hunter 2018, iç taraf vuruşu). Çerçeve dışı/direk şutlar Bar-Eli gibi dışlanır.

  python3.12 -I kalibrasyon.py [--n 150] [--harita 60] [--set keeper_model.hand_speed_mps=3.0 ...]
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import penalty_model as pm  # noqa: E402

CAL_SEED = 20261022  # kalibrasyon tohumları; final şutlarda hiç kullanılmaz
ZONES = {"left": (1.22, 3.55), "centre": (-1.22, 1.22), "right": (-3.55, -1.22)}  # keeper's left = +x
BAR_ELI_JOINT = {  # Table 1 counts: kick zone -> keeper action
    "left": {"left": 54, "stay": 1, "right": 37},
    "centre": {"left": 41, "stay": 10, "right": 31},
    "right": {"left": 46, "stay": 7, "right": 59},
}
BAR_ELI_SAVE = {
    ("left", "left"): 29.6, ("left", "stay"): 0.0, ("left", "right"): 0.0,
    ("centre", "left"): 9.8, ("centre", "stay"): 60.0, ("centre", "right"): 3.2,
    ("right", "left"): 0.0, ("right", "stay"): 0.0, ("right", "right"): 25.4,
}


def apply_sets(cfg, sets):
    cfg = copy.deepcopy(cfg)
    for s in sets or []:
        key, val = s.split("=", 1)
        d = cfg
        parts = key.split(".")
        for p in parts[:-1]:
            d = d[p]
        d[parts[-1]] = json.loads(val)
    return cfg


def cell_rate(cfg, kp, zone, action, n, tag):
    nd = NormalDist()
    saves = shots = 0
    i = 0
    while shots < n and i < n * 3:
        u = lambda lab: pm.uniform(CAL_SEED, f"{tag}|{zone}|{action}|{i}|{lab}")  # noqa: E731
        lo, hi = ZONES[zone]
        x = lo + (hi - lo) * u("x")
        y = 0.15 + 2.15 * u("y") ** 2  # low-biased placement
        speed = pm.clamp(23.5 + 1.9 * nd.inv_cdf(u("v")), 16.0, 30.0)
        plan = pm.draw_plan(cfg, CAL_SEED * 7919 + i, i)
        plan["dive_dir"] = action  # condition on the keeper's action, keep seeded leave time / catch roll
        res = pm.simulate_kick(cfg, kp, {"x": x, "y": y}, speed, plan, 0.0)
        i += 1
        if res["outcome"] in ("goal", "save"):
            shots += 1
            saves += res["outcome"] == "save"
    return 100.0 * saves / max(shots, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(HERE, "config_prova.json"))
    ap.add_argument("--n", type=int, default=150, help="hücre başına isabetli şut")
    ap.add_argument("--harita", type=int, default=60, help="harita hücresi başına kaleci çekilişi (0 = harita yok)")
    ap.add_argument("--set", action="append", help="deneme için sabit değiştir: anahtar.yolu=json_deger")
    a = ap.parse_args()
    cfg = apply_sets(pm.load_json(a.config), a.set)
    kp = pm.keeper_params(cfg)
    print(f"kaleci: tepki {kp['reaction_s']:.3f} s | dalış hızı {kp['v_dive']:.2f} m/s | "
          f"tam uzanma erişimi {kp['reach_m']:.2f} m | merkeze çekilme %{kp['pos_pull'] * 100:.0f}")
    if a.set:
        print("değiştirilen:", a.set)

    print(f"\nBar-Eli koşullu kurtarış oranları (model / gerçek), hücre başına {a.n} isabetli şut:")
    rates = {}
    total_w = total_model = total_real = 0.0
    for zone in ("left", "centre", "right"):
        for action in ("left", "stay", "right"):
            r = cell_rate(cfg, kp, zone, action, a.n, "tab")
            rates[(zone, action)] = r
            w = BAR_ELI_JOINT[zone][action]
            total_w += w
            total_model += w * r
            total_real += w * BAR_ELI_SAVE[(zone, action)]
            print(f"  vuruş {zone:6s} | kaleci {action:5s} : model %{r:5.1f}   gerçek %{BAR_ELI_SAVE[(zone, action)]:5.1f}   (n_gerçek={w})")
    print(f"  Bar-Eli ağırlıklı genel: model %{total_model / total_w:.1f}   gerçek %{total_real / total_w:.1f}"
          f"   (Hunter 2018: %16,5)")

    if a.harita:
        xs = [-3.3, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.3]
        ys = [2.2, 1.7, 1.0, 0.3]
        print(f"\nKurtarış haritası: 24 m/s, kaleci ortada, seed'den gelen gerçek plan dağılımı, hücre başına {a.harita} çekiliş")
        print("(x+ = kalecinin solu; satırlar yükseklik, m)")
        print("  y\\x  " + " ".join(f"{x:6.1f}" for x in xs))
        for y in ys:
            row = []
            for x in xs:
                s = 0
                for j in range(a.harita):
                    plan = pm.draw_plan(cfg, CAL_SEED * 104729 + j, j)
                    res = pm.simulate_kick(cfg, kp, {"x": x, "y": y}, 24.0, plan, 0.0)
                    s += res["outcome"] == "save"
                row.append(f"{100 * s / a.harita:5.0f}%")
            print(f"  {y:4.1f} " + " ".join(row))


if __name__ == "__main__":
    main()
