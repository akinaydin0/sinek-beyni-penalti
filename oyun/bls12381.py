#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bls12381.py - [tur3 2026-10-22] drand quicknet imzasını doğrulayan, BAĞIMLILIKSIZ saf Python BLS12-381 kodu.

Neden kendi kodumuz: paket indirmek (py_ecc, drand-client) Akın'ın onayını gerektiriyordu. Bu dosya yalnız
standart kütüphaneyi (hashlib) kullanır. Hız değil doğruluk için yazıldı: bir imza kontrolü bu Mac'te ~1-2 s.

Ne yapar (şema 'bls-unchained-g1-rfc9380', drand quicknet):
  mesaj    m   = SHA-256(tur numarası, 8 bayt big-endian)
  H(m)         = hash_to_curve(m) -> G1, RFC 9380 BLS12381G1_XMD:SHA-256_SSWU_RO_,
                 DST = "BLS_SIG_BLS12381G1_XMD:SHA-256_SSWU_RO_NUL_"
  imza     σ   ∈ G1 (48 bayt, sıkıştırılmış), açık anahtar pk ∈ G2 (96 bayt, sıkıştırılmış)
  geçerli  <=> e(σ, g2) == e(H(m), pk)   (ikisi bir arada: f(σ, -g2) · f(H(m), pk), sonra son üs alma = 1)

Kaynaklar ve sabitlerin kökeni:
  - p, r, h_eff, E': A', B', Z = 11 ve 11-izojeni katsayıları: RFC 9380 bölüm 8.8.1 ve Ek E.2
    (rfc-editor.org/rfc/rfc9380.html'den 22 Ekim 2026'da okundu).
  - Eğri y² = x³ + 4 (G1), y² = x³ + 4(1+u) (G2, M-twist), g2 üreteci: BLS12-381 standardı
    (sıkıştırılmış biçimi 0x93e02b60…; kod içinde eğri üstünde olduğu ve r. mertebeden olduğu da sınanır).
  - Sıkıştırma biçimi: ZCash BLS12-381 serileştirmesi (bayraklar: sıkıştırılmış / sonsuz / işaret).
Sınama (tests.py): RFC 9380 Ek J.9.1 test vektörleri (u[0], u[1], Q0, Q1, P) ve gerçek drand turları
(geçerli imza kabul, 1 bit değişmiş imza / başka tur / uydurma imza RED).

