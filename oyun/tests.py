#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests.py - penaltı motoru testleri. Düz betik olarak çalışır (pytest gerekmez):
    python3.12 -I tests.py
[tur3 2026-10-22] test_tur3_* testleri yeni akışı (Hunter açık, kayma, drand beacon + BLS, kurallar, kod özetleri,
beyin tohumu, verify etiketleri ve kurcalama) sınar; ağa çıkmaz.
[tur3b 2026-10-22] test_tur3b_* testleri balistik kaleciyi (uçuş fiziği, adım/sıçrama, tutuştan sonra eller) ve
şut sapmasını (seçenek B: formül, KAT, dağılım, determinizm, skor, şablon kuralları, verify ve JS) sınar.
pytest varsa 'pytest tests.py' de çalışır (fonksiyonlar test_ ile başlar).
"""
from __future__ import annotations

import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import penalty_model as pm  # noqa: E402
from commit import commit_digest  # noqa: E402

CFG = pm.load_json(os.path.join(HERE, "config_prova.json"))
KP = pm.keeper_params(CFG)
STUB = pm.load_json(os.path.join(HERE, "stub", "stub_beyin_kararlari.json"))
LEAVES = [round(-0.60 + 0.05 * i, 2) for i in range(19)]  # -0.60 ... +0.30


def plan(dive, leave=-0.19, u_catch=0.5):
    return {"dive_dir": dive, "leave_drawn_s": leave, "u_catch": u_catch, "u_keep": 0.0}


def kick(x, y, v, p, keeper_x=0.0, cfg=CFG):
    return pm.simulate_kick(cfg, pm.keeper_params(cfg), {"x": x, "y": y}, v, p, keeper_x)


def test_keeper_numbers_from_ratings():
    assert abs(KP["reaction_s"] - 0.248) < 0.0005, KP["reaction_s"]
    # [tur3b 2026-10-22] reach_m artık bir sınır değil: kör dalışta (ortalama çıkış -0,19 s) 0,50 s'deki parmak ucu
    # erişimi. Eski model 2,90 m'de durup havada asılı kalıyordu; balistik modelde ~3,3 m (MODEL.md bölüm 2).
    assert 3.0 < KP["reach_m"] < 3.6, KP["reach_m"]
    assert abs(KP["v_dive"] - 4.2) < 1e-9


def test_24ms_reaches_line_in_047_052():
    # centre and inner aims: 0.47-0.52 s (brief)
    for x, y in [(0.0, 1.0), (0.0, 0.3), (-2.0, 1.0), (2.5, 0.5), (-1.0, 2.0), (1.5, 1.5)]:
        r = kick(x, y, 24.0, plan("stay"))
        ft = r["flight_time"]
        assert 0.47 <= ft <= 0.52, (x, y, ft)
        assert abs(r["cross_goal"][0] - x) < 1e-3 and abs(r["cross_goal"][1] - y) < 1e-3, r["cross_goal"]
    # corners are ~0.4-0.7 m further away (and the ball slows by drag), so 0.52-0.54 s
    for x, y in [(-2.9, 0.9), (3.0, 1.5), (3.3, 2.2), (-3.3, 0.3)]:
        ft = kick(x, y, 24.0, plan("stay"))["flight_time"]
        assert 0.50 <= ft <= 0.545, (x, y, ft)


def test_fast_top_corner_unsaveable_without_early_correct_dive():
    # 28 m/s into the keeper's top-left corner (+x = keeper's left)
    for x, y in [(3.2, 2.1), (2.7, 1.9)]:
        for lv in LEAVES:
            assert kick(x, y, 28.0, plan("right", lv))["outcome"] == "goal", ("wrong side", x, y, lv)
            if lv >= 0.0:
                assert kick(x, y, 28.0, plan("left", lv))["outcome"] == "goal", ("late correct", x, y, lv)
        assert kick(x, y, 28.0, plan("stay"))["outcome"] == "goal", ("stay", x, y)
    # the far top corner is out of his envelope even with the best timing
    assert all(kick(3.2, 2.1, 28.0, plan("left", lv))["outcome"] == "goal" for lv in LEAVES)
    # a slightly less extreme top-corner shot needs exactly that: an early, correct dive
    early_saves = [lv for lv in LEAVES if lv < 0.0 and kick(2.7, 1.9, 28.0, plan("left", lv))["outcome"] == "save"]
    assert early_saves, "no early correct dive saves the (2.7, 1.9) shot"


def test_slow_centre_shot_saved():
    for x, y in [(0.3, 0.8), (-0.4, 1.2), (0.0, 0.4)]:
        for kx in (0.0, 0.25):
            for u in (0.01, 0.99):
                r = kick(x, y, 12.0, plan("stay", u_catch=u), keeper_x=kx)
                assert r["outcome"] == "save", (x, y, kx, r["outcome"], r["keeper_gap"])
    # and a slow centre shot is caught more often than parried (Handling roll)
    r = kick(0.3, 0.8, 12.0, plan("stay", u_catch=0.01))
    assert r["contact"]["type"] == "catch"


def test_panenka_beats_early_wrong_way_diver():
    r = kick(0.0, 1.0, 12.0, plan("left", -0.19))
    assert r["outcome"] == "goal"


def test_wide_over_post():
    assert kick(-4.1, 0.7, 25.0, plan("left"))["outcome"] == "wide"
    assert kick(1.6, 2.8, 21.0, plan("right"))["outcome"] == "over"
    r = kick(3.72, 1.0, 25.0, plan("right"))
    assert r["outcome"] == "post" and r["event"]["type"] == "post_left_of_keeper", r["event"]
    r = kick(-1.0, 2.50, 25.0, plan("left"))
    assert r["outcome"] == "post" and r["event"]["type"] == "crossbar", r["event"]


def test_determinism_same_seed():
    a = pm.dumps_readable(pm.run(CFG, STUB))
    b = pm.dumps_readable(pm.run(copy.deepcopy(CFG), copy.deepcopy(STUB)))
    assert a == b
    p1 = pm.draw_plan(CFG, CFG["keeper_seeds"][0], 1)
    p2 = pm.draw_plan(CFG, CFG["keeper_seeds"][0], 1)
    assert p1 == p2
    p3 = pm.draw_plan(CFG, CFG["keeper_seeds"][0] + 1, 1)
    assert p3["u"] != p1["u"]


def test_plan_does_not_depend_on_shot():
    # the keeper plan is a function of (seed, kick number) only
    import inspect
    assert list(inspect.signature(pm.draw_plan).parameters) == ["cfg", "kseed", "n"]


def test_contract_fields():
    log = pm.run(CFG, STUB)
    for key in ("run_id", "commit_sha256", "seed", "keeper", "kicks"):
        assert key in log
    assert log["prova"] is True and log["stub"] is True
    outs = set()
    for k in log["kicks"]:
        s, kp = k["shot"], k["keeper"]
        for key in ("aim", "speed_mps", "flight_time_s", "trajectory"):
            assert key in s
        for key in ("dive_dir", "leave_time_s", "reaction_s", "reach_m", "contact"):
            assert key in kp
        assert kp["dive_dir"] in ("left", "right", "stay")
        assert k["outcome"] in ("goal", "save", "post", "wide", "over")
        outs.add(k["outcome"])
        if kp["contact"]:
            assert kp["contact"]["type"] in ("catch", "parry", "fingertip")
            assert set(("t", "pos", "type")) <= set(kp["contact"])
        tr = s["trajectory"]
        assert tr[0] == [0.0, 0.0, 0.11, 11.0]
        for a, b in zip(tr, tr[1:]):
            assert abs((b[0] - a[0]) - 1 / 60) < 2e-4
        assert isinstance(k["margin_cm"], int) and k["explain"]
        # [tur3b 2026-10-22] ek alanlar: kalecinin uçuş evreleri, şut sapması (A'da null)
        assert kp["ucus"]["model"] == "balistik-v1" and kp["ucus"]["mode"] in ("dive", "step", "stand")
        assert s["sapma"] is None and abs(s["aim_effective"]["x"] - s["aim"]["x"]) < 1e-4
    # [tur3b] balistik kalecide stub'ın 1. şutu artık gol (erken çıkan kaleci top gelince yere iniyor); kurtarış
    # alanları ayrıca test_tur3b_hands_settle_after_catch içinde sınanıyor
    assert "goal" in outs and outs & {"wide", "over", "post"}
    assert log["sut_sapmasi_acik"] is False


def test_commitment_changes_with_any_input():
    _, s1 = commit_digest(CFG, None)
    _, s2 = commit_digest(copy.deepcopy(CFG), None)
    assert s1 == s2 and len(s1) == 64
    c = copy.deepcopy(CFG)
    c["keeper"]["ratings"]["diving"] = 81
    assert commit_digest(c, None)[1] != s1
    c = copy.deepcopy(CFG)
    c["keeper_seeds"][2] += 1
    assert commit_digest(c, None)[1] != s1
    assert commit_digest(CFG, "ab" * 32)[1] != s1


def test_optional_hunter_model_can_beat_keeper():
    c = copy.deepcopy(CFG)
    c["keeper_model"]["in_reach_save_model"] = {"a": -0.0447, "b": 1.72}
    p = plan("left", -0.19)
    p["u_keep"] = 0.999
    r = kick(2.2, 1.0, 26.0, p, cfg=c)
    assert r["outcome"] == "goal" and r["contact"]["beaten"] is True
    assert kick(2.2, 1.0, 26.0, plan("left", -0.19))["outcome"] == "save"


# =========================================================================== [tur3 2026-10-22] yeni akış
# Testler ağa çıkmaz: relay'ler sahte fetch ile taklit edilir. Beyin yeniden koşusu da taklit edilir (gerçeği
# verify.py --beyin-dizin ile koşar, ~20 s). BLS imzası GERÇEK drand turlarıyla, ağsız kontrol edilir.
import hashlib  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import time as _time  # noqa: E402
import beacon as bcn  # noqa: E402
import bls12381 as bls  # noqa: E402
import commit as cm  # noqa: E402
import verify as verify_mod  # noqa: E402

SABLON_P = os.path.join(HERE, "config_sablon.json")
SABLON = pm.load_json(SABLON_P)
# Gerçek, yayınlanmış iki drand quicknet turu (22 Ekim 2026'da üç relay'den aynı değerle okundu).
REAL_ROUND = {"round": 33295880,
              "randomness": "64a2d5d2d5f83225d0c7223321bcdbd8f6bf0850d5260a2f1842e815fb868716",
              "signature": "ac0bc597012eb5f4e7847c2283882a5a3ce2d29a689eda35f4f6f4376bc7fee81d2005984b59a7b07e954f7673a5aca2"}
REAL_ROUND2 = {"round": 33296123,
               "randomness": "d6f4812b08275a7e4ae0dab82129a7cf2bfb4cfb9c1794e754dcea220c0673f2",
               "signature": "b92664666cbfdacf6e40d985098f579b946068e2fe9b340a5aab2187c3cb98b4395cdec3204880c9f77c5be52847283b"}
INFO_OK = {"public_key": bcn.QUICKNET["public_key"], "period": 3, "genesis_time": 1692803367,
           "hash": bcn.QUICKNET["chain_hash"], "schemeID": "bls-unchained-g1-rfc9380"}
BEYIN_DIR = cm.beyin_dizini()


def _u_bagimsiz(key, label):
    """Kayma kuralının belgedeki tanımı, penalty_model'e dokunmadan yeniden yazılmış hali."""
    h = hashlib.sha256(f"{key}|{label}".encode("utf-8")).digest()
    return (int.from_bytes(h[:7], "big") + 0.5) / 2.0 ** 56


