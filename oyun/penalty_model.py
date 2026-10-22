#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
penalty_model.py - Sinek beyni vs Ugurcan: penalti fizik + kaleci motoru.

Saf Python 3 (yalniz standart kutuphane, numpy gerekmez). Deterministik:
ayni karar dosyasi + ayni config + ayni motor -> bayt bayt ayni penalty_log.json.

Formuller, sabitler ve kaynaklar: MODEL.md. Koordinatlar ve JSON bicimi: ../SOZLESME.md.
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
ENGINE_VERSION = "1.0.0"
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
    H = kc["height_m"]
    R = kc["ratings"]
    reaction_s = (km["rt_base_ms"] - km["rt_ms_per_point"] * (R["reflexes"] - km["rt_ref_rating"])) / 1000.0
    v_dive = km["dive_speed_ref_mps"] * (1.0 + km["dive_speed_per_point"] * (R["diving"] - km["dive_ref_rating"]))
    travel = H * (km["travel_frac_ref"] + km["travel_frac_per_point"] * (R["diving"] - km["dive_ref_rating"]))
    L_leg, L_torso, L_arm = km["leg_frac"] * H, km["torso_frac"] * H, km["arm_frac"] * H
    return {
        "H": H,
        "reaction_s": reaction_s,
        "v_dive": v_dive,
        "t_push": km["push_time_s"],
        "travel_max": travel,
        "com0_y": km["com_height_frac"] * H,
        "L_leg": L_leg, "L_torso": L_torso, "L_arm": L_arm,
        "arm_from_com": L_torso + L_arm,
        "reach_m": travel + L_torso + L_arm,  # lateral fingertip reach at full stretch
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
    }


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
    """Keeper body in the keeper plane (z = keeper_plane_z) on the RK4 time grid.
    Body = 3 capsules: legs (feet-COM), torso (COM-shoulder), arm (shoulder-hand)."""

    def __init__(self, kp, plan, x_start, bstar, t0, t1, dt):
        self.kp, self.plan, self.dt, self.t0 = kp, plan, dt, t0
        C0 = (x_start, kp["com0_y"])
        self.C0 = C0
        t_p = kp["reaction_s"]
        side = SIDE_SIGN[plan["dive_dir"]]
        self.side = side
        self.adapted = False
        if side == 0:
            # Stays in the centre; starts moving only when he perceives the ball (t = reaction).
            self.t_m = t_p
            if bstar is not None:
                dx, dy = bstar[0] - C0[0], bstar[1] - C0[1]
                dist = math.hypot(dx, dy)
            else:
                dx, dy, dist = 0.0, 1.0, 0.0
            self.d = (dx / dist, dy / dist) if dist > 1e-9 else (0.0, 1.0)
            self.p_max = clamp(dist - kp["informed_stop_frac"] * kp["arm_from_com"], 0.0, kp["travel_max"])
            self.is_dive = self.p_max >= kp["dive_min_travel"]
        else:
            self.t_m = plan["leave_drawn_s"]
            phi = kp["phi0"]
            # If he sees the ball before his feet leave the ground he may still pick the dive
            # HEIGHT (never the side: the side was drawn before the shot).
            if bstar is not None and t_p <= self.t_m + kp["t_push"] and (bstar[0] - x_start) * side > 0:
                phi = clamp(math.atan2(bstar[1] - C0[1], abs(bstar[0] - x_start)), kp["phi_min"], kp["phi_max"])
                self.adapted = True
            self.d = (side * math.cos(phi), math.sin(phi))
            self.p_max = kp["travel_max"]
            self.is_dive = True
        a = kp["v_dive"] / kp["t_push"]
        self.a = a
        half = 0.5 * kp["v_dive"] * kp["t_push"]
        if self.p_max <= half:
            tau_full = math.sqrt(2.0 * self.p_max / a) if self.p_max > 0 else 0.0
        else:
            tau_full = kp["t_push"] + (self.p_max - half) / kp["v_dive"]
        self.t_full = self.t_m + tau_full
        th = math.atan2(self.d[1], self.d[0]) if self.is_dive else math.pi / 2
        if th < -math.pi / 2:
            th += 2 * math.pi
        self.th_final = th
        self.th_flat = 0.0 if math.cos(th) >= 0 else math.pi
        # integrate arm (hand offset relative to shoulder)
        n = int(round((t1 - t0) / dt)) + 1
        self.n = n
        self.C, self.S, self.Hd, self.F = [], [], [], []
        o = kp["ready_hand"]
        L_eff = kp["L_arm"] - kp["r_hand"]
        for i in range(n):
            t = t0 + i * dt
            C, u, f_push = self._com_axis(t)
            S = (C[0] + kp["L_torso"] * u[0], max(0.10, C[1] + kp["L_torso"] * u[1]))
            F = (C[0] - kp["L_leg"] * u[0], max(0.0, C[1] - kp["L_leg"] * u[1]))
            if self.is_dive and self.t_m < t < self.t_m + kp["t_push"]:
                # push-off: the planted foot stays on the ground until take-off
                F = lerp((x_start, 0.0), F, f_push)
            if t < t_p or bstar is None:
                if self.is_dive and t > self.t_m:
                    o = lerp(kp["ready_hand"], (L_eff * u[0], L_eff * u[1]), f_push)
                else:
                    o = kp["ready_hand"]
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

    def _com_axis(self, t):
        kp = self.kp
        C0 = self.C0
        if t <= self.t_m:
            return C0, (0.0, 1.0), 0.0
        tau = t - self.t_m
        if tau <= kp["t_push"]:
            p = 0.5 * self.a * tau * tau
        else:
            p = 0.5 * kp["v_dive"] * kp["t_push"] + kp["v_dive"] * (tau - kp["t_push"])
        p = min(p, self.p_max)
        cx = C0[0] + p * self.d[0]
        cy = min(C0[1] + p * self.d[1], C0[1] + kp["jump_cap"])
        f_push = smoothstep(tau / kp["t_push"])
        th = math.pi / 2 + (self.th_final - math.pi / 2) * f_push
        if self.is_dive and t > self.t_full:
            tf = t - self.t_full
            cy_full = min(C0[1] + self.p_max * self.d[1], C0[1] + kp["jump_cap"])
            cy = cy_full - 0.5 * kp["g"] * tf * tf
            g_f = clamp(tf / 0.35, 0.0, 1.0)
            th = self.th_final + (self.th_flat - self.th_final) * g_f
        cy = max(cy, kp["y_lying"])
        return (cx, cy), (math.cos(th), math.sin(th)), f_push

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

    x_start = keeper_x_scene * (1.0 - kp["pos_pull"])
    t0k = phys["keeper_path_start_s"]
    kt = KeeperTimeline(kp, plan, x_start, bstar, t0k, phys["t_max_s"], dt)

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
    n_steps = int(round(phys["t_max_s"] / dt))
    km = cfg["keeper_model"]
    for i in range(1, n_steps + 1):
        tn = i * dt
        if caught_offset is not None:
            ks = kt.state(tn)
            pn = (ks["H"][0] + caught_offset[0], ks["H"][1] + caught_offset[1], zk)
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
                    if outcome is None:
                        outcome = "post"
                        event = {"type": name, "t": t + f * dt, "pos": [pc[0], pc[1], pc[2]]}
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
                if outcome is None:
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
                break

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
        res = simulate_kick(cfg, kp, k["aim"], k["speed_mps"], plan, float(scene.get("keeper_x", 0.0)))
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
                "path_fields": ["t", "com_x", "com_y", "shoulder_x", "shoulder_y", "hand_x", "hand_y", "feet_x", "feet_y"],
                "path": res["path"],
            },
            "outcome": res["outcome"],
            "margin_cm": int(round(margin * 100)) if margin is not None else None,
            "keeper_gap_cm": round(res["keeper_gap"] * 100, 1) if res["keeper_gap"] is not None else None,
            "event": ({"type": res["event"]["type"], "t": round(res["event"]["t"], 4),
                       "pos": [round(x, 3) for x in res["event"]["pos"]]} if res["event"] else None),
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
