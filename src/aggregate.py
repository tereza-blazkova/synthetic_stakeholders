"""
Panel aggregation: per-question medians with the paper's tie rules, answer
counts, and the provisional specification shown in the final assessment.

Rules (paper, main.tex "From survey responses to selection rules"; fixed in
analysis/rule_checklist.md section 2):
  1. Drop not_sure, prefer_not and no_answer.
  2. Rank the remaining answers on the item's ordinal scale (least -> most restrictive).
  3. Odd n: middle answer. Even n: if the two middle answers differ, the one with
     more responses; equal counts -> the more restrictive one.
  4. Nothing left -> "no_answer".
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from src.survey import NO_ANSWER

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {"not_sure", "prefer_not", NO_ANSWER}

GAIN = ["no_threshold", "small", "moderate", "large", "never"]
SENSITIVE_KEYS = ["age", "gender", "nationality", "disability", "race_ethnicity", "first_gen", "financial_aid"]

# Least -> most restrictive. Only gain scales have a restrictive direction in the
# paper; the others are conventions fixed in the checklist (matter only on ties).
SCALE_ORDER: dict[str, list[str]] = {
    "Q3.2": GAIN, "Q3.3": GAIN, "Q3.4": GAIN,
    **{f"Q3.5.{k}": GAIN for k in SENSITIVE_KEYS},
    **{f"Q3.6.{k}": ["acceptable_regardless", "only_if_fairness_improves", "never"] for k in SENSITIVE_KEYS},
    **{f"Q4.1.{k}": GAIN for k in ["high", "moderate", "low", "very_low"]},
    "Q5.1": ["loss_10", "loss_5", "loss_1_3", "no_decrease"],
    "Q5.2": ["equal_recall", "both", "equal_fpr"],
    "Q6.2": ["continuously", "twice_year", "once_year"],
    "Q7.1": ["many", "slightly_many", "balance", "slightly_fewer", "fewer"],
    "Q7.2": ["many", "slightly_many", "balance", "slightly_fewer", "fewer"],
    "Q9.1": ["not_at_all", "occasionally", "half", "often", "always"],
    "Q10.1": ["not_at_all", "slightly", "moderately", "substantially", "very_substantially"],
    "Q10.2": ["more_supportive", "slightly_more_supportive", "unchanged",
              "slightly_more_critical", "more_critical"],
}

# Items shown in the plenary (anonymous counts) and in the specification: the
# questions the paper's final assessment was based on (Q3-Q5).
SPEC_ITEMS = (["Q3.2", "Q3.3", "Q3.4"] + [f"Q3.5.{k}" for k in SENSITIVE_KEYS]
              + [f"Q3.6.{k}" for k in SENSITIVE_KEYS]
              + [f"Q4.1.{k}" for k in ["high", "moderate", "low", "very_low"]] + ["Q5.1", "Q5.2"])


def panel_median(values: list[str], order: list[str]) -> tuple[str, str | None]:
    """Median category and how a tie was resolved (None, "count" or "conservative")."""
    ranks = sorted(order.index(v) for v in values if v not in EXCLUDED)
    n = len(ranks)
    if n == 0:
        return NO_ANSWER, None
    if n % 2 == 1:
        return order[ranks[n // 2]], None
    lo, hi = ranks[n // 2 - 1], ranks[n // 2]
    if lo == hi:
        return order[lo], None
    c_lo, c_hi = ranks.count(lo), ranks.count(hi)
    if c_lo != c_hi:
        return order[lo if c_lo > c_hi else hi], "count"
    return order[hi], "conservative"


def aggregate(answers_by_agent: dict[str, dict]) -> dict[str, dict]:
    """Median (and tie rule) for every ordinal item; top options for Q6.1."""
    out: dict[str, dict] = {}
    for key, order in SCALE_ORDER.items():
        values = [a[key] for a in answers_by_agent.values() if key in a]
        if not values:
            continue
        med, tie = panel_median(values, order)
        out[key] = {"median": med, "tie": tie, "counts": dict(Counter(values))}
    picks = Counter(x for a in answers_by_agent.values() for x in a.get("Q6.1", []))
    if picks:
        third = sorted(picks.values(), reverse=True)[:3][-1]
        out["Q6.1"] = {"top": sorted(k for k, v in picks.items() if v >= third), "counts": dict(picks)}
    return out


def distribution_text(answers_by_agent: dict[str, dict], survey: dict, keys: list[str] | None = None) -> str:
    """Anonymous answer counts, as shown to the panel. Default: the SPEC_ITEMS
    (lite plenary); the full protocol's tables pass their own block's keys."""
    labels = _short_labels(survey)
    lines = []
    for key in keys or SPEC_ITEMS:
        if key == "Q6.1":                      # multi-select: count each option chosen
            counts = Counter(x for a in answers_by_agent.values() for x in a.get(key, []))
            parts = [f"{opt} {n}" for opt, n in counts.most_common()]
            lines.append(f"  {key} {labels[key]}: " + (", ".join(parts) or "no selections"))
            continue
        counts = Counter(a[key] for a in answers_by_agent.values())
        no_ans = sum(counts.pop(k, 0) for k in EXCLUDED)
        parts = [f"{opt} {counts[opt]}" for opt in SCALE_ORDER[key] if counts.get(opt)]
        if no_ans:
            parts.append(f"no answer {no_ans}")
        lines.append(f"  {key} {labels[key]}: " + ", ".join(parts))
    return "\n".join(lines)


def _short_labels(survey: dict) -> dict[str, str]:
    labels = {"Q3.2": "course performance data", "Q3.3": "admissions and enrolment data",
              "Q3.4": "Absalon online activity data", "Q5.1": "accuracy loss accepted for equal performance",
              "Q5.2": "what should be equal across groups",
              "Q6.1": "most acceptable interventions (up to two each)", "Q6.2": "how often outreach should occur",
              "Q7.1": "how selective, generic email", "Q7.2": "how selective, personalised message"}
    for row in survey["sensitive_attributes"]:
        labels[f"Q3.5.{row['key']}"] = f"{row['label']} (if it improves identification)"
        labels[f"Q3.6.{row['key']}"] = f"{row['label']} (if it only improves fairness)"
    for item in survey["blocks"][1]["items"]:          # Q4 block
        for row in item["rows"]:
            labels[f"Q4.1.{row['key']}"] = row["label"]
    return labels


# ── Provisional specification (final assessment) ──────────────────────────────

_SPEC_PHRASES = {
    "no_threshold": "acceptable even if it does not improve identification",
    "small": "only if it identifies at least about 1-3 more students per 100",
    "moderate": "only if it identifies at least about 5 more students per 100",
    "large": "only if it identifies at least about 10 more students per 100",
    "never": "never acceptable",
    "acceptable_regardless": "acceptable even if it does not improve identification or fairness",
    "only_if_fairness_improves": "only if it improves fairness across student groups",
    "no_decrease": "no decrease in students identified",
    "loss_1_3": "about 1-3 fewer students identified per 100",
    "loss_5": "about 5 fewer students identified per 100",
    "loss_10": "about 10 fewer students identified per 100",
    "equal_recall": "identifying students who would otherwise be overlooked",
    "equal_fpr": "avoiding unnecessary contact with students who are not in difficulty",
    "both": "both goals equally",
    NO_ANSWER: "no group answer (everyone left it open)",
}


def render_specification(medians: dict[str, dict], template_path: Path) -> str:
    """Fill specification_template.md with this panel's endline medians."""
    text = template_path.read_text()
    text = text.split("-->", 1)[1].strip() if text.lstrip().startswith("<!--") else text
    for key in SPEC_ITEMS:
        text = text.replace("{" + key + "}", _SPEC_PHRASES[medians[key]["median"]])
    if "{" in text:
        raise ValueError("unfilled placeholder in specification template")
    return text
