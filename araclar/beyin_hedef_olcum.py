# -*- coding: utf-8 -*-
"""[tur3b 2026-10-22] TANI ARACI (doğrulamanın parçası DEĞİL): sinek beynini seçilen Brian2 kod üretim hedefiyle
(cython ya da numpy) yeniden koşturur ve Mac referansıyla (karar dosyası + raster npz) spike spike karşılaştırır.

Neden var: verify.py beyni beyin_model.py'nin seçtiği hedefle (cython) koşturur. Başka bir işletim sisteminde
sonuç tutmazsa farkın nereden geldiğini (derleyici mi, numpy mı) bulmak için hedefi değiştirip ölçmek gerekir.
beyin_model.py taahhüde girdiği için DEĞİŞTİRİLMEZ; bu araç onu içe aktardıktan SONRA tercihi değiştirir.

Beynin kendi ortamıyla çalıştır (dosya yazmaz, -B ile __pycache__ da yazmaz; Brian2'nin derleme önbelleği hariç):
    <beyin python> -I -B araclar/beyin_hedef_olcum.py --hedef numpy --sutlar 1 --json sonuc.json

Çıktı: her şut için spikes_sha256 referansla aynı mı, değilse İLK ayrılan spike (zaman, nöron) ve süre.
"""
import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):  # Windows konsolu / boru: Türkçe karakterler için UTF-8
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")

KOK = Path(__file__).resolve().parent.parent


def ilk_fark(ref_i, ref_t, i, t):
    """İki spike listesinin (zaman sıralı) ilk ayrıldığı yer."""
    n = min(len(ref_i), len(i))
    for k in range(n):
        if ref_i[k] != i[k] or ref_t[k] != t[k]:
            return {"sira": k, "ref": [int(ref_i[k]), float(ref_t[k])], "bu": [int(i[k]), float(t[k])]}
    if len(ref_i) != len(i):
        return {"sira": n, "ref_uzunluk": int(len(ref_i)), "bu_uzunluk": int(len(i))}
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--beyin", default=str(KOK / "beyin"))
    ap.add_argument("--karar", default=str(KOK / "veri" / "prova7B" / "prova7B_beyin_kararlari.json"))  # [tur4 2026-10-23]
    ap.add_argument("--hedef", choices=["cython", "numpy", "degistirme"], default="degistirme",
                    help="Brian2 codegen.target; 'degistirme' = beyin_model.py ne seçtiyse (cython)")
    ap.add_argument("--sutlar", default="1,2,3,4,5")
    ap.add_argument("--json")
    a = ap.parse_args()
    B = Path(a.beyin).resolve()
    sys.path.insert(0, str(B))
    import ortam  # noqa: F401
    import numpy as np
    import esleme
    import dondur
    ok, kayit = dondur.kontrol()
    if not ok:
        sys.exit("esleme.py / ids.json donmuş özetle uyuşmuyor")
    import beyin_model
    from brian2 import prefs
    import brian2
    if a.hedef != "degistirme":
        prefs.codegen.target = a.hedef
    hedef = prefs.codegen.target
    dec = json.loads(Path(a.karar).read_text(encoding="utf-8"))
    ids = json.loads((B / "ids.json").read_text(encoding="utf-8"))
    t0 = time.time()
    beyin = beyin_model.SinekBeyni(esleme.tum_girdi_kimlikleri(ids), verbose=False)
    kurulum = time.time() - t0
    grup = {k: [int(r) for r in ids["groups"][k]["root_ids_v783"]] for k in esleme.COUNT_KEYS}
    sutlar = [int(x) for x in a.sutlar.split(",") if x.strip()]
    sonuc = []
    for k in dec["kicks"]:
        if k["n"] not in sutlar:
            continue
        seed, kx = int(k["trial_seed"]), float(k["scene"]["keeper_x"])
        i, t, dur = beyin.deneme(esleme.girdi_hizlari(kx, ids), seed, esleme.T_TRIAL_S)
        c = np.bincount(i, minlength=len(beyin.root_ids))
        counts = {g: int(sum(c[beyin.f2i[x]] for x in v)) for g, v in grup.items()}
        all_i, all_t = i.astype(np.int32), t.astype(np.float32)
        sp = hashlib.sha256(all_i.tobytes() + all_t.tobytes()).hexdigest()
        r = {"n": k["n"], "trial_seed": seed, "keeper_x": kx, "sure_s": round(dur, 2), "spike": int(len(i)),
             "ref_spike": k.get("brain_spikes"), "spikes_sha256": sp, "ref_spikes_sha256": k.get("spikes_sha256"),
             "ayni": sp == k.get("spikes_sha256"), "counts_ayni": counts == k.get("counts")}
        rp = k.get("raster_npz")
        npz = (KOK / rp) if rp else None
        if not r["ayni"] and npz and npz.is_file():
            z = np.load(npz)
            r["ilk_fark"] = ilk_fark(z["all_i"], z["all_t"], all_i, all_t)
        sonuc.append(r)
        print(f"şut {r['n']}: hedef {hedef}  {r['spike']} spike (ref {r['ref_spike']})  "
              f"{'AYNI' if r['ayni'] else 'FARKLI'}  sayılar {'aynı' if r['counts_ayni'] else 'FARKLI'}  "
              f"[{dur:.1f} s]" + (f"  ilk fark {r.get('ilk_fark')}" if not r["ayni"] else ""), flush=True)
    try:
        from brian2.codegen.cpp_prefs import get_compiler_and_args
        derleyici = list(get_compiler_and_args())
    except Exception as e:  # noqa: BLE001
        derleyici = f"bilinmiyor: {e}"
    ozet = {"hedef": hedef, "platform": platform.platform(), "makine": platform.machine(),
            "python": sys.version.split()[0], "brian2": brian2.__version__, "numpy": np.__version__,
            "derleyici": derleyici, "kurulum_s": round(kurulum, 1), "sonuc": sonuc,
            "hepsi_ayni": all(r["ayni"] for r in sonuc) and bool(sonuc)}
    print("ÖZET " + json.dumps({k: v for k, v in ozet.items() if k != "sonuc"}, ensure_ascii=False))
    print("SONUÇ:", "HEPSİ AYNI" if ozet["hepsi_ayni"] else "FARKLI VAR")
    if a.json:
        Path(a.json).write_text(json.dumps(ozet, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
