"""
One full multi-phase workshop (inputs/materials/facilitator_script.yaml).

Same agents, survey, follow-ups, aggregation, selection and assessment as the
lite protocol (src/workshop.py, inherited); only the discussion differs:

    framing -> baseline survey -> table discussions (3 tables, nominal group
    technique, divergence) -> plenary (table reports + 3 rounds) -> open
    discussion (1-2-4-All) -> endline survey -> final assessment

How agents hear things. Every agent has a pending buffer. Whatever is said in a
room the agent is in (facilitator text, other agents' turns) is appended to its
buffer; when the agent is next asked to act, the buffer plus the instruction
becomes one user message. So an agent hears exactly its own table, pair and
group of four, and everything in the plenary rooms, and nothing else.

The first message keeps the lite protocol's prefix order (framing, programme,
survey overview, survey, then the agent's profile), so all 12 histories share
one long identical prefix.

Speaking order in every round-robin room is shuffled with a seed derived from
the run seed and the room, so orders are matched across model families.
"""
from __future__ import annotations

import random
import time
from datetime import datetime, timezone

from src import aggregate, personas, survey as sv
from src.workshop import (ASSESSMENT_FIELDS, FRAMING_PATH, MAT, ROOT, SPEC_TEMPLATE, Workshop,
                          _strip_comment)

FULL_SCRIPT = MAT / "facilitator_script.yaml"
BLOCK_ITEMS = {  # survey items each table's block covers, shown with the anonymous counts
    "Q3": ["Q3.2", "Q3.3", "Q3.4"] + [f"Q3.5.{k}" for k in aggregate.SENSITIVE_KEYS]
          + [f"Q3.6.{k}" for k in aggregate.SENSITIVE_KEYS],
    "Q4": [f"Q4.1.{k}" for k in ("high", "moderate", "low", "very_low")],
    "Q5": ["Q5.1", "Q5.2"],
}
SHARED_ITEMS = ["Q6.1", "Q6.2", "Q7.1", "Q7.2"]          # every table also discusses Q6-Q7


