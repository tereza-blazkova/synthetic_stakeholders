"""
B1 (post-review): replay ONLY the final assessment of logged full-protocol workshops
under each card condition in inputs/variants/card_variants.yaml.

For each source workshop and agent, the logged first assessment call is re-sent
with exactly one change (the card, or one header phrase); the rest of the
history is byte-identical to what the agent saw. Same model digest, options and
follow-up rule as the original (both checked against the log); fresh seeds,
derived from (condition, run seed, agent, attempt) and logged.

    python -m src.replay_assessment --family family_1 --runs 1-20          # UCloud
    python -m src.replay_assessment --backend fake --source-root DIR --runs 1-2   # tests

Output: runs/post_review/card/<condition>/<model>/<run_id>/
    calls.jsonl, assessment.json (same format as the original), replay_meta.json
A condition folder counts as done only when assessment.json exists (written
atomically, after replay_meta.json) and its replay_meta.json names the same
variants file and model digest; an interrupted folder is redone from scratch.
Calls go agent by agent through all conditions, so the model can reuse the
agent's long cached prefix (speed only; every call is independent).
A failed workshop is logged and skipped; the exit code is non-zero if any failed,
so the shell wrapper can simply run the command again.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import yaml

from src import survey as sv
from src import variants as V
from src.llm import CallLog, FakeBackend, OllamaBackend, logged_chat
from src.workshop import MAX_FOLLOWUPS

ROOT = Path(__file__).resolve().parents[1]


def _seed(cond: str, run_seed: int, agent: str, attempt: int) -> int:
    h = hashlib.sha256(f"B1|{cond}|{run_seed}|{agent}|{attempt}".encode()).hexdigest()
    return int(h[:8], 16)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_atomic(path: Path, obj) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False))
    os.replace(tmp, path)


def source_calls(src_dir: Path) -> dict[str, dict]:
    """The first (attempt 1) assessment call of each agent in a logged workshop."""
    calls = [json.loads(l) for l in (src_dir / "calls.jsonl").open()]
    first = {c["agent"]: c for c in calls if c["phase"] == "assessment" and c["attempt"] == 1}
    if len(first) != 12:
        raise ValueError(f"{src_dir}: {len(first)} assessment calls, expected 12")
    return first


def check_same_settings(backend, first: dict[str, dict]) -> None:
    """Requirement: the replay sends the same model options and reasoning setting as the log."""
    if backend.digest == "fake":
        return
    digests = {c["model_digest"] for c in first.values()}
    if digests != {backend.digest}:
        raise SystemExit(f"logged digest {digests} != loaded {backend.digest}")
    for c in first.values():
        req = c["request"]
        logged = {k: v for k, v in req["options"].items() if k != "seed"}
        if logged != backend.options:
            raise SystemExit(f"logged options {logged} != replay options {backend.options}")
        if req.get("think") != (False if "thinking" in backend.capabilities else None) or "format" in req:
            raise SystemExit(f"reasoning/format setting differs from the log: think={req.get('think')}")


def _done(d: Path, variants_sha: str, digest: str) -> bool:
    if not (d / "assessment.json").exists():
        return False
    meta = json.loads((d / "replay_meta.json").read_text())
    if meta["variants_sha256"] != variants_sha or meta["model_digest"] != digest:
        raise SystemExit(f"{d}: finished with other inputs (variants file or model changed); "
                         "move that folder away by hand before re-running")
    json.loads((d / "assessment.json").read_text())          # must parse
    return True


def replay_run(backend, src_dir: Path, out_root: Path, conds: list[str], doc: dict, log=print) -> None:
    meta_src = json.loads((src_dir / "run_meta.json").read_text())
    run_seed, run_id = meta_src["run_seed"], src_dir.name
    if meta_src["protocol"] != "full":
        raise ValueError(f"{src_dir}: B1 replays the full protocol only")
    first = source_calls(src_dir)
    check_same_settings(backend, first)
    variants_sha = _sha256(V.VARIANTS_PATH)

    todo = []
    for cond in conds:
        d = out_root / cond / src_dir.parent.name / run_id
        if _done(d, variants_sha, backend.digest):
            continue
        for leftover in ("calls.jsonl", "replay_meta.json", "assessment.json.tmp", "replay_meta.json.tmp"):
            if (d / leftover).exists():
                log(f"  redo incomplete {cond}/{run_id} (removing {leftover})")
                (d / leftover).unlink()
        todo.append((cond, d))
    if not todo:
        log(f"skip {src_dir.parent.name}/{run_id}: all conditions done")
        return

    started = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()
    logs = {c: CallLog(d / "calls.jsonl") for c, d in todo}
    results = {c: {} for c, _ in todo}
    orders = {c: {} for c, _ in todo}
    failures = {c: [] for c, _ in todo}
    src_rel = str(src_dir.relative_to(ROOT)) if src_dir.is_relative_to(ROOT) else str(src_dir)
    for agent in sorted(first, key=lambda a: (a[0] != "A", int(a[1:]))):      # A1..A3, S1..S9
        orig = first[agent]["request"]["messages"]
        for cond, _ in todo:
            order = V.card_order(doc, cond, run_seed, agent)
            flds = [sv.Field("choice", "single", order), sv.Field("justification", "text")]
            msgs = copy.deepcopy(orig)
            msgs[-1]["content"] = V.apply_condition(msgs[-1]["content"], doc, cond, run_seed, agent)
            # Same as Workshop._structured: first ask, then up to MAX_FOLLOWUPS asking only for
            # what is missing; each follow-up sees the previous raw reply.
            texts, missing = [], []
            for attempt in range(1, MAX_FOLLOWUPS + 2):
                ask = flds if attempt == 1 else [f for f in flds if f.key in missing]
                text = logged_chat(backend, logs[cond], messages=msgs, schema=sv.answer_schema(ask),
                                   seed=_seed(cond, run_seed, agent, attempt),
                                   meta={"run_seed": run_seed, "phase": "assessment", "agent": agent,
                                         "attempt": attempt, "condition": cond, "card_order": order,
                                         "source_run": src_rel,
                                         "source_call_index": first[agent]["call_index"]})
                texts.append(text)
                answers, missing = sv.merge_replies(texts, flds)
                if not missing or attempt == MAX_FOLLOWUPS + 1:
                    break
                msgs = msgs + [{"role": "assistant", "content": text},
                               {"role": "user", "content": sv.followup_instruction(flds, missing)}]
            if missing:
                failures[cond].append({"agent": agent, "unanswered": missing})
            results[cond][agent], orders[cond][agent] = answers, order
        log(f"  {run_id} {agent}: " + " ".join(f"{c}={results[c][agent]['choice']}" for c, _ in todo))

    for cond, d in todo:
        meta = {"study": "post_review_B1_card", "condition": cond, "source_run": src_rel,
                "source_protocol": meta_src["protocol"], "run_seed": run_seed,
                "model": backend.model, "model_digest": backend.digest,
                "options": getattr(backend, "options", {}), "card_order": orders[cond],
                "seed_rule": "int(sha256('B1|cond|run_seed|agent|attempt')[:8], 16)",
                "variants_sha256": variants_sha, "n_calls": logs[cond].n,
                "failures": failures[cond], "started": started,
                "finished": datetime.now(timezone.utc).isoformat(),
                "wall_minutes_all_conditions": round((time.monotonic() - t0) / 60, 1)}
        _write_atomic(d / "replay_meta.json", meta)
        _write_atomic(d / "assessment.json", results[cond])          # last: marks the folder done
    log(f"done {src_dir.parent.name}/{run_id}: {len(todo)} conditions in "
        f"{(time.monotonic() - t0) / 60:.1f} min")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--family", help="key under models_large: in config.yaml (required with ollama)")
    p.add_argument("--runs", required=True, help="run numbers, e.g. 1-20")
    p.add_argument("--conditions", default="all", help="comma-separated, or 'all'")
    p.add_argument("--backend", choices=["ollama", "fake"], default="ollama")
    p.add_argument("--source-root", help="folder holding <model>/runNN (default runs/full)")
    p.add_argument("--out-root", help="default runs/post_review/card")
    args = p.parse_args()
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    doc = V.load()
    conds = V.conditions(doc) if args.conditions == "all" else args.conditions.split(",")
    unknown = set(conds) - set(V.conditions(doc))
    if unknown:
        sys.exit(f"unknown conditions: {sorted(unknown)}")

    if args.backend == "fake":
        backend, model = FakeBackend(), "fake"
    else:
        if not args.family:
            sys.exit("--family is required with the ollama backend")
        m = cfg["models_large"][args.family]
        s, hw = cfg["sampling"], cfg["gpu"]
        backend = OllamaBackend(m["model_id"], num_ctx=hw["num_ctx"], temperature=s["temperature"],
                                max_tokens=s["max_output_tokens"])
        if backend.digest != m["digest"]:
            sys.exit(f"{m['model_id']}: digest {backend.digest} != pinned {m['digest']}")
        model = m["model_id"]
    folder = re.sub(r"[^A-Za-z0-9._/-]", "_", model)
    src_root = Path(args.source_root) if args.source_root else ROOT / "runs" / "full"
    out_root = Path(args.out_root) if args.out_root else ROOT / "runs" / "post_review" / "card"
    lo, _, hi = args.runs.partition("-")
    failed = []
    for k in range(int(lo), int(hi or lo) + 1):
        src = src_root / folder / f"run{k:02d}"
        print(f"=== {folder} run{k:02d}: {len(conds)} conditions ===", flush=True)
        for attempt in range(1, 4):                    # transient server errors: retry, then move on
            try:
                replay_run(backend, src, out_root, conds, doc)
                break
            except (OSError, TimeoutError, ValueError, KeyError) as e:
                print(f"ERROR {folder} run{k:02d} (attempt {attempt}): {e!r}", flush=True)
                traceback.print_exc()
                time.sleep(30 * attempt)
        else:
            failed.append(k)
    if failed:
        sys.exit(f"FAILED runs: {failed} (re-run the same command; finished folders are kept)")


if __name__ == "__main__":
    main()
