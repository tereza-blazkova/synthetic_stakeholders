"""
The workshop survey: rendering it for the agents, the JSON answer format, and
validation.

Source: inputs/materials/survey.yaml (transcribed from the blank instrument).

Every answer is a flat JSON object. Keys are question ids, with grid rows
appended after a dot:

    "Q3.2"        single choice      -> option key, e.g. "small"
    "Q3.5.age"    grid row           -> option key
    "Q6.1"        multi choice       -> list of option keys
    "Q8.1"        free text          -> string
    "notes.Q3"    baseline notes     -> string (one per block)

Every single-choice item and grid row gets an extra option "no_answer", the
equivalent of leaving the item blank on the paper form. The paper excludes
blank, "Not sure" and "Prefer not to answer" from all medians (see aggregate.py).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SURVEY_PATH = ROOT / "inputs" / "materials" / "survey.yaml"

NO_ANSWER = "no_answer"
NO_ANSWER_LABEL = "(leave this question unanswered)"
NOTES_MAX_WORDS = 40


@dataclass
class Field:
    """One key in the JSON answer object."""
    key: str                      # e.g. "Q3.5.age"
    kind: str                     # "single" | "multi" | "text"
    options: list[str] = field(default_factory=list)   # option keys (single/multi)
    max_select: int | None = None


def load_survey(path: Path = SURVEY_PATH) -> dict:
    return yaml.safe_load(path.read_text())


def _options(survey: dict, item: dict) -> list[dict]:
    """The option list of an item: its own options, or a named scale."""
    if "options" in item:
        return item["options"]
    return survey["scales"][item["scale"]]


def _rows(survey: dict, item: dict) -> list[dict]:
    rows = item["rows"]
    return survey[rows] if isinstance(rows, str) else rows


def _blocks(survey: dict, administration: str) -> list[dict]:
    blocks = list(survey["blocks"])
    if administration == "endline":
        blocks += survey["endline_only"]
    return blocks


def fields(survey: dict, administration: str, skip: list[str] = ()) -> list[Field]:
    """All answer keys for one administration ("baseline" or "endline"), in order."""
    out: list[Field] = []
    for block in _blocks(survey, administration):
        for item in block["items"]:
            if item["id"] in skip:
                continue
            opts = [o["key"] for o in _options(survey, item)] if item["type"] != "text" else []
            if item["type"] == "single":
                out.append(Field(item["id"], "single", opts + [NO_ANSWER]))
            elif item["type"] == "grid":
                for row in _rows(survey, item):
                    out.append(Field(f'{item["id"]}.{row["key"]}', "single", opts + [NO_ANSWER]))
            elif item["type"] == "multi":
                out.append(Field(item["id"], "multi", opts, item.get("max_select")))
                if item.get("allow_other_text"):
                    out.append(Field(f'{item["id"]}.other_text', "text"))
            elif item["type"] == "text":
                out.append(Field(item["id"], "text"))
        if administration == "baseline" and block["id"] not in ("Q8", "Q9"):
            out.append(Field(f'notes.{block["id"]}', "text"))
    return out


# ── Rendering for the agents ──────────────────────────────────────────────────

def _render_options(opts: list[dict], with_no_answer: bool) -> str:
    lines = [f"    [{o['key']}] {o['label']}" for o in opts]
    if with_no_answer:
        lines.append(f"    [{NO_ANSWER}] {NO_ANSWER_LABEL}")
    return "\n".join(lines)


def _render_item(survey: dict, item: dict) -> str:
    text = item["text"].strip()
    if item["type"] == "single":
        return f"{item['id']} {text}\n{_render_options(_options(survey, item), True)}"
    if item["type"] == "grid":
        rows = "\n".join(f"    {item['id']}.{r['key']}: {r['label']}" for r in _rows(survey, item))
        return (f"{item['id']} {text}\n  Rows (answer each row separately):\n{rows}\n"
                f"  Options for every row:\n{_render_options(_options(survey, item), True)}")
    if item["type"] == "multi":
        cap = f" Select at most {item['max_select']}." if item.get("max_select") else ""
        other = (f"\n  If you select [other], write it in {item['id']}.other_text; otherwise leave that empty."
                 if item.get("allow_other_text") else "")
        return (f"{item['id']} {text}{cap} (A list; an empty list means unanswered.)\n"
                f"{_render_options(_options(survey, item), False)}{other}")
    return f"{item['id']} {text}\n  (Free text; may be empty.)"


def _render_blocks(survey: dict, blocks: list[dict], skip: list[str] = ()) -> str:
    parts = []
    for block in blocks:
        parts.append(f"=== {block['id']} {block['title']} ===")
        if block.get("preamble", "").strip():
            parts.append(block["preamble"].strip())
        for item in block["items"]:
            if item["id"] not in skip:
                parts.append(_render_item(survey, item))
    return "\n\n".join(parts)


def render_survey(survey: dict) -> str:
    """The survey as the agents read it (baseline questions Q2-Q9)."""
    return "SURVEY\n\n" + survey["intro"].strip() + "\n\n" + _render_blocks(survey, survey["blocks"])


def render_endline_extra(survey: dict, skip: list[str] = ()) -> str:
    """The endline-only questions (Q10), shown with the endline instruction."""
    q10 = _render_blocks(survey, survey["endline_only"], skip)
    return (q10 + "\n\nAnswer Q10.3 only if your view changed (otherwise give an empty list); "
            "answer Q10.4 only if your view did not change (otherwise no_answer).")


def answer_template(flds: list[Field]) -> str:
    """A JSON skeleton with every key, showing the expected type of each value."""
    lines = []
    for f in flds:
        v = {"single": '"<one option key>"', "multi": '["<option key>", ...]', "text": '"<your text>"'}[f.kind]
        lines.append(f'  "{f.key}": {v}')
    return "{\n" + ",\n".join(lines) + "\n}"


def answer_instruction(flds: list[Field]) -> str:
    """How to format the answer: one JSON object with exactly these keys."""
    notes = (f" The notes.* fields are your own short notes and reflections on each section "
             f"(at most {NOTES_MAX_WORDS} words each)." if any(f.key.startswith("notes.") for f in flds) else "")
    return ("Answer with one JSON object and nothing else, filling in this template (every key, "
            "in this order):\n" + answer_template(flds) + "\n"
            "For a single-choice question give one option key from the square brackets as a plain "
            f"string (for example \"small\"), or \"{NO_ANSWER}\" to leave it unanswered. For a "
            "multi-choice question give a list of option keys. Free-text fields are strings." + notes)


# ── Lenient parsing (identical for every model; used by workshop.py and score.py) ──

_KEY = re.compile(r'"([^"\n]+)"\s*:\s*')


def _extract_json(text: str) -> dict | None:
    """The JSON object in a reply, ignoring code fences and surrounding prose.

    If the object is not valid JSON (one slip, e.g. a comma for a colon, would
    otherwise lose every answer), fall back to reading each "key": value pair on
    its own, so a slip costs only the item it is in. Same rule for every model."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        obj = json.loads(text[start:end + 1])
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    pairs, dec = {}, json.JSONDecoder()
    for m in _KEY.finditer(text, start):
        try:
            value, _ = dec.raw_decode(text, m.end())
        except json.JSONDecodeError:
            continue
        pairs.setdefault(m.group(1), value)
    return pairs or None


