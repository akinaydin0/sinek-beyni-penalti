"""Kimlik sürümü denetimi: modeldeki ve ids.json'daki her kök kimliği resmi FlyWire v783
listesinde mi? (Zenodo 10.5281/zenodo.10676866, proofread_root_ids_783.npy, CC BY 4.0)

Kullanım: .venv/bin/python -I dogrula_v783.py   ->  ../veri/v783_dogrulama.json
"""
import sys
import json
import hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ortam  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

Z = ortam.BEYIN / 'indirilen' / 'zenodo_10676866' / 'proofread_root_ids_783.npy'
z = np.load(Z, allow_pickle=False)
zs = set(int(x) for x in z)
model = [int(x) for x in pd.read_csv(ortam.PATH_COMP, index_col=0).index]
ids = json.loads((ortam.BEYIN / 'ids.json').read_text())
allids = sorted({int(r) for g in ids['groups'].values() for r in g['root_ids_v783']})
out = {
    'official_list': 'https://zenodo.org/records/10676866  proofread_root_ids_783.npy',
    'official_md5': hashlib.md5(Z.read_bytes()).hexdigest(),
    'official_n': len(z),
    'model_neurons': len(model), 'model_neurons_in_v783': sum(r in zs for r in model),
    'ids_json_ids': len(allids), 'ids_json_ids_in_v783': sum(r in zs for r in allids),
}
out['pass'] = out['model_neurons'] == out['model_neurons_in_v783'] and out['ids_json_ids'] == out['ids_json_ids_in_v783']
(ortam.VERI / 'v783_dogrulama.json').write_text(json.dumps(out, indent=2) + '\n')
print(out)
