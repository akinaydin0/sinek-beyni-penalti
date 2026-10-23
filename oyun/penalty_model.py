#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
penalty_model.py - Sinek beyni vs Ugurcan: penalti fizik + kaleci motoru.

Saf Python 3 (yalniz standart kutuphane, numpy gerekmez). Deterministik:
ayni karar dosyasi + ayni config + ayni motor -> bayt bayt ayni penalty_log.json.

Formuller, sabitler ve kaynaklar: MODEL.md. Koordinatlar ve JSON bicimi: ../SOZLESME.md.
[tur3b 2026-10-22] Kaleci dalisi balistik (itme -> ucus: yatay hiz sabit, dikey ivme -g -> inis -> kayma);
istege bagli sut sapmasi (secenek B, config.sut_sapmasi.acik; varsayilan kapali). MODEL.md bolum 2 ve 8.
Butun sayisal sabitler config dosyasindan okunur (taahhut ozetine girerler);
burada yalnizca yapi (algoritma) vardir.

Kullanim:
  python3.12 -I penalty_model.py --karar ../veri/beyin_kararlari.json \
      --config config_prova.json --cikti ../veri/penalty_log.json \
      [--taahhut ../veri/taahhut_prova.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from statistics import NormalDist

ENGINE_NAME = "sinek-penalti/oyun/penalty_model.py"
ENGINE_VERSION = "1.1.1"  # [tur3b 2026-10-22] balistik kaleci + isteğe bağlı şut sapması; [tur4 2026-10-23] direkten gol
HERE = os.path.dirname(os.path.abspath(__file__))

# Keeper 'left/right' is HIS OWN left/right (Bar-Eli et al. 2007 convention).
# Contract: +x = shooter's right = keeper's LEFT.
SIDE_SIGN = {"left": +1, "right": -1, "stay": 0}


# --------------------------------------------------------------------------- hashing / canonical JSON
def canonical_json(obj) -> bytes:
    """Canonical form used for every hash: sorted keys, no spaces, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def engine_sha256() -> str:
    with open(os.path.abspath(__file__), "rb") as f:
        return sha256_hex(f.read())


def uniform(seed: int, label: str) -> float:
    """Language-independent uniform draw in (0,1): SHA-256 of '<seed>|<label>'.
    Anyone can recompute it (Python, JS, a website) from the revealed seed."""
    h = hashlib.sha256(f"{seed}|{label}".encode("utf-8")).digest()
    k = int.from_bytes(h[:7], "big")  # 56 bits
    return (k + 0.5) / float(1 << 56)


# --------------------------------------------------------------------------- small geometry helpers
def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def lerp(a, b, f):
    return tuple(ai + (bi - ai) * f for ai, bi in zip(a, b))


def seg_closest_2d(px, py, ax, ay, bx, by):
    """Closest point on segment AB to P (2D). Returns (dist, t, cx, cy)."""
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    t = 0.0 if l2 < 1e-12 else clamp(((px - ax) * dx + (py - ay) * dy) / l2, 0.0, 1.0)
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy), t, cx, cy


def seg_closest_3d(p, a, b):
    d = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    l2 = d[0] * d[0] + d[1] * d[1] + d[2] * d[2]
    t = 0.0 if l2 < 1e-12 else clamp(
        ((p[0] - a[0]) * d[0] + (p[1] - a[1]) * d[1] + (p[2] - a[2]) * d[2]) / l2, 0.0, 1.0)
    c = (a[0] + t * d[0], a[1] + t * d[1], a[2] + t * d[2])
    return math.dist(p, c), c


def smoothstep(f):
    f = clamp(f, 0.0, 1.0)
    return f * f * (3.0 - 2.0 * f)


def min_jerk(f):
    """[tur3b 2026-10-22] Minimum-jerk profile 0->1 (zero speed and acceleration at both ends)."""
    f = clamp(f, 0.0, 1.0)
    return f * f * f * (10.0 + f * (-15.0 + 6.0 * f))


def hermite_end_slope(y0, y1, m1, f):
    """[tur3b 2026-10-22] Cubic from y0 (slope 0) to y1 with end slope m1 (per unit of normalised time f).
    With m1 > 2*(y1-y0) it dips first: the countermovement before a push-off."""
    f = clamp(f, 0.0, 1.0)
    f2, f3 = f * f, f * f * f
    return y0 + (y1 - y0) * (3.0 * f2 - 2.0 * f3) + m1 * (f3 - f2)


# --------------------------------------------------------------------------- ball physics
class Ball:
    """Point-mass sphere: gravity + quadratic drag F = 1/2 rho Cd A v^2 (no spin / Magnus).
    Integrated with classical RK4 at physics.rk4_hz. Ground: bounce, then rolling friction."""

    def __init__(self, phys):
        self.g = phys["g"]
        self.r = phys["ball_radius_m"]
        area = math.pi * self.r * self.r
        self.k = 0.5 * phys["rho_air"] * phys["cd"] * area / phys["ball_mass_kg"]  # 1/m
        self.dt = 1.0 / phys["rk4_hz"]
        self.e_ground = phys["e_ground"]
        self.ground_keep = phys["ground_tangent_keep"]
        self.roll_thr = phys["roll_threshold_mps"]
        self.mu_roll = phys["rolling_decel_mps2"]

    def acc(self, v, rolling):
        vx, vy, vz = v
        s = math.sqrt(vx * vx + vy * vy + vz * vz)
        ax, ay, az = -self.k * s * vx, -self.g - self.k * s * vy, -self.k * s * vz
        if rolling:
            ay = 0.0
            h = math.hypot(vx, vz)
            if h > 1e-6:
                ax -= self.mu_roll * vx / h
                az -= self.mu_roll * vz / h
        return ax, ay, az

    def rk4(self, p, v, rolling):
        dt = self.dt
        a1 = self.acc(v, rolling)
        v2 = (v[0] + 0.5 * dt * a1[0], v[1] + 0.5 * dt * a1[1], v[2] + 0.5 * dt * a1[2])
        a2 = self.acc(v2, rolling)
        v3 = (v[0] + 0.5 * dt * a2[0], v[1] + 0.5 * dt * a2[1], v[2] + 0.5 * dt * a2[2])
        a3 = self.acc(v3, rolling)
        v4 = (v[0] + dt * a3[0], v[1] + dt * a3[1], v[2] + dt * a3[2])
        a4 = self.acc(v4, rolling)
        pn = tuple(p[i] + dt / 6.0 * (v[i] + 2 * v2[i] + 2 * v3[i] + v4[i]) for i in range(3))
        vn = tuple(v[i] + dt / 6.0 * (a1[i] + 2 * a2[i] + 2 * a3[i] + a4[i]) for i in range(3))
        return pn, vn

    def step(self, p, v, rolling):
        """One RK4 step plus ground contact. Returns (p, v, rolling)."""
        pn, vn = self.rk4(p, v, rolling)
        if rolling:
            pn = (pn[0], self.r, pn[2])
            vn = (vn[0], 0.0, vn[2])
            if math.hypot(vn[0], vn[2]) < self.mu_roll * self.dt * 1.5:
                vn = (0.0, 0.0, 0.0)
            return pn, vn, True
        if pn[1] < self.r and vn[1] < 0.0:
            f = clamp((p[1] - self.r) / max(p[1] - pn[1], 1e-12), 0.0, 1.0)
            pc = lerp(p, pn, f)
            vc = lerp(v, vn, f)
            vy = -self.e_ground * vc[1]
            vb = (vc[0] * self.ground_keep, vy, vc[2] * self.ground_keep)
            if vy < self.roll_thr:
                vb = (vb[0], 0.0, vb[2])
                rolling = True
            rest = (1.0 - f) * self.dt
            pn = (pc[0] + rest * vb[0], max(self.r, pc[1] + rest * vb[1]), pc[2] + rest * vb[2])
            vn = vb
        return pn, vn, rolling


def fly_to_plane(ball, p0, v0, zp, t_max):
    """Free flight (gravity, drag, ground only) until the ball centre crosses z = zp.
    Returns (t, p, v) at the crossing, or None."""
    p, v, rolling, t = p0, v0, False, 0.0
    n = int(t_max / ball.dt) + 1
    for _ in range(n):
        pn, vn, rolling = ball.step(p, v, rolling)
        if p[2] > zp >= pn[2]:
            f = (p[2] - zp) / (p[2] - pn[2])
            return t + f * ball.dt, lerp(p, pn, f), lerp(v, vn, f)
        p, v, t = pn, vn, t + ball.dt
    return None


def solve_launch(ball, phys, aim_x, aim_y, speed):
    """Find the launch direction so that the ball centre crosses the goal-line plane z=0
    at (aim_x, aim_y). Drag is anti-parallel to velocity, so the horizontal path is a
    straight line and x is exact; y is found by fixed-point iteration on the virtual target."""
    spot = tuple(phys["spot"])
    tx, ty = aim_x, aim_y
    last = None
    for _ in range(60):
        d = (tx - spot[0], ty - spot[1], 0.0 - spot[2])
        n = math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2)
        v0 = (d[0] / n * speed, d[1] / n * speed, d[2] / n * speed)
        res = fly_to_plane(ball, spot, v0, 0.0, phys["t_max_s"])
        if res is None:
            return v0, False, last
        _, pc, _ = res
        last = pc
        ex, ey = aim_x - pc[0], aim_y - pc[1]
        if abs(ex) < 1e-6 and abs(ey) < 1e-6:
            return v0, True, pc
        tx += ex
        ty += ey
        if ty > 60.0:  # physically unreachable target: give up, keep best direction
            break
    return v0, False, last


# --------------------------------------------------------------------------- keeper model
def keeper_params(cfg):
    """Every keeper number derives from FC ratings + height via config constants (MODEL.md)."""
    kc, km = cfg["keeper"], cfg["keeper_model"]
    uc = km.get("ucus")
    if not isinstance(uc, dict) or uc.get("surum") != "balistik-v1":
        raise SystemExit("HATA: config.keeper_model.ucus (surum 'balistik-v1') yok. [tur3b 2026-10-22] Eski kaleci "
                         "kinematiği (yatay uçup havada duran ağırlık merkezi) kaldırıldı; MODEL.md bölüm 2.")
    H = kc["height_m"]
    R = kc["ratings"]
    reaction_s = (km["rt_base_ms"] - km["rt_ms_per_point"] * (R["reflexes"] - km["rt_ref_rating"])) / 1000.0
    # [tur3b 2026-10-22] v_dive = kalkış anındaki YATAY ağırlık merkezi hızı (uçuşta sabit kalır)
    v_dive = km["dive_speed_ref_mps"] * (1.0 + km["dive_speed_per_point"] * (R["diving"] - km["dive_ref_rating"]))
    L_leg, L_torso, L_arm = km["leg_frac"] * H, km["torso_frac"] * H, km["arm_frac"] * H
    kp = {
        "H": H,
        "reaction_s": reaction_s,
        "v_dive": v_dive,
        "t_push": km["push_time_s"],
        "com0_y": km["com_height_frac"] * H,
        "L_leg": L_leg, "L_torso": L_torso, "L_arm": L_arm,
        "L_push": (km["leg_frac"] + uc["toe_frac"]) * H,   # COM -> toe tip with the ankle extended
        "arm_from_com": L_torso + L_arm,
        "r_leg": km["r_leg_m"], "r_torso": km["r_torso_m"], "r_hand": km["r_hand_m"],
        "v_hand": km["hand_speed_mps"],
        "ready_hand": tuple(km["ready_hand_offset_m"]),
        "phi0": math.radians(km["blind_dive_angle_deg"]),
        "phi_min": math.radians(km["dive_angle_min_deg"]),
        "phi_max": math.radians(km["dive_angle_max_deg"]),
        "jump_cap": km["jump_cap_m"],
        "y_lying": km["lying_com_y_m"],
        "informed_stop_frac": km["informed_stop_frac"],
        "dive_min_travel": km["dive_min_travel_m"],
        "pos_pull": clamp(km["positioning_pull_per_point"] * R["positioning"], 0.0, 1.0),
        "handling": R["handling"],
        "g": cfg["physics"]["g"],
        # [tur3b 2026-10-22] balistik dalış sabitleri (keeper_model.ucus, MODEL.md bölüm 2)
        "leg_to": math.radians(uc["leg_angle_takeoff_deg"]),
        "lean_to": math.radians(uc["torso_lean_takeoff_deg"]),
        "step_lift": uc["sidestep_lift_m"],
        "land_keep": uc["landing_keep_h"],
        "slide_mu": uc["slide_mu"],
        "step_min_s": uc["step_time_min_s"],
        "crouch_min": uc["crouch_com_min_m"],
        "settle_s": uc["hand_settle_delay_s"],
    }
    kp["reach_m"] = nominal_reach(kp, km["leave_mean_s"], uc["reach_ref_t_s"], cfg["physics"]["rk4_hz"])
    kp["reach_ref_t_s"] = uc["reach_ref_t_s"]
    return kp


def nominal_reach(kp, leave_s, t_ref, hz):
    """[tur3b 2026-10-22] Reported 'reach_m': lateral distance from the start to the fingertips at t_ref (ball
    arrival, ~0,50 s) for a BLIND dive leaving at the mean leave time, arms stretched along the body.
    Not a cap: the physics has no travel limit, only take-off speed, gravity and the ground."""
    dt = 1.0 / hz
    kt = KeeperTimeline(kp, {"dive_dir": "left", "leave_drawn_s": leave_s}, 0.0, None, t_ref - 0.1, t_ref + dt, dt)
    C, th, _, _ = kt._body(t_ref)
    S = (C[0] + kp["L_torso"] * math.cos(th), C[1] + kp["L_torso"] * math.sin(th))
    return S[0] + kp["L_arm"] * math.cos(th)


def draw_plan(cfg, kseed: int, n: int):
    """Keeper plan for kick n, drawn from the seed only (the shot is NOT an input)."""
    km = cfg["keeper_model"]
    p = km["dive_probs"]
    u_dir = uniform(kseed, f"kick{n}|dive_dir")
    u_leave = uniform(kseed, f"kick{n}|leave_time")
    u_catch = uniform(kseed, f"kick{n}|catch")
    u_keep = uniform(kseed, f"kick{n}|keep_out")  # only used if keeper_model.in_reach_save_model is set
    if u_dir < p["left"]:
        dive = "left"
    elif u_dir < p["left"] + p["stay"]:
        dive = "stay"
    else:
        dive = "right"
    z = NormalDist().inv_cdf(u_leave)
    leave = clamp(km["leave_mean_s"] + km["leave_sd_s"] * z, km["leave_min_s"], km["leave_max_s"])
    return {"dive_dir": dive, "leave_drawn_s": leave, "u_catch": u_catch, "u_keep": u_keep,
            "u": {"dive_dir": u_dir, "leave_time": u_leave, "catch": u_catch, "keep_out": u_keep}}


class KeeperTimeline:
    """[tur3b 2026-10-22] Keeper body in the keeper plane (z = keeper_plane_z) on the RK4 time grid.
    Body = 3 capsules: legs (feet-COM), torso (COM-shoulder), arm (shoulder-hand).

    BALLISTIC DIVE ('balistik-v1', MODEL.md section 2), replacing the old path whose COM flew sideways at constant
    speed, stopped in mid-air and then dropped straight down:
      1) push-off (push_time_s): COM accelerates sideways at a constant rate to the take-off speed v_dive; the
         vertical goes through a countermovement dip (cubic) to the take-off height with the take-off vertical speed;
         the feet stay on the ground (side-step, then the push foot is planted);
      2) flight: COM is a projectile: horizontal speed constant, vertical a = -g (no drag, no lift);
      3) landing when the COM reaches the lying height, then a slide with friction until rest.
    Take-off vertical speed = v_dive*tan(dive angle), limited by the jump cap (apex) and by the countermovement
    (the dip cannot be faster than free fall). Stay keepers step (minimum-jerk) or dive reactively after RT.
    """

    def __init__(self, kp, plan, x_start, bstar, t0, t1, dt, t_ball=None):
        self.kp, self.plan, self.dt, self.t0 = kp, plan, dt, t0
        y0 = kp["com0_y"]
        C0 = (x_start, y0)
        self.C0 = C0
        self.x0 = x_start
        t_p = kp["reaction_s"]
        side = SIDE_SIGN[plan["dive_dir"]]
        self.side = side
        self.adapted = False
        self.mode = "stand"
        self.s = side
        phi = kp["phi0"]
        if side == 0:
            # Stays in the centre; starts moving only when he perceives the ball (t = reaction).
            self.t_m = t_p
            if bstar is not None:
                dx, dy = bstar[0] - C0[0], bstar[1] - C0[1]
                dist = math.hypot(dx, dy)
                d = (dx / dist, dy / dist) if dist > 1e-9 else (0.0, 1.0)
                p_need = max(0.0, dist - kp["informed_stop_frac"] * kp["arm_from_com"])
                if p_need * abs(d[0]) >= kp["dive_min_travel"]:
                    self.mode = "dive"      # reactive dive towards the ball, height chosen (he sees it)
                    self.s = 1 if dx > 0 else -1
                    phi = clamp(math.atan2(dy, abs(dx)), kp["phi_min"], kp["phi_max"])
                    self.adapted = True
                elif p_need > 0.0:
                    self.mode = "step"
                    self.step = (p_need * d[0], p_need * d[1])
        else:
            self.t_m = plan["leave_drawn_s"]
            self.mode = "dive"
            # If he sees the ball before his feet leave the ground he may still pick the dive
            # HEIGHT (never the side: the side was drawn before the shot).
            if bstar is not None and t_p <= self.t_m + kp["t_push"] and (bstar[0] - x_start) * side > 0:
                phi = clamp(math.atan2(bstar[1] - C0[1], abs(bstar[0] - x_start)), kp["phi_min"], kp["phi_max"])
                self.adapted = True
        self.is_dive = self.mode == "dive"
        self.t_takeoff = self.t_land = self.t_rest = None
        self.vy0 = None
        if self.mode == "dive":
            self._setup_dive(phi)
        elif self.mode == "step":
            self._setup_step()
        # integrate arm (hand offset relative to shoulder)
        n = int(round((t1 - t0) / dt)) + 1
        self.n = n
        self.C, self.S, self.Hd, self.F = [], [], [], []
        o = kp["ready_hand"]
        L_eff = kp["L_arm"] - kp["r_hand"]
        t_settle = (t_ball + kp["settle_s"]) if t_ball is not None else None
        for i in range(n):
            t = t0 + i * dt
            C, th, F, f_arm = self._body(t)
            u = (math.cos(th), math.sin(th))
            S = (C[0] + kp["L_torso"] * u[0], max(0.10, C[1] + kp["L_torso"] * u[1]))
            if t < t_p or bstar is None:
                if self.is_dive and t > self.t_m:
                    o = lerp(kp["ready_hand"], (L_eff * u[0], L_eff * u[1]), f_arm)
                else:
                    o = kp["ready_hand"]
            else:
                if t_settle is not None and t >= t_settle:
                    # after the ball has gone past: hands come back to the body (no arm left up in the air)
                    if abs(u[0]) < 0.5:
                        tx, ty = kp["ready_hand"]
                    else:
                        tx, ty = 0.6 * L_eff * u[0], 0.6 * L_eff * u[1]
                else:
                    tx, ty = bstar[0] - S[0], bstar[1] - S[1]
                L = math.hypot(tx, ty)
                if L > L_eff:
                    tx, ty = tx / L * L_eff, ty / L * L_eff
                ex, ey = tx - o[0], ty - o[1]
                e = math.hypot(ex, ey)
                stepmax = kp["v_hand"] * dt
                if e > stepmax:
                    ex, ey = ex / e * stepmax, ey / e * stepmax
                o = (o[0] + ex, o[1] + ey)
                L = math.hypot(o[0], o[1])
                if L > L_eff:  # the body moved: keep the arm length physical
                    o = (o[0] / L * L_eff, o[1] / L * L_eff)
            Hd = (S[0] + o[0], max(0.02, S[1] + o[1]))
            self.C.append(C)
            self.S.append(S)
            self.Hd.append(Hd)
            self.F.append(F)

    # ------------------------------------------------------------------ set-up
    def _setup_dive(self, phi):
        kp = self.kp
        g, V, T = kp["g"], kp["v_dive"], kp["t_push"]
        y0 = self.C0[1]
        s = self.s
        y_to_max = kp["L_push"] * math.sin(kp["leg_to"])   # COM height with the push leg at its take-off angle
        vy = V * math.tan(phi)
        if vy > 0.0:
            y_to = min(y0 + 0.5 * vy * T, y_to_max)
            dl = y_to - y0
            vy_cap = math.sqrt(max(0.0, 2.0 * g * (y0 + kp["jump_cap"] - y_to)))   # apex <= standing + jump cap
            vy_ff = (3.0 * dl + 0.5 * g * T * T) / T                               # dip no faster than free fall
            vy = min(vy, vy_cap, vy_ff)
            y_to = min(y0 + 0.5 * vy * T, y_to_max)
        else:
            y_to = max(y0 + 0.5 * vy * T, kp["y_lying"] + 0.05)
        self.phi = phi
        self.vy0 = vy
        self.y_to = y_to
        self.x_to = self.x0 + s * 0.5 * V * T
        self.t_takeoff = self.t_m + T
        disc = vy * vy + 2.0 * g * (y_to - kp["y_lying"])
        self.tf_land = (vy + math.sqrt(max(disc, 0.0))) / g
        self.t_land = self.t_takeoff + self.tf_land
        self.x_land = self.x_to + s * V * self.tf_land
        self.apex_y = y_to + (vy * vy / (2.0 * g) if vy > 0 else 0.0)
        self.v_slide = V * kp["land_keep"]
        self.a_slide = kp["slide_mu"] * g
        self.T_slide = self.v_slide / self.a_slide if self.a_slide > 1e-9 else 0.0
        self.t_rest = self.t_land + self.T_slide
        self.th_to = math.pi / 2 - s * kp["lean_to"]
        self.th_flat = 0.0 if s > 0 else math.pi
        foot_off = y_to / math.tan(kp["leg_to"])
        self.F_p = (self.x_to - s * foot_off, 0.0)           # planted push foot (after the side-step)
        self.leg_dir_to = math.atan2(y_to, s * foot_off)     # direction foot -> COM at take-off
        self.leg_len_to = math.hypot(foot_off, y_to)

    def _setup_step(self):
        kp = self.kp
        dx, dy = self.step
        V = kp["v_dive"]
        self.T_step = max(kp["step_min_s"], 1.875 * abs(dx) / V) if V > 0 else kp["step_min_s"]
        y0 = self.C0[1]
        self.dy_step = max(dy, kp["crouch_min"] - y0) if dy < 0 else 0.0
        self.jump = None
        if dy > 0:
            g, T = kp["g"], kp["t_push"]
            h = min(dy, kp["jump_cap"])
            vj = min(math.sqrt(2.0 * g * h), 0.5 * g * T)   # countermovement no faster than free fall
            self.jump = (vj, self.t_m + T, 2.0 * vj / g)
            self.t_takeoff = self.t_m + T
            self.t_land = self.t_m + T + 2.0 * vj / g
            self.vy0 = vj
        self.t_rest = max(self.t_m + self.T_step, self.t_land or 0.0)

    # ------------------------------------------------------------------ body at time t
    def _body(self, t):
        """(COM, torso angle, feet point, arm-stretch fraction) at time t (analytic, no state)."""
        kp = self.kp
        x0, y0 = self.C0
        up = math.pi / 2
        if self.mode == "stand" or t <= self.t_m:
            return (x0, y0), up, (x0, 0.0), 0.0
        tau = t - self.t_m
        g = kp["g"]
        if self.mode == "step":
            f = min_jerk(tau / self.T_step)
            cx = x0 + self.step[0] * f
            cy = y0 + self.dy_step * f
            if self.jump:
                vj, t_jto, tf = self.jump
                T = kp["t_push"]
                if t <= t_jto:
                    cy += hermite_end_slope(0.0, 0.0, vj * T, tau / T)
                elif t <= t_jto + tf:
                    tt = t - t_jto
                    cy += vj * tt - 0.5 * g * tt * tt
            return (cx, cy), up, (cx, max(0.0, cy - kp["L_leg"])), 0.0
        s, V, T = self.s, kp["v_dive"], kp["t_push"]
        if tau <= T:   # 1) push-off: feet on the ground
            r = tau / T
            cx = x0 + s * 0.5 * (V / T) * tau * tau
            cy = hermite_end_slope(y0, self.y_to, self.vy0 * T, r)
            th = up + (self.th_to - up) * smoothstep(r)
            rs = clamp(2.0 * r, 0.0, 1.0)
            fx = x0 + (self.F_p[0] - x0) * smoothstep(rs)
            fy = kp["step_lift"] * math.sin(math.pi * rs) if rs < 1.0 else 0.0   # planted after the side-step
            return (cx, cy), th, (fx, fy), smoothstep(r)
        tf = tau - T
        if tf <= self.tf_land:   # 2) flight: projectile
            cx = self.x_to + s * V * tf
            cy = max(self.y_to + self.vy0 * tf - 0.5 * g * tf * tf, kp["y_lying"])
            f = smoothstep(tf / self.tf_land) if self.tf_land > 1e-9 else 1.0
            th = self.th_to + (self.th_flat - self.th_to) * f
            psi = self.leg_dir_to + (self.th_flat - self.leg_dir_to) * f
            L = self.leg_len_to + (kp["L_leg"] - self.leg_len_to) * f
            return (cx, cy), th, (cx - L * math.cos(psi), max(0.0, cy - L * math.sin(psi))), 1.0
        ts = min(t - self.t_land, self.T_slide)   # 3) landing + slide with friction, then rest
        cx = self.x_land + s * (self.v_slide * ts - 0.5 * self.a_slide * ts * ts)
        cy = kp["y_lying"]
        th = self.th_flat
        return (cx, cy), th, (cx - kp["L_leg"] * math.cos(th), max(0.0, cy - kp["L_leg"] * math.sin(th))), 1.0

    def summary(self):
        """Phase times for the log (keeper.ucus)."""
        r4 = lambda x: (round(x, 4) if x is not None else None)  # noqa: E731
        out = {"model": "balistik-v1", "mode": self.mode, "movement_t": r4(self.t_m) if self.mode != "stand" else None,
               "takeoff_t": r4(self.t_takeoff), "landing_t": r4(self.t_land), "rest_t": r4(self.t_rest)}
        if self.mode == "dive":
            out.update({"takeoff_v_mps": [round(self.s * self.kp["v_dive"], 3), round(self.vy0, 3)],
                        "takeoff_com_y": round(self.y_to, 4), "apex_com_y": round(self.apex_y, 4),
                        "landing_com_x": round(self.x_land, 4),
                        "rest_com_x": round(self.x_land + self.s * 0.5 * self.v_slide * self.T_slide, 4)})
        return out

    def state(self, t):
        """Linear interpolation of the body points at time t."""
        x = (t - self.t0) / self.dt
        i = int(math.floor(x))
        i = clamp(i, 0, self.n - 2)
        f = clamp(x - i, 0.0, 1.0)
        return {k: lerp(arr[i], arr[i + 1], f) for k, arr in
                (("C", self.C), ("S", self.S), ("H", self.Hd), ("F", self.F))}


def contact_check(kp, ks, bx, by, r_ball):
    """Smallest gap between the ball surface and the keeper's body capsules.
    gap <= 0 means contact; -gap is how deep the save was."""
    parts = (("legs", ks["F"], ks["C"], kp["r_leg"]),
             ("torso", ks["C"], ks["S"], kp["r_torso"]),
             ("arm", ks["S"], ks["H"], kp["r_hand"]))
    best = None
    for name, a, b, rad in parts:
        d, t, cx, cy = seg_closest_2d(bx, by, a[0], a[1], b[0], b[1])
        gap = d - rad - r_ball
        if best is None or gap < best["gap"]:
            if d > 1e-9:
                sx, sy = cx + (bx - cx) / d * rad, cy + (by - cy) / d * rad
            else:
                sx, sy = cx, cy
            best = {"part": name, "gap": gap, "seg_t": t, "closest": (cx, cy), "surface": (sx, sy)}
    return best


# --------------------------------------------------------------------------- woodwork & net
def woodwork_segments(phys):
    W = phys["goal_half_width_m"] + phys["post_radius_m"]   # post axis x
    Hb = phys["crossbar_height_m"] + phys["post_radius_m"]  # bar axis y
    return (("post_left_of_keeper", (W, 0.0, 0.0), (W, Hb, 0.0)),    # +x = keeper's left
            ("post_right_of_keeper", (-W, 0.0, 0.0), (-W, Hb, 0.0)),
            ("crossbar", (-W, Hb, 0.0), (W, Hb, 0.0)))


def woodwork_hit(phys, p, pn, v, vn, dt):
    """Detect ball vs post/crossbar in this step; return (name, f, contact_p, new_v) or None."""
    R = phys["ball_radius_m"] + phys["post_radius_m"]
    for name, a, b in woodwork_segments(phys):
        d1, _ = seg_closest_3d(pn, a, b)
        if d1 >= R:
            continue
        d0, _ = seg_closest_3d(p, a, b)
        if d0 < R:  # already touching at step start (rebound in progress)
            continue
        lo, hi = 0.0, 1.0
        for _ in range(30):
            mid = 0.5 * (lo + hi)
            dm, _ = seg_closest_3d(lerp(p, pn, mid), a, b)
            if dm < R:
                hi = mid
            else:
                lo = mid
        f = hi
        pc = lerp(p, pn, f)
        vc = lerp(v, vn, f)
        _, c = seg_closest_3d(pc, a, b)
        nrm = (pc[0] - c[0], pc[1] - c[1], pc[2] - c[2])
        L = math.sqrt(sum(x * x for x in nrm)) or 1.0
        nrm = (nrm[0] / L, nrm[1] / L, nrm[2] / L)
        vn_ = vc[0] * nrm[0] + vc[1] * nrm[1] + vc[2] * nrm[2]
        if vn_ >= 0:
            continue
        vt = (vc[0] - vn_ * nrm[0], vc[1] - vn_ * nrm[1], vc[2] - vn_ * nrm[2])
        k = phys["post_tangent_keep"]
        e = phys["e_post"]
        newv = (vt[0] * k - e * vn_ * nrm[0], vt[1] * k - e * vn_ * nrm[1], vt[2] * k - e * vn_ * nrm[2])
        return name, f, pc, newv
    return None


def apply_net(phys, p, v, r):
    """Cheap box net behind the line (visual only; outcome is decided before)."""
    W, Hb, D = phys["goal_half_width_m"], phys["crossbar_height_m"], phys["net_depth_m"]
    e, keep = phys["e_net"], phys["net_tangent_keep"]
    x, y, z = p
    vx, vy, vz = v
    if z < -D + r:
        z = -D + r
        vz, vx, vy = abs(vz) * e, vx * keep, vy * keep
    if x > W - r:
        x, vx = W - r, -abs(vx) * e
    elif x < -W + r:
        x, vx = -W + r, abs(vx) * e
    if y > Hb - r:
        y, vy = Hb - r, -abs(vy) * e
    return (x, y, z), (vx, vy, vz)


# --------------------------------------------------------------------------- one kick
def simulate_kick(cfg, kp, aim, speed, plan, keeper_x_scene=0.0):
    phys = cfg["physics"]
    ball = Ball(phys)
    r = ball.r
    dt = ball.dt
    zk = phys["keeper_plane_z_m"]
    W, Hb = phys["goal_half_width_m"], phys["crossbar_height_m"]
    spot = tuple(phys["spot"])

    aim_x = float(aim["x"])
    aim_y_eff = max(float(aim["y"]), r)
    v0, solved, cross_goal = solve_launch(ball, phys, aim_x, aim_y_eff, float(speed))

    # free flight (no keeper, no woodwork) -> flight time to the goal line, keeper-plane crossing
    ff_goal = fly_to_plane(ball, spot, v0, 0.0, phys["t_max_s"])
    ff_kp = fly_to_plane(ball, spot, v0, zk, phys["t_max_s"])
    flight_time = ff_goal[0] if ff_goal else None
    bstar = (ff_kp[1][0], ff_kp[1][1]) if ff_kp else None
    t_ball = ff_kp[0] if ff_kp else None   # [tur3b 2026-10-22] hands settle only after the ball has gone past

    x_start = keeper_x_scene * (1.0 - kp["pos_pull"])
    t0k = phys["keeper_path_start_s"]
    kt = KeeperTimeline(kp, plan, x_start, bstar, t0k, phys["t_max_s"], dt, t_ball=t_ball)

    p, v, rolling, t = spot, v0, False, 0.0
    traj = [[0.0, round(p[0], 4), round(p[1], 4), round(p[2], 4)]]
    samp = int(round(phys["rk4_hz"] / phys["sample_fps"]))
    outcome = None
    event = None
    contact = None
    keeper_gap = None
    frame_miss = None
    caught_offset = None
    crossed_kp = crossed_goal = in_goal = False
    # [tur4 2026-10-23] direkten gol (Kural 10): direk/üst direk vuruşu sonucu HEMEN belirlemez. İlk ahşap vuruşu olay
    # olarak saklanır (ahsap); sonuç top kale çizgisini geçtiğinde verilir: çerçevenin içinden -> "goal" (direkten gol),
    # dışından ya da hiç geçmezse -> "post". Kurtarıştan (çelme) sonra ahşap/çizgi sonucu değiştirmez (çelinen top girmez).
    ahsap = None
    n_steps = int(round(phys["t_max_s"] / dt))
    km = cfg["keeper_model"]
    for i in range(1, n_steps + 1):
        tn = i * dt
        if caught_offset is not None:
            ks = kt.state(tn)
            # [tur3b 2026-10-22] the held ball follows the hand but never goes below the ground
            pn = (ks["H"][0] + caught_offset[0], max(r, ks["H"][1] + caught_offset[1]), zk)
            vn = (0.0, 0.0, 0.0)
        else:
            pn, vn, rolling = ball.step(p, v, rolling)
            # 1) keeper plane
            if not crossed_kp and p[2] > zk >= pn[2]:
                crossed_kp = True
                f = (p[2] - zk) / (p[2] - pn[2])
                tc = t + f * dt
                pc = lerp(p, pn, f)
                vc = lerp(v, vn, f)
                ks = kt.state(tc)
                cc = contact_check(kp, ks, pc[0], pc[1], r)
                keeper_gap = cc["gap"]
                beaten = False
                if cc["gap"] <= 0.0 and outcome is None:
                    depth = -cc["gap"]
                    vmag = math.sqrt(vc[0] ** 2 + vc[1] ** 2 + vc[2] ** 2)
                    irm = km.get("in_reach_save_model")
                    p_keep = None
                    if irm:  # OPTIONAL (off by default): Hunter 2018 P_save = a*kick_speed + b
                        p_keep = clamp(irm["a"] * float(speed) + irm["b"], 0.0, 1.0)
                        beaten = plan.get("u_keep", 0.0) >= p_keep
                if beaten:
                    contact = {"t": tc, "pos": [cc["surface"][0], cc["surface"][1], zk], "type": "fingertip",
                               "part": cc["part"], "depth_m": depth, "ball_speed_mps": vmag,
                               "p_catch": None, "beaten": True, "p_keep": p_keep}
                    rest = (1.0 - f) * dt
                    nv = (vc[0] * 0.92, vc[1] * 0.92, vc[2] * 0.92)
                    pn = (pc[0] + rest * nv[0], max(r, pc[1] + rest * nv[1]), pc[2] + rest * nv[2])
                    vn = nv
                elif cc["gap"] <= 0.0 and outcome is None:
                    outcome = "save"
                    if cc["part"] == "arm" and depth < km["fingertip_depth_m"] and cc["seg_t"] >= km["fingertip_seg_t"]:
                        ctype = "fingertip"
                    elif cc["part"] == "legs":
                        ctype = "parry"
                    else:
                        p_catch = (kp["handling"] / 100.0) \
                            * clamp((km["catch_v_hi_mps"] - vmag) / (km["catch_v_hi_mps"] - km["catch_v_lo_mps"]), 0.0, 1.0) \
                            * clamp(depth / km["catch_depth_full_m"], 0.0, 1.0)
                        ctype = "catch" if plan["u_catch"] < p_catch else "parry"
                        cc["p_catch"] = p_catch
                    contact = {"t": tc, "pos": [cc["surface"][0], cc["surface"][1], zk], "type": ctype,
                               "part": cc["part"], "depth_m": depth, "ball_speed_mps": vmag,
                               "p_catch": cc.get("p_catch"), "beaten": False, "p_keep": p_keep}
                    event = {"type": "keeper", "t": tc, "pos": [pc[0], pc[1], zk]}
                    if ctype == "catch":
                        caught_offset = (pc[0] - ks["H"][0], pc[1] - ks["H"][1])
                        pn, vn, rolling = (pc[0], pc[1], zk), (0.0, 0.0, 0.0), False
                    else:
                        nz = km["fingertip_normal_z"] if ctype == "fingertip" else km["parry_normal_z"]
                        cx, cy = cc["closest"]
                        nx, ny = pc[0] - cx, pc[1] - cy
                        L = math.sqrt(nx * nx + ny * ny + nz * nz)
                        nrm = (nx / L, ny / L, nz / L)
                        vdn = vc[0] * nrm[0] + vc[1] * nrm[1] + vc[2] * nrm[2]
                        e = km["parry_restitution"]
                        nv = (vc[0] - (1 + e) * vdn * nrm[0], vc[1] - (1 + e) * vdn * nrm[1], vc[2] - (1 + e) * vdn * nrm[2])
                        # a parried ball must not continue into the goal (keeper plane is 20 cm out)
                        if nv[2] < 0:
                            tl = pc[2] / -nv[2]
                            xg, yg = pc[0] + nv[0] * tl, pc[1] + nv[1] * tl
                            if abs(xg) < W + r + phys["post_radius_m"] * 2 and yg < Hb + r + phys["post_radius_m"] * 2:
                                nv = (nv[0], nv[1], abs(nv[2]) * 0.4 + 1.0)
                        rest = (1.0 - f) * dt
                        pn = (pc[0] + rest * nv[0], max(r, pc[1] + rest * nv[1]), pc[2] + rest * nv[2])
                        vn, rolling = nv, False
            # 2) woodwork
            if caught_offset is None:
                hit = woodwork_hit(phys, p, pn, v, vn, dt)
                if hit:
                    name, f, pc, newv = hit
                    if outcome is None and ahsap is None:
                        # [tur4 2026-10-23] sonuç kale çizgisinde verilir (yukarıda); olay ilk ahşap vuruşu kalır
                        ahsap = {"type": name, "t": t + f * dt, "pos": [pc[0], pc[1], pc[2]]}
                        event = ahsap
                    rest = (1.0 - f) * dt
                    pn = (pc[0] + rest * newv[0], max(r, pc[1] + rest * newv[1]), pc[2] + rest * newv[2])
                    vn, rolling = newv, False
            # 3) goal line plane
            if caught_offset is None and not crossed_goal and p[2] > 0.0 >= pn[2]:
                crossed_goal = True
                f = p[2] / (p[2] - pn[2])
                pc = lerp(p, pn, f)
                inside = abs(pc[0]) < W and pc[1] < Hb
                in_goal = inside
                if outcome is None and ahsap is not None:
                    # [tur4 2026-10-23] direk/üst direkten sonra çizgi: içeriden geçtiyse GOL (direkten gol), değilse direk
                    outcome = "goal" if inside else "post"
                    ahsap["direkten_gol"] = bool(inside)
                    ahsap["cizgi"] = {"t": t + f * dt, "pos": [pc[0], pc[1], 0.0]}
                elif outcome is None:
                    if inside:
                        outcome = "goal"
                    else:
                        wx = abs(pc[0]) - (W + 2 * phys["post_radius_m"]) - r
                        oy = pc[1] - (Hb + 2 * phys["post_radius_m"]) - r
                        outcome = "wide" if wx >= oy else "over"
                        frame_miss = max(wx, oy)
                    event = {"type": "goal_line", "t": t + f * dt, "pos": [pc[0], pc[1], 0.0]}
            if in_goal and pn[2] < 0.0:
                pn, vn = apply_net(phys, pn, vn, r)
        p, v, t = pn, vn, tn
        if i % samp == 0:
            traj.append([round(t, 4), round(p[0], 4), round(p[1], 4), round(p[2], 4)])
            if event is not None and t >= event["t"] + phys["post_event_s"]:
                # [tur4 2026-10-23] ahşaptan sonra karar bekliyorsa (çizgi henüz geçilmedi) top kaleye dönebildiği sürece
                # kesme: yalnız top çerçeveye artık değemeyecek kadar öndeyse ve kaleden uzaklaşıyor/duruyorsa bitir
                if not (outcome is None and ahsap is not None
                        and not (p[2] > r + 2 * phys["post_radius_m"] and v[2] >= 0.0)):
                    break

    if outcome is None and ahsap is not None:
        # [tur4 2026-10-23] ahşaptan sonra top kale çizgisini hiç geçmedi (sahaya döndü ya da durdu): direk
        outcome = "post"
        ahsap["direkten_gol"] = False
    t_end = traj[-1][0]
    # keeper path at 60 fps, from keeper_path_start_s to the end of the ball trajectory
    path = []
    k0 = int(math.floor(t0k * phys["sample_fps"] + 1e-9))
    k1 = int(round(t_end * phys["sample_fps"]))
    for k in range(k0, k1 + 1):
        tt = k / phys["sample_fps"]
        ks = kt.state(tt)
        path.append([round(tt, 4)] + [round(c, 4) for pt in ("C", "S", "H", "F") for c in ks[pt]])

    return {
        "aim_eff": (aim_x, aim_y_eff), "solved": solved, "v0": v0,
        "cross_goal": cross_goal, "flight_time": flight_time, "bstar": bstar,
        "x_start": x_start, "keeper": kt, "traj": traj, "path": path,
        "outcome": outcome, "event": event, "contact": contact,
        "keeper_gap": keeper_gap, "frame_miss": frame_miss,
        "speed_at_goal": (math.sqrt(sum(c * c for c in ff_goal[2])) if ff_goal else None),
    }


def _event_out(ev):
    """[tur4 2026-10-23] Log'daki olay. Direk/üst direk olaylarında EK alanlar: direkten_gol (true = top sonra kale
    çizgisini çerçevenin içinden geçti, sonuç GOL; false = sonuç direk) ve cizgi (varsa çizgiyi geçtiği an ve yer).
    type/t/pos aynı kaldı (ilk ahşap vuruşu), eski okuyucular bozulmaz; sonucu her zaman outcome söyler."""
    out = {"type": ev["type"], "t": round(ev["t"], 4), "pos": [round(x, 3) for x in ev["pos"]]}
    if "direkten_gol" in ev:
        out["direkten_gol"] = bool(ev["direkten_gol"])
        cz = ev.get("cizgi")
        out["cizgi"] = ({"t": round(cz["t"], 4), "pos": [round(x, 3) for x in cz["pos"]]} if cz else None)
    return out


# --------------------------------------------------------------------------- Turkish explanation
def _num(x, nd=2):
    return f"{x:.{nd}f}".replace(".", ",")


def _dist_tr(m):
    cm = m * 100.0
    if cm < 1.0:
        return "1 cm'den az"
    if cm < 100.0:
        return f"{int(round(cm))} cm"
    return f"{_num(m, 1)} metre"


def _genitive(name):
    """Turkish genitive suffix with apostrophe (vowel harmony)."""
    vowels = "aıoueiöüAIOUEİÖÜ"
    last = next((ch for ch in reversed(name) if ch in vowels), "a").lower()
    suf = {"a": "ın", "ı": "ın", "e": "in", "i": "in", "o": "un", "u": "un", "ö": "ün", "ü": "ün"}.get(last, "ın")
    if name[-1].lower() in "aıoueiöü":
        suf = "n" + suf
    return f"{name}'{suf}"


def explain_tr(name, res, plan, kp):
    """[tur3b 2026-10-22] With option B the miss sentences say how far the kick strayed from the brain's aim."""
    txt = _explain_core(name, res, plan, kp)
    sc = res.get("scatter")
    # [tur4 2026-10-23] direkten golde de sapma söylenir (topu direğe gönderen sapmadır)
    if sc and (res["outcome"] in ("wide", "over", "post") or _direkten_gol(res)):
        d = math.hypot(sc["err"][0], sc["err"][1])
        txt = f"Vuruş, sineğin nişanından {_dist_tr(d)} saptı. " + txt
    return txt