Sabit-zamanlı DEĞİLDİR; gizli anahtar işlemez, yalnız açık veriyi doğrular. Bu yüzden zamanlama sızıntısı
önemsizdir.
"""
from __future__ import annotations

import functools
import hashlib

# --------------------------------------------------------------------------- sabitler
P = 0x1a0111ea397fe69a4b1ba7b6434bacd764774b84f38512bf6730d2a0f6b0f6241eabfffeb153ffffb9feffffffffaaab
R = 0x73eda753299d7d483339d80809a1d80553bda402fffe5bfeffffffff00000001
H_EFF_G1 = 0xd201000000010001
Z_ABS = 0xd201000000010000          # BLS parametresi z = -0xd201000000010000 (Miller döngüsü |z| ile)
B_G1 = 4
DST_G1 = b"BLS_SIG_BLS12381G1_XMD:SHA-256_SSWU_RO_NUL_"

# RFC 9380 8.8.1: E': y'^2 = x'^3 + A' x' + B', Z = 11
A_ISO = 0x144698a3b8e9433d693a02c96d4982b0ea985383ee66a8d8e8981aefd881ac98936f8da0e0f97f5cf428082d584c1d
B_ISO = 0x12e2908d11688030018b12e8753eee3b2016c1f0f24f4070a0b9c14fcef35ef55a23215a316ceaa5d1cc48e98e172be0
Z_SSWU = 11

# RFC 9380 Ek E.2: 11-izojeni E' -> E (k_(i,j), j = 0, 1, ...)
K1 = [0x11a05f2b1e833340b809101dd99815856b303e88a2d7005ff2627b56cdb4e2c85610c2d5f2e62d6eaeac1662734649b7,
      0x17294ed3e943ab2f0588bab22147a81c7c17e75b2f6a8417f565e33c70d1e86b4838f2a6f318c356e834eef1b3cb83bb,
      0xd54005db97678ec1d1048c5d10a9a1bce032473295983e56878e501ec68e25c958c3e3d2a09729fe0179f9dac9edcb0,
      0x1778e7166fcc6db74e0609d307e55412d7f5e4656a8dbf25f1b33289f1b330835336e25ce3107193c5b388641d9b6861,
      0xe99726a3199f4436642b4b3e4118e5499db995a1257fb3f086eeb65982fac18985a286f301e77c451154ce9ac8895d9,
      0x1630c3250d7313ff01d1201bf7a74ab5db3cb17dd952799b9ed3ab9097e68f90a0870d2dcae73d19cd13c1c66f652983,
      0xd6ed6553fe44d296a3726c38ae652bfb11586264f0f8ce19008e218f9c86b2a8da25128c1052ecaddd7f225a139ed84,
      0x17b81e7701abdbe2e8743884d1117e53356de5ab275b4db1a682c62ef0f2753339b7c8f8c8f475af9ccb5618e3f0c88e,
      0x80d3cf1f9a78fc47b90b33563be990dc43b756ce79f5574a2c596c928c5d1de4fa295f296b74e956d71986a8497e317,
      0x169b1f8e1bcfa7c42e0c37515d138f22dd2ecb803a0c5c99676314baf4bb1b7fa3190b2edc0327797f241067be390c9e,
      0x10321da079ce07e272d8ec09d2565b0dfa7dccdde6787f96d50af36003b14866f69b771f8c285decca67df3f1605fb7b,
      0x6e08c248e260e70bd1e962381edee3d31d79d7e22c837bc23c0bf1bc24c6b68c24b1b80b64d391fa9c8ba2e8ba2d229]
K2 = [0x8ca8d548cff19ae18b2e62f4bd3fa6f01d5ef4ba35b48ba9c9588617fc8ac62b558d681be343df8993cf9fa40d21b1c,
      0x12561a5deb559c4348b4711298e536367041e8ca0cf0800c0126c2588c48bf5713daa8846cb026e9e5c8276ec82b3bff,
      0xb2962fe57a3225e8137e629bff2991f6f89416f5a718cd1fca64e00b11aceacd6a3d0967c94fedcfcc239ba5cb83e19,
      0x3425581a58ae2fec83aafef7c40eb545b08243f16b1655154cca8abc28d6fd04976d5243eecf5c4130de8938dc62cd8,
      0x13a8e162022914a80a6f1d5f43e7a07dffdfc759a12062bb8d6b44e833b306da9bd29ba81f35781d539d395b3532a21e,
      0xe7355f8e4e667b955390f7f0506c6e9395735e9ce9cad4d0a43bcef24b8982f7400d24bc4228f11c02df9a29f6304a5,
      0x772caacf16936190f3e0c63e0596721570f5799af53a1894e2e073062aede9cea73b3538f0de06cec2574496ee84a3a,
      0x14a7ac2a9d64a8b230b3f5b074cf01996e7f63c21bca68a81996e1cdf9822c580fa5b9489d11e2d311f7d99bbdcc5a5e,
      0xa10ecf6ada54f825e920b3dafc7a3cce07f8d1d7161366b74100da67f39883503826692abba43704776ec3a79a1d641,
      0x95fc13ab9e92ad4476d6e3eb3a56680f682b4ee96f7d03776df533978f31c1593174e4b4b7865002d6384d168ecdd0a,
      1]  # x_den monik (x'^10)
K3 = [0x90d97c81ba24ee0259d1f094980dcfa11ad138e48a869522b52af6c956543d3cd0c7aee9b3ba3c2be9845719707bb33,
      0x134996a104ee5811d51036d776fb46831223e96c254f383d0f906343eb67ad34d6c56711962fa8bfe097e75a2e41c696,
      0xcc786baa966e66f4a384c86a3b49942552e2d658a31ce2c344be4b91400da7d26d521628b00523b8dfe240c72de1f6,
      0x1f86376e8981c217898751ad8746757d42aa7b90eeb791c09e4a3ec03251cf9de405aba9ec61deca6355c77b0e5f4cb,
      0x8cc03fdefe0ff135caf4fe2a21529c4195536fbe3ce50b879833fd221351adc2ee7f8dc099040a841b6daecf2e8fedb,
      0x16603fca40634b6a2211e11db8f0a6a074a7d0d4afadb7bd76505c3d3ad5544e203f6326c95a807299b23ab13633a5f0,
      0x4ab0b9bcfac1bbcb2c977d027796b3ce75bb8ca2be184cb5231413c4d634f3747a87ac2460f415ec961f8855fe9d6f2,
      0x987c8d5333ab86fde9926bd2ca6c674170a05bfe3bdd81ffd038da6c26c842642f64550fedfe935a15e4ca31870fb29,
      0x9fc4018bd96684be88c9e221e4da1bb8f3abd16679dc26c1e8b6e6a1f20cabe69d65201c78607a360370e577bdba587,
      0xe1bba7a1186bdb5223abde7ada14a23c42a0ca7915af6fe06985e7ed1e4d43b9b3f7055dd4eba6f2bafaaebca731c30,
      0x19713e47937cd1be0dfd0b8f1d43fb93cd2fcbcb6caf493fd1183e416389e61031bf3a5cce3fbafce813711ad011c132,
      0x18b46a908f36f6deb918c143fed2edcc523559b8aaf0c2462e6bfe7f911f643249d9cdf41b44d606ce07c8a4d0074d8e,
      0xb182cac101b9399d155096004f53f447aa7b12a3426b08ec02710e807b4633f06c851c1919211f20d4c04f00b971ef8,
      0x245a394ad1eca9b72fc00ae7be315dc757b3b080d4c158013e6632d3c40659cc6cf90ad1c232a6442d9d3f5db980133,
      0x5c129645e44cf1102a159f748c4a3fc5e673d81d7e86568d9ab0f5d396a7ce46ba1049b6579afb7866b1e715475224b,
      0x15e6be4e990f03ce4ea50b3b42df2eb5cb181d8f84965a3957add4fa95af01b2b665027efec01c7704b456be69c8b604]
K4 = [0x16112c4c3a9c98b252181140fad0eae9601a6de578980be6eec3232b5be72e7a07f3688ef60c206d01479253b03663c1,
      0x1962d75c2381201e1a0cbd6c43c348b885c84ff731c4d59ca4a10356f453e01f78a4260763529e3532f6102c2e49a03d,
      0x58df3306640da276faaae7d6e8eb15778c4855551ae7f310c35a5dd279cd2eca6757cd636f96f891e2538b53dbf67f2,
      0x16b7d288798e5395f20d23bf89edb4d1d115c5dbddbcd30e123da489e726af41727364f2c28297ada8d26d98445f5416,
      0xbe0e079545f43e4b00cc912f8228ddcc6d19c9f0f69bbb0542eda0fc9dec916a20b15dc0fd2ededda39142311a5001d,
      0x8d9e5297186db2d9fb266eaac783182b70152c65550d881c5ecd87b6f0f5a6449f38db9dfa9cce202c6477faaf9b7ac,
      0x166007c08a99db2fc3ba8734ace9824b5eecfdfa8d0cf8ef5dd365bc400a0051d5fa9c01a58b1fb93d1a1399126a775c,
      0x16a3ef08be3ea7ea03bcddfabba6ff6ee5a4375efa1f4fd7feb34fd206357132b920f5b00801dee460ee415a15812ed9,
      0x1866c8ed336c61231a1be54fd1d74cc4f9fb0ce4c6af5920abc5750c4bf39b4852cfe2f7bb9248836b233d9d55535d4a,
      0x167a55cda70a6e1cea820597d94a84903216f763e13d87bb5308592e7ea7d4fbc7385ea3d529b35e346ef48bb8913f55,
      0x4d2f259eea405bd48f010a01ad2911d9c6dd039bb61a6290e591b36e636a5c871a5c29f4f83060400f8b49cba8f6aa8,
      0xaccbb67481d033ff5852c1e48c50c477f94ff8aefce42d28c0f9a88cea7913516f968986f7ebbea9684b529e2561092,
      0xad6b9514c767fe3c3613144b45f1496543346d98adf02267d5ceef9a00d9b8693000763e3b90ac11e99b138573345cc,
      0x2660400eb2e4f3b628bdd0d53cd76f2bf565b94e72927c1cb748df27942480e420517bd8714cc80d1fadc1326ed06f7,
      0xe0fa1d816ddc03e6b24255e0d7819c171c40f65e273b853324efcd6356caa205ca2f570f13497804415473a1d634b8f,
      1]  # y_den monik (x'^15)

# G2 üreteci (x = x0 + x1·u, y = y0 + y1·u)
G2_GEN = ((0x024aa2b2f08f0a91260805272dc51051c6e47ad4fa403b02b4510b647ae3d1770bac0326a805bbefd48056c8c121bdb8,
           0x13e02b6052719f607dacd3a088274f65596bd0d09920b61ab5da61bbdc7f5049334cf11213945d57e5ac7d055d042b7e),
          (0x0ce5d527727d6e118cc9cdc6da2e351aadfd9baa8cbdd3a76d429a695160d12c923ac9cc3baca289e193548608b82801,
           0x0606c4a02ea734cc32acd2b02bc28b99cb3e287e85a763af267492ab572e99ab3f370d275cec1da1aaa9075ff05f79be))

HALF_P = (P - 1) // 2


class BLSHatasi(ValueError):
    pass


# --------------------------------------------------------------------------- Fp
def _inv(a):
    a %= P
    if a == 0:
        raise ZeroDivisionError("Fp: 0'ın tersi yok")
    return pow(a, P - 2, P)


def _is_square(a):
    a %= P
    return a == 0 or pow(a, HALF_P, P) == 1


def _sqrt(a):
    a %= P
    s = pow(a, (P + 1) // 4, P)  # p ≡ 3 (mod 4)
    return s if s * s % P == a else None


def _sgn0(a):
    return a % P % 2


# --------------------------------------------------------------------------- Fp2 = Fp[u]/(u²+1)
def f2_add(a, b):
    return ((a[0] + b[0]) % P, (a[1] + b[1]) % P)


def f2_sub(a, b):
    return ((a[0] - b[0]) % P, (a[1] - b[1]) % P)


def f2_neg(a):
    return ((-a[0]) % P, (-a[1]) % P)


def f2_mul(a, b):
    a0, a1 = a
    b0, b1 = b
    return ((a0 * b0 - a1 * b1) % P, (a0 * b1 + a1 * b0) % P)


def f2_muls(a, k):
    return (a[0] * k % P, a[1] * k % P)


def f2_inv(a):
    a0, a1 = a
    t = _inv(a0 * a0 + a1 * a1)
    return (a0 * t % P, (-a1) * t % P)


def f2_sqrt(a):
    """Fp2 karekökü (yoksa None). Norm yöntemi: p ≡ 3 (mod 4)."""
    a0, a1 = a[0] % P, a[1] % P
    if a1 == 0:
        s = _sqrt(a0)
        if s is not None:
            return (s, 0)
        s = _sqrt(-a0)
        return (0, s) if s is not None else None
    n = _sqrt(a0 * a0 + a1 * a1)
    if n is None:
        return None
    inv2 = _inv(2)
    for t in ((a0 + n) * inv2 % P, (a0 - n) * inv2 % P):
        x0 = _sqrt(t)
        if x0 is not None and x0 != 0:
            x1 = a1 * _inv(2 * x0) % P
            if f2_mul((x0, x1), (x0, x1)) == (a0, a1):
                return (x0, x1)
    return None


# --------------------------------------------------------------------------- eğri noktaları (afin, None = sonsuz)
def _g1_on_curve(pt):
    if pt is None:
        return True
    x, y = pt
    return (y * y - x * x * x - B_G1) % P == 0


def _g1_add(p1, p2):
    if p1 is None:
        return p2
    if p2 is None:
        return p1
    x1, y1 = p1
    x2, y2 = p2
    if x1 == x2:
        if (y1 + y2) % P == 0:
            return None
        m = 3 * x1 * x1 * _inv(2 * y1) % P
    else:
        m = (y2 - y1) * _inv(x2 - x1) % P
    x3 = (m * m - x1 - x2) % P
    return (x3, (m * (x1 - x3) - y1) % P)


def _g1_mul(pt, k):
    out = None
    add = pt
    while k:
        if k & 1:
            out = _g1_add(out, add)
        add = _g1_add(add, add)
        k >>= 1
    return out


B_G2 = (4, 4)  # 4(1+u)


def _g2_on_curve(pt):
    if pt is None:
        return True
    x, y = pt
    return f2_sub(f2_mul(y, y), f2_add(f2_mul(f2_mul(x, x), x), B_G2)) == (0, 0)


def _g2_add(p1, p2):
    if p1 is None:
        return p2
    if p2 is None:
        return p1
    x1, y1 = p1
    x2, y2 = p2
    if x1 == x2:
        if f2_add(y1, y2) == (0, 0):
            return None
        m = f2_mul(f2_muls(f2_mul(x1, x1), 3), f2_inv(f2_muls(y1, 2)))
    else:
        m = f2_mul(f2_sub(y2, y1), f2_inv(f2_sub(x2, x1)))
    x3 = f2_sub(f2_sub(f2_mul(m, m), x1), x2)
    return (x3, f2_sub(f2_mul(m, f2_sub(x1, x3)), y1))


def _g2_mul(pt, k):
    out = None
    add = pt
    while k:
        if k & 1:
            out = _g2_add(out, add)
        add = _g2_add(add, add)
        k >>= 1
    return out


# --------------------------------------------------------------------------- sıkıştırılmış noktaları açma
def g1_decompress(data: bytes):
    if len(data) != 48:
        raise BLSHatasi(f"G1 noktası 48 bayt olmalı, {len(data)} bayt geldi")
    b = bytearray(data)
    c, inf, s = (b[0] >> 7) & 1, (b[0] >> 6) & 1, (b[0] >> 5) & 1
    if not c:
        raise BLSHatasi("G1: sıkıştırma bayrağı yok")
    b[0] &= 0x1F
    x = int.from_bytes(b, "big")
    if inf:
        raise BLSHatasi("G1: sonsuzdaki nokta imza olamaz")
    if x >= P:
        raise BLSHatasi("G1: x >= p")
    y = _sqrt(x * x * x + B_G1)
    if y is None:
        raise BLSHatasi("G1: x eğri üzerinde değil")
    if (y > HALF_P) != bool(s):
        y = P - y
    pt = (x, y)
    if _g1_mul(pt, R) is not None:
        raise BLSHatasi("G1: nokta r. mertebeden alt grupta değil")
    return pt


def g2_decompress(data: bytes):
    if len(data) != 96:
        raise BLSHatasi(f"G2 noktası 96 bayt olmalı, {len(data)} bayt geldi")
    b = bytearray(data)
    c, inf, s = (b[0] >> 7) & 1, (b[0] >> 6) & 1, (b[0] >> 5) & 1
    if not c or inf:
        raise BLSHatasi("G2: sıkıştırma bayrağı yok ya da sonsuz nokta")
    b[0] &= 0x1F
    x1 = int.from_bytes(b[:48], "big")
    x0 = int.from_bytes(b[48:], "big")
    if x0 >= P or x1 >= P:
        raise BLSHatasi("G2: koordinat >= p")
    x = (x0, x1)
    y = f2_sqrt(f2_add(f2_mul(f2_mul(x, x), x), B_G2))
    if y is None:
        raise BLSHatasi("G2: x eğri üzerinde değil")
    buyuk = (y[1] > HALF_P) if y[1] != 0 else (y[0] > HALF_P)
    if buyuk != bool(s):
        y = f2_neg(y)
    pt = (x, y)
    if _g2_mul(pt, R) is not None:
        raise BLSHatasi("G2: nokta r. mertebeden alt grupta değil")
    return pt


# --------------------------------------------------------------------------- RFC 9380 hash_to_curve (G1)
def expand_message_xmd(msg: bytes, dst: bytes, len_in_bytes: int) -> bytes:
    b_in, s_in = 32, 64
    ell = -(-len_in_bytes // b_in)
    if ell > 255 or len(dst) > 255 or len_in_bytes > 65535:
        raise BLSHatasi("expand_message_xmd: uzunluk sınırı")
    dst_prime = dst + bytes([len(dst)])
    msg_prime = bytes(s_in) + msg + len_in_bytes.to_bytes(2, "big") + b"\x00" + dst_prime
    b0 = hashlib.sha256(msg_prime).digest()
    bi = hashlib.sha256(b0 + b"\x01" + dst_prime).digest()
    out = [bi]
    for i in range(2, ell + 1):
        bi = hashlib.sha256(bytes(x ^ y for x, y in zip(b0, bi)) + bytes([i]) + dst_prime).digest()
        out.append(bi)
    return b"".join(out)[:len_in_bytes]


def hash_to_field(msg: bytes, count: int, dst: bytes):
    L = 64
    u = expand_message_xmd(msg, dst, count * L)
    return [int.from_bytes(u[L * i:L * (i + 1)], "big") % P for i in range(count)]


def map_to_curve_sswu(u):
    """RFC 9380 6.6.2 (basit SWU), E' üzerinde."""
    A, B, Z = A_ISO, B_ISO, Z_SSWU
    u %= P
    t = (Z * Z * pow(u, 4, P) + Z * u * u) % P
    if t == 0:
        x1 = B * _inv(Z * A) % P
    else:
        x1 = (-B) * _inv(A) * (1 + _inv(t)) % P
    gx1 = (x1 * x1 * x1 + A * x1 + B) % P
    x2 = Z * u * u * x1 % P
    gx2 = (x2 * x2 * x2 + A * x2 + B) % P
    if _is_square(gx1):
        x, y = x1, _sqrt(gx1)
    else:
        x, y = x2, _sqrt(gx2)
    if _sgn0(u) != _sgn0(y):
        y = (-y) % P
    return x, y