def _raises(f, *a, **k):
    try:
        f(*a, **k)
    except SystemExit:
        return True
    return False


def test_tur3_template_rules():
    km = SABLON["keeper_model"]
    irm = km["in_reach_save_model"]
    assert (irm["a"], irm["b"]) == (-0.0447, 1.72)
    p20 = pm.clamp(irm["a"] * 20 + irm["b"], 0, 1)
    p30 = pm.clamp(irm["a"] * 30 + irm["b"], 0, 1)
    assert abs(p20 - 0.826) < 1e-3 and abs(p30 - 0.379) < 1e-3, (p20, p30)  # MODEL.md: %82 / %38
    assert pm.keeper_params(SABLON)["pos_pull"] == 0.0
    assert abs(pm.keeper_params(CFG)["pos_pull"] - 0.40) < 1e-12  # eski prova config'i değişmedi
    assert bcn.zincir_farklari(SABLON["beacon"]) == []
    assert cm.karar_farklari(SABLON) == []
    assert SABLON["beacon"]["min_gecikme_dk"] >= 120 and SABLON["beacon"]["varsayilan_gecikme_dk"] >= 120
    assert SABLON["beyin"]["tohum"] == "beyin-tohum-v1" and "seed_base" not in SABLON["beyin"]
    assert SABLON["keeper"] == CFG["keeper"] and SABLON["physics"] == CFG["physics"]
    # üç dosyadaki elle yazılmış quicknet sabitleri aynı
    assert bcn.QUICKNET == cm.QUICKNET_SABIT == verify_mod.QUICKNET_SABIT
    assert verify_mod.READOUT_DONDURMA == cm.READOUT_DONDURMA
    dd = pm.load_json(os.path.join(BEYIN_DIR, "DONDURMA.json"))
    assert dd["readout_sha256"] == cm.READOUT_DONDURMA


def test_tur3_keeper_stands_where_brain_sees_him():
    for x in (-0.5, -0.412, -0.3, 0.3, 0.357, 0.5):
        r = kick(-2.9, 1.5, 26.0, plan("right"), keeper_x=x, cfg=SABLON)
        assert r["x_start"] == x, (x, r["x_start"])
        r_old = kick(-2.9, 1.5, 26.0, plan("right"), keeper_x=x, cfg=CFG)
        assert abs(r_old["x_start"] - 0.6 * x) < 1e-12  # eski kural: Positioning 80 -> 0,6·X (uyumsuzluk)
    dec = copy.deepcopy(STUB)
    xs = [-0.412, 0.3, 0.5, -0.301, 0.444]
    for k, x in zip(dec["kicks"], xs):
        k["scene"] = {"keeper_x": x}
    log = pm.run(SABLON, dec)
    assert [k["keeper"]["start_x"] for k in log["kicks"]] == xs
    assert [k["beyin"]["scene"]["keeper_x"] for k in log["kicks"]] == xs


