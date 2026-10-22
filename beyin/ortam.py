"""Ortak ortam ayarları: derleyici düzeltmesi ve sabit yollar.

Homebrew python3.12'nin sysconfig'i var olmayan bir SDK'ya
(/Library/Developer/CommandLineTools/SDKs/MacOSX15.sdk) işaret ediyor; Brian2'nin
Cython derlemesi bu yüzden bağlanamıyor. Burada Xcode'un gerçek SDK yolunu
ortam değişkenleriyle veriyoruz. brian2 import edilmeden önce çağrılmalı.
"""
import os
import subprocess
from pathlib import Path

BEYIN = Path(__file__).resolve().parent
PROJE = BEYIN.parent
VERI = PROJE / 'veri'
CIKTI = PROJE / 'cikti'
SHIU_REPO = BEYIN / 'indirilen' / 'shiu_model'
SHIU_COMMIT = '91bdd1e7dcf193f3e7ca5a8933497fcef63b7960'
PATH_COMP = SHIU_REPO / 'Completeness_783.csv'
PATH_CON = SHIU_REPO / 'Connectivity_783.parquet'
ANNOT = BEYIN / 'indirilen' / 'flywire_annotations' / 'Supplemental_file1_neuron_annotations.tsv'
ANNOT_COMMIT = 'a83b2776d60d5764cef36b927f5f9679c16c47a2'


def derleyici_ayarla():
    try:
        sdk = subprocess.check_output(['xcrun', '--show-sdk-path'], text=True).strip()
    except Exception:
        return None
    os.environ['SDKROOT'] = sdk
    os.environ['LDCXXSHARED'] = f'clang++ -bundle -undefined dynamic_lookup -isysroot {sdk}'
    os.environ['LDSHARED'] = f'clang -bundle -undefined dynamic_lookup -isysroot {sdk}'
    return sdk


def shiu_model_yukle():
    """Shiu et al. deposundaki model.py'yi (sabit commit) dosya yolundan yükler.

    Klasörü sys.path'e eklemiyoruz; yalnızca bu tek dosya çalıştırılır
    (kodu okundu: brian2/pandas/joblib dışında bir şey yapmıyor).
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location('shiu_model_py', SHIU_REPO / 'model.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
