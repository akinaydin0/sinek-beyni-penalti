# Third-party licenses, data sources and required citations

[tur3b 2026-10-22] Türkçe özet: bu depo üçüncü taraf kodu ya da bağlantı verisi **içermez**. `araclar/veri_indir.py`
Shiu et al. modelinin dosyalarını sabit commit'ten indirir; Python paketlerini `araclar/kur.py` PyPI'dan kurar.
Aşağıda her birinin lisansı ve yayımlanacak her yerde (depo, video açıklaması) yapılması gereken atıflar var.

Nothing listed here is redistributed in this repository. The model code and connectome-derived data are
downloaded by `araclar/veri_indir.py` from the original source at a pinned commit and checked by SHA-256;
Python packages are installed from PyPI by `araclar/kur.py`.

## 1. Shiu et al. whole-brain LIF model (downloaded, not included)

| | |
|---|---|
| Source | https://github.com/philshiu/Drosophila_brain_model |
| Commit | `91bdd1e7dcf193f3e7ca5a8933497fcef63b7960` (2024-09-14) |
| Files used | `model.py`, `Completeness_783.csv`, `Connectivity_783.parquet` (+ `LICENSE`) |
| SHA-256 | in `beyin/ids.json` -> `model_data` and in `araclar/veri_indir.py` |
| License | MIT, Copyright (c) 2023 Philip Shiu and Nico Spiller (full text below) |
| How it is used | `beyin/beyin_model.py` loads `model.py` from its file path and builds the network with the same equations, constants and weights (`default_params`). Our wrapper changes how trials are run (network built once, `store()/restore()`, one `PoissonGroup` instead of `PoissonInput`), not the model. |

Cite: Shiu, P. K. et al. A *Drosophila* computational brain model reveals sensorimotor processing.
*Nature* 634, 210–219 (2024). https://doi.org/10.1038/s41586-024-07763-9

