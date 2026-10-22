"""DONDURULMUŞ OKUMA VE EŞLEME (frozen readout + mapping).

Bu dosya ve ids.json birlikte özetlenir (readout_sha256 = SHA-256(esleme.py baytları
+ ids.json baytları), bkz. dondur.py). Dondurulduktan sonra burada tek bir sayı
değişirse kick.py gerçek (prova olmayan) koşuyu reddeder.

Burada üç şey tanımlıdır:
  1. SAHNE -> GİRDİ: kalecinin konumu, LC10 görsel nöronlarına giden Poisson
     hızlarına nasıl çevrilir.
  2. OKUMA: 1 s'lik denemede inen nöron spike sayılarından steer ve power.
  3. EŞLEME: steer/power -> nişan (x, y) ve top hızı.

Koordinatlar SOZLESME.md ile aynı: x şutu atanın sağına pozitif, y yukarı (metre).
Sinek penaltı noktasında kaleye bakıyor; sineğin sağı = şutörün sağı = +x.

SABİTLERİN KÖKENİ
- Kale ve top ölçüleri IFAB (SOZLESME.md).
- READOUT_GAIN_M = 3.2, V_MIN/V_MAX = 18/30 m/s: görev tanımında verildi.
- R_LC10_HZ, P9_DRIVE_HZ ve P_SCALE: pilot.py'nin yön-kör pilotundan, önceden
  yazılmış bir kurala göre HESAPLANDI (yalnızca ortadaki kaleci sahnesi, yalnızca
  toplam spike sayılarına bakıldı; sol/sağ farkı pilotta hiç hesaplanmadı).
  Kural ve pilot sonuçları: ../veri/pilot.json. Bu üç sabit kalibrasyondan ÖNCE
  yazıldı ve kalibrasyon sonuçlarına göre değiştirilmedi.
"""
import math

ESLEME_SURUMU = '1.0'

# ---------------------------------------------------------------- deneme
T_TRIAL_S = 1.0           # bir beyin denemesi = 1 s biyolojik zaman (Shiu varsayılanı t_run)

# ---------------------------------------------------------------- kale/top (IFAB)
POST_X_M = 3.66           # direkler x = ±3.66
BAR_Y_M = 2.44            # üst direk yüksekliği
BALL_R_M = 0.11           # top yarıçapı (çap 0.22)
SAFETY_M = 0.15           # direk/üst direk içi güvenlik payı (top merkezi için)

# ---------------------------------------------------------------- 1. SAHNE -> GİRDİ
# Görsel girdi: TÜM LC10 alt tipleri (a, b, c-1, c-2, d, e, f), sol ve sağ optik lob.
# Hangi alt tipin "daha iyi" çalıştığına bakılmadı; hepsi eşit ağırlıkta.
LC10_TYPES = ['LC10a', 'LC10b', 'LC10c-1', 'LC10c-2', 'LC10d', 'LC10e', 'LC10f']
R_LC10_HZ = 10.0          # pilot.py (veri/pilot.json)
K_BIAS = 1.0              # yan eğilimi: kaleci direkteyse o taraf 2x, öbür taraf 0
X_BIAS_REF_M = POST_X_M   # b = clip(keeper_x / 3.66, -1, 1)
# Kaleci sahnede bir nesne: sağdaysa (x>0) sineğin SAĞ gözü / sağ LC10'ları daha çok uyarılır.
#   r_R = R_LC10 * (1 + K_BIAS * b),  r_L = R_LC10 * (1 - K_BIAS * b)
# Ortada (b = 0) iki taraf eşit uyarılır: kaleci iki gözün de gördüğü ön bölgede.
P9_DRIVE_HZ = 0.0        # pilot.py (veri/pilot.json); 0 = kapalı
CAL_KEEPER_X_M = 1.83     # kalibrasyon sahneleri: kaleci x = -1.83 / 0 / +1.83 (direğe yarı yol)


def sahne_bias(keeper_x):
    return max(-1.0, min(1.0, float(keeper_x) / X_BIAS_REF_M))


def girdi_hizlari(keeper_x, ids, r_lc10=None, p9_hz=None):
    """{root_id(int): Hz} döndürür. ids: ids.json içeriği (dict)."""
    r_lc10 = R_LC10_HZ if r_lc10 is None else r_lc10
    p9_hz = P9_DRIVE_HZ if p9_hz is None else p9_hz
    b = sahne_bias(keeper_x)
    r = {'L': r_lc10 * (1.0 - K_BIAS * b), 'R': r_lc10 * (1.0 + K_BIAS * b)}
    out = {}
    for t in LC10_TYPES:
        for s in ('L', 'R'):
            for rid in ids['groups'][f'{t}_{s}']['root_ids_v783']:
                if r[s] > 0:
                    out[int(rid)] = r[s]
    if p9_hz:
        for s in ('L', 'R'):
            for rid in ids['groups'][f'P9_{s}']['root_ids_v783']:
                out[int(rid)] = float(p9_hz)
    return out


def tum_girdi_kimlikleri(ids):
    """Ağa bağlanacak bütün olası girdi nöronları (hızları denemeye göre değişir)."""
    out = []
    for t in LC10_TYPES:
        for s in ('L', 'R'):
            out += [int(r) for r in ids['groups'][f'{t}_{s}']['root_ids_v783']]
    for s in ('L', 'R'):
        out += [int(r) for r in ids['groups'][f'P9_{s}']['root_ids_v783']]
    return out