def _match_option(v: str, options: list[str]) -> str | None:
    """An exact option key, or the one unambiguous option a shortened key refers to:
    if v has at least two '_'-separated parts and all of them occur in exactly one
    option key, that option (e.g. 'loss_3' -> 'loss_1_3'). Same rule for every model."""
    v = v.strip().strip("[]\"' ").strip()
    if v in options:
        return v
    parts = set(v.split("_"))
    if len(parts) >= 2:
        hits = [o for o in options if parts <= set(o.split("_"))]
        if len(hits) == 1:
            return hits[0]
    return None


def _normalise(f: Field, v):
    """Accept harmless format slips; return None if the value is not usable."""
    if f.kind == "single":
        if isinstance(v, list) and len(v) == 1:
            v = v[0]
        if v is None:
            return NO_ANSWER
        return _match_option(v, f.options) if isinstance(v, str) else None
    if f.kind == "multi":
        if isinstance(v, str):
            v = [v] if v else []
        if not isinstance(v, list):
            return None
        v = [_match_option(x, f.options) if isinstance(x, str) else None for x in v]
        if any(x is None for x in v) or len(set(v)) != len(v):
            return None
        return v if not f.max_select or len(v) <= f.max_select else None
    return v if isinstance(v, str) else ("" if v is None else None)


