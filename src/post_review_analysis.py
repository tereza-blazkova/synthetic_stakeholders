"""
Post-review re-scoring of the reference runs (analysis/post_review_plan.md, A1, A3-A5).
No model calls. Reference setting: large tier, full protocol, runs/full/<model>/run01..run20.

    python -m src.post_review_analysis    # -> analysis/results/post_review/*.csv and summary.md

A1  random-panel floor: distribution of rules matched (same generator and seed as src/chance.py)
A3  within-family spread of rules matched; distinct (rule configuration, selected model) pairs
A4  rules matched at baseline vs endline; per-item movement vs the humans' movement
A5  each agent's vote vs how many of the 7 rules the panel set as the agent itself answered
A2's sensitivity (within one ladder step) is R_within1, already in scores_by_run.csv.
"""
from __future__ import annotations

import csv
import random
from collections import Counter
from pathlib import Path
from statistics import mean, pstdev

from src import aggregate, survey as sv
from src.chance import N_PANELS, random_panel
from src.rule_applier import load_metrics, ruleset_from_medians, select
from src.score import ASSESSMENT, HUMAN, OUT, R_ITEMS, S_ITEMS, _rank, human_value, load_run, score_run

ROOT = Path(__file__).resolve().parents[1]
OUTDIR = OUT / "post_review"
FAMILY = {"qwen3.5": "Qwen", "gemma3": "Gemma", "mistral-small3.2": "Mistral"}


def _family(model: str) -> str:
    return FAMILY[model.split(":")[0]]


def bootstrap_ci(xs: list[float], n: int = 10_000, seed: int = 1) -> tuple[float, float]:
    rng = random.Random(seed)
    ms = sorted(mean(rng.choices(xs, k=len(xs))) for _ in range(n))
    return round(ms[int(0.025 * n)], 2), round(ms[int(0.975 * n) - 1], 2)


def _write(name: str, rows: list[dict]) -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    with (OUTDIR / name).open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def a1_random_floor() -> dict:
    rng = random.Random(20261016)                       # identical to src/chance.py
    flds = sv.fields(sv.load_survey(), "endline", skip=["Q10.5"])
    metrics = load_metrics()
    r, hits = [], 0
    for _ in range(N_PANELS):
        med = {k: v["median"] for k, v in aggregate.aggregate(random_panel(flds, rng)).items() if "median" in v}
        r.append(sum(med.get(k) == human_value(k) for k in R_ITEMS))
        s = select(metrics, ruleset_from_medians(med))
        hits += (s["model"], s["feature_set"]) == (HUMAN["model"], HUMAN["feature_set"])
    r.sort()
    dist = Counter(r)
    return {"n_panels": N_PANELS, "rules_mean": round(mean(r), 2), "rules_p2.5": r[int(0.025 * N_PANELS)],
            "rules_p97.5": r[int(0.975 * N_PANELS) - 1], "decision_match_rate": round(hits / N_PANELS, 3),
            **{f"share_{k}_of_7": round(dist[k] / N_PANELS, 3) for k in range(8)}}


# A6: keyword lists fixed in analysis/post_review_plan.md before any text was read.
# Matched case-insensitively as substrings (so "surveil" matches "surveillance").
A6_THEMES = {
    "purpose": ["why predict", "should the university", "purpose"],
    "surveillance_privacy": ["surveil", "privacy", "monitor"],
    "disagreement": ["disagree", "object", "oppose"],
    "stigma_harm": ["stigma", "label", "flagged"],
}


