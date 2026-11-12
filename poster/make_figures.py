"""Poster versions of the figures, written to poster/figs/ (nothing else is touched).

Run from the project root:
    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python poster/make_figures.py

It reuses the plotting functions in src/figures.py and src/figures_post_review.py
unchanged. Three things are redirected for the duration of each call:
  * the output folders (src.figures.FIG_DIR, src.figures_post_review.FIG) -> poster/figs/
  * the type sizes (src.paper_style.FONT and its rcParams) are multiplied by a factor
  * for fig_full, src.paper_style.TEXTWIDTH_IN (its canvas width) is set to POSTER_SPECS
The originals in analysis/figures/ are never overwritten.

Type size on the printed poster = type size in the figure x (printed width / canvas width).
Each spec below records the printed width that main.tex uses for the figure, so the
script prints the resulting smallest type size.
"""
from __future__ import annotations

import csv
import re
import sys
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import figures, figures_post_review, paper_style  # noqa: E402

OUT = ROOT / "poster" / "figs"
CM = 1 / 2.54

# canvas (inches), font factor, printed width in main.tex (cm)
POSTER_SPECS = {
    "agreement_floor": dict(width_in=3.7, height_in=1.3, font=1.1, print_cm=41.2),
    "full":            dict(width_in=7.0, height_in=1.95, font=1.0, print_cm=79.3),   # height fixed in src
    "card_conditions": dict(width_in=5.6, height_in=2.05, font=1.1, print_cm=41.1),
    "selection_map":   dict(width_in=4.4, height_in=2.7, font=1.25, print_cm=37.6),
    "results":         dict(width_in=7.0, height_in=3.68, font=1.2, print_cm=70.7),   # one figure, panels A-D
    "gemma_precision": dict(width_in=1.9, height_in=0.68, font=1.0, print_cm=17.4),
}
FONT_KEYS = ("font.size", "axes.titlesize", "axes.labelsize", "xtick.labelsize", "ytick.labelsize",
             "legend.fontsize", "legend.title_fontsize")


@contextmanager
def poster_mode(font: float, textwidth_in: float | None = None):
    """Scale type sizes and redirect output; restore everything afterwards."""
    font_saved = dict(paper_style.FONT)
    rc_saved = {k: paper_style._RCPARAMS[k] for k in FONT_KEYS}
    tw_saved = paper_style.TEXTWIDTH_IN
    dirs_saved = figures.FIG_DIR, figures_post_review.FIG
    try:
        for k in paper_style.FONT:
            paper_style.FONT[k] = font_saved[k] * font          # same dict object everywhere
        for k in FONT_KEYS:
            paper_style._RCPARAMS[k] = rc_saved[k] * font
        if textwidth_in is not None:
            paper_style.TEXTWIDTH_IN = textwidth_in
        figures.FIG_DIR = OUT
        figures_post_review.FIG = OUT
        yield
    finally:
        paper_style.FONT.update(font_saved)
        paper_style._RCPARAMS.update(rc_saved)
        paper_style.TEXTWIDTH_IN = tw_saved
        figures.FIG_DIR, figures_post_review.FIG = dirs_saved


def report(name: str, spec: dict) -> None:
    """Printed type sizes, from the saved PDF's real width (bbox_inches="tight" trims the canvas)."""
    pdf = (OUT / f"fig_{name}.pdf").read_bytes()
    m = re.search(rb"/MediaBox\s*\[\s*0 0 ([\d.]+) ([\d.]+)", pdf)
    width_in = float(m.group(1)) / 72 if m else spec["width_in"]
    scale = spec["print_cm"] * CM / width_in
    smallest = min(paper_style.FONT.values()) * spec["font"] * scale
    tick = paper_style._RCPARAMS["font.size"] * spec["font"] * scale
    print(f"{name:16s} {width_in:.2f} in wide, printed {spec['print_cm']} cm: x{scale:.2f}; "
          f"ticks {tick:.0f} pt, smallest text {smallest:.0f} pt")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    s = POSTER_SPECS["agreement_floor"]
    with poster_mode(s["font"]):
        print(figures_post_review.agreement_floor(width_in=s["width_in"], height_in=s["height_in"]))
    report("agreement_floor", s)

    s = POSTER_SPECS["full"]
    with (ROOT / "analysis" / "results" / "scores_by_run.csv").open() as f:
        rows = list(csv.DictReader(f))           # as src/report.py passes them
    with poster_mode(s["font"], textwidth_in=s["width_in"]):
        print(figures.full_figure(rows, letters=("A", "C", "D")))   # poster: B is the selection map
    report("full", s)

    s = POSTER_SPECS["card_conditions"]
    with poster_mode(s["font"]):
        print(figures_post_review.card_conditions(width_in=s["width_in"], height_in=s["height_in"], legend_top=True))
    report("card_conditions", s)

    from poster import selection_map
    s = POSTER_SPECS["selection_map"]
    with poster_mode(s["font"]):
        print(selection_map.main(s["width_in"], s["height_in"]))
    report("selection_map", s)

    from poster import fig_results
    s = POSTER_SPECS["results"]
    with poster_mode(s["font"]):
        print(fig_results.main(s["width_in"], s["height_in"]))
    report("results", s)

    s = POSTER_SPECS["gemma_precision"]
    with poster_mode(s["font"]):
        print(gemma_precision(s["width_in"], s["height_in"]))
    report("gemma_precision", s)


def gemma_precision(width_in: float, height_in: float) -> Path:
    """Poster only (takeaway 4): Gemma's final votes at 4-, 8- and 16-bit, humans on top.
    Counts are read from the run logs (assessment.json), all 20 seeded runs per condition."""
    import json
    import matplotlib.pyplot as plt
    import yaml
    paper_style.apply_style()
    opts = [k.removeprefix("assess_") for k, _, _ in figures.ASSESS]
    human = yaml.safe_load((ROOT / "inputs" / "human_ground_truth.yaml").read_text())["acceptability"]["counts"]
    rows = [("humans", [human[o] for o in opts])]
    for label, folder in [("4-bit", "runs/full/gemma3_27b-it-q4_K_M"),
                          ("8-bit", "runs/post_review/precision_q8/full/gemma3_27b-it-q8_0"),
                          ("16-bit$^\\dagger$", "runs/post_review/precision_fp16/full/gemma3_27b-it-fp16")]:
        c = dict.fromkeys(opts, 0)
        for d in sorted((ROOT / folder).glob("run[0-9]*")):
            if (d / "run_meta.json").exists():
                for v in json.loads((d / "assessment.json").read_text()).values():
                    if v.get("choice") in c:
                        c[v["choice"]] += 1
        rows.append((label, [c[o] for o in opts]))
    fig, ax = plt.subplots(figsize=(width_in, height_in))
    for y, (_, counts) in enumerate(rows):
        left, tot = 0.0, sum(counts)
        for (_, _, colour), n in zip(figures.ASSESS, counts):
            ax.barh(y, n / tot, left=left, color=colour, height=0.72, lw=0)
            left += n / tot
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows])
    ax.invert_yaxis()
    ax.axhline(0.5, color=paper_style.PALETTE["ink"], lw=0.6)
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.5, 1])
    ax.set_xticklabels(["0", "50%", "100%"])
    out = OUT / "fig_gemma_precision.pdf"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


if __name__ == "__main__":
    main()