# ---------------------------------------------------------------- 2. OKUMA
# Yang et al. 2024: DNa01, DNa02, DNb05, DNg13 kendi tarafına döndürür (ipsiversive),
# DNb06 karşı tarafa (contraversive). Bu yüzden sağa dönüş:
READOUT = ('steer = (Rturn - Lturn) / (Rturn + Lturn + 1); '
           'Rturn = DNa01_R + DNa02_R + DNb05_R + DNg13_R + DNb06_L; power = oDN1_L + oDN1_R')
RTURN = ['DNa01_R', 'DNa02_R', 'DNb05_R', 'DNg13_R', 'DNb06_L']
LTURN = ['DNa01_L', 'DNa02_L', 'DNb05_L', 'DNg13_L', 'DNb06_R']
POWER = ['oDN1_L', 'oDN1_R']
COUNT_KEYS = ['DNa01_L', 'DNa01_R', 'DNa02_L', 'DNa02_R', 'DNb05_L', 'DNb05_R', 'DNg13_L', 'DNg13_R',
              'DNb06_L', 'DNb06_R', 'oDN1_L', 'oDN1_R', 'P9_L', 'P9_R']
STEER_NEURONS = LTURN + RTURN   # raster ve decision_ms için


def oku(counts):
    """counts: {grup: spike sayısı (1 s)} -> (steer, power, rturn, lturn)."""
    rturn = sum(counts[k] for k in RTURN)
    lturn = sum(counts[k] for k in LTURN)
    steer = (rturn - lturn) / (rturn + lturn + 1)
    power = sum(counts[k] for k in POWER)
    return steer, power, rturn, lturn


def karar_ms(steer_spike_times_s):
    """decision_ms: dönüş nöronlarının (10 nöron) spike'larının yarısının atıldığı an (ms).

    Hiç spike yoksa deneme sonu (1000 ms) döner.
    """
    ts = sorted(steer_spike_times_s)
    if not ts:
        return int(round(T_TRIAL_S * 1000))
    k = (len(ts) - 1) // 2          # alt medyan: gerçekten atılmış bir spike'ın zamanı
    return int(round(ts[k] * 1000))


# ---------------------------------------------------------------- 3. EŞLEME
READOUT_GAIN_M = 3.2                                  # aim x = steer * 3.2 m
X_CLIP_M = POST_X_M - BALL_R_M - SAFETY_M             # 3.40 m; |steer| < 1 olduğu için pratikte hiç kesmez
Y_MIN_M = BALL_R_M + 0.09                             # 0.20 m: yerden sert şut (top merkezi)
Y_MAX_M = BAR_Y_M - BALL_R_M - SAFETY_M - 0.08        # 2.10 m: üst direğin altı
V_MIN_MPS = 18.0
V_MAX_MPS = 30.0
P_SCALE = 16            # pilot.py (veri/pilot.json): seçilen koşulda power medyanı


def _doygun(power):
    """0 -> 0, P_SCALE -> 0.632, sonsuz -> 1 (yumuşak doyum, sınırda kesme yok)."""
    return 1.0 - math.exp(-float(power) / float(P_SCALE))


def esle(steer, power):
    """(aim_x, aim_y, speed_mps). Sabit, önceden yazılmış eşleme."""
    ax = max(-X_CLIP_M, min(X_CLIP_M, steer * READOUT_GAIN_M))
    f = _doygun(power)
    ay = Y_MIN_M + (Y_MAX_M - Y_MIN_M) * f   # daha çok ileri sürüş -> daha yüksek
    v = V_MIN_MPS + (V_MAX_MPS - V_MIN_MPS) * f  # daha çok ileri sürüş -> daha hızlı
    return round(ax, 3), round(ay, 3), round(v, 2)


def sabitler():
    """JSON'a yazılacak, belgelenmiş sabitler."""
    return {
        'ESLEME_SURUMU': ESLEME_SURUMU, 'T_TRIAL_S': T_TRIAL_S,
        'LC10_TYPES': LC10_TYPES, 'R_LC10_HZ': R_LC10_HZ, 'K_BIAS': K_BIAS, 'X_BIAS_REF_M': X_BIAS_REF_M,
        'P9_DRIVE_HZ': P9_DRIVE_HZ, 'CAL_KEEPER_X_M': CAL_KEEPER_X_M,
        'RTURN': RTURN, 'LTURN': LTURN, 'POWER': POWER,
        'READOUT_GAIN_M': READOUT_GAIN_M, 'X_CLIP_M': X_CLIP_M, 'Y_MIN_M': Y_MIN_M, 'Y_MAX_M': Y_MAX_M,
        'V_MIN_MPS': V_MIN_MPS, 'V_MAX_MPS': V_MAX_MPS, 'P_SCALE': P_SCALE,
        'aim_y': 'Y_MIN + (Y_MAX - Y_MIN) * (1 - exp(-power / P_SCALE))',
        'speed': 'V_MIN + (V_MAX - V_MIN) * (1 - exp(-power / P_SCALE))',
        'aim_x': 'clip(steer * READOUT_GAIN_M, -X_CLIP_M, X_CLIP_M)',
        'decision_ms': 'lower-median spike time of the 10 turning neurons, ms (1000 if silent)',
    }
