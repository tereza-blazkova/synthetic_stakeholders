"""Poster results figure: panels A-D in one figure (draft, 2026-11-10).

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m poster.fig_results
    -> poster/figs/fig_results.{pdf,png}

A  endline answer per rule and family against the humans' endline (solid) and baseline
   (dashed) boxes; same drawing as panel a of src.figures.full_figure.
B  final acceptability votes: humans and the three families at 4-bit (as panel c of
   full_figure), then Gemma at 8- and 16-bit (post-review runs, read from assessment.json).
C  model selected by each panel's endline rules (poster/selection_map.py).
D  items (of 23) whose panel median moved baseline -> endline; as panel b of full_figure.
Families: large tier, full protocol, 20 seeded runs each. Nothing in src/ is changed.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

from poster import selection_map  # noqa: E402
from poster.make_figures import OUT  # noqa: E402
from src import aggregate, paper_style  # noqa: E402
from src.figures import ASSESS, LARGE_FAMILIES, LEVELS, RULES  # noqa: E402
from src.score import GT, R_ITEMS, S_ITEMS, human_value  # noqa: E402

PRECISION = [("Gemma 8-bit", "runs/post_review/precision_q8/full/gemma3_27b-it-q8_0"),
             ("Gemma 16-bit", "runs/post_review/precision_fp16/full/gemma3_27b-it-fp16")]


def load_rows() -> list[dict]:
    rows = list(csv.DictReader((ROOT / "analysis" / "results" / "scores_by_run.csv").open()))
    return [r for r in rows if r["protocol"] == "full" and r["model"] in {f[0] for f in LARGE_FAMILIES}]


def panel_a(ax, rows):
    ink, grey = paper_style.PALETTE["ink"], paper_style.PALETTE["grey"]
    n_runs = max(sum(r["model"] == f[0] for r in rows) for f in LARGE_FAMILIES)
    offsets = {f[0]: (i - 1) * 0.26 for i, f in enumerate(LARGE_FAMILIES)}
    box = dict(boxstyle="round,pad=0,rounding_size=0.06", fill=False, zorder=4)
    for x, (key, _) in enumerate(RULES):
        ax.add_patch(FancyBboxPatch((x - 0.43, LEVELS.index(human_value(key)) - 0.36), 0.86, 0.72,
                                    edgecolor=ink, lw=1.0, **box))
        hb = human_value(key, "baseline")
        if hb != human_value(key):
            ax.add_patch(FancyBboxPatch((x - 0.43, LEVELS.index(hb) - 0.36), 0.86, 0.72,
                                        edgecolor=grey, lw=0.9, ls=(0, (2, 1.5)), **box))
        for model, colour, marker, _ in LARGE_FAMILIES:
            vals = Counter(r[key] if r[key] in LEVELS else "never" for r in rows if r["model"] == model)
            for level, k in vals.items():
                ax.scatter(x + offsets[model], LEVELS.index(level), s=6 + 44 * k / n_runs, color=colour,
                           marker=marker, edgecolors="white", linewidths=0.5, zorder=3)
    ax.axvline(2.5, color=grey, lw=0.6, zorder=1)
    ax.set_xlim(-0.5, len(RULES) - 0.5)
    ax.set_ylim(-0.55, len(LEVELS) - 0.45)
    ax.set_xticks(range(len(RULES)))
    ax.set_xticklabels([("+ " + lab if i < 3 else lab) for i, (_, lab) in enumerate(RULES)])   # first three: data added
    ax.set_yticks(range(len(LEVELS)))
    ax.set_yticklabels(["0 pp", "1–3 pp", "5 pp", "10 pp", "never\nacceptable"])
    ax.set_ylabel("Recall increase required")
    for x0, x1, name in ((-0.5, 2.5, "Data added"), (2.5, 6.5, "Explainability level")):
        ax.text((x0 + x1) / 2, len(LEVELS) - 0.45, name, ha="center", va="bottom",
                fontsize=paper_style.FONT["label"])
    fam = [Line2D([], [], color=c, marker=m, ls="", ms=5, mec="white", mew=0.5, label=lab)
           for _, c, m, lab in LARGE_FAMILIES]
    human = [Line2D([], [], color=ink, marker="s", ls="", ms=6.5, mfc="none", mew=1.0, label="humans' endline"),
             FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.1", fill=False,
                            edgecolor=grey, lw=0.9, ls=(0, (2, 1.5)), label="humans' baseline")]
    return fam + human


def bar_axis(ax, names, xlab, xmax):
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names)
    ax.set_ylim(len(names) - 0.5, -0.5)
    ax.set_xlim(0, xmax)
    ax.set_xlabel(xlab)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)


def panel_c(ax, rows):
    ink = paper_style.PALETTE["ink"]
    order = aggregate.SCALE_ORDER
    hd = [(order[k].index(human_value(k)) > order[k].index(human_value(k, "baseline")))
          - (order[k].index(human_value(k)) < order[k].index(human_value(k, "baseline"))) for k in R_ITEMS + S_ITEMS]
    bars = [(ink, sum(d > 0 for d in hd), sum(d < 0 for d in hd), None)]
    for model, colour, _, _ in LARGE_FAMILIES:
        rs = [r for r in rows if r["model"] == model]
        m = lambda f: sum(float(r[f]) for r in rs) / len(rs)  # noqa: E731
        bars.append((colour, m("shift_stricter"), m("shift_permissive"), m("shift_same_as_humans")))
    for y, (colour, up, down, same) in enumerate(bars):
        ax.barh(y, up, color=colour, height=0.6)
        ax.barh(y, down, left=up, color=colour, alpha=0.4, height=0.6)
        note = f"{up + down}" if same is None else f"{up + down:.1f}"
        ax.text(up + down + 0.3, y, note, va="center", fontsize=paper_style.FONT["annot"], color=ink)
    bar_axis(ax, ["Humans"] + [lab.split()[0] for *_, lab in LARGE_FAMILIES], "Answers moved, of 23 (mean per run)", 12)
    ax.set_xticks([0, 5, 10])
    grey = paper_style.PALETTE["grey"]
    return [plt.Rectangle((0, 0), 1, 1, color=grey, label="stricter"),
            plt.Rectangle((0, 0), 1, 1, color=grey, alpha=0.4, label="looser")]


def vote_counts(folder: str) -> list[int]:
    opts = [k.removeprefix("assess_") for k, _, _ in ASSESS]
    c = dict.fromkeys(opts, 0)
    for d in sorted((ROOT / folder).glob("run[0-9]*")):
        if (d / "run_meta.json").exists():
            for v in json.loads((d / "assessment.json").read_text()).values():
                if v.get("choice") in c:
                    c[v["choice"]] += 1
    return [c[o] for o in opts]


def panel_d(ax, rows):
    names = ["Humans"]
    shares = [[GT["acceptability"]["counts"][k.removeprefix("assess_")] for k, _, _ in ASSESS]]
    for model, _, _, lab in LARGE_FAMILIES:
        rs = [r for r in rows if r["model"] == model]
        names.append(lab.split()[0])
        shares.append([sum(float(r[k]) for r in rs) for k, _, _ in ASSESS])
    for lab, folder in PRECISION:
        names.append(lab)
        shares.append(vote_counts(folder))
    ys = list(range(4)) + [4.35, 5.35]          # small gap before the precision rows
    for y, tot in zip(ys, shares):
        left = 0.0
        for (_, _, colour), v in zip(ASSESS, tot):
            ax.barh(y, v / sum(tot), left=left, color=colour, height=0.6, edgecolor="white", linewidth=0.4)
            left += v / sum(tot)
    ax.set_yticks(ys)
    ax.set_yticklabels(names)
    ax.set_ylim(ys[-1] + 0.5, -0.5)
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.5, 1])
    ax.set_xticklabels(["0", "50%", "100%"])
    ax.set_xlabel("Share of final votes")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.axhline(3.68, color=paper_style.PALETTE["grey"], lw=0.6, ls=(0, (2, 1.5)))
    return [plt.Rectangle((0, 0), 1, 1, color=c, label=lab) for _, lab, c in ASSESS]


def main(width_in: float = 7.0, height_in: float = 5.0) -> Path:
    paper_style.apply_style()
    rows = load_rows()
    fig = plt.figure(figsize=(width_in, height_in))
    # first column wider, second row shorter;
    # top: A rules | B votes, bottom: C selection grid | D movement
    gs = fig.add_gridspec(2, 2, width_ratios=[1.35, 0.614], height_ratios=[0.95, 1],
                          left=0.09, right=0.98, top=0.88, bottom=0.09, wspace=0.405, hspace=0.72)
    ax = fig.add_subplot(gs[0, 0])
    dx = fig.add_subplot(gs[0, 1])     # votes (letter B)
    bx = fig.add_subplot(gs[1, 0])     # selection grid (letter C)
    cx = fig.add_subplot(gs[1, 1])     # movement (letter D)
    leg_a = panel_a(ax, rows)
    leg_b = selection_map.draw(bx, marker_scale=0.4)
    bx.set_ylabel("Model (achieved recall)")
    leg_c = panel_c(cx, rows)
    leg_d = panel_d(dx, rows)
    fig.align_ylabels([ax, bx])
    fig.canvas.draw()
    inv = fig.transFigure.inverted()
    r = fig.canvas.get_renderer()
    kw = dict(frameon=False, handletextpad=0.4, columnspacing=1.0, borderaxespad=0, handlelength=1.4,
              loc="lower left")
    panels = {"A": (ax, leg_a, 3), "B": (dx, leg_d, 2), "C": (bx, leg_b, 4), "D": (cx, leg_c, 2)}
    for k, (axis, handles, ncol) in panels.items():
        # letter and legend just above the panel
        y = axis.get_tightbbox(r).transformed(inv).y1 + 0.012
        t = fig.text(0, y, k, fontsize=paper_style.FONT["panel"], fontweight="bold", va="top", ha="left")
        leg = fig.legend(handles=handles, ncol=ncol, bbox_to_anchor=(0, y), **kw)
        fig.canvas.draw()
        w_letter = t.get_window_extent(r).transformed(inv).width
        lb = leg.get_window_extent(r).transformed(inv)
        gap = 0.012
        pos = axis.get_position()
        # letter at the top of the y axis, immediately left of its imagined upward continuation
        t.set_position((pos.x0 - 0.006, pos.y1 + 0.004))
        t.set_ha("right")
        t.set_va("bottom")
        # legend centred over the plot area
        leg.set_bbox_to_anchor(((pos.x0 + pos.x1) / 2 - lb.width / 2, y), transform=fig.transFigure)
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"fig_results.{ext}", dpi=200)
    plt.close(fig)
    return OUT / "fig_results.png"


if __name__ == "__main__":
    print(main())