def _direkten_gol(res):
    ev = res.get("event") or {}
    return res["outcome"] == "goal" and bool(ev.get("direkten_gol"))


def _explain_core(name, res, plan, kp):
    out = res["outcome"]
    ft = res["flight_time"]
    ftxt = _num(ft) if ft is not None else "?"
    dive = plan["dive_dir"]
    side = SIDE_SIGN[dive]
    bx = res["bstar"][0] if res["bstar"] else 0.0
    rel = bx - res["x_start"]
    if side == 0:
        side_kind = "stay"
    elif abs(rel) < 0.5:
        side_kind = "centre_vs_dive"
    elif rel * side > 0:
        side_kind = "correct"
    else:
        side_kind = "wrong"
    rt = _num(kp["reaction_s"], 2)
    gap = res["keeper_gap"]
    if _direkten_gol(res):
        # [tur4 2026-10-23] direkten gol: top direğe/üst direğe çarpıp çizgiyi çerçevenin içinden geçti (Kural 10: gol)
        where = "üst direğe" if res["event"]["type"] == "crossbar" else "direğe"
        if res["contact"] and res["contact"].get("beaten"):
            return f"Top {_num(res['event']['t'])} saniyede {where} çarpıp ağlara gitti; {name} topa dokundu ama şutu durduramadı."
        return f"Top {_num(res['event']['t'])} saniyede {where} çarpıp ağlara gitti; {_genitive(name)} {_dist_tr(gap)} yetişemediği şut direkten gol oldu."
    if out == "goal" and res["contact"] and res["contact"].get("beaten"):
        kmh = int(round(res["contact"]["ball_speed_mps"] * 3.6))
        return f"Top {ftxt} saniyede kaleye vardı; {name} topa dokundu ama saatte {kmh} km hızla gelen şut elinden sıyrılıp ağlara gitti."
    if out == "goal":
        g = _dist_tr(gap)
        if side_kind == "stay":
            return f"Top {ftxt} saniyede kaleye vardı; {name} ortada bekleyip {rt} saniyede tepki verdi ama {g} yetişemedi."
        if side_kind == "correct":
            return f"Top {ftxt} saniyede kaleye vardı; {name} doğru tarafa atladı ama {g} yetişemedi."
        if side_kind == "centre_vs_dive":
            return f"Top {ftxt} saniyede kaleye vardı; {name} köşeye atladı, top ortadan girdi ve arada {g} kaldı."
        return f"Top {ftxt} saniyede kaleye vardı; {name} ters köşeye atladı, top ondan {g} uzaktan ağlara gitti."
    if out == "save":
        c = res["contact"]
        d = _dist_tr(c["depth_m"])
        verb = {"catch": "tuttu", "parry": "çeldi", "fingertip": "parmak uçlarıyla çeldi"}[c["type"]]
        if c["part"] == "legs" and side_kind in ("wrong", "centre_vs_dive"):
            return f"Top {ftxt} saniyede kaleye varacaktı; {name} köşeye atladı ama top geride kalan bacağına çarpıp döndü."
        if side_kind == "stay":
            return f"Top {ftxt} saniyede kaleye varacaktı; {name} ortada bekleyip {rt} saniyede tepki verdi ve topu {d} payla {verb}."
        if c["type"] == "fingertip":
            return f"Top {ftxt} saniyede kaleye varacaktı; {name} doğru tarafa atladı ve topu {verb}, temas yalnızca {d}."
        return f"Top {ftxt} saniyede kaleye varacaktı; {name} doğru tarafa atladı ve topu {d} payla {verb}."
    if out == "post":
        where = "üst direğe" if res["event"]["type"] == "crossbar" else "direğe"
        return f"Top {_num(res['event']['t'])} saniyede {where} çarptı; {_genitive(name)} {_dist_tr(gap)} yetişemediği şutu direk durdurdu."
    if out == "wide":
        return f"Şut direğin {_dist_tr(res['frame_miss'])} dışından auta gitti; {_genitive(name)} kurtarış yapmasına gerek kalmadı."
    if out == "over":
        return f"Şut üst direğin {_dist_tr(res['frame_miss'])} üstünden auta gitti; {_genitive(name)} kurtarış yapmasına gerek kalmadı."
    return "Sonuç hesaplanamadı."