def test_tur3_shift_and_brain_seed_rules():
    sha = "ab" * 32
    xs = bcn.kaymalar(SABLON, sha, REAL_ROUND["randomness"], 5)
    assert xs == bcn.kaymalar(copy.deepcopy(SABLON), sha, REAL_ROUND["randomness"], 5)  # deterministik
    key = f"{REAL_ROUND['randomness']}|{sha}"
    ref = []
    for n in range(1, 6):
        mag = 0.30 + 0.20 * _u_bagimsiz(key, f"kick{n}|kayma_buyukluk")
        sign = 1.0 if _u_bagimsiz(key, f"kick{n}|kayma_yon") < 0.5 else -1.0
        ref.append(round(sign * mag, 3))
    assert xs == ref, (xs, ref)
    assert bcn.kaymalar(SABLON, "cd" * 32, REAL_ROUND["randomness"], 5) != xs
    assert bcn.kaymalar(SABLON, sha, "00" * 32, 5) != xs
    allx = []
    for i in range(1500):
        allx += bcn.kaymalar(SABLON, sha, hashlib.sha256(str(i).encode()).hexdigest(), 2)
    mags = [abs(x) for x in allx]
    assert min(mags) >= 0.30 and max(mags) <= 0.50
    assert all(abs(x * 1000 - round(x * 1000)) < 1e-6 for x in allx)
    assert abs(sum(mags) / len(mags) - 0.40) < 0.006
    assert 0.47 < sum(x > 0 for x in allx) / len(allx) < 0.53
    # beyin tohumu: belgedeki tanım, beacon ve taahhüde bağlı, Brian2 sınırının (2^32) altında
    sb = bcn.beyin_tohum_tabani(sha, REAL_ROUND["randomness"])
    h = hashlib.sha256(f"{REAL_ROUND['randomness']}|{sha}|beyin|seed_base".encode()).hexdigest()
    assert sb == int(h[:8], 16) % 4_000_000_000
    assert bcn.beyin_tohum_tabani("cd" * 32, REAL_ROUND["randomness"]) != sb
    assert bcn.beyin_tohum_tabani(sha, REAL_ROUND2["randomness"]) != sb
    assert all(0 <= bcn.beyin_tohum_tabani(sha, hashlib.sha256(str(i).encode()).hexdigest()) + 5 < 2 ** 32
               for i in range(2000))


def test_tur3_drand_digest_and_round_time():
    assert bcn.imza_ozeti_tutuyor(REAL_ROUND) and bcn.imza_ozeti_tutuyor(REAL_ROUND2)
    assert not bcn.imza_ozeti_tutuyor(dict(REAL_ROUND, randomness="0" + REAL_ROUND["randomness"][1:]))
    assert not bcn.imza_ozeti_tutuyor(dict(REAL_ROUND, signature="0" + REAL_ROUND["signature"][1:]))
    assert bcn.round_time(1) == 1692803367
    assert bcn.round_time(REAL_ROUND2["round"]) == 1692803367 + (33296123 - 1) * 3
    assert bcn.iso_utc(bcn.round_time(REAL_ROUND2["round"])) == "2026-10-22T17:55:33Z"
    for t in (1792691004.0, 1792691005.9, 1800000000.5):
        r = bcn.round_at(t)
        assert bcn.round_time(r) <= t < bcn.round_time(r) + 3
    assert bcn.parse_utc("2026-10-22T17:55:33Z") == bcn.round_time(33296123)


def test_tur3_bls_signature():
    # RFC 9380 Ek J.9.1 test vektörleri (BLS12381G1_XMD:SHA-256_SSWU_RO_)
    dst = b"QUUX-V01-CS02-with-BLS12381G1_XMD:SHA-256_SSWU_RO_"
    u = bls.hash_to_field(b"", 2, dst)
    assert u == [0x0ba14bd907ad64a016293ee7c2d276b8eae71f25a4b941eece7b0d89f17f75cb3ae5438a614fb61d6835ad59f29c564f,
                 0x019b9bd7979f12657976de2884c7cce192b82c177c80e0ec604436a7f538d231552f0d96d9f7babe5fa3b19b3ff25ac9]
    assert bls.map_to_curve_g1(u[0]) == (
        0x11a3cce7e1d90975990066b2f2643b9540fa40d6137780df4e753a8054d07580db3b7f1f03396333d4a359d1fe3766fe,
        0x0eeaf6d794e479e270da10fdaf768db4c96b650a74518fc67b04b03927754bac66f3ac720404f339ecdcc028afa091b7)
    assert bls.hash_to_g1(b"", dst) == (
        0x052926add2207b76ca4fa57a8734416c8dc95e24501772c814278700eed6d1e4e8cf62d9c09db0fac349612b759e79a1,
        0x08ba738453bfed09cb546dbb0783dbb3a5f1f566ed67bb6be0e8c67e2e81a4cc68ee29813bb7994998f3eae0c9c6a265)
    assert bls.hash_to_g1(b"abc", dst) == (
        0x03567bc5ef9c690c2ab2ecdf6a96ef1c139cc0b2f284dca0a9a7943388a49a3aee664ba5379a7655d3c68900be2f6903,
        0x0b9c15f3fe6e5cf4211f346271d7b01c8f3b28be689c8429c85b67af215533311f0b8dfaaa154fa6b88176c229f2885d)
    assert bls.oz_sinama()
    pk = bcn.QUICKNET["public_key"]
    for rr in (REAL_ROUND, REAL_ROUND2):
        assert bcn.bls_dogrula(rr)[0], rr["round"]                                  # gerçek imza GEÇERLİ
        assert not bcn.bls_dogrula(dict(rr, round=rr["round"] + 1))[0]              # başka tur
        assert not bls.dogrula_drand(rr["round"], rr["signature"], pk,
                                     b"BLS_SIG_BLS12381G2_XMD:SHA-256_SSWU_RO_NUL_")[0]  # yanlış DST
    assert not bcn.bls_dogrula(dict(REAL_ROUND, signature=REAL_ROUND2["signature"]))[0]  # başka turun imzası
    assert not bcn.bls_dogrula(dict(REAL_ROUND, signature="aa" * 48))[0]            # uydurma imza (T12c)
    assert not bcn.bls_dogrula(dict(REAL_ROUND, signature=REAL_ROUND["signature"][:-1] + "3"))[0]
    # eğri üstünde, alt grupta ama imza olmayan bir nokta
    x, y = bls.hash_to_g1(b"sahte")
    fake = bytearray(x.to_bytes(48, "big"))
    fake[0] |= 0x80 | (0x20 if y > bls.HALF_P else 0)
    assert bls.g1_decompress(bytes(fake)) == (x, y)
    assert not bcn.bls_dogrula(dict(REAL_ROUND, signature=bytes(fake).hex()))[0]


def _fake_fetch(vals):
    def f(url, chain, r):
        v = vals[url]
        if isinstance(v, Exception):
            raise v
        return dict(v)
    return f


def _info(vals=None):
    def f(url, chain):
        v = (vals or {}).get(url, INFO_OK)
        if isinstance(v, Exception):
            raise v
        return dict(v)
    return f


def test_tur3_relay_comparison():
    r1, r2, r3 = bcn.QUICKNET["relays"]
    same = {u: REAL_ROUND for u in bcn.QUICKNET["relays"]}
    res = bcn.relay_karsilastir(REAL_ROUND, _fake_fetch(same), _info())
    assert (res["ayni"], res["ulasilan"], res["farkli"], res["info_farkli"]) == (3, 3, 0, [])
    two = dict(same, **{r3: OSError("yok")})
    res = bcn.relay_karsilastir(REAL_ROUND, _fake_fetch(two), _info())
    assert (res["ayni"], res["ulasilan"]) == (2, 2)
    diff = dict(same, **{r1: dict(REAL_ROUND, randomness="11" * 32)})
    assert bcn.relay_karsilastir(REAL_ROUND, _fake_fetch(diff), _info())["farkli"] == 1
    bad_info = _info({r2: dict(INFO_OK, genesis_time=1692803367 + 3600)})
    assert bcn.relay_karsilastir(REAL_ROUND, _fake_fetch(same), bad_info)["info_farkli"] == [(r2, ["genesis_time"])]
    none = {u: OSError("yok") for u in bcn.QUICKNET["relays"]}
    assert bcn.relay_karsilastir(REAL_ROUND, _fake_fetch(none), _info())["ulasilan"] == 0


# ---------------------------------------------------------------- uçtan uca (sahte beyin koşusu, gerçek beacon)
_ES, _ = verify_mod.esleme_yukle(BEYIN_DIR, cm.dosya_sha(os.path.join(BEYIN_DIR, "esleme.py")))