def parse_answers(text: str, flds: list[Field]) -> tuple[dict, list[str]]:
    """Usable answers from one reply, and the keys that are missing or invalid."""
    obj = _extract_json(text) or {}
    got, bad = {}, []
    for f in flds:
        v = _normalise(f, obj[f.key]) if f.key in obj else None
        if v is None:
            bad.append(f.key)
        else:
            got[f.key] = v
    return got, bad


def merge_replies(texts: list[str], flds: list[Field]) -> tuple[dict, list[str]]:
    """Merge a reply and its follow-ups: later replies fill keys still missing.
    Choice items never answered validly count as unanswered (as on the paper form).
    Returns (answers, choice items still missing)."""
    answers: dict = {}
    for t in texts:
        got, _ = parse_answers(t, flds)
        for k, v in got.items():
            answers.setdefault(k, v)
    # Free-text fields (notes, Q8.1, justifications) feed no rule: a missing or
    # broken one is left empty and never asked again. Only choice items are.
    missing = [f.key for f in flds if f.key not in answers and f.kind != "text"]
    for f in flds:
        answers.setdefault(f.key, NO_ANSWER if f.kind == "single" else [] if f.kind == "multi" else "")
    return answers, missing


def followup_instruction(flds: list[Field], missing: list[str]) -> str:
    """Ask again only for the missing or invalid keys, listing their options."""
    by_key = {f.key: f for f in flds}
    lines = []
    for k in missing:
        f = by_key[k]
        opts = (" options: " + ", ".join(f.options)) if f.options else " (text)"
        lines.append(f"  {k}:{opts}")
    sub = [by_key[k] for k in missing]
    return ("Some answers were missing or not one of the allowed options:\n" + "\n".join(lines)
            + "\nPlease answer only these, as one JSON object:\n" + answer_template(sub))


# ── JSON schema (passed to the model as a structured-output constraint) ───────

def answer_schema(flds: list[Field]) -> dict:
    props: dict[str, dict] = {}
    for f in flds:
        if f.kind == "single":
            props[f.key] = {"type": "string", "enum": f.options}
        elif f.kind == "multi":
            s = {"type": "array", "items": {"type": "string", "enum": f.options}, "uniqueItems": True}
            if f.max_select:
                s["maxItems"] = f.max_select
            props[f.key] = s
        else:
            props[f.key] = {"type": "string"}
    return {"type": "object", "properties": props, "required": [f.key for f in flds],
            "additionalProperties": False}


def validate(answers: dict, flds: list[Field]) -> list[str]:
    """Problems with one agent's answers; an empty list means valid."""
    problems = []
    if not isinstance(answers, dict):
        return ["answer is not a JSON object"]
    for f in flds:
        if f.key not in answers:
            problems.append(f"missing {f.key}")
            continue
        v = answers[f.key]
        if f.kind == "single" and v not in f.options:
            problems.append(f"{f.key}: invalid option {v!r}")
        elif f.kind == "multi":
            if not isinstance(v, list) or any(x not in f.options for x in v):
                problems.append(f"{f.key}: invalid list {v!r}")
            elif f.max_select and len(v) > f.max_select:
                problems.append(f"{f.key}: more than {f.max_select} selected")
        elif f.kind == "text" and not isinstance(v, str):
            problems.append(f"{f.key}: not a string")
    extra = set(answers) - {f.key for f in flds}
    if extra:
        problems.append(f"unexpected keys {sorted(extra)}")
    return problems