# --------------------------------------------------------------------------- whole run
def kick_seeds(cfg, n_kicks):
    seeds = cfg.get("keeper_seeds")
    if not seeds or len(seeds) < n_kicks:
        raise SystemExit(f"config.keeper_seeds en az {n_kicks} seed içermeli (her şut için önceden yazılmış bir seed).")
    return [int(s) for s in seeds[:n_kicks]]


def effective_seeds(cfg, seeds, beacon):
    """Optional public beacon (e.g. a drand round published AFTER the story commitment).
    Mixing it in means nobody - Akın included - could have pre-picked favourable seeds."""
    if not cfg.get("beacon_rule"):
        return seeds
    if not beacon:
        raise SystemExit(f"config.beacon_rule var ({cfg['beacon_rule']}); --beacon DEGER zorunlu.")
    return [int(sha256_hex(f"{s}|beacon|{beacon}".encode())[:15], 16) for s in seeds]


# --------------------------------------------------------------------------- [tur3b 2026-10-22] shot scatter (option B)
def scatter_rule(cfg):
    """config.sut_sapmasi when it is switched ON (acik == true), else None. Default in config_sablon.json: OFF."""
    sc = cfg.get("sut_sapmasi")
    return sc if isinstance(sc, dict) and sc.get("acik") is True else None


