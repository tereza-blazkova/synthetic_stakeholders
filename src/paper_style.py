"""
Figure style of the FAccT paper, so the abstract's figures look like Tereza's.

Adapted from ews_code/figures/scripts/paper_style.py (verbatim copy in
inputs/source_copies/paper_style.py): same rcParams, printed type sizes,
Helvetica and model palette. Two changes: figures here are drawn at their printed
width (the AES \\textwidth, 166 mm), so canvas size equals printed size and the
FONT table is the printed one; and the font ships in src/fonts/.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt

FONTS = Path(__file__).resolve().parent / "fonts"
TEXTWIDTH_IN = 166 / 25.4            # AES template: A4, 22 mm side margins

FONT = {"tick": 6.0, "legend": 6.0, "label": 6.5, "title": 6.5, "panel": 8.0, "annot": 5.5}

_RCPARAMS = {
    "font.family":       "sans-serif",
    "font.size":         FONT["tick"],
    "axes.titlesize":    FONT["title"],
    "axes.labelsize":    FONT["label"],
    "xtick.labelsize":   FONT["tick"],
    "ytick.labelsize":   FONT["tick"],
    "legend.fontsize":   FONT["legend"],
    "legend.title_fontsize": FONT["legend"],
    "figure.dpi":        150,
    "savefig.dpi":       300,
    "savefig.bbox":      "tight",
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.linewidth":    0.8,
    "xtick.major.width": 0.8,
    "ytick.major.width": 0.8,
    "lines.linewidth":   1.8,
    "lines.markersize":  6,
    "legend.frameon":    False,
    "legend.framealpha": 0,
    "legend.edgecolor":  "none",
    "pdf.fonttype":      42,
}

# The FAccT model palette (METHOD_COLOR there); the stacked-bar blues and ambers
# of its outcome panel.
PALETTE = {"teal": "#3A8FA8", "purple": "#5A5FA6", "pink": "#C4547A", "green": "#009E73",
           "vermillion": "#D55E00", "blue": "#56B4E9", "light_blue": "#CCE9F8",
           "amber": "#E69F00", "light_amber": "#F8E3B3", "ink": "#333333", "grey": "#999999"}


def apply_style() -> None:
    plt.style.use("seaborn-v0_8-white")
    sans = ["Arial", "Helvetica Neue", "DejaVu Sans"]
    ttf = FONTS / "Helvetica.ttf"
    if ttf.exists():
        try:
            fm.fontManager.addfont(str(ttf))
            sans = ["Helvetica", "Arial", "DejaVu Sans"]
        except Exception as exc:                                    # noqa: BLE001
            print(f"  ! Helvetica not loaded ({exc}) — falling back to {sans[0]}")
    else:
        print(f"  ! no {ttf} — falling back to {sans[0]}")
    mpl.rcParams.update(_RCPARAMS | {"font.sans-serif": sans})