def _counts(seed, x):
    """Gerçek beynin yerine: tohum ve yerden deterministik spike sayıları (yalnız test)."""
    h = hashlib.sha256(f"{seed}|{x}".encode()).digest()
    c = {k: h[i] % 9 for i, k in enumerate(_ES["COUNT_KEYS"])}
    side = "L" if x < 0 else "R"
    c[f"DNa02_{side}"] += 30
    c["oDN1_L"] += 10
    c["oDN1_R"] += 12
    return c


def _kick_out(n, seed, x):
    c = _counts(seed, x)
    s, pw, rt, lt = _ES["oku"](c)
    ax, ay, v = _ES["esle"](s, pw)
    sp = hashlib.sha256(f"spikes|{seed}|{x}".encode()).hexdigest()
    return {"n": n, "trial_seed": seed, "scene": {"keeper_x": x}, "counts": c, "steer": round(s, 4),
            "power_spikes": int(pw), "aim": {"x": ax, "y": ay}, "speed_mps": v, "decision_ms": 400 + n,
            "Rturn": rt, "Lturn": lt, "brain_spikes": 10000 + n, "spikes_sha256": sp}


def _sahte_beyin(isler):
    """verify'ın beyin yeniden koşusunun taklidi: aynı (tohum, yer) -> aynı çıktı."""
    out = []
    for j in isler:
        k = _kick_out(j["n"], j["trial_seed"], j["keeper_x"])
        out.append(dict({f: k[f] for f in verify_mod.YENIDEN_ALANLAR}, n=j["n"], trial_seed=j["trial_seed"],
                        keeper_x=j["keeper_x"], raster="yok"))
    return out


def _mini(mod="final", rr=REAL_ROUND, degis=None):
    cfg = copy.deepcopy(SABLON)
    if degis:
        degis(cfg)
    cfg["mod"] = mod
    cfg["not"] = "TEST"
    b = cfg["beacon"]
    b["round"] = rr["round"]
    b["round_time_utc"] = bcn.iso_utc(bcn.round_time(rr["round"]))
    cfg["beacon_rule"] = f"drand quicknet round {rr['round']} randomness (test)"
    cfg["kod_ozetleri"] = cm.kod_ozetleri_hesapla(HERE, BEYIN_DIR)
    cfg["ortam"] = {"python": "test", "platform": "test", "paketler": []}
    payload, sha = cm.commit_digest(cfg, cm.READOUT_DONDURMA)
    t_r = bcn.round_time(rr["round"])
    t = {"sha256": sha, "short": sha[:12], "payload": payload, "kural_ozeti_sha256": cm.kural_ozeti(cfg),
         "created_at_utc": bcn.iso_utc(t_r - 4 * 3600), "prova": mod != "final"}
    bc = dict(rr, chain_hash=bcn.QUICKNET["chain_hash"])
    xs = bcn.kaymalar(cfg, sha, bc["randomness"], 5)
    sb = bcn.beyin_tohum_tabani(sha, bc["randomness"])
    ko = cfg["kod_ozetleri"]
    dec = {"prova": mod != "final", "readout_sha256": cm.READOUT_DONDURMA, "readout": _ES["READOUT"],
           "constants": json.loads(json.dumps(_ES["sabitler"]())), "seed_base": sb, "commit_sha256": sha,
           "scene_input": [{"n": i + 1, "keeper_x": x} for i, x in enumerate(xs)],
           "kicks": [_kick_out(i + 1, sb + i + 1, x) for i, x in enumerate(xs)],
           "code_sha256": {f: ko[f"beyin/{f}"] for f in verify_mod.BEYIN_KOD},
           "data_sha256": dict({f: ko[p] for f, p in verify_mod.BEYIN_VERI.items()}, shiu_commit=verify_mod.SHIU_COMMIT)}
    log = pm.run(cfg, dec, sha, beacon=bc["randomness"])
    return cfg, t, bc, dec, log


def _v(cfg, t, bc, dec, log, **kw):
    t_r = bcn.round_time(int(cfg["beacon"]["round"]))
    args = dict(kod=t["sha256"], kural_sha=cm.duyuru_ozeti(SABLON, cm.kod_ozetleri_hesapla(HERE, BEYIN_DIR)),
                yayin_utc=bcn.iso_utc(t_r - 3 * 3600),
                log=log, dec=dec, beacon_dosya=bc, sablon=SABLON, beyin_dir=BEYIN_DIR, beyin_kos=_sahte_beyin,
                fetch=_fake_fetch({u: dict(bc) for u in bcn.QUICKNET["relays"]}), info_fetch=_info())
    args.update(kw)
    lines = []
    rp = verify_mod.dogrula(t, cfg, out=lines.append, **args)
    return verify_mod.sonuc_etiketi(rp)[0], lines


def _rerun(cfg, t, bc, dec):
    return pm.run(cfg, dec, t["sha256"], beacon=bc["randomness"])


def test_tur3_verify_labels():
    cfg, t, bc, dec, log = _mini("final")
    lab, lines = _v(cfg, t, bc, dec, log)
    assert lab == "DOĞRULANDI", "\n".join(x for x in lines if not x.startswith("TAMAM"))
    assert lines[0].startswith("MOD: FINAL")
    assert any("BLS imzası quicknet açık anahtarıyla GEÇERLİ" in x and x.startswith("TAMAM") for x in lines)
    # dış kanıtlar ve beyin koşusu eksikse DOĞRULANDI yok
    assert _v(cfg, t, bc, dec, log, kod=None)[0] == verify_mod.EKSIK_KOD
    assert _v(cfg, t, bc, dec, log, kural_sha=None)[0] == verify_mod.EKSIK_KURAL
    assert _v(cfg, t, bc, dec, log, yayin_utc=None)[0] == verify_mod.EKSIK_ZAMAN
    assert _v(cfg, t, bc, dec, log, beyin_kos=None)[0] == verify_mod.EKSIK_BEYIN
    # ağ yok ya da tek relay: BLS geçerli olduğu için yine DOĞRULANDI (UYARI ile)
    off = _fake_fetch({u: OSError("ağ yok") for u in bcn.QUICKNET["relays"]})
    lab, lines = _v(cfg, t, bc, dec, log, fetch=off)
    assert lab == "DOĞRULANDI" and any(x.startswith("UYARI") for x in lines)
    assert _v(cfg, t, bc, dec, log, cevrimdisi=True)[0] == "DOĞRULANDI"
    # prova her şey tutsa da yalnız PROVA DOĞRULANDI alır
    p = _mini("prova")
    lab, lines = _v(*p)
    assert lab.startswith("PROVA DOĞRULANDI") and lines[0].startswith("MOD: PROVA"), lab
    # final config ama taahhüt prova işaretli -> HATA
    t2 = dict(t, prova=True)
    assert _v(cfg, t2, bc, dec, log)[0] == "DOĞRULANAMADI"


