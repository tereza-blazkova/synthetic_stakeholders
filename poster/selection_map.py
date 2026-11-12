"""Poster figure "One model, every run": the FAccT paper's Fig. 2 (participatory model selection test)
as a grid, with the configuration each LLM workshop selected.

    called from poster/make_figures.py
    -> poster/figs/fig_selection_map.{pdf,png}

Grid: models (rows) x cumulative feature sets (columns), with the 2021 recall of each combination
(inputs/metrics_2021.csv). Shaded: combinations the humans' endline rules permit (src.rule_applier on
the human medians); dark grey: blocked by their rules. Black ring: the humans' selected model.
Markers: endline selections of the reference runs (large tier, full protocol, 20 per family), area and
label = number of runs. Hollow squares: Gemma at 16-bit (post hoc, exploratory).
"""
from __future__ import annotations

import collections
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

from poster.make_figures import OUT, poster_mode  # noqa: E402
from src import paper_style  # noqa: E402
from src.figures import LARGE_FAMILIES  # noqa: E402
from src.rule_applier import load_metrics, ruleset_from_medians, select  # noqa: E402
from src.score import human_value, score_run  # noqa: E402

MODELS = [("fasterrisk", "FasterRisk"), ("logistic_regression", "Logistic\nregression"),
          ("xgboost", "XGBoost"), ("mlp", "Neural\nnetwork")]
FS = ["a_credits", "b_credits_performance", "c_plus_enrollment", "d_plus_lms", "e_plus_sensitive"]
FS_LABEL = ["Credits\ndata", "+ Perfor-\nmance", "+ Enrol-\nment", "+ LMS", "+ Sensi-\ntive"]
RULE_KEYS = ["Q3.2", "Q3.3", "Q3.4", "Q3.5.age", "Q3.5.gender", "Q3.5.nationality",
             "Q4.1.high", "Q4.1.moderate", "Q4.1.low", "Q4.1.very_low"]


def selections() -> dict:
    out = {}
    rows = list(csv.DictReader((ROOT / "analysis" / "results" / "scores_by_run.csv").open()))
    for model, colour, marker, label in LARGE_FAMILIES:
        out[label] = (colour, marker, collections.Counter(
            r["endline_selected"] for r in rows if r["protocol"] == "full" and r["model"] == model), True)
    d = ROOT / "runs/post_review/precision_fp16/full/gemma3_27b-it-fp16"
    out["Gemma 16-bit (post hoc)"] = (LARGE_FAMILIES[1][1], "s", collections.Counter(
        score_run(r)["endline_selected"] for r in sorted(d.glob("run[0-9]*")) if (r / "run_meta.json").exists()), False)
    return out


def draw(ax, marker_scale: float = 1.0) -> list:
    """Draw the selection grid on ax; return the legend handles for the extra symbols."""
    recall = {(r["model"], r["feature_set"]): float(r["recall"]) for r in csv.DictReader((ROOT / "inputs/metrics_2021.csv").open())}
    human = select(load_metrics(), ruleset_from_medians({k: human_value(k) for k in RULE_KEYS}))
    permitted = {(c["model"], c["feature_set"]) for c in human["cells"] if c["permissible"]}
    blocked = set(human["blocked_feature_sets"])
    sel = selections()
    grey, ink = paper_style.PALETTE["grey"], paper_style.PALETTE["ink"]
    nrow = len(MODELS)
    offsets = dict(zip(sel, (-0.3, -0.1, 0.1, 0.3)))
    for r, (m, _) in enumerate(MODELS):
        y = nrow - 1 - r
        for c, fs in enumerate(FS):
            if fs in blocked or m == "mlp":
                face = "#BDBDBD"
            elif (m, fs) in permitted:
                face = "#E6F2EC"
            else:
                face = "#F4F4F4"
            ax.add_patch(Rectangle((c - 0.48, y - 0.46), 0.96, 0.92, facecolor=face, edgecolor="white", lw=1.5, zorder=0))
            ax.text(c + 0.44, y + 0.40, f"{recall[(m, fs)]:.2f}", ha="right", va="top",
                    fontsize=paper_style.FONT["annot"], color=grey, zorder=1)
    hm, hf = human["model"], human["feature_set"]
    hy = nrow - 1 - [m for m, _ in MODELS].index(hm)
    ax.add_patch(Rectangle((FS.index(hf) - 0.48, hy - 0.46), 0.96, 0.92, fill=False, edgecolor="black", lw=2.2, zorder=4))
    for lab, (colour, marker, counts, filled) in sel.items():
        for cfg, n in counts.items():
            mm, fs = cfg.split("+")
            x = FS.index(fs) + offsets[lab]
            y = nrow - 1 - [m for m, _ in MODELS].index(mm) - 0.05
            ax.scatter([x], [y], s=(10 + 4.5 * n) * marker_scale, marker=marker, zorder=3, linewidths=1.1,
                       facecolors=colour if filled else "white", edgecolors=colour)
            ax.text(x, y - 0.30, str(n), ha="center", va="center", fontsize=paper_style.FONT["annot"],
                    color=colour, fontweight="bold", zorder=3)
    ax.set_xlim(-0.5, len(FS) - 0.5)
    ax.set_ylim(-0.5, nrow - 0.5)
    ax.set_xticks(range(len(FS)))
    ax.set_xticklabels(FS_LABEL)
    ax.xaxis.tick_top()
    ax.set_yticks(range(nrow))
    ax.set_yticklabels([lab for _, lab in reversed(MODELS)])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    # family symbols are explained in panel A's legend; only the extra symbols are listed here
    handles = [plt.Line2D([], [], ls="", marker="s", markersize=6, markerfacecolor="white",
                          markeredgecolor=LARGE_FAMILIES[1][1], label="Gemma 16-bit"),
                Rectangle((0, 0), 1, 1, fill=False, edgecolor="black", lw=2, label="humans' model"),
                Rectangle((0, 0), 1, 1, facecolor="#E6F2EC", label="humans: permitted"),
                Rectangle((0, 0), 1, 1, facecolor="#BDBDBD", label="humans: never")]
    return handles


def main(width_in: float = 5.2, height_in: float = 2.5) -> Path:
    paper_style.apply_style()
    fig, ax = plt.subplots(figsize=(width_in, height_in))
    handles = draw(ax)
    fig.legend(handles=handles, loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.5, -0.03), columnspacing=1.0, handletextpad=0.4)
    fig.tight_layout(rect=(0, 0.15, 1, 0.93))
    fig.text(0.01, 0.99, "B", fontsize=paper_style.FONT["panel"], fontweight="bold", va="top", ha="left")
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"fig_selection_map.{ext}", dpi=200)
    plt.close(fig)
    return OUT / "fig_selection_map.png"


if __name__ == "__main__":
    with poster_mode(1.3):
        print(main(4.6, 2.4))
