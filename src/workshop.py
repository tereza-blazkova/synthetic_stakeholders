"""
One deliberation-lite workshop (inputs/materials/facilitator_script_lite.yaml).

Each of the 12 agents keeps its own message history: everything it saw and said,
nothing from other agents except what was said in the plenary. Message order is
chosen so that all 12 histories share one long identical prefix (system prompt,
framing, programme, survey) and the agent's profile comes after it.

    system   shared participant instruction
    user     framing + programme + survey  | profile | baseline instruction
    asst     baseline survey (JSON)
    user     plenary intro with anonymous baseline counts + the turns before this agent
    asst     plenary turn (free text)
    user     the turns after this agent + endline instruction + Q10
    asst     endline survey (JSON)
    user     provisional specification (this panel's endline medians) + assessment card
    asst     assessment (JSON)

Seeds: the run seed shuffles the plenary speaking order and seeds every call
(call seed = run seed * 1000 + call number), so a run is fully specified by
(model, digest, run seed, input file hashes), all recorded in run_meta.json.
"""
from __future__ import annotations

import hashlib
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from src import aggregate, personas, survey as sv
from src.llm import CallLog, logged_chat
from src.rule_applier import load_metrics, ruleset_from_medians, select

ROOT = Path(__file__).resolve().parents[1]
MAT = ROOT / "inputs" / "materials"
SCRIPT_PATH = MAT / "facilitator_script_lite.yaml"
FRAMING_PATH = MAT / "framing_intro.md"
SPEC_TEMPLATE = MAT / "specification_template.md"
INPUT_FILES = [SCRIPT_PATH, FRAMING_PATH, SPEC_TEMPLATE, MAT / "survey.yaml",
               ROOT / "inputs" / "personas.yaml", ROOT / "inputs" / "metrics_2021.csv"]

ASSESSMENT_OPTIONS = ["support", "support_with_reservations", "object_no_block", "block", "prefer_not"]
ASSESSMENT_FIELDS = [sv.Field("choice", "single", ASSESSMENT_OPTIONS), sv.Field("justification", "text")]
MAX_FOLLOWUPS = 2     # extra calls asking only for missing/invalid answers

# Spoken and private turns only (never surveys): stop when a reply starts a new line
# with another speaker's tag, and cap length. Added 2026-10-20 after Mistral Small
# 3.2 scripted other speakers' lines in the full-protocol pilot; a no-op for every
# earlier run (no turn in them contains such a line or exceeds the cap).
SPEAKER_TAGS = ["Facilitator"] + [f"A{i}" for i in range(1, 4)] + [f"S{i}" for i in range(1, 10)]
TURN_OPTIONS = {"stop": [f"\n{t}:" for t in SPEAKER_TAGS], "num_predict": 600}
# No structured-output constraint: Ollama enforces JSON schemas for some models
# but not others (qwen3.5), which would give some families extra help. Every
# model gets the same prompt-only JSON request, lenient parsing and follow-ups.


