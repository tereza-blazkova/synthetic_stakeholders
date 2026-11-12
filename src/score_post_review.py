"""
Score the post-review runs (analysis/post_review_plan.md, B1-B4). Exploratory; kept
apart from the pre-registered tables. Reads only runs/post_review/ and the reference
setting (runs/full/<model>/run01..run20).

    python -m src.score_post_review      # -> analysis/results/post_review/b*.csv, summary_runs.md

B1  per card condition and family: share of each option (Wilson 95%), and paired with the
    `baseline_replay` control (same agent, same transcript): share of agents who change
    their vote, toward more support or more objection. Also: baseline_replay vs the
    original votes (replay noise).
B2-B4  every finished workshop under runs/post_review/<condition>/full/<model>/runNN is
    scored with the unchanged src.score.score_run and compared with its reference: rules
    matched (mean, bootstrap 95% CI of the difference), human model chosen (k/n, Wilson),
    modal-choice share, vote shares. Pilot runs are excluded.
"""
from __future__ import annotations

import csv
import json
import random
from collections import Counter
from pathlib import Path
from statistics import mean

from src.score import ASSESSMENT, OUT, score_run, wilson

ROOT = Path(__file__).resolve().parents[1]
PR = ROOT / "runs" / "post_review"
OUTDIR = OUT / "post_review"
SUPPORT_RANK = {"support": 0, "support_with_reservations": 1, "object_no_block": 2, "block": 3}
FAMILY = {"qwen3.5": "Qwen", "gemma3": "Gemma", "mistral-small3.2": "Mistral"}
# post-review model -> the reference model it is compared with
REFERENCE = {"qwen3.5:27b-q8_0": "qwen3.5:27b-q4_K_M", "gemma3:27b-it-q8_0": "gemma3:27b-it-q4_K_M",
             "mistral-small3.2:24b-instruct-2506-q8_0": "mistral-small3.2:24b-instruct-2506-q4_K_M",
             "qwen3.5:122b-a10b-q4_K_M": "qwen3.5:27b-q4_K_M",
             "gemma3:27b-it-fp16": "gemma3:27b-it-q4_K_M"}   # post hoc, 2026-11-09


def _fam(model_folder: str) -> str:
    return next(v for k, v in FAMILY.items() if model_folder.startswith(k))


def _write(name: str, rows: list[dict]) -> None:
    if not rows:
        return
    OUTDIR.mkdir(parents=True, exist_ok=True)
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with (OUTDIR / name).open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def _choice(a: dict) -> str:
    c = a.get("choice")
    return c if c in ASSESSMENT else "prefer_not"


def b1() -> list[dict]:
    root = PR / "card"
    if not root.exists():
        return []
    votes: dict = {}          # (cond, family) -> {(run, agent): choice}
    for f in root.glob("*/*/run*/assessment.json"):
        cond, model, run = f.parts[-4], f.parts[-3], f.parts[-2]
        for agent, a in json.loads(f.read_text()).items():
            votes.setdefault((cond, _fam(model)), {})[(model, run, agent)] = _choice(a)
    # original votes of the source runs, for the replay-noise check
    orig = {}
    for (_, fam), d in votes.items():
        for (model, run, agent) in d:
            if (model, run) not in orig:
                src = ROOT / "runs" / "full" / model / run / "assessment.json"
                orig[(model, run)] = {k: _choice(v) for k, v in json.loads(src.read_text()).items()}
    rows = []
    fams = sorted({f for _, f in votes})
    for fam in fams + ["pooled"]:
        conds = sorted({c for c, _ in votes})
        for cond in conds:
            d = {k: v for (c, f), dd in votes.items() if c == cond and (f == fam or fam == "pooled")
                 for k, v in dd.items()}
            ctrl = {k: v for (c, f), dd in votes.items() if c == "baseline_replay" and (f == fam or fam == "pooled")
                    for k, v in dd.items()}
            n = len(d)
            if not n:
                continue
            cnt = Counter(d.values())
            row = {"family": fam, "condition": cond, "n_cards": n,
                   "n_runs": len({(m, r) for m, r, _ in d})}
            for o in ASSESSMENT:
                lo, hi = wilson(cnt[o], n)
                row[f"{o}_share"], row[f"{o}_ci"] = round(cnt[o] / n, 3), f"[{lo}, {hi}]"
            paired = [k for k in d if k in ctrl]
            ch = [SUPPORT_RANK.get(d[k], 9) - SUPPORT_RANK.get(ctrl[k], 9) for k in paired
                  if d[k] in SUPPORT_RANK and ctrl[k] in SUPPORT_RANK]
            row["paired_n"] = len(ch)
            row["paired_changed_share"] = round(sum(c != 0 for c in ch) / len(ch), 3) if ch else None
            row["paired_more_objection_share"] = round(sum(c > 0 for c in ch) / len(ch), 3) if ch else None
            row["paired_more_support_share"] = round(sum(c < 0 for c in ch) / len(ch), 3) if ch else None
            same_orig = [d[k] == orig[(k[0], k[1])].get(k[2]) for k in d]
            row["same_as_original_vote_share"] = round(mean(same_orig), 3)
            rows.append(row)
    _write("b1_card_conditions.csv", rows)
    return rows