def _poly(coeffs, x):
    acc = 0
    for c in reversed(coeffs):
        acc = (acc * x + c) % P
    return acc


def iso_map_g1(pt):
    xp, yp = pt
    x = _poly(K1, xp) * _inv(_poly(K2, xp)) % P
    y = yp * _poly(K3, xp) * _inv(_poly(K4, xp)) % P
    return x, y


def map_to_curve_g1(u):
    return iso_map_g1(map_to_curve_sswu(u))


def hash_to_g1(msg: bytes, dst: bytes = DST_G1):
    u0, u1 = hash_to_field(msg, 2, dst)
    q = _g1_add(map_to_curve_g1(u0), map_to_curve_g1(u1))
    return _g1_mul(q, H_EFF_G1)


# --------------------------------------------------------------------------- Fp12 = Fp[w]/(w^12 - 2w^6 + 2)
# Fp2 gömmesi: a + b·u  ->  (a - b) + b·w^6   (çünkü u = w^6 - 1, (w^6-1)^2 = -1)
# M-twist: E'(Fp2) noktası (x', y')  ->  E(Fp12) noktası (x'/w², y'/w³)   (w^6 = 1 + u)
def _f12_mul(a, b):
    c = [0] * 23
    for i, ai in enumerate(a):
        if ai:
            for j, bj in enumerate(b):
                if bj:
                    c[i + j] += ai * bj
    for k in range(22, 11, -1):
        ck = c[k]
        if ck:
            c[k - 6] += 2 * ck
            c[k - 12] -= 2 * ck
    return [x % P for x in c[:12]]