def a6_content(run_dirs: list[Path]) -> tuple[list[dict], list[dict]]:
    """Share of runs / agents that raise each theme at least once (spoken turns, private notes,
    assessment justifications). Agent text only. Also returns every hit for spot-checking."""
    import json
    per_run, hits = [], []
    for d in run_dirs:
        fam = _family(json.loads((d / "run_meta.json").read_text())["model"])
        texts = [(t["agent"], t["phase"], t["text"]) for t in json.loads((d / "transcript.json").read_text())]
        texts += [(a, "assessment", v.get("justification", ""))
                  for a, v in json.loads((d / "assessment.json").read_text()).items()]
        for theme, words in A6_THEMES.items():
            agents = set()
            for agent, phase, text in texts:
                low = text.lower()
                w = next((w for w in words if w in low), None)
                if w:
                    agents.add(agent)
                    i = low.index(w)
                    hits.append({"family": fam, "run": d.name, "theme": theme, "keyword": w, "agent": agent,
                                 "phase": phase, "context": text[max(0, i - 120): i + 120].replace("\n", " ")})
            per_run.append({"family": fam, "run": d.name, "theme": theme, "agents": len(agents)})
    rows = []
    for fam in sorted({r["family"] for r in per_run}):
        for theme in A6_THEMES:
            rs = [r for r in per_run if r["family"] == fam and r["theme"] == theme]
            rows.append({"family": fam, "theme": theme, "share_runs": round(sum(r["agents"] > 0 for r in rs) / len(rs), 2),
                         "mean_agents_per_run_of_12": round(mean(r["agents"] for r in rs), 1)})
    return rows, hits