def draw_scatter(cfg, kseed: int, n: int, aim, speed):
    """Execution error of kick n (MODEL.md section 8). Fixed, pre-registered rule; the brain's aim is the INTENDED aim.
      u1 = U(kseed, 'kick<n>|sapma_u1'), u2 = U(kseed, 'kick<n>|sapma_u2')   (same U as every other draw; kseed is
           the beacon-mixed keeper seed of kick n, so nobody could know it at commitment time)
      z1 = sqrt(-2 ln u1) cos(2 pi u2), z2 = sqrt(-2 ln u1) sin(2 pi u2)     (Box-Muller: two independent N(0,1))
      f  = clamp(aim_y / yukseklik_ref_m, 0, 1)
      sigma_x = olcek * (ah_zemin + (ah_yuksek - ah_zemin) f) * speed^delta_h   (Hunter et al. 2018, side-foot)
      sigma_y = olcek * (av_zemin + (av_yuksek - av_zemin) f) * speed^delta_v
      actual aim = intended aim + (sigma_x z1, sigma_y z2)
    Returns None when the rule is OFF."""
    sc = scatter_rule(cfg)
    if sc is None:
        return None
    u1 = uniform(kseed, f"kick{n}|sapma_u1")
    u2 = uniform(kseed, f"kick{n}|sapma_u2")
    rad = math.sqrt(-2.0 * math.log(u1))
    z1 = rad * math.cos(2.0 * math.pi * u2)
    z2 = rad * math.sin(2.0 * math.pi * u2)
    ax, ay, v = float(aim["x"]), float(aim["y"]), float(speed)
    f = clamp(ay / sc["yukseklik_ref_m"], 0.0, 1.0)
    a_h = sc["alpha_h_zemin"] + (sc["alpha_h_yuksek"] - sc["alpha_h_zemin"]) * f
    a_v = sc["alpha_v_zemin"] + (sc["alpha_v_yuksek"] - sc["alpha_v_zemin"]) * f
    sx = sc["olcek"] * a_h * v ** sc["delta_h"]
    sy = sc["olcek"] * a_v * v ** sc["delta_v"]
    ex, ey = sx * z1, sy * z2
    return {"u": (u1, u2), "z": (z1, z2), "sigma": (sx, sy), "err": (ex, ey),
            "aim": {"x": ax + ex, "y": ay + ey}}


