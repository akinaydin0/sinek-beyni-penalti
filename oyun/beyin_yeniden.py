# -*- coding: utf-8 -*-
"""
beyin_yeniden.py - [tur3 2026-10-22, delik 1] verify.py'nin sinek beyni YENİDEN KOŞUSU.

verify.py bunu beynin kendi ortamıyla çağırır:
    <beyin>/.venv/bin/python -I -B beyin_yeniden.py --beyin <beyin klasörü>   (stdin: iş listesi JSON)
stdin : {"isler": [{"n": 1, "trial_seed": 123, "keeper_x": -0.422, "raster": "/yol/kick_01.npz" | null}, ...]}
stdout: son satır  SONUC_JSON {"readout_sha256": ..., "sonuc": [...]}

Hesap kick.py'nin döngü gövdesiyle BİREBİR aynıdır (girdi_hizlari -> SinekBeyni.deneme -> oku -> esle ->
karar_ms -> spikes_sha256); tek fark: hiçbir dosya YAZILMAZ (raster yazılmaz, -B ile __pycache__ da yazılmaz).
Tohum ve kaleci yeri karar dosyasından DEĞİL, verify.py'nin taahhüt + beacon'dan hesapladığı değerlerden gelir;
böylece "beyin başka yerde/tohumla koşturuldu, etiketi doğru yazıldı" sahteliği yakalanır.
Raster dosyası verilirse (npz) içindeki bütün spike'ların özeti de yeniden koşuyla karşılaştırılır.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--beyin", required=True)
    a = ap.parse_args()
    B = Path(a.beyin).resolve()
    sys.path.insert(0, str(B))
    import ortam  # noqa: F401  (yollar)
    import numpy as np
    import esleme
    import dondur
    ok, kayit = dondur.kontrol()
    if not ok:
        print("SONUC_JSON " + json.dumps({"hata": "esleme.py / ids.json donmuş özetle (DONDURMA.json) uyuşmuyor"}))
        sys.exit(1)
    from beyin_model import SinekBeyni
    isler = json.loads(sys.stdin.read())["isler"]
    ids = json.loads((B / "ids.json").read_text())
    beyin = SinekBeyni(esleme.tum_girdi_kimlikleri(ids), verbose=False)
    grup = {k: [int(r) for r in ids["groups"][k]["root_ids_v783"]] for k in esleme.COUNT_KEYS}
    steer_idx = np.array([beyin.f2i[x] for k in esleme.STEER_NEURONS for x in grup[k]])
    out = []
    for j in isler:
        seed = int(j["trial_seed"])
        kx = float(j["keeper_x"])
        i, t, dur = beyin.deneme(esleme.girdi_hizlari(kx, ids), seed, esleme.T_TRIAL_S)
        c = np.bincount(i, minlength=len(beyin.root_ids))
        counts = {k: int(sum(c[beyin.f2i[x]] for x in v)) for k, v in grup.items()}
        steer, power, rt, lt = esleme.oku(counts)
        ax, ay, v = esleme.esle(steer, power)
        dms = esleme.karar_ms(t[np.isin(i, steer_idx)].tolist())
        all_i = i.astype(np.int32)
        all_t = t.astype(np.float32)
        sp = hashlib.sha256(all_i.tobytes() + all_t.tobytes()).hexdigest()
        r = {"n": int(j["n"]), "trial_seed": seed, "keeper_x": kx, "counts": counts, "steer": round(steer, 4),
             "power_spikes": int(power), "aim": {"x": ax, "y": ay}, "speed_mps": v, "decision_ms": dms,
             "Rturn": rt, "Lturn": lt, "brain_spikes": int(len(i)), "spikes_sha256": sp,
             "runtime_s": round(dur, 2), "raster": "yok"}
        rp = j.get("raster")
        if rp and Path(rp).is_file():
            z = np.load(rp)
            r_sp = hashlib.sha256(z["all_i"].astype(np.int32).tobytes() + z["all_t"].astype(np.float32).tobytes()).hexdigest()
            r["raster"] = ("aynı" if (r_sp == sp and int(z["trial_seed"]) == seed and float(z["keeper_x"]) == kx)
                           else f"FARKLI (raster özeti {r_sp[:12]}, tohum {int(z['trial_seed'])}, x {float(z['keeper_x'])})")
        out.append(r)
        print(f"[beyin_yeniden] şut {r['n']}: tohum {seed} x {kx:+.3f} -> nişan ({ax:+.3f}, {ay:.3f}) {v} m/s "
              f"[{dur:.1f} s]", file=sys.stderr, flush=True)
    print("SONUC_JSON " + json.dumps({"readout_sha256": kayit["readout_sha256"], "sonuc": out}))


if __name__ == "__main__":
    main()
