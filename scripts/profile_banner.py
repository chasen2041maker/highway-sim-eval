"""Banner for the GitHub profile README: one real sweep of the simulated 32-beam LiDAR, seen from above.

Writes outputs/banner_scan_light.png and outputs/banner_scan_dark.png (2400 x 684, GitHub light / dark backgrounds),
which are copied to the profile repo as assets/scan-light.png and assets/scan-dark.png.

Run from the project root: python -m scripts.profile_banner
"""
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from sim.fake_lidar import scan

pts, lab = scan()
x, y = pts[:, 0], pts[:, 1]
X0, X1, Y0, Y1 = -24, 44, -9.7, 9.7
MODES = {
    'light': dict(bg='#ffffff', g='#6e7781', ga=0.95, o='#0969da', car='#57606a'),
    'dark': dict(bg='#0d1117', g='#8b949e', ga=0.8, o='#58a6ff', car='#8b949e'),
}
for mode, c in MODES.items():
    fig = plt.figure(figsize=(12, 12 * (Y1 - Y0) / (X1 - X0)), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1])
    fig.patch.set_facecolor(c['bg']); ax.set_facecolor(c['bg'])
    g = lab == -1
    ax.scatter(x[g], y[g], s=0.9, c=c['g'], linewidths=0, alpha=c['ga'])
    ax.scatter(x[~g], y[~g], s=2.4, c=c['o'], linewidths=0)
    ax.add_patch(FancyBboxPatch((-2.3, -0.95), 4.6, 1.9, boxstyle='round,pad=0,rounding_size=0.35', fill=False, ec=c['car'], lw=1.5))
    ax.plot([0], [0], 'o', ms=3, color=c['o'])
    sx, sy = X1 - 12.5, Y0 + 1.2
    ax.plot([sx, sx + 10], [sy, sy], color=c['car'], lw=1.4)
    for e in (sx, sx + 10):
        ax.plot([e, e], [sy - 0.3, sy + 0.3], color=c['car'], lw=1.4)
    ax.text(sx + 5, sy + 0.5, '10 m', color=c['car'], ha='center', va='bottom', fontsize=10, family='DejaVu Sans Mono')
    ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1); ax.set_aspect('equal'); ax.axis('off')
    fig.savefig(f'outputs/banner_scan_{mode}.png', facecolor=c['bg'], dpi=200)
    plt.close(fig)
print('ok')