def run(cfg, decisions, commit_sha=None, beacon=None):
    kp = keeper_params(cfg)
    kicks_in = decisions.get("kicks") or []
    if not kicks_in:
        raise SystemExit("Karar dosyasında 'kicks' yok.")
    seeds = effective_seeds(cfg, kick_seeds(cfg, max(int(k["n"]) for k in kicks_in)), beacon)
    stub = bool(decisions.get("stub"))
    mod = cfg.get("mod", "prova")
    prova = stub or bool(decisions.get("prova")) or mod != "final"
    name = cfg["keeper"].get("first_name") or cfg["keeper"]["name"].split()[0]
    out_kicks = []
    for k in sorted(kicks_in, key=lambda k: int(k["n"])):
        n = int(k["n"])
        plan = draw_plan(cfg, seeds[n - 1], n)
        scene = k.get("scene") or {}
        # [tur3b 2026-10-22] option B: the brain's aim is the intended aim; the foot adds a seeded execution error
        sc = draw_scatter(cfg, seeds[n - 1], n, k["aim"], k["speed_mps"])
        aim_kick = sc["aim"] if sc else k["aim"]
        res = simulate_kick(cfg, kp, aim_kick, k["speed_mps"], plan, float(scene.get("keeper_x", 0.0)))
        res["scatter"] = sc
        kt = res["keeper"]
        if res["outcome"] == "save":
            margin = res["contact"]["depth_m"]
        elif res["outcome"] in ("wide", "over"):
            margin = res["frame_miss"]
        else:
            margin = res["keeper_gap"]
        c = res["contact"]
        contact = None
        if c:
            contact = {"t": round(c["t"], 4), "pos": [round(x, 3) for x in c["pos"]], "type": c["type"],
                       "part": c["part"], "depth_cm": round(c["depth_m"] * 100, 1),
                       "ball_speed_mps": round(c["ball_speed_mps"], 2),
                       "p_catch": (round(c["p_catch"], 3) if c["p_catch"] is not None else None),
                       "beaten": c["beaten"],
                       "p_keep": (round(c["p_keep"], 3) if c["p_keep"] is not None else None)}
        leave_out = kt.t_m
        out_kicks.append({
            "n": n,
            "beyin": {key: k.get(key) for key in ("trial_seed", "steer", "power_spikes", "decision_ms", "scene")},
            "shot": {
                "aim": {"x": k["aim"]["x"], "y": k["aim"]["y"]},
                "speed_mps": k["speed_mps"],
                "flight_time_s": round(res["flight_time"], 3) if res["flight_time"] is not None else None,
                "trajectory": res["traj"],
                "aim_effective": {"x": round(res["aim_eff"][0], 4), "y": round(res["aim_eff"][1], 4)},
                "aim_solved": res["solved"],
                "launch_velocity": [round(x, 4) for x in res["v0"]],
                "speed_at_goal_line_mps": round(res["speed_at_goal"], 2) if res["speed_at_goal"] else None,
                # [tur3b 2026-10-22] şut sapması (seçenek B); kapalıysa null ve aim_effective = aim
                "sapma": ({"kural": cfg["sut_sapmasi"]["surum"],
                           "u": [round(x, 9) for x in sc["u"]], "z": [round(x, 6) for x in sc["z"]],
                           "sigma_m": [round(x, 4) for x in sc["sigma"]], "hata_m": [round(x, 4) for x in sc["err"]],
                           "nisan_niyet": {"x": k["aim"]["x"], "y": k["aim"]["y"]},
                           "nisan_gercek": {"x": round(sc["aim"]["x"], 4), "y": round(sc["aim"]["y"], 4)}}
                          if sc else None),
            },
            "keeper": {
                "dive_dir": plan["dive_dir"],
                "leave_time_s": round(leave_out, 3),
                "reaction_s": round(kp["reaction_s"], 3),
                "reach_m": round(kp["reach_m"], 2),
                "contact": contact,
                "start_x": round(res["x_start"], 4),
                "leave_drawn_s": round(plan["leave_drawn_s"], 3),
                "dive_speed_mps": round(kp["v_dive"], 2),
                "dive_height_adapted": kt.adapted,
                "seed_uniforms": {key: round(val, 6) for key, val in plan["u"].items()},
                "plane_z": cfg["physics"]["keeper_plane_z_m"],
                "ucus": kt.summary(),  # [tur3b 2026-10-22] balistik dalışın evreleri (kalkış, iniş, duruş)
                "path_fields": ["t", "com_x", "com_y", "shoulder_x", "shoulder_y", "hand_x", "hand_y", "feet_x", "feet_y"],
                "path": res["path"],
            },
            "outcome": res["outcome"],
            "margin_cm": int(round(margin * 100)) if margin is not None else None,
            "keeper_gap_cm": round(res["keeper_gap"] * 100, 1) if res["keeper_gap"] is not None else None,
            "event": (_event_out(res["event"]) if res["event"] else None),
            "explain": explain_tr(name, res, plan, kp),
        })
    cfg_sha = sha256_hex(canonical_json(cfg))
    dec_sha = sha256_hex(canonical_json(decisions))
    eng = engine_sha256()
    run_id = ("PROVA-" if prova else "FINAL-") + sha256_hex((cfg_sha + dec_sha + eng).encode())[:10]
    kc = cfg["keeper"]
    phys = cfg["physics"]
    log = {
        "run_id": run_id,
        "commit_sha256": commit_sha,
        "seed": cfg["seed"],
        "keeper": {"name": kc["name"], "number": kc["number"], "height_m": kc["height_m"],
                   "ratings": kc["ratings"], "source": kc["source"]},
        "kicks": out_kicks,
        "prova": prova,
        "stub": stub,
        "UYARI": ("PROVA / STUB: sahte (elle yazılmış) karar dosyasıyla üretildi, gerçek sonuç DEĞİL." if stub else
                  ("PROVA: taahhütten önce yapılan deneme koşusu, yayınlanacak sonuç DEĞİL." if prova else None)),
        "keeper_seeds": seeds,
        "sut_sapmasi_acik": scatter_rule(cfg) is not None,  # [tur3b 2026-10-22]
        "beacon": ({"rule": cfg["beacon_rule"], "value": beacon} if cfg.get("beacon_rule") else None),
        "engine": {"name": ENGINE_NAME, "version": ENGINE_VERSION, "sha256": eng},
        "config_sha256": cfg_sha,
        "decisions_sha256": dec_sha,
        "decisions_readout_sha256": decisions.get("readout_sha256"),
        "pitch": {
            "post_inner_x": phys["goal_half_width_m"],
            "post_axis_x": phys["goal_half_width_m"] + phys["post_radius_m"],
            "post_radius": phys["post_radius_m"],
            "crossbar_lower_y": phys["crossbar_height_m"],
            "crossbar_axis_y": phys["crossbar_height_m"] + phys["post_radius_m"],
            "woodwork_axis_z": 0.0,
            "net_depth": phys["net_depth_m"],
            "ball_radius": phys["ball_radius_m"],
            "spot": phys["spot"],
            "keeper_plane_z": phys["keeper_plane_z_m"],
            "note": "x+ = şutörün sağı = kalecinin SOLU. Kaleci 'left/right' kendi solu/sağıdır.",
        },
    }
    return log


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _is_scalar(x):
    return x is None or isinstance(x, (bool, int, float, str))


