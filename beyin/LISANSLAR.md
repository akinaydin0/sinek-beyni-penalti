# Lisanslar ve kaynaklar (beyin/)

İndirilen her şey `indirilen/` altında, kendi klasöründe duruyor. Hiçbiri değiştirilmedi.

| Ne | Nereden | Sürüm / commit | Lisans | Nasıl kullanıldı |
|---|---|---|---|---|
| Shiu et al. tüm-beyin LIF modeli (`model.py`, `utils.py`) | https://github.com/philshiu/Drosophila_brain_model | `91bdd1e7dcf193f3e7ca5a8933497fcef63b7960` (14 Eyl 2024) | MIT, © 2023 Philip Shiu ve Nico Spiller (`indirilen/shiu_model/LICENSE`) | `model.py` dosya yolundan yüklenir. Duman testinde `run_exp` hiç değiştirilmeden koşar. Hızlı sarmalayıcı (`beyin_model.py`) aynı `default_params`'ı ve aynı kurulum adımlarını kullanır. |
| `Completeness_783.csv`, `Connectivity_783.parquet` | aynı depo | aynı commit; SHA-256 değerleri `ids.json` → `model_data` | Depo MIT. Veri FlyWire v783'ten türetilmiş, ona da CC BY 4.0 geçerli (aşağıda). | Modelin nöron listesi ve sinaps ağırlıkları |
| Depodaki örnek sonuçlar (`results/example/*.parquet`, v630) | aynı depo | aynı commit | MIT | Duman testinde referans MN9 hızı |
| FlyWire v783 nöron açıklamaları `Supplemental_file1_neuron_annotations.tsv` | https://github.com/flyconnectome/flywire_annotations (supplemental_files/) | `a83b2776d60d5764cef36b927f5f9679c16c47a2` (29 Eyl 2026) | Depoda LICENSE dosyası yok. README, Berg et al. 2026, Schlegel et al. 2024, Tastekin et al. 2026, Matsliah et al. 2024 ve Dorkenwald et al. 2024'e atıf istiyor. | Hücre tipi ve taraf → kök kimlikleri (`kimlikler.py` → `ids.json`) |
| FlyWire v783 resmi kimlik listesi `proofread_root_ids_783.npy` | https://zenodo.org/records/10676866 (doi:10.5281/zenodo.10676866) | sürüm 783.0, md5 `e0e6c19732fd8c7a4e39a2d170105421` | CC BY 4.0 | Yalnızca denetim için: modeldeki ve `ids.json`'daki her kimliğin v783'te olduğu kontrol edilir (`dogrula_v783.py`) |
| eonsystemspbc/fly-brain (hızlı yeniden yazım) | https://github.com/eonsystemspbc/fly-brain | `a3db62f9436074e485c0278290c2164ed6150808` | GPL-2.0 | Kod KOPYALANMADI ve çalıştırılmadı. Yalnızca okundu. Oradan iki bilgi alındı: şeker GRN listesindeki tek v783 değişikliği (720575940620900446 → 720575940639259967) ve P9 deneyindeki 100 Hz hızı. Klasör silinebilir. |
| JetBrains Mono (Regular, Bold, ExtraBold .ttf) | https://github.com/JetBrains/JetBrainsMono (fonts/ttf) | `19371302b95d218af43299bce79ddbddd0bc364d` | SIL Open Font License 1.1 (`indirilen/fonts/OFL.txt`) | `raster.py` videosundaki yazılar |

## PyPI paketleri (`.venv`, python 3.12.10)

| Paket | Sürüm | Lisans |
|---|---|---|
| brian2 | 2.10.1 | CeCILL 2.1 (GPL uyumlu) |
| numpy | 2.5.4 | BSD-3 |
| pandas | 3.0.6 | BSD-3 |
| pyarrow | 26.0.0 | Apache 2.0 |
| joblib | 1.6.0 | BSD-3 |
| scipy | 1.18.1 | BSD-3 |
| matplotlib | 3.11.2 | Matplotlib (PSF tabanlı) |
| Cython | 3.1.3 | Apache 2.0 |
| sympy | 1.14.0 | BSD-3 |
| pillow | 13.0.0 | MIT-CMU (HPND) |

## Atıf yapılan makaleler (yöntem kaynakları, dosya alınmadı)

- Shiu et al., *A Drosophila computational brain model reveals sensorimotor processing*, Nature 2024, doi:10.1038/s41586-024-07763-9
- Yang et al., *Fine-grained descending control of steering in walking Drosophila*, Cell 2024, doi:10.1016/j.cell.2024.08.033 (DNa01, DNa02, DNb05, DNg13 kendi tarafına; DNb06 karşı tarafa döndürür)
- Bidaye et al., *Two brain pathways initiate distinct forward walking programs in Drosophila*, Neuron 2020, doi:10.1016/j.neuron.2020.07.032 (P9, oDN1)
- Sapkal et al., *Neural circuit mechanisms underlying context-specific halting in Drosophila*, Nature 2024, doi:10.1038/s41586-024-07854-7 (oDN1 = DNg97)
- *Connectome simulations identify a central pattern generator circuit for fly walking*, bioRxiv 2025, doi:10.1101/2025.09.12.675944 ("DNg97 (oDN1)" ifadesi)
- Dorkenwald et al., Nature 2024 ve Schlegel et al., Nature 2024 (FlyWire v783 bağlantı haritası ve açıklamaları)

EA FC'ye ait hiçbir görsel, model, logo ya da ekran görüntüsü kullanılmadı. Bu klasörde Uğurcan Çakır'a ait hiçbir görüntü yok.
