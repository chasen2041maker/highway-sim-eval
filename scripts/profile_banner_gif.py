"""Animated banner for the GitHub profile README: SEE -> TRACK -> DRIVE, every frame computed by this repo's code.

  01 SEE    one sweep of sim/fake_lidar.scan -> ads/perception: remove_ground, cluster_points (DBSCAN), cluster_to_box
  02 TRACK  sim/fake_traffic.make_scene -> ads/tracking.MultiTracker (Kalman + one-to-one matching + IDs);
            the numbers in the chip come from evaluation/metrics.tracking_metrics on the same run
  03 DRIVE  ads/planning: idm_accel + mobil_should_change decide, lane_change_d + frenet_to_xy draw the path,
            ads/vehicle.step + ads/control (Pure Pursuit) drive it on a gently winding road

Writes outputs/banner_dark.gif and outputs/banner_light.gif (1200 x 360, 80 ms per frame, loops forever),
copied to the profile repo as assets/banner-dark.gif and assets/banner-light.gif.

Run from the project root: python -m scripts.profile_banner_gif
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgb, to_rgba
from matplotlib.patches import Polygon
from PIL import Image

from ads.control import find_lookahead_point, pure_pursuit_steer
from ads.perception import cluster_points, cluster_to_box, remove_ground
from ads.planning import frenet_to_xy, idm_accel, lane_change_d, mobil_should_change
from ads.tracking import MultiTracker
from ads.vehicle import MAX_STEER_RAD, WHEELBASE_M, VehicleState, step
from evaluation.metrics import lateral_error_m, tracking_metrics
from sim.fake_lidar import scan
from sim.fake_traffic import DT_S as TRAFFIC_DT_S, default_cars, make_scene

W, H, DPI = 1200, 360, 100
FRAME_MS = 80
PX_PER_M = 18.75                       # 64 m across the banner
VIEW_W_M, VIEW_H_M = W / PX_PER_M, H / PX_PER_M
FADE_FRAMES = 6                        # cross-fade between scenes
FONT = "DejaVu Sans Mono"              # ships with matplotlib, so the banner looks the same on every machine
CAR_L, CAR_W = 4.6, 1.9

THEMES = {
    "dark": dict(bg="#0d1117", text="#e6edf3", muted="#7d8590", faint="#30363d", ground="#8b949e", glow="#e6edf3",
                 blue="#58a6ff", purple="#bc8cff", orange="#ffa657", green="#3fb950", red="#ff7b72"),
    "light": dict(bg="#ffffff", text="#1f2328", muted="#656d76", faint="#d0d7de", ground="#8c959f", glow="#0969da",
                  blue="#0969da", purple="#8250df", orange="#bc4c00", green="#1a7f37", red="#cf222e"),
}
SCENES = ["SEE", "TRACK", "DRIVE"]
SCENE_ACCENT = {"SEE": "blue", "TRACK": "purple", "DRIVE": "green"}


# ---------------------------------------------------------------- drawing helpers

def car_outline(cx, cy, yaw=0.0, length=CAR_L, width=CAR_W, r=0.45, n=5):
    """A car seen from above: rounded rectangle centred at (cx, cy), turned by yaw. Returns (N, 2) points."""
    hl, hw = length / 2 - r, width / 2 - r
    pts = []
    for sx, sy, a0 in [(1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)]:
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((sx * hl + r * math.cos(a), sy * hw + r * math.sin(a)))
    c, s = math.cos(yaw), math.sin(yaw)
    return np.array([(cx + c * x - s * y, cy + s * x + c * y) for x, y in pts])


def mix(c1, c2, t):
    """Colour between c1 (t = 0) and c2 (t = 1)."""
    a, b = np.array(to_rgb(c1)), np.array(to_rgb(c2))
    return tuple(a + (b - a) * min(max(t, 0.0), 1.0))


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


class Frame:
    """One 1200 x 360 frame: a world view (metres, equal scale) plus a HUD drawn in pixels."""

    def __init__(self, theme: str, x0: float, y0: float):
        self.c = THEMES[theme]
        self.fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI)
        self.fig.patch.set_facecolor(self.c["bg"])
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_facecolor(self.c["bg"])
        self.ax.set_xlim(x0, x0 + VIEW_W_M)
        self.ax.set_ylim(y0, y0 + VIEW_H_M)
        self.ax.axis("off")

    # world layer
    def car(self, cx, cy, yaw=0.0, edge=None, fill=None, fill_alpha=0.0, lw=1.4, ls="-", z=5, alpha=1.0, ego=False):
        edge = edge or self.c["muted"]
        face = to_rgba(fill or edge, fill_alpha * alpha) if fill_alpha > 0 else to_rgba(self.c["bg"], 1.0 if ego else 0.0)
        self.ax.add_patch(Polygon(car_outline(cx, cy, yaw), closed=True, fc=face, ec=to_rgba(edge, alpha),
                                  lw=lw, ls=ls, zorder=z, joinstyle="round"))
        if ego:   # windscreen line: shows which way the car points
            c, s = math.cos(yaw), math.sin(yaw)
            fx, fy = cx + c * 0.9, cy + s * 0.9
            hw = CAR_W / 2 - 0.35
            self.ax.plot([fx - s * hw, fx + s * hw], [fy + c * hw, fy - c * hw], color=to_rgba(edge, alpha),
                         lw=1.2, zorder=z + 0.1, solid_capstyle="round")

    def label(self, x, y, text, color=None, size=10, ha="center", va="bottom", alpha=1.0, z=8, weight="normal"):
        self.ax.text(x, y, text, color=to_rgba(color or self.c["muted"], alpha), fontsize=size, family=FONT,
                     ha=ha, va=va, zorder=z, weight=weight)

    def dashes(self, pts, dash_m=3.0, gap_m=6.0, offset_m=0.0, color=None, lw=1.2, alpha=1.0, z=1):
        """Lane dashes fixed to the world along a polyline (spacing in metres, not screen points)."""
        pts = np.asarray(pts)
        seg = np.hypot(*np.diff(pts, axis=0).T)
        s = np.concatenate([[0.0], np.cumsum(seg)])
        period = dash_m + gap_m
        k0 = math.floor((s[0] - offset_m) / period)
        k1 = math.ceil((s[-1] - offset_m) / period)
        for k in range(k0, k1 + 1):
            a, b = offset_m + k * period, offset_m + k * period + dash_m
            a, b = max(a, s[0]), min(b, s[-1])
            if b <= a:
                continue
            ss = np.linspace(a, b, 6)
            self.ax.plot(np.interp(ss, s, pts[:, 0]), np.interp(ss, s, pts[:, 1]),
                         color=to_rgba(color or self.c["faint"], alpha), lw=lw, zorder=z, solid_capstyle="butt")

    # HUD layer (pixels from the bottom-left corner)
    def text_px(self, x, y, text, color, size=13, ha="left", va="baseline", weight="normal", alpha=1.0):
        self.fig.text(x / W, y / H, text, color=to_rgba(color, alpha), fontsize=size, family=FONT,
                      ha=ha, va=va, weight=weight, zorder=20)

    def hud(self, scene: str, progress: float, steps: list[str], active: int, chip: str, alpha: float = 1.0):
        c = self.c
        # soft fade at the edges so the HUD sits on clean background
        yy = np.arange(H)[:, None]
        xx = np.arange(W)[None, :]
        top = np.clip((70 - yy) / 40.0, 0, 1)                 # rows 0..30 opaque, fading out by row 70
        bot = np.clip((yy - (H - 70)) / 40.0, 0, 1)
        side = np.clip(1 - np.minimum(xx, W - 1 - xx) / 50.0, 0, 1) * 0.85
        a = np.maximum(np.maximum(top, bot), side)
        img = np.zeros((H, W, 4))
        img[..., :3] = to_rgb(c["bg"])
        img[..., 3] = a
        over = self.fig.add_axes([0, 0, 1, 1], zorder=10)
        over.imshow(img, extent=(0, W, 0, H), origin="upper", interpolation="nearest")
        over.set_xlim(0, W)
        over.set_ylim(0, H)
        over.axis("off")

        accent = c[SCENE_ACCENT[scene]]
        cw = 13 * DPI / 72 * 0.602                             # width of one character at 13 pt (mono)
        x = 28
        for i, name in enumerate(SCENES):
            on = name == scene
            num = f"{i + 1:02d}"
            self.text_px(x, H - 36, num, c[SCENE_ACCENT[name]] if on else c["muted"], alpha=alpha)
            self.text_px(x + 3 * cw, H - 36, name, c["text"] if on else c["muted"], weight="bold" if on else "normal",
                         alpha=alpha)
            width = (3 + len(name)) * cw
            if on:
                over.plot([x, x + width], [H - 50, H - 50], color=to_rgba(c["faint"], alpha), lw=2,
                          solid_capstyle="butt")
                over.plot([x, x + width * min(max(progress, 0), 1)], [H - 50, H - 50], color=to_rgba(accent, alpha),
                          lw=2, solid_capstyle="butt")
            x += width + 3 * cw
        self.text_px(W - 28, H - 36, "highway-sim-eval", c["muted"], size=12, ha="right", alpha=alpha)

        # pipeline caption: done steps in text colour, the current one in the accent, the rest muted
        x = 28
        cw = 12 * DPI / 72 * 0.602
        for i, s in enumerate(steps):
            col = accent if i == active else (c["text"] if i < active else c["muted"])
            self.text_px(x, 26, s, col, size=12, weight="bold" if i == active else "normal", alpha=alpha)
            x += len(s) * cw
            if i < len(steps) - 1:
                self.text_px(x, 26, "  →  ", c["muted"], size=12, alpha=alpha)
                x += 5 * cw
        if chip:
            self.fig.text((W - 28) / W, 26 / H, chip, color=to_rgba(c["text"], alpha), fontsize=12, family=FONT,
                          ha="right", va="baseline", zorder=20,
                          bbox=dict(boxstyle="round,pad=0.55,rounding_size=0.8", fc=to_rgba(c["bg"], alpha),
                                    ec=to_rgba(c["faint"], alpha), lw=1))

    def pixels(self) -> np.ndarray:
        self.fig.canvas.draw()
        arr = np.asarray(self.fig.canvas.buffer_rgba())[..., :3].copy()
        plt.close(self.fig)
        return arr


# ---------------------------------------------------------------- 01 SEE

def scene_see(theme: str) -> list[np.ndarray]:
    c = THEMES[theme]
    pts, _ = scan()
    kept, keep = remove_ground(pts, -1.6)
    labels = cluster_points(kept, 1.0, 5)
    boxes = cluster_to_box(kept, labels)
    order = np.argsort(np.hypot(boxes[:, 0], boxes[:, 1]))            # boxes pop in from near to far
    az = np.mod(np.arctan2(pts[:, 1], pts[:, 0]), 2 * np.pi)
    cluster_cols = [c["blue"], c["purple"], c["orange"], c["green"], c["red"], c["blue"], c["purple"]]
    steps = ["32-beam LiDAR", "ground removal", "DBSCAN", "boxes"]
    chip = f"{len(pts):,} points → {len(boxes)} objects"
    n_sweep, n_ground, n_cluster, n_box = 30, 10, 8, 16
    total = n_sweep + n_ground + n_cluster + n_box
    x0, y0 = -22.0, -VIEW_H_M / 2
    frames = []
    for f in range(total):
        fr = Frame(theme, x0, y0)
        ax = fr.ax
        sweep = min((f + 1) / n_sweep, 1.0) * 2 * np.pi
        ground_t = ease((f - n_sweep) / n_ground)
        clus_t = ease((f - n_sweep - n_ground) / n_cluster)
        box_f = f - n_sweep - n_ground - n_cluster
        seen = az <= sweep + 1e-9
        glow = seen & (sweep - az < 0.6) & (f < n_sweep)
        # ground (what remove_ground threw away)
        g = seen & ~keep
        ax.scatter(pts[g, 0], pts[g, 1], s=1.5, c=[mix(c["ground"], c["bg"], 0.25 + 0.4 * ground_t)],
                   linewidths=0, zorder=2)
        # objects (what remove_ground kept): grey -> accent -> one colour per DBSCAN cluster
        kept_seen = seen[keep]
        for k in range(-1, labels.max() + 1):
            m = kept_seen & (labels == k)
            if not m.any():
                continue
            target = cluster_cols[k % len(cluster_cols)] if k >= 0 else c["muted"]
            col = mix(mix(c["ground"], c["blue"], ground_t), target, clus_t)
            ax.scatter(kept[m, 0], kept[m, 1], s=3.4, c=[col], linewidths=0, zorder=3)
        if glow.any():
            ax.scatter(pts[glow, 0], pts[glow, 1], s=2.2, c=[c["glow"]], linewidths=0, zorder=4, alpha=0.9)
        # the beam
        if f < n_sweep:
            for i in range(8):
                a1 = sweep - i * 0.07
                a0 = a1 - 0.07
                th = np.linspace(a0, a1, 6)
                poly = np.vstack([[0, 0], np.c_[60 * np.cos(th), 60 * np.sin(th)]])
                ax.add_patch(Polygon(poly, closed=True, fc=to_rgba(c["blue"], 0.10 * (1 - i / 8)), ec="none", zorder=1))
            ax.plot([0, 60 * math.cos(sweep)], [0, 60 * math.sin(sweep)], color=to_rgba(c["blue"], 0.55), lw=1, zorder=4)
        # boxes from cluster_to_box, popping in one by one
        for rank, k in enumerate(order):
            t = (box_f - rank * 2) / 5
            if t <= 0:
                continue
            t = ease(t)
            bx, by, lx, ly = boxes[k]
            grow = 1 + 0.35 * (1 - t)
            hx, hy = (lx / 2 + 0.35) * grow, (ly / 2 + 0.35) * grow
            col = to_rgba(c["text"], t)
            arm_x, arm_y = min(0.9, hx), min(0.9, hy)
            for sx in (-1, 1):
                for sy in (-1, 1):
                    cx_, cy_ = bx + sx * hx, by + sy * hy
                    ax.plot([cx_ - sx * arm_x, cx_, cx_], [cy_, cy_, cy_ - sy * arm_y], color=col, lw=1.5, zorder=6,
                            solid_capstyle="round", solid_joinstyle="miter")
            below = by > 3          # near the top edge: put the range under the box
            fr.label(bx, by - hy - 0.35 if below else by + hy + 0.35, f"{math.hypot(bx, by):.0f} m", alpha=t,
                     va="top" if below else "bottom")
        fr.car(0, 0, 0, edge=c["text"], ego=True, z=7)
        if f < n_sweep:
            active = 0
        elif f < n_sweep + n_ground:
            active = 1
        elif f < n_sweep + n_ground + n_cluster:
            active = 2
        else:
            active = 3
        fr.hud("SEE", (f + 1) / total, steps, active, chip if f >= n_sweep + n_ground + n_cluster else "")
        frames.append(fr.pixels())
    return frames


# ---------------------------------------------------------------- 02 TRACK

def run_tracker():
    scene = make_scene()
    speed = {car.name: (car.vx_mps, 0.0) for car in default_cars()}
    mt = MultiTracker(gate_m=2.0, max_misses=10)
    snaps, truth, tracks = [], [], []
    for k, det in enumerate(scene.detections):
        mt.step(det, TRAFFIC_DT_S)
        snaps.append([(t.id, *t.xy, t.kx.x[1], t.ky.x[1], t.misses) for t in mt.tracks])
        truth.append({name: (*xy[k], *speed[name]) for name, xy in scene.truth.items()})
        tracks.append({t.id: (*t.xy, t.kx.x[1], t.ky.x[1]) for t in mt.tracks})
    m = tracking_metrics(truth, tracks, 2.0)
    n_checks = sum(len(f) for f in truth)
    m["mota"] = 1 - (m["missed"] + m["false_tracks"] + m["id_switches"]) / n_checks
    return scene, snaps, m


def scene_track(theme: str) -> list[np.ndarray]:
    c = THEMES[theme]
    scene, snaps, m = run_tracker()
    hidden = next(car for car in default_cars() if car.hidden_frames)
    ids_at_start = {i for i, *_ in snaps[0]}
    first_seen = {}
    for k, snap in enumerate(snaps):
        for i, *_ in snap:
            first_seen.setdefault(i, k)
    # which ID ended up on the car that gets hidden, and which ID is the guardrail ghost
    hid_k = hidden.hidden_frames[0]
    hx_true = scene.truth[hidden.name][hid_k]
    hidden_id = min(snaps[hid_k], key=lambda s: math.hypot(s[1] - hx_true[0], s[2] - hx_true[1]))[0]
    ghost_ids = {i for i in first_seen if i not in ids_at_start}
    palette = [c["blue"], c["purple"], c["orange"]]
    color_of = {i: palette[n % 3] for n, i in enumerate(sorted(ids_at_start))}
    for i in ghost_ids:
        color_of[i] = c["red"]
    ghost_k = min(first_seen[i] for i in ghost_ids) if ghost_ids else None
    ghost_end = max(k for k, snap in enumerate(snaps) for i, *_ in snap if i in ghost_ids) if ghost_ids else None

    steps = ["predict (Kalman)", "match (2 m gate)", "keep IDs"]
    chip = f"MOTA {m['mota']:.2f} · ID switches {m['id_switches']} · {m['pos_err_m']:.2f} m err"
    hold = 8
    total = len(snaps) + hold
    x0, y0 = -14.0, -VIEW_H_M / 2
    ego_speed = 20.0                     # only for the lane dashes: everything else is relative to my car
    frames = []
    for f in range(total):
        k = min(f, len(snaps) - 1)
        t_s = k * TRAFFIC_DT_S
        fr = Frame(theme, x0, y0)
        ax = fr.ax
        xs = np.array([x0 - 5, x0 + VIEW_W_M + 5])
        for y in (-5.25, 5.25):
            ax.plot(xs, [y, y], color=c["faint"], lw=1.4, zorder=1)
        for y in (-6.1, 6.1):
            ax.plot(xs, [y, y], color=c["faint"], lw=0.8, ls=(0, (1, 3)), zorder=1)
        for y in (-1.75, 1.75):
            fr.dashes([(xs[0], y), (xs[1], y)], offset_m=-ego_speed * t_s % 9.0)
        det = scene.detections[k]
        if len(det):
            ax.scatter(det[:, 0], det[:, 1], marker="+", s=40, c=[c["muted"]], linewidths=1.1, zorder=4)
        for tid, x, y, vx, vy, misses in snaps[k]:
            col = color_of.get(tid, c["red"])
            coasting = misses > 0
            fr.car(x, y, 0.0, edge=col, fill=col, fill_alpha=0.05 if coasting else 0.16,
                   ls=(0, (3, 2)) if coasting else "-", lw=1.5)
            tag = f"#{tid}"
            info = f" {vx:+.1f} m/s"
            cw_m = 10 * DPI / 72 * 0.602 / PX_PER_M
            left = x - (len(tag) + len(info)) * cw_m / 2
            fr.label(left, y + 1.25, tag, color=col, ha="left", weight="bold")
            fr.label(left + len(tag) * cw_m, y + 1.25, info, ha="left")
            # where the filter thinks it will be in 1 s
            if abs(vx) > 0.3:
                ax.annotate("", xy=(x + np.sign(vx) * (CAR_L / 2) + vx * 0.8, y),
                            xytext=(x + np.sign(vx) * (CAR_L / 2 + 0.1), y),
                            arrowprops=dict(arrowstyle="-|>", color=to_rgba(col, 0.8), lw=1.2, mutation_scale=9),
                            zorder=5)
        # notes for the two events worth seeing
        hidden_frames = hidden.hidden_frames
        if hidden_frames[0] <= k <= hidden_frames[-1] + 8:
            hx, hy = next(((x, y) for tid, x, y, *_ in snaps[k] if tid == hidden_id), (None, None))
            if hx is not None:
                note = (f"hidden {len(hidden_frames) * TRAFFIC_DT_S:.1f} s · Kalman keeps predicting"
                        if k <= hidden_frames[-1] else f"seen again · still #{hidden_id}, no ID switch")
                fr.label(hx, hy - 1.35, note, color=color_of[hidden_id], va="top")
        if ghost_k is not None and ghost_k <= k <= ghost_end + 6:
            note = ("guardrail false alarm → new track" if k <= ghost_k + 3 else
                    "no detections → dropped after 1 s" if k > ghost_end else "ghost: nothing matches it")
            fr.label(8.0 + CAR_L / 2 + 0.8, -6.0, note, color=c["red"], va="center", ha="left")
        fr.car(0, 0, 0, edge=c["text"], ego=True, z=7)
        if hidden_frames[0] <= k <= hidden_frames[-1]:
            active = 0
        elif ghost_k is not None and ghost_k <= k <= ghost_end + 1:
            active = 2
        else:
            active = 1
        fr.hud("TRACK", (f + 1) / total, steps, active, chip if k >= 10 else "")
        frames.append(fr.pixels())
    return frames


# ---------------------------------------------------------------- 03 DRIVE

LANE_M = 3.5
SPEED = 13.0              # me, m/s
LEAD_SPEED = 7.0          # slow car ahead in my lane
BACK_SPEED = 10.0         # car behind in the left lane
DRIVE_DT = FRAME_MS / 1000
DECIDE_S, CHANGE_S = 0.6, 4.0
LOOKAHEAD_M = 8.0


def road():
    """My lane's centre line: a gentle wave (amplitude 2.5 m, one wave per 180 m), a point every 0.5 m."""
    xs = np.arange(-80.0, 300.0, 0.5)
    return [(float(x), float(2.5 * math.sin(2 * math.pi * x / 180.0 + 0.6))) for x in xs]


