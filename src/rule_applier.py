"""
Apply a panel's selection rules to the candidate-model metrics and select a model.

A faithful port of select_grid_config() from ews_code/src/workshop_rules.py
(copy: inputs/source_copies/workshop_rules_REFERENCE_ONLY.py), which implements
main.tex "Workshop-grounded model selection":

- Data rule, per model: walk the cumulative ladder a -> b -> c -> d -> e on that
  model's own recalls; each step must gain at least its threshold over the
  previous step; stop at the first rejection. "never" blocks the step and all
  later ones.
- Explainability rule, per feature set: start at the credits policy (very high);
  step down the levels; accept a level if its best model gains at least the sum of
  the thresholds of every level between the held model and it. A rejection does
  not stop the walk. Within a tier (low: XGBoost, CatBoost), every model that
  clears the same demand is accepted.
- A (model, feature set) passes if both rules pass; the passing combination with
  the highest recall is selected. If none passes: the most explainable ML model on
  credits only.

Only addition (pre-registered in analysis/rule_checklist.md section 5): when LMS is
not blocked, the sensitive step (e) needs a price; it is the most restrictive of
the panel's Q3.5 medians for age, gender and nationality (as BASELINE_RULES does).
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METRICS_PATH = ROOT / "inputs" / "metrics_2021.csv"

GAIN_PP = {"no_threshold": 0.0, "small": 0.01, "moderate": 0.05, "large": 0.10, "never": None}
_GAIN_ORDER = ["no_threshold", "small", "moderate", "large", "never"]

FS_ORDER = ["a_credits", "b_credits_performance", "c_plus_enrollment", "d_plus_lms", "e_plus_sensitive"]
EXPL_GROUPS = [("very_high", ["credits_policy"]), ("high", ["fasterrisk"]),
               ("moderate", ["logistic_regression"]), ("low", ["xgboost", "catboost"]),
               ("very_low", ["mlp"])]
ROUND = 6   # metrics have 3 decimals; round differences so 0.05 is not 0.0499999


@dataclass
class RuleSet:
    """Recall gain (fraction) required per step; None = never acceptable."""
    fs_gain: dict[str, float | None]      # keyed by the feature set being added
    expl_gain: dict[str, float | None]    # keyed by explainability level

    @property
    def fs_ladder(self) -> list[tuple[str, str | None, float | None]]:
        ladder = [(FS_ORDER[0], None, None)]
        for prev, fs in zip(FS_ORDER, FS_ORDER[1:]):
            thr = self.fs_gain.get(fs)
            if thr is None:
                break
            ladder.append((fs, prev, thr))
        return ladder

    @property
    def expl_groups(self) -> list[tuple[str, list[str]]]:
        groups = [EXPL_GROUPS[0]]
        for level, models in EXPL_GROUPS[1:]:
            if self.expl_gain.get(level) is None:
                break
            groups.append((level, models))
        return groups

    def expl_gain_between(self, held: str, target: str) -> float:
        order = [lvl for lvl, _ in self.expl_groups]
        i, j = order.index(held), order.index(target)
        return round(sum(self.expl_gain[lvl] for lvl in order[i + 1:j + 1]), 10)


def ruleset_from_medians(medians: dict[str, str]) -> RuleSet:
    """Build the rule set from a panel's medians (keys as in the survey: Q3.2, Q4.1.low, ...).

    A no_answer median for a selection item is treated as "never" (no consent given).
    """
    def g(key: str) -> float | None:
        m = medians.get(key, "no_answer")
        return GAIN_PP.get(m) if m in GAIN_PP else None

    sens = [medians.get(f"Q3.5.{k}", "no_answer") for k in ("age", "gender", "nationality")]
    sens_gain = (None if any(s not in GAIN_PP or s == "never" for s in sens)
                 else GAIN_PP[max(sens, key=_GAIN_ORDER.index)])
    return RuleSet(
        fs_gain={"b_credits_performance": g("Q3.2"), "c_plus_enrollment": g("Q3.3"),
                 "d_plus_lms": g("Q3.4"), "e_plus_sensitive": sens_gain},
        expl_gain={"high": g("Q4.1.high"), "moderate": g("Q4.1.moderate"),
                   "low": g("Q4.1.low"), "very_low": g("Q4.1.very_low")},
    )


def load_metrics(path: Path = METRICS_PATH) -> dict[tuple[str, str], dict]:
    with path.open() as f:
        return {(r["model"], r["feature_set"]): {k: float(r[k]) for k in ("recall", "precision", "fpr_derived")}
                for r in csv.DictReader(f)}


def _recall(metrics: dict, model: str, fs: str) -> float | None:
    if model == "credits_policy":
        return metrics[("credits_policy", "rule_60_ects")]["recall"]
    row = metrics.get((model, fs))
    return row["recall"] if row else None


def data_permissible(metrics: dict, model: str, rules: RuleSet) -> list[str]:
    ok = []
    for fs, prev, thr in rules.fs_ladder:
        if prev is None:
            ok.append(fs)
            continue
        r, r_prev = _recall(metrics, model, fs), _recall(metrics, model, prev)
        if r is None or r_prev is None or round(r - r_prev, ROUND) < thr:
            break
        ok.append(fs)
    return ok


def expl_accepted(metrics: dict, fs: str, rules: RuleSet) -> set[str]:
    groups = rules.expl_groups
    held_level, held_model = groups[0][0], groups[0][1][0]
    held_recall = _recall(metrics, held_model, fs)
    accepted = {held_model}
    for level, models in groups[1:]:
        recalls = {m: _recall(metrics, m, fs) for m in models if _recall(metrics, m, fs) is not None}
        if not recalls:
            continue
        thr = rules.expl_gain_between(held_level, level)
        best = max(recalls, key=recalls.get)
        if round(recalls[best] - held_recall, ROUND) >= thr:
            accepted |= {m for m, r in recalls.items() if round(r - held_recall, ROUND) >= thr}
            held_level, held_model, held_recall = level, best, recalls[best]
    return accepted


def select(metrics: dict, rules: RuleSet) -> dict:
    """Run the grid selection. Returns the choice and the per-cell verdicts."""
    ml_models = [m for _, ms in rules.expl_groups for m in ms if m != "credits_policy"]
    candidate_fs = [fs for fs, _, _ in rules.fs_ladder]
    data_ok = {m: set(data_permissible(metrics, m, rules)) for m in ml_models}
    expl_ok = {fs: expl_accepted(metrics, fs, rules) for fs in candidate_fs}
    cells = []
    for fs in candidate_fs:
        for m in ml_models:
            r = _recall(metrics, m, fs)
            if r is None:
                continue
            cells.append({"model": m, "feature_set": fs, "recall": r,
                          "data_ok": fs in data_ok[m], "expl_ok": m in expl_ok[fs],
                          "permissible": fs in data_ok[m] and m in expl_ok[fs]})
    passing = [c for c in cells if c["permissible"]]
    if passing:
        best = max(passing, key=lambda c: c["recall"])
        choice, fallback = (best["model"], best["feature_set"]), False
    elif ml_models:
        first = next(m for m in ml_models if _recall(metrics, m, candidate_fs[0]) is not None)
        choice, fallback = (first, candidate_fs[0]), True
    else:
        # Every ML model is blocked (high explainability "never"): keep the status
        # quo. Not covered by the paper; pre-registered in rule_checklist.md section 5.
        choice, fallback = ("credits_policy", "rule_60_ects"), "no_ml"
    row = metrics[choice]
    return {"model": choice[0], "feature_set": choice[1], "fallback": fallback,
            "recall": row["recall"], "fpr": row["fpr_derived"], "precision": row["precision"],
            "blocked_feature_sets": [fs for fs in FS_ORDER if fs not in candidate_fs],
            "blocked_models": [m for _, ms in EXPL_GROUPS for m in ms
                               if m not in ml_models and m != "credits_policy"],
            "cells": cells}
