"""White UCPH logo as vector PDF, traced from poster/logo/ucph_logo_white.png.

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python poster/make_logo_vector.py
    -> poster/logo/ucph_logo_white.pdf (same aspect ratio and position as the PNG)

The three circles and the horizontal line are redrawn as exact shapes. The lettering is
traced (outline at 50% coverage of the slightly smoothed PNG). This is a trace of an
800-pixel source, not the official UCPH vector file: edges print sharp, but letter shapes
are only as accurate as that source.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, Rectangle
from PIL import Image, ImageFilter

LOGO = Path(__file__).resolve().parent / "logo"
WIDTH_CM = 16.0
SEAL = (2717.5, 282.5, 281.5)        # centre x, centre y, radius (px), measured from the PNG


def main() -> Path:
    im = Image.open(LOGO / "ucph_logo_white.png").getchannel("A")
    raw = np.asarray(im, float) / 255
    H, W = raw.shape
    yy, xx = np.mgrid[:H, :W]

    # the horizontal line: rows and x extent
    prof = raw[:, 100:2000].mean(axis=1)
    rows = [y for y in range(800, H) if prof[y] > 0.5]
    y0, y1 = rows[0], rows[-1] + 1
    xs = np.where(raw[(y0 + y1) // 2] > 0.5)[0]
    line = (xs.min(), xs.max() + 1)

    # middle circle (free-standing) and small circle on the line
    box = (xx > 2200) & (xx < 2560) & (yy > 570) & (yy < 900) & (raw > 0.5)
    ys, xs = np.where(box)
    mid = ((xs.min() + xs.max() + 1) / 2, (ys.min() + ys.max() + 1) / 2, (xs.max() + 1 - xs.min()) / 2)
    box = (xx > 2550) & (xx < 2900) & (yy > 850) & (raw > 0.5)
    ys = np.where(box.any(axis=1))[0]
    top, bottom = ys.min(), ys.max() + 1
    _, xs = np.where(box & (yy < y0 - 5))
    dot = ((xs.min() + xs.max() + 1) / 2, (top + bottom) / 2, (bottom - top) / 2)

    # lettering only: blank out the exact shapes, smooth, take the 50% outline
    a = np.asarray(im.filter(ImageFilter.GaussianBlur(2.0)), float) / 255
    for cx, cy, r in (SEAL, mid, dot):
        a[np.hypot(xx - cx, yy - cy) <= r + 8] = 0
    a[y0 - 8:y1 + 8, :] = 0

    fig = plt.figure(figsize=(WIDTH_CM / 2.54, WIDTH_CM / 2.54 * H / W))
    fig.patch.set_alpha(0)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.axis("off")
    ax.contourf(np.arange(W) + 0.5, np.arange(H) + 0.5, a, levels=[0.5, 2], colors="white", antialiased=False)
    for cx, cy, r in (SEAL, mid, dot):
        ax.add_patch(Circle((cx, cy), r, facecolor="white", edgecolor="none"))
    ax.add_patch(Rectangle((line[0], y0), line[1] - line[0], y1 - y0, facecolor="white", edgecolor="none"))
    out = LOGO / "ucph_logo_white.pdf"
    fig.savefig(out, transparent=True)
    plt.close(fig)
    print("line", y0, y1, line, "mid", mid, "dot", dot)
    return out


if __name__ == "__main__":
    print(main())