```
MIT License

Copyright (c) 2023 Philip Shiu and Nico Spiller

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 2. FlyWire v783 connectome (data behind the Shiu files and `beyin/ids.json`)

The connectivity and neuron list in the Shiu files are derived from FlyWire materialization 783. FlyWire data
are released under **CC BY 4.0** (https://creativecommons.org/licenses/by/4.0/), which requires attribution.
`beyin/ids.json` contains FlyWire v783 root IDs and cell-type labels taken from the FlyWire annotation file
(below). FlyWire's own citation guidelines: https://flywire.ai/guidelines (check before publishing).

Required / requested citations:
- Dorkenwald, S. et al. Neuronal wiring diagram of an adult brain. *Nature* 634, 124–138 (2024).
  https://doi.org/10.1038/s41586-024-07558-y
- Schlegel, P. et al. Whole-brain annotation and multi-connectome cell typing of *Drosophila*. *Nature* (2024).
  https://doi.org/10.1038/s41586-024-07686-5
- Zheng, Z. et al. A complete electron microscopy volume of the brain of adult *Drosophila melanogaster*.
  *Cell* 174, 730–743.e22 (2018). https://doi.org/10.1016/j.cell.2018.06.019  (EM data)
- Buhmann, J. et al. Automatic detection of synaptic partners in a whole-brain *Drosophila* electron microscopy
  data set. *Nat. Methods* 18, 771–774 (2021). https://doi.org/10.1038/s41592-021-01183-7  (synapses)
- Heinrich, L. et al. Synaptic cleft segmentation in non-isotropic volume electron microscopy of the complete
  *Drosophila* brain. MICCAI 2018, 317–325. https://doi.org/10.1007/978-3-030-00934-2_36
- Eckstein, N. et al. Neurotransmitter classification from electron microscopy images at synaptic sites in
  *Drosophila melanogaster*. *Cell* 187, 2574–2594.e23 (2024). https://doi.org/10.1016/j.cell.2024.03.016
  (the excitatory/inhibitory sign of each connection in the model comes from these predictions)

FlyWire v783 official ID list, used only for an audit (`beyin/dogrula_v783.py`, not needed for verification):
Zenodo record 10676866, `proofread_root_ids_783.npy`, https://doi.org/10.5281/zenodo.10676866 (CC BY 4.0).

## 3. FlyWire neuron annotations (used to build `beyin/ids.json`; optional download)

| | |
|---|---|
| Source | https://github.com/flyconnectome/flywire_annotations (`supplemental_files/Supplemental_file1_neuron_annotations.tsv`) |
| Commit | `a83b2776d60d5764cef36b927f5f9679c16c47a2`; SHA-256 in `beyin/ids.json` -> `annotation_file` |
| License | the repository has no LICENSE file; its README asks for citations (below) |
| Download | only with `araclar/veri_indir.py --ek` (needed to re-derive `ids.json` with `beyin/kimlikler.py`) |

The README of that repository (versions >= 3.2.0) asks to cite: Berg et al. (2026), Schlegel et al. (2024),
Tastekin et al. (2026), Matsliah et al. (2024) and Dorkenwald et al. (2024):
- Berg, S. et al. Sexual dimorphism in the complete *Drosophila* male central nervous system connectome.
  *Cell* 189, 5504–5526.e15 (2026). https://doi.org/10.1016/j.cell.2026.08.015
- Tastekin, I. et al. The complete gustatory connectome of adult *Drosophila* reveals how taste guides feeding,
  foraging, and social behavior. *Cell* 189, 5527–5551 (2026). https://doi.org/10.1016/j.cell.2026.08.016
- Matsliah, A. et al. Neuronal parts list and wiring diagram for a visual system. *Nature* (2024).
  https://doi.org/10.1038/s41586-024-07981-1

## 4. Methods taken from papers (no files)

- Yang, H. H. et al. Fine-grained descending control of steering in walking *Drosophila*. *Cell* (2024).
  https://doi.org/10.1016/j.cell.2024.08.033 (which descending neurons turn the fly left/right)
- Bidaye, S. S. et al. Two brain pathways initiate distinct forward walking programs in *Drosophila*.
  *Neuron* (2020). https://doi.org/10.1016/j.neuron.2020.07.032 (P9, oDN1)
- Sapkal, N. et al. Neural circuit mechanisms underlying context-specific halting in *Drosophila*. *Nature* (2024).
  https://doi.org/10.1038/s41586-024-07854-7 (oDN1 = DNg97)
- Hunter, A. H. et al. (2018), probability that a keeper stops a ball within reach as a function of shot speed;
  Bar-Eli et al. (2007), keeper dive-direction frequencies. Full references and how they are used: `oyun/MODEL.md`.
- RFC 9380 (Hashing to Elliptic Curves), constants and test vectors used by `oyun/bls12381.py`;
  https://www.rfc-editor.org/rfc/rfc9380. No code was copied.
- eonsystemspbc/fly-brain (GPL-2.0): read only, **no code copied, not included**. Two facts were taken from it
  (one v783 ID change in the sugar-GRN list and the 100 Hz P9 rate); see `beyin/LISANSLAR.md`.

## 5. drand quicknet (public randomness)

The beacon value comes from the League of Entropy's drand "quicknet" network (chain hash
`52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971`), fetched from public relays
(api.drand.sh, api2.drand.sh, drand.cloudflare.com). Only the published round values are used; no drand code.
https://drand.love

## 6. Python packages (installed from PyPI by `araclar/kur.py`, not included)

Pinned in `beyin/requirements.txt` (same versions as the reference Mac run).

| Package | Version | License |
|---|---|---|
| Brian2 | 2.10.1 | CeCILL 2.1 (GPL-compatible) |
| numpy | 2.5.4 | BSD-3-Clause |
| pandas | 3.0.6 | BSD-3-Clause |
| pyarrow | 26.0.0 | Apache-2.0 |
| scipy | 1.18.1 | BSD-3-Clause |
| Cython | 3.1.3 | Apache-2.0 |
| sympy | 1.14.0 | BSD-3-Clause |
| mpmath | 1.3.0 | BSD-3-Clause |
| matplotlib | 3.11.2 | Matplotlib License (PSF-based) |
| pillow | 13.0.0 | MIT-CMU (HPND) |
| joblib | 1.6.0 | BSD-3-Clause |
| Jinja2 / MarkupSafe | 3.1.6 / 3.0.4 | BSD-3-Clause |
| setuptools | 84.2.1 | MIT |
| pip | 26.2.2 | MIT |
| others (cloudpickle, contourpy, cycler, fonttools, kiwisolver, packaging, pyparsing, python-dateutil, six, tzdata) | see requirements.txt | BSD / MIT / Apache-2.0 |

Brian2 citation: Stimberg, M., Brette, R. & Goodman, D. F. M. Brian 2, an intuitive and efficient neural
simulator. *eLife* 8, e47314 (2019). https://doi.org/10.7554/eLife.47314

Node.js (optional, for `oyun/bagimsiz/kontrol.mjs`) is not included; MIT.

## 7. Names and trademarks

"Uğurcan Çakır" is used only as a name, with his EA SPORTS FC 27 ratings (DIV 80, HAN 76, KIC 81, POS 80,
REF 82, height 1.91 m) as published on EA's official ratings page. No likeness, photo, club crest, EA asset,
logo or game footage is used or included. EA SPORTS FC is a trademark of Electronic Arts; this project is not
affiliated with or endorsed by Electronic Arts, the player, or his club.