def arc_length_at_x(ref, x):
    s = 0.0
    for (x0, y0), (x1, y1) in zip(ref, ref[1:]):
        if x1 > x:
            return s + math.hypot(x - x0, (x - x0) / (x1 - x0) * (y1 - y0))
        s += math.hypot(x1 - x0, y1 - y0)
    return s


def heading_at(ref, s):
    (xa, ya), (xb, yb) = frenet_to_xy(ref, s, 0.0), frenet_to_xy(ref, s + 0.5, 0.0)
    return math.atan2(yb - ya, xb - xa)


def plan_drive():
    ref = road()
    s0 = arc_length_at_x(ref, 0.0)             # my rear axle starts here
    lead0, back0 = s0 + 1.4 + 32.0, s0 + 1.4 - 17.0   # centres of the other two cars at t = 0

    # MOBIL at DECIDE_S, with IDM accelerations (gaps are bumper to bumper)
    me_c = s0 + 1.4 + SPEED * DECIDE_S
    lead_c, back_c = lead0 + LEAD_SPEED * DECIDE_S, back0 + BACK_SPEED * DECIDE_S
    me_now = idm_accel(SPEED, LEAD_SPEED, lead_c - me_c - CAR_L, 16.0)
    me_after = idm_accel(SPEED, SPEED, 1e6, 16.0)                       # left lane is empty ahead
    back_now = idm_accel(BACK_SPEED, BACK_SPEED, 1e6, 16.0)
    back_after = idm_accel(BACK_SPEED, SPEED, me_c - back_c - CAR_L, 16.0)
    go = mobil_should_change(me_now, me_after, back_now, back_after)
    assert go, "MOBIL should say change here"

    # the planned path: quintic d(t) in Frenet, turned into map points
    path, sd = [], []
    s = s0 - 10.0
    while s < s0 + 140:
        t = (s - s0) / SPEED
        d = lane_change_d(t - DECIDE_S, CHANGE_S, LANE_M)[0]
        path.append(frenet_to_xy(ref, s, d))
        sd.append((s, d))
        s += 0.5
    left_lane = [frenet_to_xy(ref, s, LANE_M) for s, _ in sd]

    # drive it: bicycle model + Pure Pursuit
    x, y = frenet_to_xy(ref, s0, 0.0)
    state = VehicleState(x, y, heading_at(ref, s0), SPEED)
    n = round(6.0 / DRIVE_DT)
    states, targets, lat = [], [], []
    for _ in range(n + 1):
        tx, ty = find_lookahead_point(path, state, LOOKAHEAD_M)
        steer = max(-MAX_STEER_RAD, min(MAX_STEER_RAD, pure_pursuit_steer(state, tx, ty)))
        states.append(state)
        targets.append((tx, ty))
        lat.append(SPEED ** 2 * math.tan(steer) / WHEELBASE_M)
        state = step(state, 0.0, steer, DRIVE_DT)
    end_i = round((DECIDE_S + CHANGE_S + 0.8) / DRIVE_DT)
    # the curvature of the road itself is in lat too, so take the extra over just following the lane
    info = dict(me_gain=me_after - me_now, back_after=back_after,
                peak_lat=max(abs(a) for a in lat),
                end_err=lateral_error_m(left_lane, states[end_i].x_m + WHEELBASE_M / 2 * math.cos(states[end_i].heading_rad),
                                        states[end_i].y_m + WHEELBASE_M / 2 * math.sin(states[end_i].heading_rad)))
    return ref, s0, lead0, back0, path, states, targets, info


