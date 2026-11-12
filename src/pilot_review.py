"""
Quick review of pilot runs (never scored): rules, answer rates, prompt lengths
against the context window, and assessment spread.

    python -m src.pilot_review            # all runs/**/pilot folders
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from src.score import R_ITEMS, ROOT, score_run

ASSESS = ["support", "support_with_reservations", "object_no_block", "block", "prefer_not"]


def main() -> None:
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    limits = {"small": cfg["local"]["num_ctx"], "large": cfg["gpu"]["num_ctx"]}
    for d in sorted((ROOT / "runs").rglob("pilot")):
        rel = d.relative_to(ROOT / "runs")
        if (any(p.startswith("_") for p in rel.parts) or rel.parts[0] == "post_review"
                or not (d / "run_meta.json").exists()):
            continue
        r = score_run(d)
        calls = [json.loads(line) for line in (d / "calls.jsonl").open()]
        pt = [c["usage"]["prompt_tokens"] or 0 for c in calls]
        ct = [c["usage"]["completion_tokens"] or 0 for c in calls]
        limit = limits["large"] if any(x in str(rel) for x in ("27b", "24b")) else limits["small"]
        print(f"\n== {rel}  [{r['protocol']}]")
        print(f"  rules matched {r['R_coverage']}/7, other items {r['S_coverage']}/16, D {r['D_score']}/4; "
              f"selects {r['endline_selected']} (baseline {r['baseline_selected']})")
        print(f"  calls {len(calls)}, follow-ups {r['followup_calls']}, unanswered {r['items_unanswered_after_followups']}; "
              f"max prompt {max(pt)} tokens (limit {limit}, {max(pt) / limit:.0%}), max output {max(ct)}")
        print("  rules:", {k: r[k] for k in R_ITEMS})
        print("  assessment:", {k: r[f"assess_{k}"] for k in ASSESS},
              f"| Q10 more supportive {r['q10_more_supportive']}, more critical {r['q10_more_critical']}")


if __name__ == "__main__":
    main()
