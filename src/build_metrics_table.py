"""
Build inputs/metrics_2021.csv from the paper's 2021 results table.

Source: inputs/source_copies/results_table1.tex (copied from
ews-paper/descriptive_text/results_table1.tex; real-data, aggregate only).

Keeps the enrollment-level columns the rule applier needs (flag rate, recall,
precision) and derives the false-alarm rate (FPR), which the paper does not report:

    prevalence  pi  = precision * flag_rate / recall      (TP/N = recall*pi = precision*flag)
    FPR             = flag_rate * (1 - precision) / (1 - pi)

The derived prevalence should be ~0.218 on every row (same cohort); the script
checks this as a sanity test of the transcription.

Run:  python src/build_metrics_table.py
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "inputs" / "source_copies" / "results_table1.tex"
OUT = ROOT / "inputs" / "metrics_2021.csv"

# Paper display names -> ids used by the rule applier (same ids as ews_code).
MODEL_IDS = {
    "Credits policy": "credits_policy",
    "FasterRisk": "fasterrisk",
    "Logistic regression": "logistic_regression",
    "XGBoost": "xgboost",
    "CatBoost": "catboost",
    "NN": "mlp",
}
FEATURE_SET_IDS = {
    "(a) Credits": "a_credits",
    "(b) + Performance": "b_credits_performance",
    "(c) + Enrollment": "c_plus_enrollment",
    "(d) + LMS": "d_plus_lms",
    "(e) + Sensitive": "e_plus_sensitive",
    r"Rule: $\geq$60 ECTS behind": "rule_60_ects",
}


def first_number(cell: str) -> float:
    """'0.623 {\\scriptsize[0.60,\\,0.64]}' -> 0.623"""
    return float(re.match(r"\s*([0-9.]+)", cell).group(1))


def parse_rows(tex: str) -> list[dict]:
    rows, model, fs = [], None, None
    for line in tex.splitlines():
        if "&" not in line or line.lstrip().startswith(r"\textbf{Model}"):
            continue
        cells = [c.strip() for c in line.rstrip(r"\ ").split("&")]
        if len(cells) != 9:
            continue
        name, fs_cell = cells[0], cells[1]
        model = MODEL_IDS.get(name, model) if name else model
        if fs_cell:
            fs = FEATURE_SET_IDS.get(fs_cell)  # None for the experimental used_vars set
        if fs is None:
            continue
        rows.append({
            "model": model,
            "feature_set": fs,
            "flag_rate": first_number(cells[2]),
            "recall": first_number(cells[3]),
            "precision": first_number(cells[4]),
        })
    return rows


def main() -> None:
    rows = parse_rows(SRC.read_text())
    for r in rows:
        pi = r["precision"] * r["flag_rate"] / r["recall"]
        r["prevalence_derived"] = round(pi, 4)
        r["fpr_derived"] = round(r["flag_rate"] * (1 - r["precision"]) / (1 - pi), 4)
        assert 0.20 < pi < 0.235, f"prevalence check failed for {r}"
    expected = 1 + 5 * 5  # credits policy + 5 models x 5 feature sets
    assert len(rows) == expected, f"expected {expected} rows, got {len(rows)}"
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