def _f12_sqr(a):
    c = [0] * 23
    for i in range(12):
        ai = a[i]
        if not ai:
            continue
        c[2 * i] += ai * ai
        t = 2 * ai
        for j in range(i + 1, 12):
            if a[j]:
                c[i + j] += t * a[j]
    for k in range(22, 11, -1):
        ck = c[k]
        if ck:
            c[k - 6] += 2 * ck
            c[k - 12] -= 2 * ck
    return [x % P for x in c[:12]]


F12_ONE = [1] + [0] * 11


def _f12_pow(a, e):
    # 4 bitlik pencere
    tab = [F12_ONE, a]
    for _ in range(14):
        tab.append(_f12_mul(tab[-1], a))
    out = F12_ONE
    bits = bin(e)[2:]
    bits = "0" * ((-len(bits)) % 4) + bits
    for i in range(0, len(bits), 4):
        if out is not F12_ONE:
            for _ in range(4):
                out = _f12_sqr(out)
        d = int(bits[i:i + 4], 2)
        if d:
            out = tab[d] if out is F12_ONE else _f12_mul(out, tab[d])
    return out


def _line(lam, xt, yt, xp, yp):
    """w³ · (doğru T'den eğim lam ile, P'de değerlendirilmiş): (yT - lam·xT) + (lam·xP)·w² - yP·w³.
    w³ çarpanı Fp4 alt cisminde olduğu için son üs almada yok olur."""
    c0 = f2_sub(yt, f2_mul(lam, xt))
    c2 = f2_muls(lam, xp)
    f = [0] * 12
    f[0] = (c0[0] - c0[1]) % P
    f[6] = c0[1]
    f[2] = (c2[0] - c2[1]) % P
    f[8] = c2[1]
    f[3] = (-yp) % P
    return f