def test_tur3_verify_catches_tampering():
    cfg, t, bc, dec, log = _mini("final")
    sha = t["sha256"]
    bad = {}

    def run(name, cfg_=cfg, t_=t, bc_=bc, dec_=dec, log_=None, **kw):
        log_ = log_ if log_ is not None else _rerun(cfg_, t_, bc_, dec_)
        bad[name] = _v(cfg_, t_, bc_, dec_, log_, **kw)[0]

    # T02: beyin 1 cm yanlış yerde koşturuldu, etiket doğru
    d = copy.deepcopy(dec)
    x0 = d["kicks"][0]["scene"]["keeper_x"]
    d["kicks"][0].update({k: v for k, v in _kick_out(1, d["kicks"][0]["trial_seed"], round(x0 + 0.01, 3)).items()
                          if k not in ("scene", "n", "trial_seed")})
    run("T02_beyin_yanlis_yer", dec_=d)
    # T04: spike takası, tutarlı biçimde yeniden hesaplandı
    d = copy.deepcopy(dec)
    k = d["kicks"][3]
    c = k["counts"]
    c["DNa02_L"], c["DNa02_R"] = c["DNa02_R"], c["DNa02_L"]
    s, pw, rt, lt = _ES["oku"](c)
    ax, ay, v = _ES["esle"](s, pw)
    k.update({"steer": round(s, 4), "power_spikes": int(pw), "aim": {"x": ax, "y": ay}, "speed_mps": v,
              "Rturn": rt, "Lturn": lt})
    run("T04_spike_takas_tutarli", dec_=d)
    # T05: nişan elle
    d = copy.deepcopy(dec)
    d["kicks"][3]["aim"]["x"] = -0.30
    run("T05_nisan_elle", dec_=d)
    # T08: başka tohumla koşturulup etiket değiştirildi
    d = copy.deepcopy(dec)
    k = d["kicks"][3]
    k.update({f: v for f, v in _kick_out(4, k["trial_seed"] + 5000, k["scene"]["keeper_x"]).items()
              if f not in ("scene", "n", "trial_seed")})
    run("T08_baska_tohum", dec_=d)
    # tohum tabanı etiketi
    d = copy.deepcopy(dec)
    d["seed_base"] += 1
    run("tohum_tabani", dec_=d)
    # T15: readout alanı silindi;  T16: code/data özetleri sıfırlandı
    d = copy.deepcopy(dec)
    d.pop("readout_sha256")
    run("T15_readout_yok", dec_=d)
    d = copy.deepcopy(dec)
    d["code_sha256"]["beyin_model.py"] = "0" * 64
    d["data_sha256"]["Connectivity_783.parquet"] = "0" * 64
    run("T16_kod_ozeti_sifir", dec_=d)
    d = copy.deepcopy(dec)
    d.pop("code_sha256")
    run("T16b_kod_ozeti_yok", dec_=d)
    # T19: 4 şut
    d = copy.deepcopy(dec)
    d["kicks"] = d["kicks"][:4]
    run("T19_4_sut", dec_=d)
    # T10: Hunter b = 1,50 ile BAŞTAN taahhüt;  p_positive; dive_probs (yalnız şablon farkı)
    for name, fn in (("T10_hunter_b", lambda c: c["keeper_model"]["in_reach_save_model"].update(b=1.50)),
                     ("p_positive", lambda c: c["keeper_shift"].update(p_positive=0.7)),
                     ("dive_probs", lambda c: c["keeper_model"]["dive_probs"].update(left=0.6, right=0.337))):
        m = _mini("final", degis=fn)
        bad[name] = _v(*m)[0]
    # T17: genesis kaydırıldı (+3600 s);  başka zincir
    m = _mini("final", degis=lambda c: c["beacon"].update(genesis_time=c["beacon"]["genesis_time"] + 3600))
    bad["T17_genesis"] = _v(*m)[0]
    m = _mini("final", degis=lambda c: c["beacon"].update(chain_hash="8990e7a9aaed2ffed73dbd7092123d6f289930540d7651336225dc172e51b2ce"))
    bad["baska_zincir"] = _v(*m)[0]
    # T12c: uydurma ama iç tutarlı beacon; relay'ler de taklit edilip aynı değeri veriyor
    fake_sig = "aa" * 48
    bc3 = dict(bc, signature=fake_sig, randomness=hashlib.sha256(bytes.fromhex(fake_sig)).hexdigest())
    xs3 = bcn.kaymalar(cfg, sha, bc3["randomness"], 5)
    sb3 = bcn.beyin_tohum_tabani(sha, bc3["randomness"])
    d = copy.deepcopy(dec)
    d["seed_base"] = sb3
    d["scene_input"] = [{"n": i + 1, "keeper_x": x} for i, x in enumerate(xs3)]
    d["kicks"] = [_kick_out(i + 1, sb3 + i + 1, x) for i, x in enumerate(xs3)]
    run("T12c_sahte_beacon_sahte_ag", bc_=bc3, dec_=d,
        fetch=_fake_fetch({u: dict(bc3) for u in bcn.QUICKNET["relays"]}))
    # T12a: başka (gerçek) turun beacon'ı
    bc4 = dict(REAL_ROUND2, chain_hash=bcn.QUICKNET["chain_hash"])
    run("T12a_baska_tur", bc_=bc4, fetch=_fake_fetch({u: dict(bc4) for u in bcn.QUICKNET["relays"]}))
    # T11: tur yayınlandıktan sonra taahhüt (dış kanıt turdan sonra);  turdan yalnız 30 dk önce
    t_r = bcn.round_time(cfg["beacon"]["round"])
    run("T11_yayin_turdan_sonra", log_=log, yayin_utc=bcn.iso_utc(t_r + 600))
    run("final_30dk_once", log_=log, yayin_utc=bcn.iso_utc(t_r - 1800))
    t5 = dict(t)
    t5.pop("created_at_utc")
    run("T11_saat_alani_yok", t_=t5, log_=log)
    # T11: kısa (12 karakter) kod, yanlış kod
    run("kisa_kod", log_=log, kod=sha[:12])
    run("yanlis_kod", log_=log, kod="0" * 64)
    run("yanlis_kural_ozeti", log_=log, kural_sha="0" * 64)
    # kod özetleri: taahhüt edilmiş özet şimdiki dosyayla tutmuyor (T14: beacon.py değişmiş gibi)
    m = _mini("final", degis=lambda c: None)
    cfg5, t5b, bc5, dec5, _ = m
    cfg5["kod_ozetleri"]["oyun/beacon.py"] = "1" * 64
    p5, sha5 = cm.commit_digest(cfg5, cm.READOUT_DONDURMA)
    t5b = dict(t5b, sha256=sha5, payload=p5)
    bad["T14_kod_ozeti_farkli"] = _v(cfg5, t5b, bc5, dec5, _rerun(cfg5, t5b, bc5, dec5), kod=sha5)[0]
    # T14b: beacon.py taahhütten ÖNCE değiştirilmiş gibi (kayma yönü ters); veriler değiştirilmiş kodla tutarlı
    orj = bcn.kaymalar
    try:
        bcn.kaymalar = lambda c, s, r, n: [-x for x in orj(c, s, r, n)]
        m = _mini("final")
        bad["T14b_kod_once_degisti_KAT"] = _v(*m)[0]
    finally:
        bcn.kaymalar = orj
    # motor log'u elle
    lg = copy.deepcopy(log)
    lg["kicks"][0]["outcome"] = "save" if lg["kicks"][0]["outcome"] == "goal" else "goal"
    run("T20_log_elle", log_=lg)
    kacan = {k: v for k, v in bad.items() if v != "DOĞRULANAMADI"}
    assert not kacan, kacan