def _strip_comment(md: str) -> str:
    return md.split("-->", 1)[1].strip() if md.lstrip().startswith("<!--") else md.strip()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Workshop:
    PROTOCOL = "lite"
    SCRIPT = SCRIPT_PATH
    INPUT_FILES = INPUT_FILES

    def __init__(self, backend, run_dir: Path, run_seed: int, log=print, personas_path: Path | None = None):
        """`personas_path`: a persona variant file (post-review B2 only); default inputs/personas.yaml."""
        self.backend, self.run_dir, self.seed, self.say = backend, run_dir, run_seed, log
        self.script = yaml.safe_load(self.SCRIPT.read_text())
        self.survey = sv.load_survey()
        if personas_path is not None:          # hash the file actually used, in its place in the list
            personas_path = Path(personas_path).resolve()
            personas_path.relative_to(ROOT)    # fail now, not after the workshop (input_sha256 needs it)
            self.INPUT_FILES = [personas_path if p.name == "personas.yaml" else p for p in self.INPUT_FILES]
            self.pdoc = personas.load_personas(personas_path)
        else:
            self.pdoc = personas.load_personas()
        personas.check_marginals(self.pdoc)
        self.agents = personas.agents(self.pdoc)
        self.calls = CallLog(run_dir / "calls.jsonl")
        self.history: dict[str, list[dict]] = {}
        self.failures: list[dict] = []
        self.max_words = self.script["turn_length"]["spoken_max_words"]

    # ── helpers ───────────────────────────────────────────────────────────────
    def _call(self, agent_id: str, phase: str, attempt: int = 1, flds: list | None = None) -> str:
        """One model call on the agent's history; appends the reply to the history.
        `flds` is only a hint for FakeBackend; real backends get no constraint."""
        seed = self.seed * 1000 + self.calls.n + 1
        schema = sv.answer_schema(flds) if flds else None
        extra = None if flds else TURN_OPTIONS          # flds is None exactly for spoken/private turns
        text = logged_chat(self.backend, self.calls, messages=self.history[agent_id], schema=schema, extra=extra,
                           seed=seed, meta={"run_seed": self.seed, "phase": phase,
                                            "agent": agent_id, "attempt": attempt})
        self.history[agent_id].append({"role": "assistant", "content": text})
        return text

    def _structured(self, agent_id: str, phase: str, flds: list[sv.Field]) -> dict:
        """A JSON answer, with up to MAX_FOLLOWUPS follow-ups asking only for what is missing."""
        texts = [self._call(agent_id, phase, flds=flds)]
        answers, missing = sv.merge_replies(texts, flds)
        for k in range(MAX_FOLLOWUPS):
            if not missing:
                break
            self.history[agent_id].append({"role": "user", "content": sv.followup_instruction(flds, missing)})
            texts.append(self._call(agent_id, phase, attempt=k + 2,
                                    flds=[f for f in flds if f.key in missing]))
            answers, missing = sv.merge_replies(texts, flds)
        if missing:
            self.failures.append({"agent": agent_id, "phase": phase, "unanswered": missing})
        return answers

    def _survey(self, phase: str, flds: list[sv.Field]) -> dict[str, dict]:
        answers = {}
        for a in self.agents:
            t0 = time.monotonic()
            answers[a["id"]] = self._structured(a["id"], phase, flds)
            n_missing = sum(len(f["unanswered"]) for f in self.failures
                            if f["agent"] == a["id"] and f["phase"] == phase)
            self.say(f"  {phase:9s} {a['id']:3s} {time.monotonic() - t0:6.1f}s"
                     + (f"  ({n_missing} items left unanswered)" if n_missing else ""))
        return answers

    def _plenary_turn(self, agent_id: str) -> str:
        text = self._call(agent_id, "plenary").strip()
        if not text:                       # one retry on an empty reply
            self.history[agent_id].pop()
            text = self._call(agent_id, "plenary", attempt=2).strip()
        return text

    # ── the workshop ──────────────────────────────────────────────────────────
    def run(self) -> dict:
        started = datetime.now(timezone.utc).isoformat()
        t_start = time.monotonic()
        s = self.script
        base_fields = sv.fields(self.survey, "baseline")
        end_fields = sv.fields(self.survey, "endline", skip=s["endline_skip_items"])

        # 1-2. Framing, then the baseline survey. Shared prefix first, profile after.
        shared = (_strip_comment(FRAMING_PATH.read_text()) + "\n\n" + s["programme"].strip()
                  + "\n\n" + sv.render_survey(self.survey))
        for a in self.agents:
            self.history[a["id"]] = [
                {"role": "system", "content": self.pdoc["system_prompt"].strip()},
                {"role": "user", "content": shared + "\n\n=== Your profile ===\n"
                 + personas.profile_text(self.pdoc, a) + "\n\n" + s["baseline_instruction"].strip()
                 + "\n\n" + sv.answer_instruction(base_fields)}]
        self.say("baseline survey")
        baseline = self._survey("baseline", base_fields)

        # 3. One plenary round, shuffled order; each speaker sees the turns before theirs.
        order = [a["id"] for a in self.agents]
        random.Random(self.seed).shuffle(order)
        intro = s["plenary_intro"].format(
            baseline_distribution=aggregate.distribution_text(baseline, self.survey)).strip()
        turns: list[tuple[str, str]] = []
        self.say(f"plenary (order: {' '.join(order)})")
        for agent_id in order:
            before = "\n\n".join(f"{who}: {what}" for who, what in turns) or "You are the first to speak."
            self.history[agent_id].append({"role": "user", "content": intro + "\n\n" + s["plenary_turn"].format(
                turns_so_far="What has been said so far:\n\n" + before if turns else before,
                agent_id=agent_id, max_words=self.max_words).strip()})
            t0 = time.monotonic()
            turns.append((agent_id, self._plenary_turn(agent_id)))
            self.say(f"  plenary   {agent_id:3s} {time.monotonic() - t0:6.1f}s  "
                     f"({len(turns[-1][1].split())} words)")

        # 4. Endline survey; everyone first hears the rest of the round.
        endline_text = (s["endline_instruction"].strip() + "\n\n" + sv.render_endline_extra(
            self.survey, s["endline_skip_items"]) + "\n\n" + sv.answer_instruction(end_fields))
        for i, agent_id in enumerate(order):
            after = "\n\n".join(f"{who}: {what}" for who, what in turns[i + 1:])
            after = ("After you, the others said:\n\n" + after) if after else "You were the last to speak."
            self.history[agent_id].append({"role": "user", "content":
                s["plenary_after"].format(turns_after=after).strip() + "\n\n" + endline_text})
        self.say("endline survey")
        endline = self._survey("endline", end_fields)

        # 5. Aggregate, select, and the final assessment of the provisional specification.
        def card(spec: str) -> str:
            return (s["assessment_instruction"].format(specification=spec, max_words=self.max_words).strip()
                    + "\n\n" + sv.answer_instruction(ASSESSMENT_FIELDS))
        return self._finish(baseline, endline, card, started, t_start,
                            extra_meta={"plenary_order": order},
                            extra_files={"plenary": [{"agent": w, "text": t} for w, t in turns]})

    def _assess(self, card_text: str) -> dict:
        """Hand every agent the assessment card; returns their structured answers."""
        assessment = {}
        for a in self.agents:
            self.history[a["id"]].append({"role": "user", "content": card_text})
            assessment[a["id"]] = self._structured(a["id"], "assessment", ASSESSMENT_FIELDS)
        return assessment

    def _finish(self, baseline: dict, endline: dict, card, started: str, t_start: float,
                extra_meta: dict, extra_files: dict) -> dict:
        """Shared by both protocols: aggregate, select, final assessment, summary files.
        `card(spec)` returns the full user message for the assessment (protocol-specific)."""
        agg_base, agg_end = aggregate.aggregate(baseline), aggregate.aggregate(endline)
        metrics = load_metrics()
        sel = {adm: select(metrics, ruleset_from_medians({k: v["median"] for k, v in agg.items()
                                                           if "median" in v}))
               for adm, agg in (("baseline", agg_base), ("endline", agg_end))}
        spec = aggregate.render_specification(agg_end, SPEC_TEMPLATE)
        self.say("final assessment")
        assessment = self._assess(card(spec))

        # Write the summary files (all re-derivable from calls.jsonl).
        meta = {"protocol": self.PROTOCOL, "run_seed": self.seed, "model": self.backend.model,
                "model_digest": self.backend.digest,
                "model_info": self.backend.model_info, "options": getattr(self.backend, "options", {}),
                "started": started, "finished": datetime.now(timezone.utc).isoformat(),
                "wall_minutes": round((time.monotonic() - t_start) / 60, 1),
                **extra_meta, "n_calls": self.calls.n, "failures": self.failures,
                "input_sha256": {str(p.relative_to(ROOT)): _sha256(p) for p in self.INPUT_FILES}}
        out = {"run_meta": meta, "answers_baseline": baseline, "answers_endline": endline, **extra_files,
               "aggregate_baseline": agg_base, "aggregate_endline": agg_end,
               "selection_baseline": {k: v for k, v in sel["baseline"].items() if k != "cells"},
               "selection_endline": {k: v for k, v in sel["endline"].items() if k != "cells"},
               "specification": spec, "assessment": assessment}
        for name, obj in out.items():
            (self.run_dir / f"{name}.json").write_text(json.dumps(obj, indent=2, ensure_ascii=False))
        self.say(f"done in {meta['wall_minutes']} min, {self.calls.n} calls, "
                 f"{len(self.failures)} failed attempts; endline selects "
                 f"{sel['endline']['model']} + {sel['endline']['feature_set']}")
        return out