def _miller(q, p):
    """f_{|z|,Q}(P), Q ∈ G2 (E' üzerinde), P ∈ G1."""
    xp, yp = p
    t = q
    f = F12_ONE
    for bit in bin(Z_ABS)[3:]:
        xt, yt = t
        lam = f2_mul(f2_muls(f2_mul(xt, xt), 3), f2_inv(f2_muls(yt, 2)))
        f = _f12_mul(_f12_sqr(f), _line(lam, xt, yt, xp, yp))
        x3 = f2_sub(f2_sub(f2_mul(lam, lam), xt), xt)
        t = (x3, f2_sub(f2_mul(lam, f2_sub(xt, x3)), yt))
        if bit == "1":
            xt, yt = t
            xq, yq = q
            if xt == xq:
                raise BLSHatasi("Miller döngüsü: beklenmeyen dikey doğru")
            lam = f2_mul(f2_sub(yq, yt), f2_inv(f2_sub(xq, xt)))
            f = _f12_mul(f, _line(lam, xt, yt, xp, yp))
            x3 = f2_sub(f2_sub(f2_mul(lam, lam), xt), xq)
            t = (x3, f2_sub(f2_mul(lam, f2_sub(xt, x3)), yt))
    return f


FINAL_EXP = (P ** 12 - 1) // R