def main() -> None:
    run_dirs = sorted(d for d in (ROOT / "runs" / "full").glob("*/run*") if (d / "run_meta.json").exists())
    by_fam: dict[str, list] = {}
    a4_items, a5 = [], Counter()
    for d in run_dirs:
        row, run = score_run(d), load_run(d)
        fam = _family(row["model"])
        agg = {adm: aggregate.aggregate(run[adm]) for adm in ("baseline", "endline")}
        med = {adm: {k: v["median"] for k, v in a.items() if "median" in v} for adm, a in agg.items()}
        r_base = sum(med["baseline"].get(k) == human_value(k) for k in R_ITEMS)
        miss_end = [k for k in R_ITEMS if med["endline"].get(k) != human_value(k)]
        miss_both = [k for k in miss_end if med["baseline"].get(k) != human_value(k)]
        config = tuple(med["endline"].get(k) for k in R_ITEMS)
        by_fam.setdefault(fam, []).append({"run": d.name, "R_end": row["R_coverage"], "R_base": r_base,
                                           "miss_end": len(miss_end), "miss_both": len(miss_both),
                                           "config": config, "selected": row["endline_selected"]})
        for k in R_ITEMS + S_ITEMS:
            pb, pe = _rank(k, med["baseline"].get(k, "")), _rank(k, med["endline"].get(k, ""))
            hb, he = _rank(k, human_value(k, "baseline")), _rank(k, human_value(k))
            if None in (pb, pe, hb, he):
                continue
            a4_items.append({"family": fam, "run": d.name, "item": k, "panel_moved": pe != pb,
                             "panel_dir": (pe > pb) - (pe < pb), "human_dir": (he > hb) - (he < hb)})
        for agent, ans in run["endline"].items():
            own = sum(ans.get(k) == med["endline"].get(k) for k in R_ITEMS)
            vote = run["assessment"].get(agent, {}).get("choice")
            a5[(fam, own, vote if vote in ASSESSMENT else "prefer_not")] += 1

    floor = a1_random_floor()
    _write("a1_random_floor.csv", [floor])

    a3 = []
    for fam, rs in sorted(by_fam.items()):
        xs = [r["R_end"] for r in rs]
        lo, hi = bootstrap_ci(xs)
        a3.append({"family": fam, "n_runs": len(rs), "rules_mean": round(mean(xs), 2), "ci_lo": lo, "ci_hi": hi,
                   "sd": round(pstdev(xs), 2), "min": min(xs), "max": max(xs),
                   "distinct_rule_configs": len({r["config"] for r in rs}),
                   "distinct_config_model_pairs": len({(r["config"], r["selected"]) for r in rs}),
                   "distinct_selected_models": len({r["selected"] for r in rs})})
    _write("a3_within_family_spread.csv", a3)

    a4 = []
    for fam, rs in sorted(by_fam.items()):
        items = [x for x in a4_items if x["family"] == fam]
        human_movers = [x for x in items if x["human_dir"] != 0]
        a4.append({"family": fam, "rules_baseline_mean": round(mean(r["R_base"] for r in rs), 2),
                   "rules_endline_mean": round(mean(r["R_end"] for r in rs), 2),
                   "share_endline_mismatch_already_at_baseline":
                       round(sum(r["miss_both"] for r in rs) / max(1, sum(r["miss_end"] for r in rs)), 3),
                   "items_moved_per_run": round(sum(x["panel_moved"] for x in items) / len(rs), 2),
                   "human_moves_repeated_share":
                       round(sum(x["panel_dir"] == x["human_dir"] for x in human_movers) / max(1, len(human_movers)), 3),
                   "panel_moves_opposite_to_humans_share":
                       round(sum(x["panel_dir"] == -x["human_dir"] for x in human_movers) / max(1, len(human_movers)), 3)})
    _write("a4_start_vs_change.csv", a4)

    a5_rows = [{"family": f, "own_rules_matched_by_panel": o, "vote": v, "n_agents": n}
               for (f, o, v), n in sorted(a5.items(), key=lambda x: (x[0][0], x[0][1], ASSESSMENT.index(x[0][2])))]
    _write("a5_vote_vs_own_answers.csv", a5_rows)

    lines = ["# Post-review re-scoring (A1, A3-A5), reference setting: large tier, full protocol",
             "", "Generated by `src/post_review_analysis.py`. Exploratory / post-review.", "",
             f"**A1 random panel** ({floor['n_panels']} panels): rules matched mean {floor['rules_mean']} of 7, "
             f"95% of panels {floor['rules_p2.5']}–{floor['rules_p97.5']}; human model chosen "
             f"{floor['decision_match_rate']:.1%}. Humans' own baseline→endline match: 3 of 7.", "",
             "**A3 within-family spread** (rules matched of 7 over 20 runs)", "",
             "| Family | mean [95% CI] | SD | range | distinct rule configs | distinct selected models |",
             "|---|---|---|---|---|---|"]
    lines += [f"| {r['family']} | {r['rules_mean']} [{r['ci_lo']}, {r['ci_hi']}] | {r['sd']} | {r['min']}–{r['max']} "
              f"| {r['distinct_rule_configs']} | {r['distinct_selected_models']} |" for r in a3]
    lines += ["", "**A4 start vs change**", "",
              "| Family | rules matched at baseline | at endline | endline mismatches already at baseline "
              "| items moved per run (of 23) | human moves repeated |", "|---|---|---|---|---|---|"]
    lines += [f"| {r['family']} | {r['rules_baseline_mean']} | {r['rules_endline_mean']} "
              f"| {r['share_endline_mismatch_already_at_baseline']:.0%} | {r['items_moved_per_run']} "
              f"| {r['human_moves_repeated_share']:.0%} |" for r in a4]
    lines += ["", "**A5 vote vs own answers**: see `a5_vote_vs_own_answers.csv` (agents by family, by how many of "
              "the 7 rules the panel set as the agent itself answered, by vote)."]
    for fam in sorted(by_fam):
        rows = [r for r in a5_rows if r["family"] == fam]
        tot = sum(r["n_agents"] for r in rows)
        low = [r for r in rows if r["own_rules_matched_by_panel"] <= 3]
        res = sum(r["n_agents"] for r in low if r["vote"] == "support_with_reservations")
        lines.append(f"- {fam}: {sum(r['n_agents'] for r in low)} of {tot} agents saw 3 or fewer of their own rules "
                     f"adopted; {res} of them still voted 'support with reservations'.")
    a6, a6_hits = a6_content(run_dirs)
    _write("a6_content_themes.csv", a6)
    _write("a6_content_hits.csv", a6_hits)
    rng = random.Random(6)                              # 20 random hits for Tereza's spot-check
    _write("a6_spotcheck_sample.csv", rng.sample(a6_hits, min(20, len(a6_hits))))
    lines += ["", "**A6 content themes** (keyword lists fixed in the plan; share of runs where at least one agent "
              "raises the theme; mean agents per run of 12). Spot-check sample: `a6_spotcheck_sample.csv`.", "",
              "| Family | " + " | ".join(A6_THEMES) + " |", "|---|" + "---|" * len(A6_THEMES)]
    for fam in sorted({r["family"] for r in a6}):
        cells = [next(r for r in a6 if r["family"] == fam and r["theme"] == t) for t in A6_THEMES]
        lines.append(f"| {fam} | " + " | ".join(f"{c['share_runs']:.0%} ({c['mean_agents_per_run_of_12']})"
                                                 for c in cells) + " |")
    (OUTDIR / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
