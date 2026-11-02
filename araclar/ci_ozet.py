# -*- coding: utf-8 -*-
"""[tur3b 2026-10-22] CI özeti: dogrula.py ve beyin_hedef_olcum.py JSON'larından Markdown tablo yazar.

    python araclar/ci_ozet.py <JSON klasörü> [--cikti ozet.md]
Klasördeki dosyalar: dogrula_<os>.json, hedef_numpy_<os>.json, hedef_cython_<os>.json, negatif_<os>.json (varsa).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.dont_write_bytecode = True


def oku(p):
    if not p:
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def main():
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8", errors="backslashreplace")
    ap = argparse.ArgumentParser()
    ap.add_argument("klasor")
    ap.add_argument("--cikti")
    a = ap.parse_args()
    oslar = sorted({os.path.basename(p).split("_", 1)[1].rsplit(".", 1)[0]
                    for p in glob.glob(os.path.join(a.klasor, "**", "dogrula_*.json"), recursive=True)})
    bul = lambda ad: next(iter(glob.glob(os.path.join(a.klasor, "**", ad), recursive=True)), None)  # noqa: E731
    sat = ["| OS | platform | verify sonucu | beyin (cython, Mac'e göre) | verify süresi | numpy hedefi | numpy s/şut | cython s/şut | derleyicisiz deneme |",
           "|---|---|---|---|---|---|---|---|---|"]
    for o in oslar:
        d = oku(bul(f"dogrula_{o}.json")) or {}
        n = oku(bul(f"hedef_numpy_{o}.json")) or {}
        c = oku(bul(f"hedef_cython_{o}.json")) or {}
        neg = oku(bul(f"negatif_{o}.json"))
        b = d.get("beyin") or {}
        ayni = sum(1 for v in b.values() if v.get("ayni"))
        ns = n.get("sonuc") or []
        cs = c.get("sonuc") or []
        n_ayni = sum(1 for r in ns if r.get("ayni"))
        ort = lambda xs: (f"{sum(r['sure_s'] for r in xs) / len(xs):.1f}" if xs else "-")  # noqa: E731
        neg_s = "-" if neg is None else f"{neg.get('etiket')} (beyin satırı {len(neg.get('beyin') or {})})"
        sat.append(f"| {o} | {d.get('platform', '?')} | {d.get('etiket', 'YOK')} (çıkış {d.get('verify_cikis')}) | "
                   f"{ayni}/5 bit bit aynı | {d.get('verify_sure_s', '-')} s | "
                   f"{n_ayni}/{len(ns)} aynı | {ort(ns)} | {ort(cs)} | {neg_s} |")
    farklar = []
    for o in oslar:
        d = oku(bul(f"dogrula_{o}.json")) or {}
        mf = d.get("mac_farki") or {}
        if mf.get("yalniz_mac") or mf.get("yalniz_bu"):
            farklar.append(f"\n**{o}: Mac verify çıktısından farklı satırlar**\n")
            farklar += [f"- yalnız Mac: `{s}`" for s in mf.get("yalniz_mac", [])]
            farklar += [f"- yalnız {o}: `{s}`" for s in mf.get("yalniz_bu", [])]
        for r in (oku(bul(f"hedef_cython_{o}.json")) or {}).get("sonuc", []) + \
                (oku(bul(f"hedef_numpy_{o}.json")) or {}).get("sonuc", []):
            if not r.get("ayni"):
                farklar.append(f"- {o} şut {r['n']}: spike {r['spike']} (Mac {r['ref_spike']}), ilk fark {r.get('ilk_fark')}")
    md = "## Sinek beyni penaltı: üç işletim sisteminde doğrulama\n\n" + "\n".join(sat) + "\n" + "\n".join(farklar) + "\n"
    # [tur5 2026-11-02] final dosyalar (elle tetikleme): yalnız durum, sonuç satırı dosyalarda
    fin = [(o, oku(bul(f"final_{o}.json"))) for o in oslar]
    if any(d for _, d in fin):
        md += "\n### Final koşu\n\n| OS | verify sonucu | beyin (Mac'e göre) | verify süresi |\n|---|---|---|---|\n"
        for o, d in fin:
            d = d or {}
            ayni = sum(1 for v in (d.get("beyin") or {}).values() if v.get("ayni"))
            md += f"| {o} | {d.get('etiket', 'YOK')} (çıkış {d.get('verify_cikis')}) | {ayni}/5 bit bit aynı | {d.get('verify_sure_s', '-')} s |\n"
    print(md)
    if a.cikti:
        with open(a.cikti, "w", encoding="utf-8") as f:
            f.write(md)


if __name__ == "__main__":
    main()
