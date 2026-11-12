"""
Smoke test for a local model: one baseline-survey call for one agent, timed and
validated. Logs go to runs/_smoke/ (never scored).

    python -m src.smoke qwen3.5:4b-q4_K_M
"""
from __future__ import annotations

import json
import sys
import time

from src import personas, survey as sv
from src.llm import CallLog, OllamaBackend
from src.workshop import FRAMING_PATH, ROOT, _strip_comment
import yaml


def main(model: str) -> None:
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    script = yaml.safe_load((ROOT / "inputs/materials/facilitator_script_lite.yaml").read_text())
    backend = OllamaBackend(model, num_ctx=cfg["local"]["num_ctx"],
                            temperature=cfg["sampling"]["temperature"],
                            max_tokens=cfg["sampling"]["max_output_tokens"])
    survey, pdoc = sv.load_survey(), personas.load_personas()
    agent = personas.agents(pdoc)[5]                       # S3
    flds = sv.fields(survey, "baseline")
    shared = (_strip_comment(FRAMING_PATH.read_text()) + "\n\n" + script["programme"].strip()
              + "\n\n" + sv.render_survey(survey))
    messages = [{"role": "system", "content": pdoc["system_prompt"].strip()},
                {"role": "user", "content": shared + "\n\n=== Your profile ===\n"
                 + personas.profile_text(pdoc, agent) + "\n\n" + script["baseline_instruction"].strip()
                 + "\n\n" + sv.answer_instruction(flds)}]
    t0 = time.monotonic()
    r = backend.chat(messages, sv.answer_schema(flds), seed=1)
    wall = time.monotonic() - t0
    log = CallLog(ROOT / "runs" / "_smoke" / model.replace(":", "_") / "calls.jsonl")
    log.write({"phase": "smoke", "agent": agent["id"], "model": model, "model_digest": backend.digest,
               "request": r["request"], "response": r["text"], "usage": r["usage"], "wall_seconds": wall})
    u = r["usage"]
    print(f"{model}: digest {backend.digest}, capabilities {backend.capabilities}, {backend.model_info}")
    print(f"  wall {wall:.0f}s | prompt {u['prompt_tokens']} tok in {u['prompt_seconds']:.0f}s "
          f"({u['prompt_tokens'] / max(u['prompt_seconds'], 1e-9):.0f} tok/s) | "
          f"output {u['completion_tokens']} tok in {u['completion_seconds']:.0f}s "
          f"({u['completion_tokens'] / max(u['completion_seconds'], 1e-9):.1f} tok/s) | load {u['load_seconds']:.0f}s")
    ans, bad = sv.parse_answers(r["text"], flds)
    print(f"  parsed {len(ans)}/{len(flds)} keys; missing or invalid: {bad[:8]}")
    sel = {k: ans.get(k) for k in ["Q3.2", "Q3.3", "Q3.4", "Q4.1.high", "Q4.1.low", "Q4.1.very_low", "Q5.2"]}
    print(f"  sample answers: {sel}")
    print(f"  notes.Q3: {ans.get('notes.Q3', '')[:200]!r}")


if __name__ == "__main__":
    main(sys.argv[1])