def test_tur3_commit_yeni():
    d = tempfile.mkdtemp(prefix="tur3_test_")
    try:
        out = os.path.join(d, "c.json")
        cm.main(["yeni", "--sablon", SABLON_P, "--cikti", out, "--prova", "--beacon-gecikme-dk", "20"])
        c = pm.load_json(out)
        b = c["beacon"]
        dt = bcn.round_time(b["round"]) - _time.time()
        assert 19 * 60 < dt < 21 * 60, dt
        assert c["mod"] == "prova" and c["beacon_rule"].startswith(f"drand quicknet round {b['round']} ")
        assert c["beyin"] == SABLON["beyin"] and "seed_base" not in c["beyin"]
        assert c["keeper_seeds"] != SABLON["keeper_seeds"] and len(c["keeper_seeds"]) == 5
        assert cm.kural_farklari(c, SABLON) == [] and cm.kural_ozeti(c) == cm.kural_ozeti(SABLON)
        assert cm.kod_farklari(c, HERE, BEYIN_DIR) == []
        assert c["ortam"]["paketler"] and any(p.lower().startswith("brian2==") for p in c["ortam"]["paketler"])
        assert _raises(cm.main, ["yeni", "--sablon", SABLON_P, "--cikti", out, "--prova"])  # üzerine yazmaz
        f = os.path.join(d, "f.json")
        assert _raises(cm.main, ["yeni", "--sablon", SABLON_P, "--cikti", f, "--beacon-turu", str(REAL_ROUND["round"])])
        assert _raises(cm.main, ["yeni", "--sablon", SABLON_P, "--cikti", f, "--beacon-gecikme-dk", "30"])  # < 120 dk
        assert not os.path.exists(f)
        cm.main(["yeni", "--sablon", SABLON_P, "--cikti", f])  # final, varsayılan 180 dk
        dt = bcn.round_time(pm.load_json(f)["beacon"]["round"]) - _time.time()
        assert 179 * 60 < dt < 181 * 60, dt
        # şablon kurallardan saparsa üretmez (T10, T17)
        for fn in (lambda s: s["keeper_model"]["in_reach_save_model"].update(b=1.5),
                   lambda s: s["beacon"].update(genesis_time=s["beacon"]["genesis_time"] + 3600)):
            s = copy.deepcopy(SABLON)
            fn(s)
            sp = os.path.join(d, "s.json")
            pm.write_json(sp, s)
            assert _raises(cm.main, ["yeni", "--sablon", sp, "--cikti", os.path.join(d, "x.json"), "--prova"])
        # hesapla: kod değişmişse taahhüt yazmaz
        c2 = pm.load_json(out)
        c2["kod_ozetleri"]["oyun/verify.py"] = "2" * 64
        p2 = os.path.join(d, "c2.json")
        pm.write_json(p2, c2)
        assert _raises(cm.main, ["hesapla", "--config", p2, "--yaz", os.path.join(d, "t2.json")])
        assert not os.path.exists(os.path.join(d, "t2.json"))
        cm.main(["hesapla", "--config", out, "--yaz", os.path.join(d, "t.json")])
        assert os.path.exists(os.path.join(d, "taahhut_gecmisi.jsonl"))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_tur3_independent_js_check():
    node = shutil.which("node")
    if not node:
        print("   (node yok: bağımsız JS kontrolü atlandı)")
        return
    cfg, t, bc, dec, log = _mini("prova", rr=REAL_ROUND2)
    d = tempfile.mkdtemp(prefix="tur3_js_")
    try:
        paths = {}
        for name, obj in (("b", bc), ("t", t), ("log", log), ("dec", dec)):
            paths[name] = os.path.join(d, name + ".json")
            pm.write_json(paths[name], obj)
        p = subprocess.run([node, os.path.join(HERE, "bagimsiz", "kontrol.mjs"), paths["b"], paths["t"], paths["log"],
                            paths["dec"]], capture_output=True, text=True, timeout=60)
        assert p.returncode == 0 and "BAĞIMSIZ KONTROL: TUTUYOR" in p.stdout, p.stdout + p.stderr
        xs = bcn.kaymalar(cfg, t["sha256"], bc["randomness"], 5)
        assert "kaymalar (m): " + ", ".join(repr(x) for x in xs) in p.stdout, p.stdout
        # bozuk log'u yakalıyor mu?
        lg = copy.deepcopy(log)
        lg["kicks"][2]["keeper"]["start_x"] = round(lg["kicks"][2]["keeper"]["start_x"] + 0.001, 3)
        pm.write_json(paths["log"], lg)
        p = subprocess.run([node, os.path.join(HERE, "bagimsiz", "kontrol.mjs"), paths["b"], paths["t"], paths["log"],
                            paths["dec"]], capture_output=True, text=True, timeout=60)
        assert p.returncode == 1 and "TUTMUYOR" in p.stdout
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_tur3_score_rule():
    log = {"kicks": [{"outcome": o} for o in ("goal", "save", "wide", "over", "post")]}
    assert verify_mod.skor(log) == (1, 4)
    log = {"kicks": [{"outcome": o} for o in ("goal", "goal", "goal", "save", "wide")]}
    assert verify_mod.skor(log) == (3, 2)
    assert "aut (wide)" in SABLON["skor_kurali"] and "üstten aut (over)" in SABLON["skor_kurali"]


# =========================================================================== [tur3b 2026-10-22] balistik kaleci + şut sapması
import math  # noqa: E402

# Testler seçenekten bağımsız: şablon A da olsa B de olsa (oyun_B/config_sablon.json) aynı tests.py geçer.
SABLON_A = copy.deepcopy(SABLON)
SABLON_A["sut_sapmasi"]["acik"] = False
SABLON_B = copy.deepcopy(SABLON)
SABLON_B["sut_sapmasi"]["acik"] = True
KP_S = pm.keeper_params(SABLON)


def _tl(dive, leave, bstar, x0=0.0, t_ball=None, dt=1 / 600):
    p = {"dive_dir": dive, "leave_drawn_s": leave, "u_catch": 0.5, "u_keep": 0.0}
    return pm.KeeperTimeline(KP_S, p, x0, bstar, -1.0, 2.5, dt, t_ball=t_ball)


def test_tur3b_dive_is_ballistic():
    """Kalkıştan inişe ağırlık merkezi bir mermi: yatay hız sabit, dikey ivme -g; havada durup düşmek yok."""
    g, V, dt = KP_S["g"], KP_S["v_dive"], 1 / 600
    cases = [("left", -0.19, None), ("right", -0.35, (-2.9, 0.9)), ("left", -0.10, (2.6, 2.1)),
             ("right", -0.05, (-2.5, 0.3)), ("left", 0.10, (1.5, 1.6))]
    for dive, leave, bstar in cases:
        kt = _tl(dive, leave, bstar, x0=0.3)
        s = pm.SIDE_SIGN[dive]
        assert kt.mode == "dive" and kt.t_takeoff < kt.t_land < kt.t_rest, kt.summary()
        y0 = KP_S["com0_y"]
        ts = [kt.t_m + i * dt for i in range(int((kt.t_rest + 0.2 - kt.t_m) / dt))]
        body = [kt._body(t) for t in ts]
        for (t, (C, th, F, _)), (t2, (C2, _, F2, _)) in zip(zip(ts, body), zip(ts[1:], body[1:])):
            vx = (C2[0] - C[0]) / dt
            assert abs(C2[0] - C[0]) <= (V + 1e-6) * dt and abs(C2[1] - C[1]) <= 6.0 * dt, (dive, t)  # süreklilik
            assert F[1] >= 0.0 and math.dist(F, C) <= KP_S["L_push"] + 1e-9, (dive, t, F, C)            # ayak yerin altında değil, bacak boyu
            if kt.t_takeoff + dt < t < kt.t_land - 2 * dt:                       # uçuş
                assert abs(vx - s * V) < 1e-6, (dive, t, vx)                     # yatay hız sabit: havada durmak yok
                assert F[1] <= C[1] + 1e-9                                        # ayaklar gövdenin altında
            if kt.t_m < t < kt.t_m + 0.5 * KP_S["t_push"]:
                assert F[1] <= KP_S["step_lift"] + 1e-12
            elif kt.t_m + 0.5 * KP_S["t_push"] <= t <= kt.t_takeoff:
                assert F[1] == 0.0                                                # itme ayağı yerde
            if t >= kt.t_land:
                assert abs(C[1] - KP_S["y_lying"]) < 1e-12 and s * (C2[0] - C[0]) >= -1e-12   # yerde, geri kaymıyor
        # dikey ivme uçuşta -g
        for t in (kt.t_takeoff + 0.05, 0.5 * (kt.t_takeoff + kt.t_land)):
            y = [kt._body(t + j * dt)[0][1] for j in (-1, 0, 1)]
            assert abs((y[0] - 2 * y[1] + y[2]) / dt ** 2 + g) < 1e-6, (dive, t)
        assert kt.apex_y <= y0 + KP_S["jump_cap"] + 1e-9
        # iniş ve kayma: v1²/(2μg) kadar kayıp durur
        v1 = V * KP_S["land_keep"]
        x_end = kt._body(kt.t_rest + 0.5)[0][0]
        assert abs(x_end - (kt.x_land + s * v1 * v1 / (2 * KP_S["slide_mu"] * g))) < 1e-9
        assert kt._body(kt.t_rest + 0.5)[0] == kt._body(kt.t_rest + 1.0)[0]
        # gövde ve kol boyları fiziksel
        for i in range(0, kt.n, 7):
            C, S, Hh = kt.C[i], kt.S[i], kt.Hd[i]
            assert math.dist(S, Hh) <= KP_S["L_arm"] + 1e-6 or Hh[1] == 0.02
            assert math.dist(C, S) <= KP_S["L_torso"] + 1e-9


