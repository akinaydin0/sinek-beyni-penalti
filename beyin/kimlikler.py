"""ids.json üretir: okuma/uyarma için kullanılan tüm nöronların FlyWire v783 kök kimlikleri.

Kaynak: flyconnectome/flywire_annotations, supplemental_files/
Supplemental_file1_neuron_annotations.tsv (root_id = v783). Hücre tipi her zaman
`cell_type` sütunundan alınır (FlyWire tipi), `side` sütunu somanın bulunduğu
taraftır (sineğin kendi solu/sağı). Her kimliğin model verisinde
(Completeness_783.csv) bulunduğu kontrol edilir; v630 kimliği kullanılmaz.

Kullanım: .venv/bin/python -I kimlikler.py   ->  ids.json
"""
import sys
import json
import hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ortam  # noqa: E402
import pandas as pd  # noqa: E402

YANG = 'Yang et al., Cell 2024, "Fine-grained descending control of steering in walking Drosophila", doi:10.1016/j.cell.2024.08.033'
BIDAYE = 'Bidaye et al., Neuron 2020, "Two brain pathways initiate distinct forward walking programs in Drosophila", doi:10.1016/j.neuron.2020.07.032'
SAPKAL = 'Sapkal et al., Nature 2024, "Neural circuit mechanisms underlying context-specific halting in Drosophila", doi:10.1038/s41586-024-07854-7 (oDN1 = DNg97)'
CPG = 'Connectome simulations identify a central pattern generator circuit for fly walking, bioRxiv 2025, doi:10.1101/2025.09.12.675944 ("DNg97 (oDN1)", citing Sapkal et al. 2024)'
SCHLEGEL = 'Schlegel et al., Nature 2024; Dorkenwald et al., Nature 2024 (FlyWire v783 annotations)'
SHIU = 'Shiu et al., Nature 2024, doi:10.1038/s41586-024-07763-9; example.ipynb in github.com/philshiu/Drosophila_brain_model'

# (grup adı, FlyWire cell_type, rol, kaynak)
DN_TIPLERI = [
    ('DNa01', 'DNa01', 'steering, ipsiversive (turns toward its own side)', YANG),
    ('DNa02', 'DNa02', 'steering, ipsiversive (turns toward its own side); causal test in Yang et al.', YANG),
    ('DNb05', 'DNb05', 'steering, ipsiversive (turns toward its own side)', YANG),
    ('DNg13', 'DNg13', 'steering, ipsiversive (turns toward its own side); causal test in Yang et al.', YANG),
    ('DNb06', 'DNb06', 'steering, contraversive (turns away from its own side)', YANG),
    ('oDN1', 'DNg97', 'forward drive (power readout)', f'{BIDAYE}; {SAPKAL}; {CPG}'),
    ('P9', 'DNp09', 'forward walking command; optional fixed bilateral drive', BIDAYE),
]
LC10_TIPLERI = ['LC10a', 'LC10b', 'LC10c-1', 'LC10c-2', 'LC10d', 'LC10e', 'LC10f']


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main():
    ann = pd.read_csv(ortam.ANNOT, sep='\t', low_memory=False)
    comp = pd.read_csv(ortam.PATH_COMP, index_col=0)
    model_ids = set(int(x) for x in comp.index)
    groups = {}

    def ekle(ad, ct, side, rol, kaynak, tek=False):
        m = ann[(ann.cell_type == ct) & (ann.side == side)]
        ids = sorted(int(r) for r in m.root_id)
        assert ids, f'{ct} {side} bulunamadı'
        if tek:
            assert len(ids) == 1, f'{ct} {side}: {len(ids)} nöron'
        eksik = [r for r in ids if r not in model_ids]
        assert not eksik, f'{ad}: model verisinde olmayan kimlik {eksik}'
        hb = sorted(set(m.hemibrain_type.dropna().astype(str)))
        groups[ad] = {
            'root_ids_v783': [str(r) for r in ids], 'n': len(ids),
            'flywire_cell_type': ct, 'side': side,
            'hemibrain_type': hb, 'super_class': sorted(set(m.super_class.dropna())),
            'top_nt': sorted(set(m.top_nt.dropna())),
            'role': rol, 'source': kaynak,
        }

    for ad, ct, rol, kaynak in DN_TIPLERI:
        for side, s in [('left', 'L'), ('right', 'R')]:
            ekle(f'{ad}_{s}', ct, side, rol, kaynak, tek=True)
    for ct in LC10_TIPLERI:
        for side, s in [('left', 'L'), ('right', 'R')]:
            ekle(f'{ct}_{s}', ct, side, 'visual input (lobula columnar, projects to ipsilateral AOTU)',
                 f'{SCHLEGEL}; LC10 types per FlyWire cell_type')

    # Duman testi nöronları
    from smoke_test import SUGAR_V783, MN9
    sug = ann[ann.root_id.isin(SUGAR_V783)]
    groups['sugar_GRN_smoke'] = {
        'root_ids_v783': [str(r) for r in SUGAR_V783], 'n': len(SUGAR_V783),
        'flywire_cell_type': sorted(set(sug.cell_type.dropna())), 'side': sorted(set(sug.side.dropna())),
        'role': 'smoke test input (Shiu et al. sugar GRNs, "sugarR")',
        'source': f'{SHIU}; 20 ids identical in v630/v783, 720575940620900446 (v630) -> 720575940639259967 (v783) '
                  'as listed in github.com/eonsystemspbc/fly-brain code/benchmark.py',
    }
    groups['MN9_smoke'] = {'root_ids_v783': [str(MN9)], 'n': 1, 'role': 'smoke test readout (proboscis motor neuron MN9)',
                           'flywire_cell_type': ann.loc[ann.root_id == MN9, 'cell_type'].tolist(), 'source': SHIU}

    out = {
        'connectome': 'FlyWire v783 (materialization 783)',
        'id_version': 783,
        'annotation_file': {
            'url': 'https://github.com/flyconnectome/flywire_annotations/blob/main/supplemental_files/Supplemental_file1_neuron_annotations.tsv',
            'commit': ortam.ANNOT_COMMIT, 'sha256': sha256(ortam.ANNOT),
        },
        'model_data': {
            'repo': 'https://github.com/philshiu/Drosophila_brain_model', 'commit': ortam.SHIU_COMMIT,
            'Completeness_783.csv_sha256': sha256(ortam.PATH_COMP),
            'Connectivity_783.parquet_sha256': sha256(ortam.PATH_CON),
        },
        'side_convention': ('"L"/"R" = FlyWire `side` column = soma side from the fly\'s own point of view. '
                            'The fly stands at the penalty spot facing the goal, so its right = shooter\'s right = +x.'),
        'naming_notes': [
            'DNa01: FlyWire cell_type DNa01 (hemibrain_type VES006). FlyWire DNae001 carries hemibrain_type "DNa01"; '
            'we follow the FlyWire cell_type, which is what Yang et al. and the v783 annotations use.',
            'DNp09 (P9): FlyWire cell_type DNp09. DNp71 carries hemibrain_type "DNp09" and is NOT used.',
            'oDN1 has no oDN1 label in the annotation file; it is the FlyWire type DNg97 per Sapkal et al. 2024.',
            'eonsystemspbc/fly-brain labels 720575940627652358 as "P9 left"; the v783 annotation says side=right. '
            'We use the annotation.',
        ],
        'groups': groups,
    }
    with open(ortam.BEYIN / 'ids.json', 'w') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write('\n')
    for k, v in groups.items():
        print(k, v['n'], v['root_ids_v783'][:2])


if __name__ == '__main__':
    main()
