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


# --------------------------------------------------------------------------- [tur3b 2026-10-22] şut sapması kalibrasyonu
# Gerçek veri (kaleyi bulmayan penaltı = aut + üstten aut + direk; kurtarışlar hariç):
#   Vollmer, Schoch & Brandes 2024 (PLoS One 19:e0315017), Transfermarkt, 2012/13-2022/23, maç içi penaltılar:
#   kupalar %4,29 (7694), ligler %4,94 (23519) -> birleşik %4,78 (31213). Seri penaltılarda %9,92 (14189).
#   Almeida, Volossovitch & Duarte 2016 (IJPAS), UEFA ŞL + UAL, 536 penaltı: %5,2 kaçan; üst sıra ~%14, alt sıra ~%3.
SAPMA_HEDEF = (0.0429 * 7694 + 0.0494 * 23519) / (7694 + 23519)   # = 0,0478
ZONE_W = {"left": 92, "centre": 82, "right": 112}   # Bar-Eli 2007 vuruş bölgesi toplamları (Tablo 1)


def _sapma_isi(args):
    cfg_path, sets, olcek, i0, i1 = args
    cfg = apply_sets(pm.load_json(cfg_path), sets)
    cfg["sut_sapmasi"] = dict(cfg["sut_sapmasi"], acik=True, olcek=olcek)
    kp = pm.keeper_params(cfg)
    nd = NormalDist()
    tot = sum(ZONE_W.values())
    c = {"goal": 0, "save": 0, "wide": 0, "over": 0, "post": 0}
    rows = {"ust": [0, 0], "alt": [0, 0]}   # [şut, kaçan] gerçek geçiş yüksekliğine göre (Almeida gibi)
    for i in range(i0, i1):
        u = lambda lab: pm.uniform(CAL_SEED, f"sapma|{i}|{lab}")  # noqa: E731
        uz = u("zone") * tot
        zone = "left" if uz < ZONE_W["left"] else ("centre" if uz < ZONE_W["left"] + ZONE_W["centre"] else "right")
        lo, hi = ZONES[zone]
        x = lo + (hi - lo) * u("x")
        y = 0.15 + 2.15 * u("y") ** 2
        speed = pm.clamp(23.5 + 1.9 * nd.inv_cdf(u("v")), 16.0, 30.0)
        kseed = int(pm.sha256_hex(f"{CAL_SEED}|sapma|{i}".encode())[:15], 16)
        plan = pm.draw_plan(cfg, kseed, 1)
        sc = pm.draw_scatter(cfg, kseed, 1, {"x": x, "y": y}, speed)
        res = pm.simulate_kick(cfg, kp, sc["aim"], speed, plan, 0.0)
        o = res["outcome"]
        c[o] += 1
        row = "ust" if sc["aim"]["y"] > 1.22 else "alt"
        rows[row][0] += 1
        rows[row][1] += o in ("wide", "over", "post")
    return c, rows


def sapma_olc(cfg_path, sets, olcek, n, isci):
    from multiprocessing import Pool
    parts = [(cfg_path, sets, olcek, k * n // isci, (k + 1) * n // isci) for k in range(isci)]
    with Pool(isci) as pool:
        out = pool.map(_sapma_isi, parts)
    c = {k: sum(o[0][k] for o in out) for k in out[0][0]}
    rows = {r: [sum(o[1][r][0] for o in out), sum(o[1][r][1] for o in out)] for r in out[0][1]}
    miss = (c["wide"] + c["over"] + c["post"]) / n
    return miss, c, rows


def sapma_kalibre(a):
    """Ortak rastgele sayılarla (aynı şutlar, aynı zarlar) olcek'e göre ikiye bölme: kaçan oranı = SAPMA_HEDEF."""
    print(f"Şut sapması kalibrasyonu: hedef kaçan oranı %{100 * SAPMA_HEDEF:.2f} (Vollmer ve ark. 2024, maç içi), "
          f"{a.sapma_n} şut, standart şut kümesi NİYET nişanı sayılır, kaleci gerçek dağılımdan (draw_plan)")
    cache = {}

    def F(cv):
        if cv not in cache:
            cache[cv] = sapma_olc(a.config, a.set, cv, a.sapma_n, a.isci)
            m, c, rows = cache[cv]
            print(f"  olcek {cv:.4f}: kaçan %{100 * m:5.2f} (aut {c['wide']}, üst {c['over']}, direk {c['post']}) | "
                  f"üst sıra %{100 * rows['ust'][1] / max(rows['ust'][0], 1):4.1f}, alt sıra %{100 * rows['alt'][1] / max(rows['alt'][0], 1):4.1f}",
                  flush=True)
        return cache[cv][0]

    F(1.0)
    lo, hi = 0.02, 1.0
    for _ in range(a.adim):
        mid = round(0.5 * (lo + hi), 4)
        if F(mid) < SAPMA_HEDEF:
            lo = mid
        else:
            hi = mid
    best = round(0.5 * (lo + hi), 3)
    F(best)
    m, c, rows = cache[best]
    print(f"\nSONUÇ olcek = {best:.3f}: kaçan %{100 * m:.2f} | aut %{100 * c['wide'] / a.sapma_n:.2f}, üstten aut "
          f"%{100 * c['over'] / a.sapma_n:.2f}, direk %{100 * c['post'] / a.sapma_n:.2f} | kurtarış %{100 * c['save'] / a.sapma_n:.2f}"
          f" | gol %{100 * c['goal'] / a.sapma_n:.2f}")
    print(f"   Almeida 2016 kıyası (gerçek geçiş yüksekliğine göre): üst sıra model %{100 * rows['ust'][1] / max(rows['ust'][0], 1):.1f} "
          f"(gerçek ~%13,7), alt sıra model %{100 * rows['alt'][1] / max(rows['alt'][0], 1):.1f} (gerçek ~%2,7)")
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(HERE, "config_prova.json"))
    ap.add_argument("--n", type=int, default=150, help="hücre başına isabetli şut")
    ap.add_argument("--harita", type=int, default=60, help="harita hücresi başına kaleci çekilişi (0 = harita yok)")
    ap.add_argument("--set", action="append", help="deneme için sabit değiştir: anahtar.yolu=json_deger")
    # [tur3b 2026-10-22] şut sapması (seçenek B) kalibrasyonu
    ap.add_argument("--sapma-kalibre", action="store_true", help="sut_sapmasi.olcek'i gerçek kaçan oranına kalibre et")
    ap.add_argument("--sapma-olcek", type=float, help="yalnız bu olcek ile kaçan oranını ölç")
    ap.add_argument("--sapma-n", type=int, default=12000)
    ap.add_argument("--adim", type=int, default=11)
    ap.add_argument("--is", dest="isci", type=int, default=9)
    a = ap.parse_args()
    if a.sapma_kalibre:
        sapma_kalibre(a)
        return
    if a.sapma_olcek is not None:
        m, c, rows = sapma_olc(a.config, a.set, a.sapma_olcek, a.sapma_n, a.isci)
        print(f"olcek {a.sapma_olcek}: kaçan %{100 * m:.2f}", c, rows)
        return
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