def _boot_diff(xs: list[float], ys: list[float], n: int = 10_000, seed: int = 1) -> tuple[float, float]:
    rng = random.Random(seed)
    ds = sorted(mean(rng.choices(xs, k=len(xs))) - mean(rng.choices(ys, k=len(ys))) for _ in range(n))
    return round(ds[int(0.025 * n)], 2), round(ds[int(0.975 * n) - 1], 2)


def _summ(rows: list[dict]) -> dict:
    n = len(rows)
    k = sum(bool(r["decision_match"]) for r in rows)
    modal, m = Counter(r["endline_selected"] for r in rows).most_common(1)[0]
    cards = Counter()
    for r in rows:
        for o in ASSESSMENT:
            cards[o] += r[f"assess_{o}"]
    tot = sum(cards.values())
    return {"n_runs": n, "rules_mean": round(mean(r["R_coverage"] for r in rows), 2),
            "human_model": f"{k}/{n}", "human_model_ci": str(wilson(k, n)),
            "modal_choice": modal, "modal_share": f"{m}/{n}",
            "reservations_share": round(cards["support_with_reservations"] / tot, 3),
            "block_cards": cards["block"], "object_cards": cards["object_no_block"]}


def b234() -> list[dict]:
    ref_rows: dict = {}
    out = []
    for cond_dir in sorted(p for p in PR.iterdir() if p.is_dir() and p.name not in ("card", "_logs")):
        for model_dir in sorted((cond_dir / "full").glob("*")):
            runs = sorted(d for d in model_dir.glob("run*") if (d / "run_meta.json").exists())
            if not runs:
                continue
            rows = [score_run(d) for d in runs]
            model = rows[0]["model"]
            ref_model = REFERENCE.get(model, model)
            ref_folder = ref_model.replace(":", "_")
            if ref_folder not in ref_rows:
                ref_rows[ref_folder] = {d.name: score_run(d) for d in (ROOT / "runs" / "full" / ref_folder).glob("run*")
                                        if (d / "run_meta.json").exists()}
            ref_all = list(ref_rows[ref_folder].values())
            ref_same = [ref_rows[ref_folder][r["run"]] for r in rows if r["run"] in ref_rows[ref_folder]]
            lo, hi = _boot_diff([r["R_coverage"] for r in rows], [r["R_coverage"] for r in ref_all])
            out.append({"condition": cond_dir.name, "model": model, "reference_model": ref_model, **_summ(rows),
                        "ref_rules_mean_all20": round(mean(r["R_coverage"] for r in ref_all), 2),
                        "ref_rules_mean_same_seeds": round(mean(r["R_coverage"] for r in ref_same), 2) if ref_same else None,
                        "diff_rules_vs_ref": round(mean(r["R_coverage"] for r in rows) - mean(r["R_coverage"] for r in ref_all), 2),
                        "diff_ci": f"[{lo}, {hi}]", "ref_reservations_share": _summ(ref_all)["reservations_share"],
                        "ref_human_model": _summ(ref_all)["human_model"]})
    _write("b234_runs.csv", out)
    return out


def main() -> None:
    r1, r2 = b1(), b234()
    lines = ["# Post-review runs (B1-B4): exploratory, scored by `src/score_post_review.py`", ""]
    if r1:
        lines += ["## B1 card format (replay of the final assessment only)", "",
                  "| Family | Condition | runs | cards | with reservations [95% CI] | object | block | support "
                  "| changed vs control | same as original |", "|---|---|---|---|---|---|---|---|---|---|"]
        for r in r1:
            lines.append(f"| {r['family']} | {r['condition']} | {r['n_runs']} | {r['n_cards']} "
                         f"| {r['support_with_reservations_share']:.0%} {r['support_with_reservations_ci']} "
                         f"| {r['object_no_block_share']:.0%} | {r['block_share']:.0%} | {r['support_share']:.0%} "
                         f"| {'' if r['paired_changed_share'] is None else format(r['paired_changed_share'], '.0%')} "
                         f"| {r['same_as_original_vote_share']:.0%} |")
    if r2:
        lines += ["", "## B2-B4 full reruns vs reference (large tier, full protocol)", "",
                  "| Condition | Model | runs | rules matched (ref) | diff [95% CI] | human model (ref) | modal share "
                  "| with reservations (ref) |", "|---|---|---|---|---|---|---|---|"]
        for r in r2:
            lines.append(f"| {r['condition']} | {r['model']} | {r['n_runs']} | {r['rules_mean']} ({r['ref_rules_mean_all20']}) "
                         f"| {r['diff_rules_vs_ref']} {r['diff_ci']} | {r['human_model']} ({r['ref_human_model']}) "
                         f"| {r['modal_share']} | {r['reservations_share']:.0%} ({r['ref_reservations_share']:.0%}) |")
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / "summary_runs.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