def pairing_product_is_one(pairs):
    """pairs: [(P ∈ G1, Q ∈ G2), ...]  ->  ∏ e(P, Q) == 1 ?"""
    f = F12_ONE
    for p, q in pairs:
        f = _f12_mul(f, _miller(q, p))
    return _f12_pow(f, FINAL_EXP) == F12_ONE


# --------------------------------------------------------------------------- drand
def drand_mesaji(round_no: int) -> bytes:
    return hashlib.sha256(int(round_no).to_bytes(8, "big")).digest()


@functools.lru_cache(maxsize=8)
def _pk(pk_hex: str):
    return g2_decompress(bytes.fromhex(pk_hex))


@functools.lru_cache(maxsize=64)
def dogrula_drand(round_no: int, signature_hex: str, public_key_hex: str, dst: bytes = DST_G1):
    """(geçerli_mi, açıklama). Şema bls-unchained-g1-rfc9380 (drand quicknet)."""
    try:
        sig = g1_decompress(bytes.fromhex(signature_hex))
    except (ValueError, BLSHatasi) as e:
        return False, f"imza açılamadı: {e}"
    try:
        pk = _pk(public_key_hex.lower())
    except (ValueError, BLSHatasi) as e:
        return False, f"açık anahtar açılamadı: {e}"
    hm = hash_to_g1(drand_mesaji(round_no), dst)
    g2n = (G2_GEN[0], f2_neg(G2_GEN[1]))
    ok = pairing_product_is_one([(sig, g2n), (hm, pk)])
    return ok, ("e(imza, g2) = e(H(tur), açık anahtar)" if ok else "eşleştirme eşitliği TUTMUYOR (imza geçersiz)")


def oz_sinama():
    """Kendi kendine sınama: üreteç eğri üstünde ve r. mertebeden mi?"""
    assert _g2_on_curve(G2_GEN), "g2 üreteci eğri üzerinde değil"
    assert _g2_mul(G2_GEN, R) is None, "g2 üreteci r. mertebeden değil"
    return True


if __name__ == "__main__":
    import sys
    import time
    if len(sys.argv) != 4:
        print("kullanım: python3.12 -I bls12381.py <tur> <imza hex> <açık anahtar hex>")
        sys.exit(2)
    t0 = time.time()
    ok, msg = dogrula_drand(int(sys.argv[1]), sys.argv[2].lower(), sys.argv[3].lower())
    print(("GEÇERLİ: " if ok else "GEÇERSİZ: ") + msg, f"({time.time() - t0:.1f} s)")
    sys.exit(0 if ok else 1)