def test_tur3b_old_superman_path_is_gone():
    """Prova5'in 1. şutu: eski model COM'u -1,05 m'de yatayda durdurup 0,5 s dikine düşürüyordu."""
    r = kick(-1.64, 1.52, 26.3, plan("right", -0.212), keeper_x=0.477, cfg=SABLON)
    path = r["path"]
    kt = r["keeper"]
    fl = [row for row in path if kt.t_takeoff < row[0] < kt.t_land]
    vx = [(b[1] - a[1]) * 60 for a, b in zip(fl, fl[1:])]
    assert vx and max(vx) < -4.1 and min(vx) > -4.3, vx[:3]      # bütün uçuş boyunca ~4,2 m/s yana
    dropping = [row for row in fl if row[0] > kt.t_takeoff + 0.2]
    assert dropping and all(abs(b[1] - a[1]) * 60 > 4.0 for a, b in zip(dropping, dropping[1:]))   # düşerken de yana gidiyor


def test_tur3b_stay_keeper_steps_or_dives_after_reaction():
    rt = KP_S["reaction_s"]
    kt = _tl("stay", 0.0, (1.5, 0.5))         # yakın top: adım, uçuş yok
    assert kt.mode == "step" and kt.t_m == rt
    for t in (rt + 0.05, rt + 0.2, rt + 0.6):
        C, th, F, _ = kt._body(t)
        assert F[1] == 0.0 and C[1] >= KP_S["crouch_min"] - 1e-12 and th == math.pi / 2
    a = kt._body(rt + kt.T_step + 0.01)[0]
    b = kt._body(rt + kt.T_step + 0.5)[0]
    assert a == b                                # yumuşak durdu, sonra kımıldamıyor
    kt = _tl("stay", 0.0, (0.2, 2.3))          # ortaya yüksek top: kısa sıçrama, havada asılı kalmak yok
    assert kt.mode in ("step", "stand")
    ys = [kt._body(rt + i * 0.01)[0][1] for i in range(150)]
    assert max(ys) <= KP_S["com0_y"] + (0.5 * KP_S["g"] * KP_S["t_push"]) ** 2 / (2 * KP_S["g"]) + 1e-9
    assert abs(ys[-1] - KP_S["com0_y"]) < 1e-9   # ayağının üstüne geri indi
    kt = _tl("stay", 0.0, (-2.8, 1.0))         # uzak top: tepkiden sonra gerçek bir dalış
    assert kt.mode == "dive" and kt.t_m == rt and kt.s == -1 and kt.adapted


def test_tur3b_hands_settle_after_catch():
    """Tutulan top yere yatan kalecinin elinde: el (ve top) havada dik kolla kalmıyor; top yerin altına girmiyor."""
    found = None
    for lv in [round(-0.40 + 0.02 * i, 2) for i in range(25)]:
        for x, y in ((2.0, 0.9), (2.2, 1.0), (1.8, 0.6), (2.4, 0.5)):
            r = kick(x, y, 19.0, plan("left", lv, u_catch=0.0), cfg=SABLON)
            if r["outcome"] == "save" and r["contact"]["type"] == "catch" and r["keeper"].mode == "dive":
                found = r
                break
        if found:
            break
    assert found, "tutuş bulunamadı"
    kt = found["keeper"]
    t_end = found["traj"][-1][0]
    assert t_end > kt.t_land
    last = found["traj"][-1]
    hand = kt.state(last[0])["H"]
    assert hand[1] < 0.6 and last[2] >= 0.11 - 1e-9, (hand, last)


def _u_ref(seed, label):
    return _u_bagimsiz(seed, label)


def _sapma_ref(sc, kseed, n, ax, ay, v):
    """Belgedeki formülün (MODEL.md bölüm 8) penalty_model'e dokunmadan yeniden yazılmışı."""
    u1, u2 = _u_ref(kseed, f"kick{n}|sapma_u1"), _u_ref(kseed, f"kick{n}|sapma_u2")
    z1 = math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)
    z2 = math.sqrt(-2 * math.log(u1)) * math.sin(2 * math.pi * u2)
    f = min(max(ay / sc["yukseklik_ref_m"], 0.0), 1.0)
    sx = sc["olcek"] * (sc["alpha_h_zemin"] + (sc["alpha_h_yuksek"] - sc["alpha_h_zemin"]) * f) * v ** sc["delta_h"]
    sy = sc["olcek"] * (sc["alpha_v_zemin"] + (sc["alpha_v_yuksek"] - sc["alpha_v_zemin"]) * f) * v ** sc["delta_v"]
    return sx * z1, sy * z2, sx, sy


