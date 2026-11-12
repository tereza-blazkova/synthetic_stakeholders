"""
Main figure of the extended abstract: where synthetic panels put each rule, and
which model their rules select.

    python -m src.report      # calls main_figure(); writes analysis/figures/fig_rules.{pdf,png}

(a) For each of the 7 selection rules (two ladders: data added, explainability
    level), the endline median of every run, per model family: one marker per
    (family, value), area proportional to the number of runs. The human rule is a
    hollow black box. Above the bar = stricter than the humans, below = more permissive.
(b) The configuration each run's rules select (model + feature set): per family, a
    marker (area = runs) and the number of runs. The human choice is highlighted; the right column gives the
    configuration's 2021 enrolment-level recall.

Encoding: family = fixed categorical colour AND marker shape (circle, square,
triangle), so the figure survives grayscale print and colour-vision deficiency.
Colours are slots 1-3 of the dataviz reference palette, in fixed order.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch

from src.rule_applier import load_metrics
from src.score import R_ITEMS, human_value

ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "analysis" / "figures"

INK, MUTED, GRID, BAND = "#1f1f1f", "#6b6b6b", "#e3e3e3", "#f3f1ec"
FAMILIES = [  # fixed order: colour slot, marker, label
    ("qwen3.5:4b-q4_K_M", "#2a78d6", "o", "Qwen 3.5 4B"),
    ("gemma3:4b-it-q4_K_M", "#eb6834", "s", "Gemma 3 4B"),
    ("ministral-3:3b-instruct-2512-q4_K_M", "#1baf7a", "^", "Ministral 3 3B"),
]
LEVELS = ["no_threshold", "small", "moderate", "large", "never"]
LEVEL_LABELS = ["none", "small\n(1–3)", "moderate\n(5)", "large\n(10)", "never"]
RULES = [("Q3.2", "Perfor-\nmance"), ("Q3.3", "Enrol-\nment"), ("Q3.4", "LMS"),
         ("Q4.1.high", "High"), ("Q4.1.moderate", "Mod."), ("Q4.1.low", "Low"), ("Q4.1.very_low", "Very\nlow")]
MODEL_NAMES = {"credits_policy": "Credit rule", "fasterrisk": "FasterRisk", "logistic_regression": "Log. regr.",
               "xgboost": "XGBoost", "catboost": "CatBoost", "mlp": "Neural net"}
FS_NAMES = {"rule_60_ects": "", "a_credits": "credits", "b_credits_performance": "+ perform.",
            "c_plus_enrollment": "+ enrol.", "d_plus_lms": "+ LMS", "e_plus_sensitive": "+ sensitive"}
EXPL_ORDER = list(MODEL_NAMES)
FS_ORDER = list(FS_NAMES)
HUMAN = ("logistic_regression", "b_credits_performance")


def _style() -> None:
    plt.rcParams.update({
        "font.family": "sans-serif", "font.size": 7, "axes.edgecolor": GRID, "axes.linewidth": 0.8,
        "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": MUTED,
        "xtick.major.size": 0, "ytick.major.size": 0, "pdf.fonttype": 42})


def _panel_rules(ax, rows: list[dict], families: list[tuple]) -> None:
    offsets = {f[0]: (i - (len(families) - 1) / 2) * 0.27 for i, f in enumerate(families)}
    n_runs = max(sum(r["model"] == f[0] for r in rows) for f in families)
    for x, (key, _) in enumerate(RULES):
        # human rule: a black bar spanning the rule's column
        # human rule: a hollow box around that level, drawn over the markers so
        # agreement stays visible (markers inside the box = same rule as the humans)
        hy = LEVELS.index(human_value(key))
        ax.add_patch(FancyBboxPatch((x - 0.44, hy - 0.36), 0.88, 0.72, boxstyle="round,pad=0,rounding_size=0.08",
                                    fill=False, edgecolor=INK, lw=1.1, zorder=4))
        for model, colour, marker, _ in families:
            # no_answer counts as never, exactly as in the selection rules
            vals = Counter(r[key] if r[key] in LEVELS else "never" for r in rows if r["model"] == model)
            for level, k in vals.items():
                ax.scatter(x + offsets[model], LEVELS.index(level), s=10 + 62 * k / n_runs,
                           color=colour, marker=marker, edgecolors="white", linewidths=0.8, zorder=3)
    for x in range(len(RULES)):
        if x % 2 == 0:
            ax.axvspan(x - 0.5, x + 0.5, color=BAND, lw=0, zorder=0)
    ax.axvline(2.5, color=MUTED, lw=0.8, zorder=1)
    ax.set_xlim(-0.5, len(RULES) - 0.5)
    ax.set_ylim(-0.6, len(LEVELS) - 0.4)
    ax.set_xticks(range(len(RULES)))
    ax.set_xticklabels([lab for _, lab in RULES])
    ax.set_yticks(range(len(LEVELS)))
    ax.set_yticklabels(LEVEL_LABELS)
    ax.set_ylabel("Gain required per 100 students\n(higher = stricter)", color=MUTED, fontsize=6.5)
    for x0, x1, name in ((-0.5, 2.5, "Data added"), (2.5, 6.5, "Explainability level")):
        ax.text((x0 + x1) / 2, len(LEVELS) - 0.4, name, ha="center", va="bottom", color=INK, fontsize=7)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def _config_label(model: str, fs: str) -> str:
    return f"{MODEL_NAMES[model]} {FS_NAMES[fs]}".strip()


def _panel_selection(ax, rows: list[dict], families: list[tuple]) -> None:
    picks = {f[0]: Counter(tuple(r["endline_selected"].split("+")) for r in rows if r["model"] == f[0])
             for f in families}
    configs = {c for p in picks.values() for c in p} | {HUMAN}
    configs = sorted(configs, key=lambda c: (EXPL_ORDER.index(c[0]), FS_ORDER.index(c[1])))
    metrics = load_metrics()
    n_runs = max(sum(p.values()) for p in picks.values())
    col_w = 1.0
    for y, cfg in enumerate(configs):
        if cfg == HUMAN:
            ax.axhspan(y - 0.45, y + 0.45, color=BAND, lw=0, zorder=0)
        for i, (model, colour, marker, _) in enumerate(families):
            k = picks[model].get(cfg, 0)
            x0 = i * col_w
            if k:                # one marker per family, with its number of runs
                ax.scatter(x0 + 0.3, y, s=16 + 70 * k / n_runs, color=colour, marker=marker,
                           edgecolors="white", linewidths=0.6, zorder=3)
                ax.text(x0 + 0.52, y, str(k), va="center", ha="left", fontsize=7,
                        color=INK, fontweight="bold" if cfg == HUMAN else "normal")
        recall = metrics[cfg]["recall"] if cfg in metrics else None
        ax.text(len(families) * col_w + 0.2, y, f"{recall:.0%}" if recall is not None else "",
                va="center", ha="left", fontsize=6.5, color=INK if cfg == HUMAN else MUTED)
    for i in range(1, len(families)):
        ax.axvline(i * col_w, color=GRID, lw=0.8)
    ax.set_xlim(0, len(families) * col_w + 0.62)
    ax.set_ylim(len(configs) - 0.5, -0.5)
    ax.set_yticks(range(len(configs)))
    ax.set_yticklabels([_config_label(*c) + ("  (human)" if c == HUMAN else "") for c in configs], fontsize=6.8)
    for t, c in zip(ax.get_yticklabels(), configs):
        t.set_color(INK if c == HUMAN else MUTED)
        t.set_fontweight("bold" if c == HUMAN else "normal")
    ax.set_xticks([(i + 0.5) * col_w for i in range(len(families))] + [len(families) * col_w + 0.37])
    ax.set_xticklabels([f[3].split()[0] for f in families] + ["Recall"], fontsize=6.5)
    ax.xaxis.tick_top()
    for s in ax.spines.values():
        s.set_visible(False)


def main_figure(rows: list[dict]) -> Path:
    _style()
    families = [f for f in FAMILIES if any(r["model"] == f[0] for r in rows)]
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(7.0, 2.3), gridspec_kw={"width_ratios": [1.55, 1]})
    _panel_rules(ax, rows, families)
    _panel_selection(bx, rows, families)
    handles = [Line2D([], [], color=c, marker=m, ls="", ms=5.5, mec="white", mew=0.6, label=lab)
               for _, c, m, lab in families]
    handles.append(Line2D([], [], color=INK, marker="s", ls="", ms=7, mfc="none", mew=1.1,
                          label="Human workshop rule"))
    fig.legend(handles=handles, loc="lower center", ncol=len(handles), frameon=False,
               bbox_to_anchor=(0.5, -0.02), fontsize=6.8, handletextpad=0.4, columnspacing=1.6)
    fig.tight_layout(rect=(0, 0.07, 1, 0.93), w_pad=2.0)
    fig.text(ax.get_position().x0 - 0.06, 0.985, "(a) Selection rules set by each panel",
             fontsize=7.5, color=INK, va="top", fontweight="bold")
    fig.text(bx.get_position().x0 - 0.17, 0.985, "(b) Model selected by each panel's rules (number of runs)",
             fontsize=7.5, color=INK, va="top", fontweight="bold")
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(FIG_DIR / f"fig_rules.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)
    return FIG_DIR / "fig_rules.pdf"


# ── All nine settings: validity vs stability ─────────────────────────────────

SETTING_GROUPS = [("small", "lite", "Small (3–4B)\nlite protocol"), ("large", "lite", "Large (24–27B)\nlite protocol"),
                  ("large", "full", "Large (24–27B)\nfull protocol")]
FAMILY_OF = {  # model id -> (family index into FAMILIES colours/markers, tier)
    "qwen3.5:4b-q4_K_M": (0, "small"), "gemma3:4b-it-q4_K_M": (1, "small"),
    "ministral-3:3b-instruct-2512-q4_K_M": (2, "small"), "qwen3.5:27b-q4_K_M": (0, "large"),
    "gemma3:27b-it-q4_K_M": (1, "large"), "mistral-small3.2:24b-instruct-2506-q4_K_M": (2, "large"),
}
FAMILY_NAMES = ["Qwen", "Gemma", "Mistral"]


def settings_figure(rows: list[dict], chance: dict) -> Path:
    """(a) rules matched per run in every setting; (b) validity vs stability per setting."""
    _style()
    rows = [r for r in rows if r["model"] in FAMILY_OF]
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(7.0, 2.35), gridspec_kw={"width_ratios": [1.35, 1]})
    p0 = float(chance["R_coverage_mean"])
    offsets = [-0.25, 0, 0.25]
    points = {}   # (family, tier, protocol) -> (stability, validity)
    for g, (tier, protocol, label) in enumerate(SETTING_GROUPS):
        if g % 2 == 0:
            ax.axvspan(g - 0.5, g + 0.5, color=BAND, lw=0, zorder=0)
        for model, (fi, mtier) in FAMILY_OF.items():
            if mtier != tier:
                continue
            rs = [r for r in rows if r["model"] == model and r["protocol"] == protocol]
            if not rs:
                continue
            _, colour, marker, _ = FAMILIES[fi]
            counts = Counter(int(r["R_coverage"]) for r in rs)
            for v, k in counts.items():
                ax.scatter(g + offsets[fi], v, s=12 + 60 * k / len(rs), color=colour, marker=marker,
                           edgecolors="white", linewidths=0.6, zorder=3)
            mean = sum(int(r["R_coverage"]) for r in rs) / len(rs)
            ax.plot([g + offsets[fi] - 0.09, g + offsets[fi] + 0.09], [mean, mean], color=INK, lw=1.4, zorder=4)
            picks = Counter(r["endline_selected"] for r in rs)
            # small horizontal offset per family so coinciding points stay visible in (b)
            points[(fi, tier, protocol)] = (picks.most_common(1)[0][1] / len(rs) + (fi - 1) * 0.013, mean)
    ax.axhline(p0, color=MUTED, lw=0.9, ls=(0, (3, 2)), zorder=1)
    # Reference: the same human panel before deliberation vs its own endline rules
    hs = sum(human_value(k, "baseline") == human_value(k) for k in R_ITEMS)
    ax.axhline(hs, color=INK, lw=0.9, ls=(0, (1, 1.5)), zorder=1)
    ax.set_xlim(-0.5, 2.5)
    ax.set_ylim(-0.4, 7.3)
    ax.set_yticks(range(0, 8))
    ax.set_xticks(range(3))
    ax.set_xticklabels([lab for _, _, lab in SETTING_GROUPS], fontsize=6.5)
    ax.set_ylabel("Rules matching the human\nworkshop (of 7); bar = mean", color=MUTED, fontsize=6.5)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)

    # (b) validity vs stability, arrows: small -> large (lite), lite -> full (large)
    style = {("small", "lite"): dict(facecolors="white", linewidths=1.3),
             ("large", "lite"): dict(linewidths=0.6, edgecolors="white"),
             ("large", "full"): dict(linewidths=1.3, edgecolors=INK)}
    for (fi, tier, protocol), (x, y) in points.items():
        _, colour, marker, _ = FAMILIES[fi]
        kw = dict(style[(tier, protocol)])
        if tier == "small":
            kw["edgecolors"] = colour
            bx.scatter(x, y, s=48, marker=marker, zorder=4, **kw)
        else:
            bx.scatter(x, y, s=48, color=colour, marker=marker, zorder=4, **kw)
    for fi in range(3):
        _, colour, _, _ = FAMILIES[fi]
        chain = [points.get((fi, "small", "lite")), points.get((fi, "large", "lite")), points.get((fi, "large", "full"))]
        for a, b, ls in ((chain[0], chain[1], (0, (2, 2))), (chain[1], chain[2], "-")):
            if a and b:
                bx.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle="-|>", color=colour, lw=0.9,
                                                                 linestyle=ls, shrinkA=5, shrinkB=5, alpha=0.8))
    bx.axhline(p0, color=MUTED, lw=0.9, ls=(0, (3, 2)))
    bx.axhline(hs, color=INK, lw=0.9, ls=(0, (1, 1.5)))
    bx.set_xlim(0.45, 1.05)
    bx.set_ylim(0, 4.2)
    bx.set_xlabel("Stability: runs choosing the modal configuration", color=MUTED, fontsize=6.5)
    bx.set_ylabel("Agreement: mean rules matching\nthe human workshop", color=MUTED, fontsize=6.5)
    bx.set_xticks([0.5, 0.75, 1.0])
    bx.set_xticklabels(["50%", "75%", "100%"])
    bx.grid(color=GRID, lw=0.5)
    bx.set_axisbelow(True)
    for s in ("top", "right"):
        bx.spines[s].set_visible(False)

    fam = [Line2D([], [], color=c, marker=m, ls="", ms=5.5, mec="white", mew=0.6, label=FAMILY_NAMES[i])
           for i, (_, c, m, _) in enumerate(FAMILIES)]
    tiers = [Line2D([], [], color="white", marker="o", ls="", ms=5.5, mec=MUTED, mew=1.2, label="small, lite"),
             Line2D([], [], color=MUTED, marker="o", ls="", ms=5.5, mec="white", mew=0.6, label="large, lite"),
             Line2D([], [], color=MUTED, marker="o", ls="", ms=5.5, mec=INK, mew=1.2, label="large, full")]
    refs = [Line2D([], [], color=MUTED, lw=0.9, ls=(0, (3, 2)), label="random panels"),
            Line2D([], [], color=INK, lw=0.9, ls=(0, (1, 1.5)), label="same humans before deliberation")]
    fig.legend(handles=fam + tiers + refs, loc="lower center", ncol=8, frameon=False, bbox_to_anchor=(0.5, -0.03),
               fontsize=6.5, handletextpad=0.3, columnspacing=1.0, handlelength=1.6)
    fig.tight_layout(rect=(0, 0.07, 1, 0.93), w_pad=2.5)
    fig.text(ax.get_position().x0 - 0.07, 0.985, "(a) Agreement with the human workshop's rules", fontsize=7.5,
             color=INK, va="top", fontweight="bold")
    fig.text(bx.get_position().x0 - 0.06, 0.985, "(b) Larger models: more stable, less agreement", fontsize=7.5,
             color=INK, va="top", fontweight="bold")
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(FIG_DIR / f"fig_settings.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)
    return FIG_DIR / "fig_settings.pdf"


# ── Full protocol only: the setting that replicates the human workshop ───────

LARGE_FAMILIES = [   # approximate logo colours: Qwen violet, Gemma (Google) blue, Mistral orange
    ("qwen3.5:27b-q4_K_M", "#6B4EE6", "o", "Qwen 3.5 27B"),
    ("gemma3:27b-it-q4_K_M", "#1A9BE8", "s", "Gemma 3 27B"),
    ("mistral-small3.2:24b-instruct-2506-q4_K_M", "#FA520F", "^", "Mistral Small 3.2 24B"),
]
# support -> block, kept clear of the family colours: greens for support, reds for objections
ASSESS = [("assess_support", "support", "#1B7F5A"),
          ("assess_support_with_reservations", "with reservations", "#A8D5C2"),
          ("assess_object_no_block", "object", "#F2B8B5"), ("assess_block", "block", "#C62828")]


def full_figure(rows: list[dict], letters: tuple[str, str, str] = ("a", "b", "c")) -> Path:
    """Full protocol only, in the FAccT paper's figure style (src/paper_style.py).

    a  endline answer per rule and family (marker area = runs giving it) against the
       human endline rule (solid box) and human baseline where different (dashed box);
    b  items (of 23) whose panel median moved between baseline and endline, stricter vs
       looser, with the share of the humans' own moves each panel repeated;
    c  final acceptability votes (families: 240 cards each; humans: the 10 cards
       filled in, counts from the workshop records, not in the FAccT paper).
    """
    from src import aggregate
    from src.paper_style import FONT, PALETTE, TEXTWIDTH_IN, apply_style
    from src.score import GT, S_ITEMS
    apply_style()
    ink, grey = PALETTE["ink"], PALETTE["grey"]
    rows = [r for r in rows if r["protocol"] == "full" and r["model"] in {f[0] for f in LARGE_FAMILIES}]
    fig, (ax, bx, cx) = plt.subplots(1, 3, figsize=(TEXTWIDTH_IN, 1.95),
                                     gridspec_kw={"width_ratios": [1.5, 0.8, 0.8]})

    # a  endline rules
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
    ax.set_xticklabels([lab for _, lab in RULES])
    ax.set_yticks(range(len(LEVELS)))
    ax.set_yticklabels(["none", "small (1–3)", "moderate (5)", "large (10)", "never"])
    ax.set_ylabel("Gain required per 100 students")
    for x0, x1, name in ((-0.5, 2.5, "Data added"), (2.5, 6.5, "Explainability level")):
        ax.text((x0 + x1) / 2, len(LEVELS) - 0.45, name, ha="center", va="bottom", fontsize=FONT["label"])

    # b  baseline -> endline movement of the panel medians
    order = aggregate.SCALE_ORDER
    hd = [(order[k].index(human_value(k)) > order[k].index(human_value(k, "baseline")))
          - (order[k].index(human_value(k)) < order[k].index(human_value(k, "baseline"))) for k in R_ITEMS + S_ITEMS]
    bars = [(ink, sum(d > 0 for d in hd), sum(d < 0 for d in hd), None)]
    for model, colour, _, _ in LARGE_FAMILIES:
        rs = [r for r in rows if r["model"] == model]
        m = lambda f: sum(float(r[f]) for r in rs) / len(rs)
        bars.append((colour, m("shift_stricter"), m("shift_permissive"), m("shift_same_as_humans")))
    for y, (colour, up, down, same) in enumerate(bars):
        bx.barh(y, up, color=colour, height=0.6)
        bx.barh(y, down, left=up, color=colour, alpha=0.4, height=0.6)
        note = f"{up + down}" if same is None else f"{up + down:.1f} ({same:.0%})"
        bx.text(up + down + 0.3, y, note, va="center", fontsize=FONT["annot"], color=ink)

    # c  final acceptability votes
    shares = [[GT["acceptability"]["counts"][k.removeprefix("assess_")] for k, _, _ in ASSESS]]
    for model, _, _, _ in LARGE_FAMILIES:
        rs = [r for r in rows if r["model"] == model]
        shares.append([sum(float(r[k]) for r in rs) for k, _, _ in ASSESS])
    for y, tot in enumerate(shares):
        left = 0.0
        for (_, _, colour), v in zip(ASSESS, tot):
            cx.barh(y, v / sum(tot), left=left, color=colour, height=0.6, edgecolor="white", linewidth=0.4)
            left += v / sum(tot)

    names = ["Humans"] + [lab.split()[0] for _, _, _, lab in LARGE_FAMILIES]
    for axis, xlab, xmax in ((bx, "Items moved, of 23 (mean per run)", 14),
                             (cx, "Share of final votes", 1.0)):
        axis.set_yticks(range(len(names)))
        axis.set_yticklabels(names)
        axis.set_ylim(len(names) - 0.5, -0.5)
        axis.set_xlim(0, xmax)
        axis.set_xlabel(xlab)
        axis.spines["left"].set_visible(False)
        axis.tick_params(axis="y", length=0)
    bx.set_xticks([0, 5, 10])
    cx.set_xticks([0, 0.5, 1])
    cx.set_xticklabels(["0", "50%", "100%"])
    cx.set_yticklabels([])

    # one legend per panel, on top, as in the FAccT figures
    fam = [Line2D([], [], color=c, marker=m, ls="", ms=5, mec="white", mew=0.5, label=lab)
           for _, c, m, lab in LARGE_FAMILIES]
    human = [Line2D([], [], color=ink, marker="s", ls="", ms=6.5, mfc="none", mew=1.0, label="human endline rule"),
             FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.1", fill=False, edgecolor=grey,
                            lw=0.9, ls=(0, (2, 1.5)), label="human baseline")]
    # legends fill column by column: this order gives rows (families) and (human boxes)
    legend_a = [fam[0], human[0], fam[1], human[1], fam[2]]
    legend_b = [plt.Rectangle((0, 0), 1, 1, color=grey, label="stricter"),
                plt.Rectangle((0, 0), 1, 1, color=grey, alpha=0.4, label="looser")]
    legend_c = [plt.Rectangle((0, 0), 1, 1, color=c, label=lab) for _, lab, c in ASSESS]
    kw = dict(loc="lower left", frameon=False, handletextpad=0.4, columnspacing=1.0, borderaxespad=0,
              handlelength=1.4)
    fig.tight_layout(rect=(0, 0, 1, 0.80), w_pad=1.5)
    # centre b between a and c: equal white space on both sides, counting b's row labels
    fig.canvas.draw()
    inv = fig.transFigure.inverted()
    a_right, c_left, pb = ax.get_position().x1, cx.get_position().x0, bx.get_position()
    b_left_ink = bx.get_tightbbox(fig.canvas.get_renderer()).transformed(inv).x0
    gap = ((c_left - a_right) - (pb.x1 - b_left_ink)) / 2
    bx.set_position([pb.x0 + a_right + gap - b_left_ink, pb.y0, pb.width, pb.height])
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    legend_y = ax.get_position().y1 + 0.085          # clears a's "Data added" labels
    letter_y = legend_y + 0.13
    for axis, letter, handles, ncol in ((ax, letters[0], legend_a, 3), (bx, letters[1], legend_b, 1),
                                        (cx, letters[2], legend_c, 2)):
        x0 = axis.get_tightbbox(renderer).transformed(inv).x0
        fig.legend(handles=handles, ncol=ncol, bbox_to_anchor=(x0, legend_y), **kw)
        fig.text(x0, letter_y, letter, fontsize=FONT["panel"], fontweight="bold", va="bottom", ha="left")
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(FIG_DIR / f"fig_full.{ext}")
    plt.close(fig)
    return FIG_DIR / "fig_full.pdf"