class FullWorkshop(Workshop):
    PROTOCOL = "full"
    SCRIPT = FULL_SCRIPT
    INPUT_FILES = [FULL_SCRIPT] + [p for p in Workshop.INPUT_FILES if p.name != "facilitator_script_lite.yaml"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ids = [a["id"] for a in self.agents]
        self.pending: dict[str, list[str]] = {i: [] for i in self.ids}
        self.transcript: list[dict] = []        # every spoken turn, for later reading
        self.orders: dict[str, list[str]] = {}  # speaking order per room
        self.reports: dict[str, list[tuple[str, str]]] = {}
        self.ps = self.script["panel_structure"]
        tl = self.script["turn_length"]
        self.max_words, self.private_words = tl["spoken_max_words"], tl["private_max_words"]
        self.baseline: dict = {}

    # ── hearing and speaking ──────────────────────────────────────────────────
    def _hear(self, members: list[str], text: str) -> None:
        for m in members:
            self.pending[m].append(text)

    def _flush(self, agent: str, instruction: str) -> None:
        content = "\n\n".join(self.pending[agent] + [instruction])
        self.pending[agent] = []
        self.history[agent].append({"role": "user", "content": content})

    def _speak(self, agent: str, room: str, members: list[str], phase: str, instruction: str) -> str:
        """Ask one agent to speak; everyone else in the room hears the turn."""
        self._flush(agent, instruction)
        t0 = time.monotonic()
        text = self._plenary_turn_phase(agent, phase)
        self._hear([m for m in members if m != agent], f"{agent}: {text}")
        self.transcript.append({"phase": phase, "room": room, "agent": agent, "text": text})
        self.say(f"  {phase:24s} {agent:3s} {time.monotonic() - t0:6.1f}s ({len(text.split())} words)")
        return text

    def _plenary_turn_phase(self, agent: str, phase: str) -> str:
        text = self._call(agent, phase).strip()
        if not text:                                  # one retry on an empty reply
            self.history[agent].pop()
            text = self._call(agent, phase, attempt=2).strip()
        return text

    def _order(self, room: str, members: list[str]) -> list[str]:
        order = list(members)
        random.Random(f"{self.seed}:{room}").shuffle(order)
        self.orders[room] = order
        return order

    def _turn_instruction(self, agent: str, rnd: int, rounds: int) -> str:
        r = f" (round {rnd} of {rounds})" if rounds > 1 else ""
        return (f"It is your turn ({agent}){r}. Speak in the first person, as yourself, "
                f"in at most {self.max_words} words.")

    # ── rooms ─────────────────────────────────────────────────────────────────
    def _rooms(self, room: str) -> list[tuple[str, list[str], dict]]:
        """(room name, members, placeholder values) for a room spec."""
        if room == "all":
            return [("all", self.ids, {})]
        if room == "each_table":
            out = []
            for t, spec in self.ps["tables"].items():
                first, second = self.ps["table_spokespeople"][t]
                keys = BLOCK_ITEMS[spec["block"]] + SHARED_ITEMS
                out.append((t, spec["members"], {
                    "table_id": t[1:], "table_members": ", ".join(spec["members"]),
                    "table_block": spec["block"], "table_block_name": spec["name"].lower(),
                    "speaker_first": first, "speaker_second": second,
                    "baseline_distribution_for_table_blocks":
                        aggregate.distribution_text(self.baseline, self.survey, keys)}))
            return out
        if room == "each_pair":
            return [(p, m, {}) for p, m in self.ps["open_discussion_pairs"].items()]
        if room == "each_four":
            return [(f, [a for p in spec["pairs"] for a in self.ps["open_discussion_pairs"][p]],
                     {"four_reporter": spec["reporter"]})
                    for f, spec in self.ps["open_discussion_fours"].items()]
        raise ValueError(f"unknown room {room!r}")

    def _fmt(self, text: str, ctx: dict, agent: str | None = None, room_members: list[str] = ()) -> str:
        if agent and "{pair_partner}" in text:
            ctx = {**ctx, "pair_partner": next(m for m in room_members if m != agent)}
        return text.format(**ctx).strip()

    # ── modes ─────────────────────────────────────────────────────────────────
    def _step(self, phase_id: str, step: dict, room_spec: str) -> None:
        mode = step["mode"]
        for room, members, ctx in self._rooms(room_spec):
            phase = f"{phase_id}.{room}" if room != "all" else phase_id
            if mode == "broadcast":
                if "text_file" in step:
                    text = _strip_comment((ROOT / step["text_file"]).read_text())
                    self._hear(members, text)
                else:
                    for m in members:     # formatted per listener (e.g. their pair partner)
                        self._hear([m], "Facilitator: " + self._fmt(step["text"], ctx, m, members))
            elif mode == "private":
                for m in members:
                    instr = ("Facilitator (to you only): " + self._fmt(step["text"], ctx, m, members)
                             + f"\nWrite at most {self.private_words} words; nobody else will see this.")
                    self._flush(m, instr)
                    t0 = time.monotonic()
                    text = self._plenary_turn_phase(m, phase)
                    self.transcript.append({"phase": phase, "room": f"private:{m}", "agent": m, "text": text})
                    self.say(f"  {phase:24s} {m:3s} {time.monotonic() - t0:6.1f}s (private)")
            elif mode == "round_robin":
                for m in members:
                    self._hear([m], "Facilitator: " + self._fmt(step["text"], ctx, m, members))
                order = self._order(f"{phase}#{len(self.orders)}", members)
                rounds = step.get("rounds", 1)
                for r in range(1, rounds + 1):
                    for m in order:
                        self._speak(m, room, members, phase, self._turn_instruction(m, r, rounds))
            elif mode == "speakers":
                if step["speakers"] == "table_spokespeople":
                    speakers = self.ps["table_spokespeople"][room]
                    self._hear(members, "Facilitator: " + self._fmt(step["text"], ctx))
                    # The report is drafted at the table but delivered in the plenary
                    # (replay below), so table members hear it there, once. The second
                    # spokesperson sees the first's draft, to add what is missing.
                    report = []
                    for s_ in speakers:
                        text = self._speak(s_, room, [s_] + [x for x, _ in report], phase,
                                           self._turn_instruction(s_, 1, 1))
                        report.append((s_, text))
                        if s_ == speakers[0]:
                            self._hear([speakers[1]], f"{s_}: {text}")
                    self.reports[room] = report
                elif step["speakers"] == "four_reporters":
                    for f, spec in self.ps["open_discussion_fours"].items():
                        s = spec["reporter"]
                        self._hear(members, "Facilitator: " + self._fmt(step["text"], {"four_reporter": s}))
                        self._speak(s, room, members, f"{phase}.{f}", self._turn_instruction(s, 1, 1))
                else:
                    raise ValueError(step["speakers"])
            elif mode == "replay":
                for t, turns in self.reports.items():
                    block = "\n\n".join(f"{who}: {what}" for who, what in turns)
                    self._hear(members, f"Report from Table {t[1:]}:\n\n{block}")
            else:
                raise ValueError(f"mode {mode!r} is handled outside _step")

    # ── the workshop ──────────────────────────────────────────────────────────
    def run(self) -> dict:
        started = datetime.now(timezone.utc).isoformat()
        t_start = time.monotonic()
        base_fields = sv.fields(self.survey, "baseline")
        end_fields = sv.fields(self.survey, "endline")          # Q10.5 asked: tables exist here
        for a in self.agents:
            self.history[a["id"]] = [{"role": "system", "content": self.pdoc["system_prompt"].strip()}]
        endline = {}
        for phase in self.script["phases"]:
            pid = phase["id"]
            self.say(pid)
            for step in phase["steps"]:
                room = step.get("room", phase.get("room", "all"))
                if step["mode"] == "survey" and step["administration"] == "baseline":
                    # Shared prefix (framing, programme, overview, survey), then the profile.
                    survey_text = sv.render_survey(self.survey)
                    for a in self.agents:
                        self._flush(a["id"], survey_text + "\n\n=== Your profile ===\n"
                                    + personas.profile_text(self.pdoc, a) + "\n\n"
                                    + sv.answer_instruction(base_fields))
                    self.baseline = self._survey("baseline", base_fields)
                elif step["mode"] == "survey" and step["administration"] == "endline":
                    extra = (sv.render_endline_extra(self.survey) + "\n\n" + sv.answer_instruction(end_fields))
                    for a in self.agents:
                        self._flush(a["id"], extra)
                    endline = self._survey("endline", end_fields)
                elif pid == "8_final_assessment":
                    break                                      # handled by the shared _finish
                else:
                    self._step(pid, step, room)
            if pid == "7_endline_survey":
                break

        assess_text = next(s["text"] for s in self.script["phases"][-2]["steps"] if s.get("structured"))

        def card(spec: str) -> str:
            return (spec + "\n\nFacilitator: " + assess_text.strip()
                    + f"\nJustify in at most {self.max_words} words.\n\n" + sv.answer_instruction(ASSESSMENT_FIELDS))

        return self._finish(self.baseline, endline, card, started, t_start,
                            extra_meta={"speaking_orders": self.orders},
                            extra_files={"transcript": self.transcript,
                                         "table_reports": {t: [{"agent": a, "text": x} for a, x in r]
                                                           for t, r in self.reports.items()}})

    # Override: the assessment card is preceded by whatever the agent has pending.
    def _assess(self, card_text: str) -> dict:
        assessment = {}
        for a in self.agents:
            self._flush(a["id"], card_text)
            assessment[a["id"]] = self._structured(a["id"], "assessment", ASSESSMENT_FIELDS)
        return assessment