def test_tur3b_scatter_rule():
    sc = SABLON_B["sut_sapmasi"]
    # A (varsayılan): kapalı, hiçbir şey değişmez
    assert type(SABLON["sut_sapmasi"]["acik"]) is bool and pm.draw_scatter(SABLON_A, 123, 1, {"x": 1.0, "y": 1.0}, 25) is None
    # formül = belge (bağımsız yeniden yazım) ve verify.py'deki bilinen cevap (KAT)
    for kseed, n, ax, ay, v in ((1, 1, 0.0, 0.5, 20.0), (987654321987654321, 3, -2.1, 1.55, 27.3), (5, 5, 3.0, 2.3, 16.0)):
        d = pm.draw_scatter(SABLON_B, kseed, n, {"x": ax, "y": ay}, v)
        ex, ey, sx, sy = _sapma_ref(sc, kseed, n, ax, ay, v)
        assert abs(d["err"][0] - ex) < 1e-12 and abs(d["err"][1] - ey) < 1e-12 and d["sigma"] == (sx, sy)
        assert d["aim"] == {"x": ax + d["err"][0], "y": ay + d["err"][1]}
    k = verify_mod.KAT_SAPMA
    ex, ey, _, _ = _sapma_ref(sc, k["kseed"], k["n"], k["aim"]["x"], k["aim"]["y"], k["speed"])
    assert abs(ex - k["hata_m"][0]) < 1e-9 and abs(ey - k["hata_m"][1]) < 1e-9
    # Hunter 2018: hızla ve yükseklikle büyür
    s = lambda y, v: pm.draw_scatter(SABLON_B, 7, 1, {"x": 0, "y": y}, v)["sigma"]  # noqa: E731
    assert s(0.3, 20)[0] < s(0.3, 28)[0] and s(0.3, 20)[1] < s(0.3, 28)[1] and s(0.2, 25)[1] < s(1.6, 25)[1]
    assert s(1.6, 25) == s(2.2, 25)           # 1,6 m üstü yüksek hedef değeri
    # dağılım: N(0,1), bağımsız
    zs = [pm.draw_scatter(SABLON_B, i, 1 + i % 5, {"x": 0, "y": 1}, 25)["z"] for i in range(6000)]
    for j in (0, 1):
        m = sum(z[j] for z in zs) / len(zs)
        sd = math.sqrt(sum((z[j] - m) ** 2 for z in zs) / len(zs))
        assert abs(m) < 0.05 and abs(sd - 1) < 0.04, (j, m, sd)
    cor = sum(z[0] * z[1] for z in zs) / len(zs)
    assert abs(cor) < 0.05
    # motor: deterministik, beacon'a bağlı, A ile B aynı kaleci planını kullanır
    dec = copy.deepcopy(STUB)
    a1 = pm.dumps_readable(pm.run(SABLON_B, dec))
    assert a1 == pm.dumps_readable(pm.run(copy.deepcopy(SABLON_B), copy.deepcopy(dec)))
    la, lb = pm.run(SABLON_A, dec), pm.run(SABLON_B, dec)
    assert la["sut_sapmasi_acik"] is False and lb["sut_sapmasi_acik"] is True
    for ka, kb in zip(la["kicks"], lb["kicks"]):
        assert ka["keeper"]["seed_uniforms"] == kb["keeper"]["seed_uniforms"]
        assert ka["shot"]["sapma"] is None and kb["shot"]["sapma"]["nisan_niyet"] == ka["shot"]["aim"]
        assert abs(kb["shot"]["aim_effective"]["x"] - kb["shot"]["sapma"]["nisan_gercek"]["x"]) < 1e-9
    c1 = dict(SABLON_B, beacon_rule="x")
    e1 = pm.run(c1, dec, beacon="aa" * 32)["kicks"][0]["shot"]["sapma"]["hata_m"]
    e2 = pm.run(c1, dec, beacon="bb" * 32)["kicks"][0]["shot"]["sapma"]["hata_m"]
    assert e1 != e2
    # sapan şut aut / üstten aut / direk olabilir ve ÇAKIR'a sayılır
    seen = set()
    for i in range(1500):
        d = {"kicks": [{"n": 1, "aim": {"x": -3.4, "y": 2.05}, "speed_mps": 28.0, "scene": {"keeper_x": 0.4}}]}
        c = dict(SABLON_B, keeper_seeds=[i] + SABLON_B["keeper_seeds"][1:])
        o = pm.run(c, d)["kicks"][0]
        seen.add(o["outcome"])
        if o["outcome"] in ("wide", "over", "post"):
            assert verify_mod.skor({"kicks": [o]}) == (0, 1)
            assert "saptı" in o["explain"], o["explain"]
        if {"goal", "wide", "over", "post"} <= seen:
            break
    assert {"goal", "wide", "over", "post"} <= seen, seen


def test_tur3b_template_and_rules():
    km = SABLON["keeper_model"]
    assert km["ucus"]["surum"] == "balistik-v1" and "travel_frac_ref" not in km
    assert cm.karar_farklari(SABLON) == [] and cm.karar_farklari(SABLON_A) == [] and cm.karar_farklari(SABLON_B) == []
    assert cm.secenek(SABLON_A) == "A" and cm.secenek(SABLON_B) == "B" and cm.secenek(SABLON) in ("A", "B")
    assert SABLON["sut_sapmasi"]["olcek"] == cm.TUR3B_KURALLARI["sut_sapmasi.olcek"]
    for fn in (lambda c: c["sut_sapmasi"].update(olcek=0.2), lambda c: c["sut_sapmasi"].update(acik="evet"),
               lambda c: c["sut_sapmasi"].update(delta_v=1.5), lambda c: c["keeper_model"]["ucus"].update(surum="eski")):
        c = copy.deepcopy(SABLON)
        fn(c)
        assert cm.karar_farklari(c), c["sut_sapmasi"]
    c = copy.deepcopy(SABLON)
    c["keeper_model"].pop("ucus")
    assert _raises(pm.keeper_params, c)          # eski kinematik yok
    assert cm.kural_ozeti(SABLON_A) != cm.kural_ozeti(SABLON_B)   # A/B seçimi duyuru özetine girer


def test_tur3b_verify_option_b():
    kod = cm.kod_ozetleri_hesapla(HERE, BEYIN_DIR)
    ds_a = cm.duyuru_ozeti(SABLON_A, kod)
    ds_b = cm.duyuru_ozeti(SABLON_B, kod)
    m = _mini("final", degis=lambda c: c["sut_sapmasi"].update(acik=True))
    cfg, t, bc, dec, log = m
    assert all(k["shot"]["sapma"] for k in log["kicks"])
    lab, lines = _v(*m, sablon=SABLON_B, kural_sha=ds_b)
    assert lab == "DOĞRULANDI", "\n".join(x for x in lines if not x.startswith("TAMAM"))
    assert any("SEÇENEK B" in x for x in lines)
    assert _v(*m, sablon=SABLON_A, kural_sha=ds_a)[0] == "DOĞRULANAMADI"   # A şablonuna ve A duyurusuna göre: kurallar farklı
    # taahhütten sonra sapma kapatılır / log'daki sapma elle değiştirilir
    c2 = copy.deepcopy(cfg)
    c2["sut_sapmasi"]["acik"] = False
    assert _v(c2, t, bc, dec, _rerun(c2, t, bc, dec), sablon=SABLON_B, kural_sha=ds_b)[0] == "DOĞRULANAMADI"
    lg = copy.deepcopy(log)
    lg["kicks"][0]["shot"]["sapma"]["hata_m"][0] += 0.05
    assert _v(cfg, t, bc, dec, lg, sablon=SABLON_B, kural_sha=ds_b)[0] == "DOĞRULANAMADI"
    # A ile de DOĞRULANDI (A şablonu ve A duyurusuyla)
    mA = _mini("final", degis=lambda c: c["sut_sapmasi"].update(acik=False))
    assert _v(*mA, sablon=SABLON_A, kural_sha=ds_a)[0] == "DOĞRULANDI"
    assert _v(*mA, sablon=SABLON_B, kural_sha=ds_b)[0] == "DOĞRULANAMADI"
    # bağımsız JS kontrolü B'nin sapmalarını da yeniden hesaplıyor
    node = shutil.which("node")
    if node:
        d = tempfile.mkdtemp(prefix="tur3b_js_")
        try:
            paths = {}
            for name, obj in (("b", bc), ("t", t), ("log", log), ("dec", dec)):
                paths[name] = os.path.join(d, name + ".json")
                pm.write_json(paths[name], obj)
            js = os.path.join(HERE, "bagimsiz", "kontrol.mjs")
            p = subprocess.run([node, js, paths["b"], paths["t"], paths["log"], paths["dec"]],
                               capture_output=True, text=True, timeout=60)
            assert p.returncode == 0 and "BAĞIMSIZ KONTROL: TUTUYOR" in p.stdout and "sapması" in p.stdout, p.stdout
            pm.write_json(paths["log"], lg)
            p = subprocess.run([node, js, paths["b"], paths["t"], paths["log"], paths["dec"]],
                               capture_output=True, text=True, timeout=60)
            assert p.returncode == 1 and "TUTMUYOR" in p.stdout
        finally:
            shutil.rmtree(d, ignore_errors=True)


def main():
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, f in tests:
        t0 = _time.time()
        try:
            f()
            print(f"GEÇTİ  {name}  ({_time.time() - t0:.1f} s)")
        except AssertionError as e:
            failed += 1
            print("KALDI ", name, "->", str(e)[:1500])
    print(f"\n{len(tests) - failed}/{len(tests)} test geçti")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
