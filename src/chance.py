"""
Chance reference: how well does a panel of 12 uniformly random respondents agree
with the human workshop? Gives the floor against which agreement scores are read.

Each simulated respondent picks uniformly among every option of each item,
including no_answer (the same distribution as FakeBackend). Baseline and endline
are drawn independently.

    python -m src.chance            # 2000 panels -> analysis/results/chance_reference.csv
"""
from __future__ import annotations

import csv
import random
from collections import Counter
from statistics import mean

from src import aggregate, survey as sv
from src.rule_applier import load_metrics, ruleset_from_medians, select
from src.score import HUMAN, OUT, R_ITEMS, S_ITEMS, T_ITEMS, human_value

N_PANELS = 2000


def random_panel(flds: list[sv.Field], rng: random.Random) -> dict[str, dict]:
    return {f"P{i}": {f.key: rng.choice(f.options) for f in flds if f.kind == "single"}
            for i in range(12)}


def main() -> None:
    rng = random.Random(20261016)
    flds = sv.fields(sv.load_survey(), "endline", skip=["Q10.5"])
    metrics = load_metrics()
    r_cov, s_cov, t_cov, picks, item_hits = [], [], [], Counter(), Counter()
    for _ in range(N_PANELS):
        med = {k: v["median"] for k, v in aggregate.aggregate(random_panel(flds, rng)).items() if "median" in v}
        r_cov.append(sum(med.get(k) == human_value(k) for k in R_ITEMS))
        item_hits.update(k for k in R_ITEMS if med.get(k) == human_value(k))
        s_cov.append(sum(med.get(k) == human_value(k) for k in S_ITEMS))
        t_cov.append(sum(med.get(k) == human_value(k) for k in T_ITEMS))
        s = select(metrics, ruleset_from_medians(med))
        picks[(s["model"], s["feature_set"])] += 1
    match = picks[(HUMAN["model"], HUMAN["feature_set"])] / N_PANELS
    row = {"n_panels": N_PANELS, "R_coverage_mean": round(mean(r_cov), 2), "R_of": len(R_ITEMS),
           "S_coverage_mean": round(mean(s_cov), 2), "S_of": len(S_ITEMS),
           "T_coverage_mean": round(mean(t_cov), 2), "T_of": len(T_ITEMS),
           "decision_match_rate": round(match, 3),
           "most_common_pick": "+".join(picks.most_common(1)[0][0]),
           **{f"item_{k}": round(item_hits[k] / N_PANELS, 3) for k in R_ITEMS}}
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "chance_reference.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        w.writeheader()
        w.writerow(row)
    print(row)


if __name__ == "__main__":
    main()