def scene_drive(theme: str) -> list[np.ndarray]:
    c = THEMES[theme]
    ref, s0, lead0, back0, path, states, targets, info = plan_drive()
    path = np.array(path)
    steps = ["IDM", "MOBIL", "quintic in Frenet", "Pure Pursuit"]
    chip_mobil = f"MOBIL: me {info['me_gain']:+.1f} · rear {info['back_after']:+.1f} m/s² → go"
    chip_end = f"peak lat. {info['peak_lat']:.2f} m/s² · {info['end_err']:.2f} m off centre"
    lane_lines = {}
    for d in (-1.75, 1.75, 5.25):
        lane_lines[d] = np.array([frenet_to_xy(ref, s, d) for s in np.arange(s0 - 40, s0 + 160, 1.0)])
    total = len(states)
    frames = []
    trail = []
    for f in range(total):
        t = f * DRIVE_DT
        st = states[f]
        cx = st.x_m + WHEELBASE_M / 2 * math.cos(st.heading_rad)
        cy = st.y_m + WHEELBASE_M / 2 * math.sin(st.heading_rad)
        trail.append((cx, cy))
        cam_x = cx - 24.0
        mid = frenet_to_xy(ref, s0 + SPEED * t + 14, 1.75)
        fr = Frame(theme, cam_x, mid[1] - VIEW_H_M / 2 - 0.4)
        ax = fr.ax
        ax.plot(*lane_lines[-1.75].T, color=c["faint"], lw=1.4, zorder=1)
        ax.plot(*lane_lines[5.25].T, color=c["faint"], lw=1.4, zorder=1)
        fr.dashes(lane_lines[1.75], dash_m=3.0, gap_m=6.0)
        # other cars
        s_lead = lead0 + LEAD_SPEED * t
        s_back = back0 + BACK_SPEED * t
        lx, ly = frenet_to_xy(ref, s_lead, 0.0)
        bx, by = frenet_to_xy(ref, s_back, LANE_M)
        fr.car(lx, ly, heading_at(ref, s_lead), edge=c["muted"], fill=c["muted"], fill_alpha=0.12)
        fr.car(bx, by, heading_at(ref, s_back), edge=c["muted"], fill=c["muted"], fill_alpha=0.12)
        if t < DECIDE_S + 0.3:   # IDM: the gap I am closing
            a = frenet_to_xy(ref, s0 + 1.4 + SPEED * t + CAR_L / 2 + 0.4, 0.0)
            b = frenet_to_xy(ref, s_lead - CAR_L / 2 - 0.4, 0.0)
            ax.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle="<->", color=c["muted"], lw=1, mutation_scale=8))
            gap = s_lead - (s0 + 1.4 + SPEED * t) - CAR_L
            fr.label((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 0.3, f"gap {gap:.0f} m · closing {SPEED - LEAD_SPEED:.0f} m/s")
        if DECIDE_S - 0.1 <= t < DECIDE_S + 1.6:   # MOBIL: look in the mirror
            k = ease((t - DECIDE_S + 0.1) / 0.4) * (1 - ease((t - DECIDE_S - 1.2) / 0.4))
            ss = np.linspace(s_back + CAR_L / 2 + 0.3, s0 + 1.4 + SPEED * t + CAR_L / 2, 30)
            edge_r = [frenet_to_xy(ref, q, 1.95) for q in ss]
            edge_l = [frenet_to_xy(ref, q, 5.05) for q in ss[::-1]]
            ax.add_patch(Polygon(edge_r + edge_l, closed=True, fc=to_rgba(c["green"], 0.13 * k),
                                 ec=to_rgba(c["green"], 0.55 * k), lw=1, ls=(0, (2, 2)), zorder=0.5))
            lx_, ly_ = frenet_to_xy(ref, (ss[0] + ss[-1]) / 2, 5.5)
            fr.label(lx_, ly_, f"rear car: {info['back_after']:+.1f} m/s² if I cut in (limit −2) ✓",
                     color=c["green"], alpha=k)
        if t >= DECIDE_S:          # the planned path grows out in front of me
            grow = ease((t - DECIDE_S) / 0.6)
            ahead = np.hypot(path[:, 0] - cx, path[:, 1] - cy)
            i0 = int(np.argmin(ahead))
            i1 = min(len(path), i0 + int(grow * 120))
            fr.dashes(path[i0:i1], dash_m=1.2, gap_m=0.9, color=c["green"], lw=1.6, z=3)
        if len(trail) > 1:
            tr = np.array(trail)
            ax.plot(tr[:, 0], tr[:, 1], color=to_rgba(c["green"], 0.55), lw=2.2, zorder=2, solid_capstyle="round")
        if t >= DECIDE_S + 0.4:    # Pure Pursuit: the point I am steering at
            tx, ty = targets[f]
            ax.plot([st.x_m, tx], [st.y_m, ty], color=to_rgba(c["green"], 0.8), lw=1, zorder=8)
            ax.plot([tx], [ty], "o", ms=5, color=c["green"], zorder=8)
        fr.car(cx, cy, st.heading_rad, edge=c["text"], ego=True, z=7)
        if t < DECIDE_S:
            active, chip = 0, ""
        elif t < DECIDE_S + 1.0:
            active, chip = 1, chip_mobil
        elif t < DECIDE_S + 2.0:
            active, chip = 2, chip_mobil
        else:
            active, chip = 3, chip_end if t > DECIDE_S + CHANGE_S else chip_mobil
        fr.hud("DRIVE", (f + 1) / total, steps, active, chip)
        frames.append(fr.pixels())
    return frames


# ---------------------------------------------------------------- put it together

def dip(a: np.ndarray, b: np.ndarray, bg: np.ndarray, n: int) -> list[np.ndarray]:
    """Fade a out to the background, then b in from it (n frames in all)."""
    half = n // 2
    out = [(a + (bg - a) * w) for w in np.arange(1, half + 1) / half]
    out += [(bg + (b - bg) * w) for w in np.arange(1, n - half + 1) / (n - half + 1)]
    return [f.astype(np.uint8) for f in out]


def build(theme: str) -> list[np.ndarray]:
    parts = [scene_see(theme), scene_track(theme), scene_drive(theme)]
    bg = np.array(to_rgb(THEMES[theme]["bg"])) * 255
    frames = []
    for i, p in enumerate(parts):
        frames += p
        nxt = parts[(i + 1) % len(parts)]
        frames += dip(p[-1].astype(float), nxt[0].astype(float), bg, FADE_FRAMES)
    return frames


def theme_palette(theme: str, levels: int = 26) -> Image.Image:
    """A fixed GIF palette: every theme colour blended into the background at `levels` strengths
    (anti-aliased edges and see-through fills are exactly such blends), so colours never drift."""
    c = THEMES[theme]
    bg = np.array(to_rgb(c["bg"]))
    cols = [bg]
    for name, value in c.items():
        if name in ("bg", "glow"):
            continue
        for a in np.linspace(1.0 / levels, 1.0, levels):
            cols.append(bg + (np.array(to_rgb(value)) - bg) * a)
    flat = (np.round(np.array(cols[:256]) * 255)).astype(np.uint8).ravel().tolist()
    pal = Image.new("P", (1, 1))
    pal.putpalette(flat + [0] * (768 - len(flat)))
    return pal


def save_gif(frames: list[np.ndarray], out: Path, theme: str) -> None:
    pal = theme_palette(theme)
    imgs = [Image.fromarray(f).quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    imgs[0].save(out, save_all=True, append_images=imgs[1:], duration=FRAME_MS, loop=0, optimize=True, disposal=1)


def main():
    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)
    for theme in THEMES:
        frames = build(theme)
        out = out_dir / f"banner_{theme}.gif"
        save_gif(frames, out, theme)
        Image.fromarray(frames[45]).save(out_dir / f"banner_{theme}_still.png")
        print(f"{out}: {len(frames)} frames, {len(frames) * FRAME_MS / 1000:.1f} s, {out.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
