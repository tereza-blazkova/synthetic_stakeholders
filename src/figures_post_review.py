"""
Post-review figures (poster and website paper). The paper figures in src/figures.py are untouched.

    python -m src.figures_post_review    # -> analysis/figures/post_review/fig_agreement_floor.{pdf,png}

fig_agreement_floor (A1): rules matched (of 7) per run for each family, large tier, full protocol,
against the random-panel floor (shaded: middle 95% of 2000 random panels; line: mean) and the
humans' own baseline->endline match (3 of 7, dashed).
"""
from __future__ import annotations

import csv
import random
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.figures import LARGE_FAMILIES
from src.paper_style import FONT, PALETTE, TEXTWIDTH_IN, apply_style
from src.score import score_run

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "analysis" / "figures" / "post_review"
RES = ROOT / "analysis" / "results" / "post_review"


def agreement_floor(width_in: float = 3.3, height_in: float = 1.9) -> Path:
    apply_style()
    floor = next(csv.DictReader((RES / "a1_random_floor.csv").open()))
    ink, grey = PALETTE["ink"], PALETTE["grey"]
    fig, ax = plt.subplots(figsize=(width_in, height_in))
    lo, hi, m = float(floor["rules_p2.5"]), float(floor["rules_p97.5"]), float(floor["rules_mean"])
    ax.axvspan(lo, hi, color=grey, alpha=0.15, lw=0, zorder=0)
    ax.axvline(m, color=grey, lw=1.0, zorder=1)
    ax.axvline(3, color=ink, lw=1.0, ls=(0, (3, 2)), zorder=1)
    rng = random.Random(3)
    for y, (model, colour, marker, label) in enumerate(reversed(LARGE_FAMILIES)):
        runs = sorted((ROOT / "runs" / "full" / model.replace(":", "_")).glob("run*"))
        xs = [score_run(d)["R_coverage"] for d in runs if (d / "run_meta.json").exists()]
        ax.scatter([x + rng.uniform(-0.12, 0.12) for x in xs], [y + rng.uniform(-0.18, 0.18) for _ in xs],
                   s=9, color=colour, marker=marker, alpha=0.55, edgecolors="none", zorder=2)
        ax.scatter([sum(xs) / len(xs)], [y], s=42, color=colour, marker=marker, edgecolors="white",
                   linewidths=0.8, zorder=3)
    ax.set_yticks(range(len(LARGE_FAMILIES)))
    ax.set_yticklabels([f[3] for f in reversed(LARGE_FAMILIES)])
    ax.set_xlim(-0.3, 7.3)
    ax.set_xticks(range(8))
    ax.set_xlabel("Rules matching the human panel (of 7), per run")
    ax.text(lo + 0.08, len(LARGE_FAMILIES) - 0.35, f"random panels:\nmean {m:.2f},\nshaded 95%",
            ha="left", va="bottom", fontsize=FONT["annot"], color=grey)
    ax.text(3.08, len(LARGE_FAMILIES) - 0.35, "humans' own\nbaseline vs endline", ha="left", va="bottom",
            fontsize=FONT["annot"], color=ink)
    ax.set_ylim(-0.6, len(LARGE_FAMILIES) + 0.35)
    FIG.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(FIG / f"fig_agreement_floor.{ext}")
    plt.close(fig)
    return FIG / "fig_agreement_floor.pdf"


B1_ORDER = [("baseline_replay", "original card (control)"), ("reversed_order", "order reversed"),
            ("reservations_fourth", "'reservations' 4th"), ("shuffled_per_agent", "order shuffled"),
            ("symmetric_definitions", "symmetric definitions"), ("definitions_removed", "no definitions"),
            ("conditional_label", "conditional label"), ("no_reservations_word", "header: no 'reservations'"),
            ("no_legitimacy_bullet", "header: no legitimacy line"), ("no_majority_claim", "header: no majority claim")]


def card_conditions(width_in: float = TEXTWIDTH_IN, height_in: float = 2.3, legend_top: bool = False) -> Path:
    """B1: final-vote shares per card condition, one panel per family, humans on top."""
    from src.figures import ASSESS
    import yaml
    apply_style()
    rows = {(r["family"], r["condition"]): r for r in csv.DictReader((RES / "b1_card_conditions.csv").open())}
    human = yaml.safe_load((ROOT / "inputs" / "human_ground_truth.yaml").read_text())["acceptability"]["counts"]
    opts = [k.removeprefix("assess_") for k, _, _ in ASSESS]
    hum = [human[o] / sum(human[o] for o in opts) for o in opts]
    fams = [("Qwen", "Qwen 3.5 27B"), ("Gemma", "Gemma 3 27B"), ("Mistral", "Mistral Small 3.2 24B")]
    fig, axes = plt.subplots(1, 3, figsize=(width_in, height_in), sharey=True)
    labels = ["humans (n = 10)"] + [lab for _, lab in B1_ORDER]
    for ax, (fam, title) in zip(axes, fams):
        data = [hum] + [[float(rows[(fam, c)][f"{o}_share"]) if (fam, c) in rows else 0 for o in opts]
                        for c, _ in B1_ORDER]
        n = rows.get((fam, "baseline_replay"), {}).get("n_runs", "?")
        for y, shares in enumerate(data):
            left = 0.0
            for (_, _, colour), v in zip(ASSESS, shares):
                ax.barh(y, v, left=left, color=colour, height=0.72, lw=0)
                left += v
            if left < 0.999:   # prefer not / no answer
                ax.barh(y, 1 - left, left=left, color=PALETTE["grey"], alpha=0.35, height=0.72, lw=0)
        ax.axhline(0.5, color=PALETTE["ink"], lw=0.6)
        ax.set_title(f"{title} ({n} runs)", fontsize=FONT["title"])
        ax.set_xlim(0, 1)
        ax.set_xticks([0, 0.5, 1])
        ax.set_xticklabels(["0", "50%", "100%"])
        ax.invert_yaxis() if ax is axes[0] else None
    axes[0].set_yticks(range(len(labels)))
    axes[0].set_yticklabels(labels)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c, label=lab) for _, lab, c in ASSESS]
    if legend_top:             # poster: legend above the panels, centred over them
        fig.tight_layout(rect=(0, 0, 1, 0.93))
        centre = (axes[0].get_position().x0 + axes[-1].get_position().x1) / 2
        fig.legend(handles=handles, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(centre, 1.0))
    else:
        fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.6, -0.02))
        fig.tight_layout(rect=(0, 0.07, 1, 1))
    FIG.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(FIG / f"fig_card_conditions.{ext}")
    plt.close(fig)
    return FIG / "fig_card_conditions.pdf"


if __name__ == "__main__":
    print(agreement_floor())
    print(card_conditions())
