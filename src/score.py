"""
Score runs against the pre-registered checklist (analysis/rule_checklist.md).

Everything is rebuilt from each run's calls.jsonl (the raw log), not from the
summary files, so any run can be re-scored without new model calls.

    python -m src.score                 # all runs under runs/ except _fake and _smoke
    python -m src.score --include-test  # also score runs/_fake (for testing this script)

Writes analysis/results/scores_by_run.csv and analysis/results/summary_by_model.csv.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path

import yaml

from src import aggregate
from src.rule_applier import load_metrics, ruleset_from_medians, select

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis" / "results"
GT = yaml.safe_load((ROOT / "inputs" / "human_ground_truth.yaml").read_text())
HUMAN = {"model": "logistic_regression", "feature_set": "b_credits_performance",
         "recall": GT["selected"]["recall"], "fpr": GT["selected"]["fpr_derived"]}

R_ITEMS = ["Q3.2", "Q3.3", "Q3.4", "Q4.1.high", "Q4.1.moderate", "Q4.1.low", "Q4.1.very_low"]
S_ITEMS = ([f"Q3.5.{k}" for k in aggregate.SENSITIVE_KEYS] + [f"Q3.6.{k}" for k in aggregate.SENSITIVE_KEYS]
           + ["Q5.1", "Q5.2"])
T_ITEMS = ["Q6.2", "Q7.1", "Q7.2", "Q9.1"]
ASSESSMENT = ["support", "support_with_reservations", "object_no_block", "block", "prefer_not"]


def human_value(key: str, administration: str = "endline") -> str:
    for qid, v in GT["questions"].items():
        k = qid.split("_")[0]
        if k in ("Q3.5", "Q3.6", "Q4.1"):
            k += "." + qid.split("_", 1)[1]
        if k == key:
            return v[administration]
    raise KeyError(key)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(max(0.0, c - h), 3) + 0.0, round(min(1.0, c + h), 3))   # + 0.0 turns -0.0 into 0.0


def load_run(run_dir: Path) -> dict:
    """Each agent's answers per phase, rebuilt from calls.jsonl with the same
    lenient parsing and follow-up merging the workshop used (src/survey.py)."""
    from src import survey as sv
    from src.workshop import ASSESSMENT_FIELDS, SCRIPT_PATH
    meta_path = run_dir / "run_meta.json"
    protocol = json.loads(meta_path.read_text()).get("protocol", "lite") if meta_path.exists() else "lite"
    # lite skips Q10.5 (its options refer to tables); the full protocol asks it
    skip = yaml.safe_load(SCRIPT_PATH.read_text())["endline_skip_items"] if protocol == "lite" else []
    survey = sv.load_survey()
    flds = {"baseline": sv.fields(survey, "baseline"), "endline": sv.fields(survey, "endline", skip=skip),
            "assessment": ASSESSMENT_FIELDS}
    replies: dict[tuple[str, str], list[str]] = {}
    out: dict = {"baseline": {}, "endline": {}, "assessment": {}, "model": None, "protocol": protocol,
                 "unanswered": 0, "followup_calls": 0, "n_calls": 0}
    for line in (run_dir / "calls.jsonl").open():
        c = json.loads(line)
        out["model"] = c["model"]
        out["n_calls"] += 1
        out["followup_calls"] += c["phase"] != "plenary" and c.get("attempt", 1) > 1
        replies.setdefault((c["phase"], c["agent"]), []).append(c["response"])
    for (phase, agent), texts in replies.items():
        if phase in flds:
            out[phase][agent], missing = sv.merge_replies(texts, flds[phase])
            out["unanswered"] += len(missing) if phase != "assessment" else 0
    return out


def _rank(key: str, value: str) -> int | None:
    order = aggregate.SCALE_ORDER[key]
    return order.index(value) if value in order else None


def score_run(run_dir: Path) -> dict:
    run = load_run(run_dir)
    agg = {adm: aggregate.aggregate(run[adm]) for adm in ("baseline", "endline")}
    med = {adm: {k: v["median"] for k, v in a.items() if "median" in v} for adm, a in agg.items()}
    metrics = load_metrics()
    sel = {adm: select(metrics, ruleset_from_medians(med[adm])) for adm in med}
    row: dict = {"model": run["model"], "protocol": run["protocol"], "run": run_dir.name, "n_calls": run["n_calls"],
                 "followup_calls": run["followup_calls"],
                 "items_unanswered_after_followups": run["unanswered"]}

    for key in R_ITEMS + S_ITEMS + T_ITEMS:          # exact match and distance, endline
        h, p = _rank(key, human_value(key)), _rank(key, med["endline"].get(key, "no_answer"))
        row[f"{key}"] = med["endline"].get(key)
        row[f"{key}_dist"] = abs(h - p) if p is not None else None
    exact = lambda items: sum(med["endline"].get(k) == human_value(k) for k in items)
    within1 = lambda items: sum((row[f"{k}_dist"] is not None and row[f"{k}_dist"] <= 1) for k in items)
    row.update({"R_coverage": exact(R_ITEMS), "R_within1": within1(R_ITEMS),
                "S_coverage": exact(S_ITEMS), "T_coverage": exact(T_ITEMS)})

    top = set(agg["endline"].get("Q6.1", {}).get("top", []))
    human_top = set(GT["Q6.1_top_interventions"])
    row["T5_jaccard"] = round(len(top & human_top) / len(top | human_top), 3) if top | human_top else None

    e = med["endline"]
    gain = aggregate.GAIN
    row["D1_lms_blocked"] = e.get("Q3.4") == "never"
    row["D2_very_low_blocked"] = e.get("Q4.1.very_low") == "never"
    row["D3_perf_cheaper_than_enrol"] = (e.get("Q3.2") in gain and e.get("Q3.3") in gain
                                         and gain.index(e["Q3.2"]) < gain.index(e["Q3.3"]))
    row["D4_sensitive_at_least_moderate"] = all(
        e.get(f"Q3.5.{k}") in ("moderate", "large", "never") for k in aggregate.SENSITIVE_KEYS)
    row["D_score"] = sum(row[k] for k in row if k.startswith("D") and k[1].isdigit())

    for adm in ("baseline", "endline"):
        s = sel[adm]
        row[f"{adm}_selected"] = f"{s['model']}+{s['feature_set']}"
        row[f"{adm}_fallback"] = s["fallback"]
    s = sel["endline"]
    row["decision_match"] = (s["model"], s["feature_set"]) == (HUMAN["model"], HUMAN["feature_set"])
    row["model_match"] = s["model"] == HUMAN["model"]
    row["feature_set_match"] = s["feature_set"] == HUMAN["feature_set"]
    row["recall_gap"] = round(s["recall"] - HUMAN["recall"], 4)
    row["fpr_gap"] = round(s["fpr"] - HUMAN["fpr"], 4)

    # Deliberation shift: direction per item vs the human direction.
    same = n = 0
    for key in R_ITEMS + S_ITEMS + T_ITEMS:
        hb, he = _rank(key, human_value(key, "baseline")), _rank(key, human_value(key))
        pb, pe = _rank(key, med["baseline"].get(key, "")), _rank(key, med["endline"].get(key, ""))
        if None in (hb, he, pb, pe):
            continue
        n += 1
        same += (pe > pb) - (pe < pb) == (he > hb) - (he < hb)
    row["shift_direction_agreement"] = round(same / n, 3) if n else None
    row["items_shifted"] = sum(med["baseline"].get(k) != med["endline"].get(k) for k in R_ITEMS + S_ITEMS)
    # Baseline -> endline movement of the panel medians on the 23 assessed items, by
    # direction (rank up = stricter), and agreement with the humans' own movement.
    up = down = rules_moved = 0
    human_moved = agree = 0
    for key in R_ITEMS + S_ITEMS:
        pb, pe = _rank(key, med["baseline"].get(key, "")), _rank(key, med["endline"].get(key, ""))
        if pb is None or pe is None:
            continue
        d = (pe > pb) - (pe < pb)
        up += d > 0
        down += d < 0
        rules_moved += key in R_ITEMS and d != 0
        hb, he = _rank(key, human_value(key, "baseline")), _rank(key, human_value(key))
        hd = (he > hb) - (he < hb)
        if hd != 0:
            human_moved += 1
            agree += d == hd
    row["shift_stricter"], row["shift_permissive"], row["rules_shifted"] = up, down, rules_moved
    row["shift_same_as_humans"] = round(agree / human_moved, 3) if human_moved else None

    choices = Counter(a.get("choice") if a.get("choice") in ASSESSMENT else "prefer_not"
                      for a in run["assessment"].values())
    for c in ASSESSMENT:
        row[f"assess_{c}"] = choices.get(c, 0)
    row["assess_support_majority"] = choices.get("support", 0) > len(run["assessment"]) / 2
    row["assess_any_block"] = choices.get("block", 0) > 0
    q10 = Counter(a.get("Q10.2") for a in run["endline"].values())
    row["q10_more_supportive"] = q10["more_supportive"] + q10["slightly_more_supportive"]
    row["q10_more_critical"] = q10["more_critical"] + q10["slightly_more_critical"]
    return row


def summarise(rows: list[dict]) -> list[dict]:
    out = []
    for model, protocol in sorted({(r["model"], r["protocol"]) for r in rows}):
        rs = [r for r in rows if r["model"] == model and r["protocol"] == protocol]
        n = len(rs)
        picks = Counter(r["endline_selected"] for r in rs)
        modal, k_modal = picks.most_common(1)[0]
        k_match = sum(r["decision_match"] for r in rs)
        cov = [r["R_coverage"] for r in rs]
        mean = sum(cov) / n
        out.append({
            "model": model, "protocol": protocol, "n_runs": n,
            "decision_match": f"{k_match}/{n}", "decision_match_ci": wilson(k_match, n),
            "modal_choice": modal, "modal_share": f"{k_modal}/{n}", "modal_share_ci": wilson(k_modal, n),
            "R_coverage_mean": round(mean, 2), "R_coverage_range": f"{min(cov)}-{max(cov)}",
            "R_coverage_sd": round((sum((c - mean) ** 2 for c in cov) / max(n - 1, 1)) ** 0.5, 2),
            "S_coverage_mean": round(sum(r["S_coverage"] for r in rs) / n, 2),
            "mean_recall_gap": round(sum(r["recall_gap"] for r in rs) / n, 4),
            "mean_fpr_gap": round(sum(r["fpr_gap"] for r in rs) / n, 4),
            "shift_direction_agreement_mean": round(
                sum(r["shift_direction_agreement"] or 0 for r in rs) / n, 3),
            "runs_support_majority": f"{sum(r['assess_support_majority'] for r in rs)}/{n}",
            "mean_followup_calls": round(sum(r["followup_calls"] for r in rs) / n, 1),
            "mean_items_unanswered": round(sum(r["items_unanswered_after_followups"] for r in rs) / n, 1),
            "runs_any_block": f"{sum(r['assess_any_block'] for r in rs)}/{n}",
            **{f"item_agreement_{k}": round(Counter(r[k] for r in rs).most_common(1)[0][1] / n, 2)
               for k in R_ITEMS},
        })
    return out


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--include-test", action="store_true")
    args = p.parse_args()
    def wanted(parts: tuple) -> bool:    # _fake folders only with --include-test; never _smoke etc.
        if parts[0] == "post_review":    # post-review runs are scored apart (analysis/post_review_plan.md)
            return False
        under = [p for p in parts[:-2] if p.startswith("_")]
        return under == ["_fake"] if args.include_test else not under
    run_dirs = sorted(d.parent for d in (ROOT / "runs").rglob("calls.jsonl")
                      if wanted(d.relative_to(ROOT / "runs").parts) and d.parent.name != "pilot"
                      and (d.parent / "run_meta.json").exists())   # finished workshops only
    if not run_dirs:
        raise SystemExit("no runs to score (pilot runs are excluded; use --include-test for runs/_fake)")
    rows = [score_run(d) for d in run_dirs]
    _write(OUT / "scores_by_run.csv", rows)
    _write(OUT / "summary_by_model.csv", summarise(rows))
    print(f"scored {len(rows)} runs -> {OUT.relative_to(ROOT)}/")
    for s in summarise(rows):
        print(f"  {s['model']} [{s['protocol']}]: decision match {s['decision_match']}, modal {s['modal_choice']} "
              f"({s['modal_share']}), R coverage {s['R_coverage_mean']} of 7")


if __name__ == "__main__":
    main()
