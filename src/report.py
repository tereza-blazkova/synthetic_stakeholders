"""
Figure and table for the extended abstract, from the scored runs.

    python -m src.report                 # needs analysis/results/scores_by_run.csv (python -m src.score)

Writes analysis/figures/fig_agreement.{pdf,png} and analysis/tables/table_main.tex.

Figure: (a) share of runs whose panel median equals the human rule, per model and
selection rule, with the random-panel rate as a reference row; (b) share of runs
selecting the human model (logistic regression on credits + performance), with
Wilson 95% intervals and the random-panel rate as a dashed line.
Colour: one sequential blue ramp (light = low, dark = high), readable in grayscale.
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

from src.score import OUT, R_ITEMS, human_value, wilson

ROOT = Path(__file__).resolve().parents[1]
FIG_DIR, TAB_DIR = ROOT / "analysis" / "figures", ROOT / "analysis" / "tables"

# Sequential blue ramp (dataviz reference palette, steps 100 -> 700)
BLUES = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
INK, MUTED, GRID = "#1f1f1f", "#6b6b6b", "#d9d9d9"

RULE_LABELS = {"Q3.2": "Perform.", "Q3.3": "Enrol.", "Q3.4": "LMS",
               "Q4.1.high": "High", "Q4.1.moderate": "Moderate", "Q4.1.low": "Low", "Q4.1.very_low": "Very low"}
MODEL_LABELS = {"qwen3.5:4b-q4_K_M": "Qwen 3.5 4B", "gemma3:4b-it-q4_K_M": "Gemma 3 4B",
                "ministral-3:3b-instruct-2512-q4_K_M": "Ministral 3 3B", "fake": "Fake (test)"}
VALUE_LABELS = {"no_threshold": "none", "small": "small", "moderate": "moderate", "large": "large", "never": "never"}


def _read(path: Path) -> list[dict]:
    with path.open() as f:
        return list(csv.DictReader(f))


def _ink_on(hex_colour: str) -> str:
    r, g, b = (int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return "white" if 0.2126 * r + 0.7152 * g + 0.0722 * b < 0.5 else INK


def figure(rows: list[dict], chance: dict) -> None:
    models = [m for m in MODEL_LABELS if any(r["model"] == m for r in rows)]
    grid = [[sum(r[k] == human_value(k) for r in rows if r["model"] == m)
             / sum(r["model"] == m for r in rows) for k in R_ITEMS] for m in models]
    grid.append([float(chance[f"item_{k}"]) for k in R_ITEMS])
    row_labels = [MODEL_LABELS[m] for m in models] + ["Random panel"]

    plt.rcParams.update({"font.family": "sans-serif", "font.size": 7.5, "axes.edgecolor": GRID,
                         "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": INK})
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(7.0, 2.0), gridspec_kw={"width_ratios": [3.2, 1.25]})
    cmap = LinearSegmentedColormap.from_list("blues", BLUES)

    # (a) per-rule agreement
    for i, row in enumerate(grid):
        for j, v in enumerate(row):
            colour = matplotlib.colors.to_hex(cmap(v))
            ax.add_patch(plt.Rectangle((j + 0.04, i + 0.06), 0.92, 0.88, color=colour, lw=0))
            ax.text(j + 0.5, i + 0.5, f"{v:.0%}" if i < len(models) else f"{v:.0%}",
                    ha="center", va="center", color=_ink_on(colour), fontsize=7)
    ax.axhline(len(models) + 0.0, color="white", lw=3)
    ax.set_xlim(0, len(R_ITEMS)); ax.set_ylim(len(grid), 0)
    ax.set_xticks([j + 0.5 for j in range(len(R_ITEMS))])
    ax.set_xticklabels([f"{RULE_LABELS[k]}\n[{VALUE_LABELS[human_value(k)]}]" for k in R_ITEMS], fontsize=6.5)
    ax.xaxis.tick_top()
    ax.set_yticks([i + 0.5 for i in range(len(grid))]); ax.set_yticklabels(row_labels)
    ax.get_yticklabels()[-1].set_color(MUTED)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    # Group headers above the column labels, placed in points so they never
    # collide with the two-line tick labels whatever the figure height.
    from matplotlib.transforms import blended_transform_factory, offset_copy
    for x0, x1, name in ((0, 3, "Data added"), (3, 7, "Explainability level")):
        base = blended_transform_factory(ax.transData, ax.transAxes)
        line_tr = offset_copy(base, fig=fig, y=27, units="points")
        ax.plot([x0 + 0.08, x1 - 0.08], [1, 1], color=GRID, lw=0.8, transform=line_tr, clip_on=False)
        ax.text((x0 + x1) / 2, 1, name, ha="center", va="bottom", fontsize=6.5, color=INK,
                transform=offset_copy(base, fig=fig, y=29, units="points"))

    # (b) decision match with Wilson intervals
    for i, m in enumerate(models):
        rs = [r for r in rows if r["model"] == m]
        k, n = sum(r["decision_match"] == "True" for r in rs), len(rs)
        lo, hi = wilson(k, n)
        bx.plot([lo, hi], [i, i], color=BLUES[4], lw=2, solid_capstyle="round")
        bx.plot(k / n, i, "o", ms=6, color=BLUES[5], mec="white", mew=1.5)
        bx.text(1.02, i, f"{k}/{n}", va="center", fontsize=6.5, color=MUTED, transform=bx.get_yaxis_transform())
    p0 = float(chance["decision_match_rate"])
    bx.axvline(p0, color=MUTED, lw=1, ls=(0, (3, 2)))
    bx.text(p0 + 0.02, 1.01, "random panel", fontsize=6, color=MUTED, va="bottom",
            transform=bx.get_xaxis_transform())
    bx.set_xlim(-0.03, 1); bx.set_ylim(len(models) - 0.4, -0.6)
    bx.set_yticks(range(len(models))); bx.set_yticklabels([MODEL_LABELS[m] for m in models])
    bx.set_xticks([0, 0.5, 1]); bx.set_xticklabels(["0%", "50%", "100%"])
    bx.grid(axis="x", color=GRID, lw=0.6); bx.set_axisbelow(True)
    bx.tick_params(length=0)
    for s in ("top", "right", "left"):
        bx.spines[s].set_visible(False)


    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(w_pad=2.5, rect=(0, 0, 1, 0.95))
    fig.text(ax.get_position().x0, 0.97, "(a) Share of runs whose rule equals the human rule [human value]",
             fontsize=7.5, color=INK, va="top")
    fig.text(bx.get_position().x0, 0.97, "(b) Share of runs selecting the human model",
             fontsize=7.5, color=INK, va="top")
    for ext in ("pdf", "png"):
        fig.savefig(FIG_DIR / f"fig_agreement.{ext}", dpi=300, bbox_inches="tight")


# The nine settings, in reporting order: (macro suffix, model id, protocol, family, setting label)
SETTINGS = [
    ("QwenSmall", "qwen3.5:4b-q4_K_M", "lite", "Qwen", "small, lite"),
    ("GemmaSmall", "gemma3:4b-it-q4_K_M", "lite", "Gemma", "small, lite"),
    ("MistralSmall", "ministral-3:3b-instruct-2512-q4_K_M", "lite", "Mistral", "small, lite"),
    ("QwenLargeLite", "qwen3.5:27b-q4_K_M", "lite", "Qwen", "large, lite"),
    ("GemmaLargeLite", "gemma3:27b-it-q4_K_M", "lite", "Gemma", "large, lite"),
    ("MistralLargeLite", "mistral-small3.2:24b-instruct-2506-q4_K_M", "lite", "Mistral", "large, lite"),
    ("QwenLargeFull", "qwen3.5:27b-q4_K_M", "full", "Qwen", "large, full"),
    ("GemmaLargeFull", "gemma3:27b-it-q4_K_M", "full", "Gemma", "large, full"),
    ("MistralLargeFull", "mistral-small3.2:24b-instruct-2506-q4_K_M", "full", "Mistral", "large, full"),
]
FULL_NAMES = {**MODEL_LABELS, "qwen3.5:27b-q4_K_M": "Qwen 3.5 27B", "gemma3:27b-it-q4_K_M": "Gemma 3 27B",
              "mistral-small3.2:24b-instruct-2506-q4_K_M": "Mistral Small 3.2 24B"}


def _summary_for(summary: list[dict], model: str, protocol: str) -> dict | None:
    return next((s for s in summary if s["model"] == model and s["protocol"] == protocol), None)


def table(summary: list[dict], chance: dict) -> None:
    """One row per setting, grouped by size and protocol, plus the random panel."""
    def ci(lo: float, hi: float) -> str:
        return f"{lo:.2f}".lstrip("0") + "--" + f"{hi:.2f}".lstrip("0").replace("1.00", "1")
    lines = [r"\begin{tabular}{@{}llccccr@{}}", r"\toprule",
             r"Setting & Model & Rules /7 & Other /16 & Human model [95\% CI] & Modal & Recall gap \\"]
    group = None
    for key, model, protocol, family, label in SETTINGS:
        s = _summary_for(summary, model, protocol)
        if s is None:
            continue
        if label != group:
            lines.append(r"\midrule")
            group = label
        lo, hi = (float(x) for x in s["decision_match_ci"].strip("()").split(", "))
        lines.append(f"{label} & {FULL_NAMES.get(model, model)} & {s['R_coverage_mean']} ({s['R_coverage_range'].replace('-', '--')}) "
                     f"& {s['S_coverage_mean']} & {s['decision_match']} [{ci(lo, hi)}] & {s['modal_share']} "
                     f"& {float(s['mean_recall_gap']) * 100:+.1f} pp \\\\")
    lines += [r"\midrule",
              f"Random panel & & {chance['R_coverage_mean']} & {chance['S_coverage_mean']} & "
              f"{float(chance['decision_match_rate']) * 100:.0f}\\% & -- & -- \\\\", r"\bottomrule", r"\end{tabular}"]
    TAB_DIR.mkdir(parents=True, exist_ok=True)
    (TAB_DIR / "table_main.tex").write_text("\n".join(lines) + "\n")


def table_full(rows: list[dict], summary: list[dict], chance: dict) -> None:
    """Full-protocol settings only (the ones that replicate the human workshop), with
    the random panel and the same humans before deliberation as reference rows."""
    import statistics as st
    from src import aggregate
    from src.score import R_ITEMS, S_ITEMS, human_value
    def ci(lo: float, hi: float) -> str:
        return f"{lo:.2f}".lstrip("0") + "--" + f"{hi:.2f}".lstrip("0").replace("1.00", "1")
    lines = [r"\begin{tabular}{@{}lcccccc@{}}", r"\toprule",
             r" & Rules /7 & Other /16 & Human model [95\% CI] & Modal & Moved b$\to$e (str./perm.) & Rules moved /7 \\",
             r"\midrule"]
    for key, model, protocol, family, label in SETTINGS:
        if protocol != "full":
            continue
        s = _summary_for(summary, model, protocol)
        rs = [r for r in rows if r["model"] == model and r["protocol"] == protocol]
        lo, hi = (float(x) for x in s["decision_match_ci"].strip("()").split(", "))
        m = lambda f: st.mean(float(r[f]) for r in rs)
        lines.append(f"{FULL_NAMES[model]} & {s['R_coverage_mean']} ({s['R_coverage_range'].replace('-', '--')}) & {s['S_coverage_mean']} "
                     f"& {s['decision_match']} [{ci(lo, hi)}] & {s['modal_share']} "
                     f"& {m('shift_stricter') + m('shift_permissive'):.1f} ({m('shift_stricter'):.1f}/{m('shift_permissive'):.1f}) "
                     f"& {m('rules_shifted'):.1f} \\\\")
    hb_r = sum(human_value(k, "baseline") == human_value(k) for k in R_ITEMS)
    hb_s = sum(human_value(k, "baseline") == human_value(k) for k in S_ITEMS)
    order = aggregate.SCALE_ORDER
    d = [(order[k].index(human_value(k)) > order[k].index(human_value(k, "baseline")))
         - (order[k].index(human_value(k)) < order[k].index(human_value(k, "baseline"))) for k in R_ITEMS + S_ITEMS]
    moved_r = sum(human_value(k, "baseline") != human_value(k) for k in R_ITEMS)
    lines += [r"\midrule",
              f"Humans (baseline vs.\\ endline) & {hb_r} & {hb_s} & yes & -- & {sum(x != 0 for x in d)} "
              f"({sum(x > 0 for x in d)}/{sum(x < 0 for x in d)}) & {moved_r} \\\\",
              f"Random panel & {chance['R_coverage_mean']} & {chance['S_coverage_mean']} & "
              f"{float(chance['decision_match_rate']) * 100:.0f}\\% & -- & -- & -- \\\\",
              r"\bottomrule", r"\end{tabular}"]
    TAB_DIR.mkdir(parents=True, exist_ok=True)
    (TAB_DIR / "table_full.tex").write_text("\n".join(lines) + "\n")


def numbers(rows: list[dict], summary: list[dict], chance: dict) -> None:
    """Every number the paper text quotes, as LaTeX macros (\\input by the paper),
    so the prose never holds a hand-typed result. Per-setting macros are suffixed
    with the setting key (e.g. \\rulesQwenLargeFull); totals are per tier."""
    m = [r"% Generated by src/report.py from analysis/results/. Do not edit by hand."]
    def put(name, value):
        m.append(f"\\newcommand{{\\{name}}}{{{value}}}")
    from src import survey as sv
    survey = sv.load_survey()
    per_agent = {"lite": sum(f.kind != "text" for f in sv.fields(survey, "baseline"))
                         + sum(f.kind != "text" for f in sv.fields(survey, "endline", skip=["Q10.5"])),
                 "full": sum(f.kind != "text" for f in sv.fields(survey, "baseline"))
                         + sum(f.kind != "text" for f in sv.fields(survey, "endline"))}
    small = {model for _, model, _, _, label in SETTINGS if label.startswith("small")}
    for tier, keep in (("Small", lambda r: r["model"] in small), ("Large", lambda r: r["model"] not in small),
                       ("Full", lambda r: r["protocol"] == "full"), ("All", lambda r: True)):
        rs = [r for r in rows if keep(r)]
        if not rs:
            continue
        put(f"nWorkshops{tier}", len(rs))
        put(f"nCalls{tier}", f"{sum(int(r['n_calls']) for r in rs):,}")
        items = sum(12 * per_agent[r["protocol"]] for r in rs)
        put(f"pctAnswered{tier}", f"{(1 - sum(int(r['items_unanswered_after_followups']) for r in rs) / items) * 100:.1f}\\%")
        put(f"nCards{tier}", 12 * len(rs))
        put(f"blockCards{tier}", sum(int(r["assess_block"]) for r in rs))
    put("nRuns", min(int(s["n_runs"]) for s in summary))
    put("chanceRules", chance["R_coverage_mean"])
    put("chanceSpec", chance["S_coverage_mean"])
    put("chanceDecision", f"{float(chance['decision_match_rate']) * 100:.0f}\\%")
    for key, model, protocol, family, label in SETTINGS:
        s = _summary_for(summary, model, protocol)
        if s is None:
            continue
        rs = [r for r in rows if r["model"] == model and r["protocol"] == protocol]
        put(f"rules{key}", s["R_coverage_mean"])
        put(f"rulesRange{key}", s["R_coverage_range"].replace("-", "--"))
        put(f"spec{key}", s["S_coverage_mean"])
        put(f"decision{key}", s["decision_match"])
        put(f"modal{key}", s["modal_share"])
        put(f"recallGap{key}", f"{float(s['mean_recall_gap']) * 100:+.1f}")
        put(f"block{key}", s["runs_any_block"])
        put(f"moreSupportive{key}", sum(int(r["q10_more_supportive"]) for r in rs))
        put(f"moreCritical{key}", sum(int(r["q10_more_critical"]) for r in rs))
    # Size and protocol effects on rules matched, with 95% bootstrap intervals
    # (10,000 resamples of runs, fixed seed), and the large-tier decision pattern.
    import random as _random
    import statistics as _st
    rng = _random.Random(1)

    def cov(model, protocol):
        return [int(r["R_coverage"]) for r in rows if r["model"] == model and r["protocol"] == protocol]

    def boot(a, b, B=10000):
        d = sorted(_st.mean(rng.choice(b) for _ in b) - _st.mean(rng.choice(a) for _ in a) for _ in range(B))
        return _st.mean(b) - _st.mean(a), d[int(0.025 * B)], d[int(0.975 * B)]

    fmt = lambda x: f"{x:+.2f}".replace("+0.00", "0.00").replace("-0.00", "0.00")
    pairs = {"Qwen": ("qwen3.5:4b-q4_K_M", "qwen3.5:27b-q4_K_M"), "Gemma": ("gemma3:4b-it-q4_K_M", "gemma3:27b-it-q4_K_M"),
             "Mistral": ("ministral-3:3b-instruct-2512-q4_K_M", "mistral-small3.2:24b-instruct-2506-q4_K_M")}
    for fam, (sm, lg) in pairs.items():
        for name, (a, b) in (("size", (cov(sm, "lite"), cov(lg, "lite"))), ("protocol", (cov(lg, "lite"), cov(lg, "full")))):
            if a and b:
                d, lo, hi = boot(a, b)
                put(f"{name}Diff{fam}", fmt(d))
                put(f"{name}CI{fam}", f"[{fmt(lo)}, {fmt(hi)}]")
    large = [r for r in rows if r["model"] not in small]
    if large:
        put("nRunsLarge", len(large))
        put("lrcLarge", sum(r["endline_selected"] == "logistic_regression+c_plus_enrollment" for r in large))
        put("enrolLowLarge", sum(r["Q3.3"] in ("no_threshold", "small", "moderate") for r in large))

    # Reference point: the same human panel before deliberation (baseline medians)
    # compared with its own endline rules. One human workshop is a single draw,
    # so this indicates how far one group's rules move, not a ceiling.
    from src import aggregate
    from src.score import R_ITEMS, S_ITEMS, human_value
    put("humanSelfRules", sum(human_value(k, "baseline") == human_value(k) for k in R_ITEMS))
    put("humanSelfSpec", sum(human_value(k, "baseline") == human_value(k) for k in S_ITEMS))
    put("humanChangedRules", sum(human_value(k, "baseline") != human_value(k) for k in R_ITEMS))

    # Baseline -> endline movement of the panel medians (23 assessed items), per setting,
    # and the human panel's own movement for comparison.
    for key, model, protocol, _, _ in SETTINGS:
        rs = [r for r in rows if r["model"] == model and r["protocol"] == protocol]
        if not rs:
            continue
        mean = lambda f: _st.mean(float(r[f]) for r in rs)
        put(f"shiftItems{key}", f"{mean('shift_stricter') + mean('shift_permissive'):.1f}")
        put(f"shiftStricter{key}", f"{mean('shift_stricter'):.1f}")
        put(f"shiftPermissive{key}", f"{mean('shift_permissive'):.1f}")
        put(f"rulesShifted{key}", f"{mean('rules_shifted'):.1f}")
        put(f"shiftSame{key}", f"{mean('shift_same_as_humans') * 100:.0f}\\%")
    hd = {k: (aggregate.SCALE_ORDER[k].index(human_value(k)) > aggregate.SCALE_ORDER[k].index(human_value(k, "baseline")))
             - (aggregate.SCALE_ORDER[k].index(human_value(k)) < aggregate.SCALE_ORDER[k].index(human_value(k, "baseline")))
          for k in R_ITEMS + S_ITEMS}
    put("humanShiftItems", sum(v != 0 for v in hd.values()))
    put("humanShiftStricter", sum(v > 0 for v in hd.values()))
    put("humanShiftPermissive", sum(v < 0 for v in hd.values()))
    put("humanSensitiveStricter", sum(v > 0 for k, v in hd.items() if k.startswith("Q3.5.")))
    put("nSensitive", sum(k.startswith("Q3.5.") for k in hd))
    full = [r for r in rows if r["protocol"] == "full"]
    if full:
        put("nRunsFullAll", len(full))
        put("lrcFull", sum(r["endline_selected"] == "logistic_regression+c_plus_enrollment" for r in full))
        put("enrolLowFull", sum(r["Q3.3"] in ("no_threshold", "small", "moderate") for r in full))
        put("baseLrcFull", sum(r["baseline_selected"] == "logistic_regression+c_plus_enrollment" for r in full))
        cards = {k: sum(float(r[k]) for r in full) for k in ("assess_support", "assess_support_with_reservations",
                                                              "assess_object_no_block", "assess_block")}
        put("supportCardsFull", int(cards["assess_support"]))
        from src.score import GT
        for k, v in GT["acceptability"]["counts"].items():   # human cards, n = 10 (workshop records)
            put("human" + "".join(w.capitalize() for w in k.split("_")) + "Cards", v)
        put("reservationsFull", f"{cards['assess_support_with_reservations'] / sum(cards.values()) * 100:.0f}\\%")

    # Exploratory (not pre-registered): share of survey answers that changed
    # between baseline and endline, per setting (src/exploratory.py).
    expl_path = OUT / "exploratory_by_model.csv"
    if expl_path.exists():
        expl = {(r["model"], r["protocol"]): r for r in _read(expl_path)}
        for key, model, protocol, _, _ in SETTINGS:
            if (model, protocol) in expl:
                put(f"changed{key}", f"{float(expl[(model, protocol)]['share_answers_changed']) * 100:.0f}\\%")

    # Aliases used by the 2-page draft written before the large tier existed:
    # the plain names mean the small tier (laptop, lite protocol).
    m.append("% aliases: small tier")
    for plain, small_key in (("Qwen", "QwenSmall"), ("Gemma", "GemmaSmall"), ("Ministral", "MistralSmall")):
        for stem in ("rules", "rulesRange", "spec", "decision", "modal", "recallGap", "block",
                     "moreSupportive", "moreCritical"):
            m.append(f"\\newcommand{{\\{stem}{plain}}}{{\\{stem}{small_key}}}")
    for stem in ("nWorkshops", "nCalls", "pctAnswered", "nCards", "blockCards"):
        m.append(f"\\newcommand{{\\{stem}}}{{\\{stem}Small}}")
    TAB_DIR.mkdir(parents=True, exist_ok=True)
    (TAB_DIR / "numbers.tex").write_text("\n".join(m) + "\n")


def main() -> None:
    rows = _read(OUT / "scores_by_run.csv")
    summary = _read(OUT / "summary_by_model.csv")
    chance = _read(OUT / "chance_reference.csv")[0]
    small_rows = [r for r in rows if r["model"] in MODEL_LABELS]
    figure(small_rows, chance)                 # supplementary: per-rule agreement grid (small tier)
    from src.figures import full_figure, main_figure, settings_figure
    main_figure(small_rows)                    # small tier: rules and selections per family
    settings_figure(rows, chance)              # all nine settings: validity vs stability
    full_figure(rows)                          # full protocol only: rules and baseline->endline shifts
    table(summary, chance)
    table_full(rows, summary, chance)
    numbers(rows, summary, chance)
    print(f"wrote {FIG_DIR.relative_to(ROOT)}/fig_agreement.pdf, {TAB_DIR.relative_to(ROOT)}/table_main.tex "
          f"and numbers.tex")


if __name__ == "__main__":
    main()
