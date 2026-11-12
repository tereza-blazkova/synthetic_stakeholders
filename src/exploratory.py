"""
EXPLORATORY analyses (not pre-registered; added 2026-10-20 after the small-tier
results were seen, for the Cooperative AI lens). Report them as exploratory.

All three are computed from the logs (via src.score.load_run), on the 23
assessed ordinal items (7 selection rules + 16 other assessed items), with
not_sure / prefer_not / no_answer excluded, as in the medians.

1. Diversity collapse: within-panel spread of answers at baseline and endline,
   as the mean absolute deviation of the 12 agents' ranks from the panel median
   rank, averaged over items. Negative change = answers converged.
2. Conformity: for every (agent, item) answered at both times, did the endline
   answer move toward the panel's baseline median, away from it, or stay?
3. Speaking-order influence: does the panel's endline median agree more often
   with the FIRST plenary speaker's baseline answer than with the other 11
   agents' baseline answers (their average)? Seeded orders, matched across families.

    python -m src.exploratory      # -> analysis/results/exploratory_{by_run,by_model}.csv
"""
from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

from src import aggregate
from src.score import OUT, R_ITEMS, ROOT, S_ITEMS, load_run

ITEMS = R_ITEMS + S_ITEMS


def _rank(key: str, value) -> int | None:
    order = aggregate.SCALE_ORDER[key]
    return order.index(value) if value in order else None


def _median_rank(ranks: list[int], order: list[str]) -> int | None:
    if not ranks:
        return None
    med, _ = aggregate.panel_median([order[r] for r in ranks], order)
    return order.index(med) if med in order else None


def _first_plenary_speaker(run_dir: Path) -> str | None:
    meta = json.loads((run_dir / "run_meta.json").read_text())
    if "plenary_order" in meta:                                   # lite
        return meta["plenary_order"][0]
    for room, order in meta.get("speaking_orders", {}).items():   # full: first plenary round
        if room.startswith("4_plenary"):
            return order[0]
    return None


def analyse_run(run_dir: Path) -> dict:
    run = load_run(run_dir)
    base, end = run["baseline"], run["endline"]
    agents = sorted(base)
    spread = {"baseline": [], "endline": []}
    toward = away = stay = 0
    first = _first_plenary_speaker(run_dir)
    first_hits = other_hits = n_items = 0
    for key in ITEMS:
        order = aggregate.SCALE_ORDER[key]
        rb = {a: _rank(key, base[a].get(key)) for a in agents}
        re_ = {a: _rank(key, end[a].get(key)) for a in agents}
        for when, r in (("baseline", rb), ("endline", re_)):
            ranks = [x for x in r.values() if x is not None]
            m = _median_rank(ranks, order)
            if m is not None:
                spread[when].append(statistics.mean(abs(x - m) for x in ranks))
        mb = _median_rank([x for x in rb.values() if x is not None], order)
        if mb is not None:
            for a in agents:
                if rb[a] is None or re_[a] is None:
                    continue
                d0, d1 = abs(rb[a] - mb), abs(re_[a] - mb)
                toward += d1 < d0
                away += d1 > d0
                stay += d1 == d0
        me = _median_rank([x for x in re_.values() if x is not None], order)
        if me is not None and first in rb and rb[first] is not None:
            others = [rb[a] == me for a in agents if a != first and rb[a] is not None]
            if others:
                n_items += 1
                first_hits += rb[first] == me
                other_hits += statistics.mean(others)
    moved = toward + away
    return {
        "model": run["model"], "protocol": run["protocol"], "run": run_dir.name,
        "spread_baseline": round(statistics.mean(spread["baseline"]), 3),
        "spread_endline": round(statistics.mean(spread["endline"]), 3),
        "spread_change": round(statistics.mean(spread["endline"]) - statistics.mean(spread["baseline"]), 3),
        "answers_toward_median": toward, "answers_away": away, "answers_unchanged": stay,
        "share_toward_of_moved": round(toward / moved, 3) if moved else None,
        "first_speaker": first,
        "endline_matches_first_speaker": round(first_hits / n_items, 3) if n_items else None,
        "endline_matches_other_speakers": round(other_hits / n_items, 3) if n_items else None,
    }


def main() -> None:
    run_dirs = sorted(d.parent for d in (ROOT / "runs").rglob("run_meta.json")
                      if not any(p.startswith("_") for p in d.relative_to(ROOT / "runs").parts)
                      and d.relative_to(ROOT / "runs").parts[0] != "post_review"   # scored apart
                      and d.parent.name != "pilot")
    rows = [analyse_run(d) for d in run_dirs]
    groups = sorted({(r["model"], r["protocol"]) for r in rows})
    summary = []
    for model, protocol in groups:
        rs = [r for r in rows if (r["model"], r["protocol"]) == (model, protocol)]
        mean = lambda k: round(statistics.mean(r[k] for r in rs if r[k] is not None), 3)
        summary.append({"model": model, "protocol": protocol, "n_runs": len(rs),
                        "spread_baseline": mean("spread_baseline"), "spread_endline": mean("spread_endline"),
                        "spread_change": mean("spread_change"),
                        "share_toward_of_moved": mean("share_toward_of_moved"),
                        "share_answers_changed": round(sum(r["answers_toward_median"] + r["answers_away"] for r in rs)
                                                       / sum(r["answers_toward_median"] + r["answers_away"]
                                                             + r["answers_unchanged"] for r in rs), 3),
                        "endline_matches_first_speaker": mean("endline_matches_first_speaker"),
                        "endline_matches_other_speakers": mean("endline_matches_other_speakers")})
    OUT.mkdir(parents=True, exist_ok=True)
    for name, data in (("exploratory_by_run", rows), ("exploratory_by_model", summary)):
        with (OUT / f"{name}.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)
    print(f"{len(rows)} runs -> {OUT.relative_to(ROOT)}/exploratory_*.csv")
    for s in summary:
        print(f"  {s['model'][:22]:22s} [{s['protocol']}] spread {s['spread_baseline']} -> {s['spread_endline']} "
              f"({s['spread_change']:+}); changed {s['share_answers_changed']:.0%} of answers, "
              f"{s['share_toward_of_moved']:.0%} toward median; endline = first speaker "
              f"{s['endline_matches_first_speaker']:.0%} vs others {s['endline_matches_other_speakers']:.0%}")


if __name__ == "__main__":
    main()