def dumps_readable(obj, ind=0):
    """Deterministic, readable JSON: objects indented, numeric rows (trajectory) one per line."""
    pad, pad1 = " " * ind, " " * (ind + 1)
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        items = [f"{pad1}{json.dumps(k, ensure_ascii=False)}: {dumps_readable(v, ind + 1)}" for k, v in obj.items()]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    if isinstance(obj, list):
        if all(_is_scalar(x) for x in obj):
            return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        if all(isinstance(x, list) and all(_is_scalar(y) for y in x) for x in obj):
            rows = [pad1 + json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in obj]
            return "[\n" + ",\n".join(rows) + "\n" + pad + "]"
        return "[\n" + ",\n".join(pad1 + dumps_readable(x, ind + 1) for x in obj) + "\n" + pad + "]"
    return json.dumps(obj, ensure_ascii=False)


def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(dumps_readable(obj))
        f.write("\n")
    os.replace(tmp, path)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Penaltı motoru: beyin kararları + config -> penalty_log.json")
    ap.add_argument("--karar", required=True, help="beyin_kararlari.json (ya da stub)")
    ap.add_argument("--config", required=True)
    ap.add_argument("--cikti", required=True)
    ap.add_argument("--taahhut", help="commit.py'nin yazdığı taahhüt dosyası (final için zorunlu)")
    ap.add_argument("--beacon", help="config.beacon_rule varsa: taahhütten sonra yayınlanan açık rastgele değer")
    a = ap.parse_args(argv)
    cfg = load_json(a.config)
    dec = load_json(a.karar)
    commit_sha = None
    if a.taahhut:
        t = load_json(a.taahhut)
        sys.path.insert(0, HERE)
        from commit import build_payload  # our own file in this folder
        payload = build_payload(cfg, t["payload"].get("readout_sha256"))
        sha = sha256_hex(canonical_json(payload))
        if sha != t["sha256"]:
            raise SystemExit("HATA: config/motor taahhütle uyuşmuyor (biri değişmiş). Koşu iptal.")
        if t["payload"].get("readout_sha256") and dec.get("readout_sha256") and \
                t["payload"]["readout_sha256"] != dec["readout_sha256"]:
            raise SystemExit("HATA: beyin dosyasının readout_sha256'sı taahhüttekiyle aynı değil. Koşu iptal.")
        commit_sha = sha
    if cfg.get("mod") == "final":
        if dec.get("stub") or dec.get("prova"):
            raise SystemExit("HATA: final modda stub/prova karar dosyası kullanılamaz.")
        if not commit_sha:
            raise SystemExit("HATA: final koşu için --taahhut zorunlu (önce story'de özet paylaşılmalı).")
    log = run(cfg, dec, commit_sha, beacon=a.beacon)
    write_json(a.cikti, log)
    for k in log["kicks"]:
        print(f"[{log['run_id']}] şut {k['n']}: {k['outcome']:5s} ({k['margin_cm']} cm) | {k['explain']}")
    print(f"yazıldı: {a.cikti}")


if __name__ == "__main__":
    main()
