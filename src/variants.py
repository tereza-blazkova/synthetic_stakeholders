"""
Post-review sensitivity variants of the final acceptability card (B1).

Source of all wording: inputs/variants/card_variants.yaml (approved by Tereza
2026-11-07). This module only renders that file; it never invents text.

    card_text(cond, run_seed, agent)  -> the card exactly as the agent sees it
    card_order(cond, run_seed, agent) -> option keys in the order shown
    apply_condition(prompt, cond, ...) -> a logged assessment prompt with only the
                                          card (or one header phrase) replaced

The baseline order rendered from `options` reproduces the original card byte for
byte (tests/test_variants.py), so `baseline_replay` sends exactly the original prompt.
"""
from __future__ import annotations

import random
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
VARIANTS_PATH = ROOT / "inputs" / "variants" / "card_variants.yaml"
BASELINE_ORDER = ["support", "support_with_reservations", "object_no_block", "block", "prefer_not"]
LEAD = ("Please complete the anonymous final assessment card. Choose one option and briefly justify\n"
        "your choice in writing.")
KEY_WIDTH, DEF_INDENT = 28, 30         # column layout of the original card


def load(path: Path = VARIANTS_PATH) -> dict:
    return yaml.safe_load(path.read_text())


def conditions(doc: dict) -> list[str]:
    """All B1 conditions: card variants first (control first), then header variants."""
    return list(doc["card_variants"]) + list(doc["spec_header_variants"])


def card_order(doc: dict, cond: str, run_seed: int, agent: str) -> list[str]:
    v = doc["card_variants"].get(cond)
    if v is None:                                   # header variants keep the baseline card
        return list(BASELINE_ORDER)
    if v["order"] == "random_first_four":
        first = BASELINE_ORDER[:4]
        random.Random(f"{run_seed}:{agent}:card_order").shuffle(first)
        return first + ["prefer_not"]
    order = list(v["order"])
    assert sorted(order) == sorted(BASELINE_ORDER) and order[-1] == "prefer_not", cond
    return order


def card_text(doc: dict, cond: str, run_seed: int, agent: str) -> str:
    v = doc["card_variants"].get(cond, {})
    labels = {k: o["label"] for k, o in doc["options"].items()}
    defs = {k: o["definition"] for k, o in doc["options"].items()}
    labels.update(v.get("label_override") or {})
    if v.get("definition_override") == "all_null":
        defs = {k: None for k in defs}
    else:
        defs.update(v.get("definition_override") or {})
    lines = [LEAD]
    for k in card_order(doc, cond, run_seed, agent):
        lines.append("  " + f"[{k}]".ljust(KEY_WIDTH) + labels[k])
        if defs[k]:
            lines.append(" " * DEF_INDENT + f"({defs[k]})")
    return "\n".join(lines)


def _replace_once(text: str, old: str, new: str, what: str) -> str:
    n = text.count(old)
    if n != 1:
        raise ValueError(f"{what}: expected exactly one occurrence in the prompt, found {n}")
    return text.replace(old, new)


def apply_condition(prompt: str, doc: dict, cond: str, run_seed: int, agent: str) -> str:
    """The original final-assessment user message with only this condition's change."""
    out = _replace_once(prompt, doc["baseline_text"].strip(), card_text(doc, cond, run_seed, agent),
                        f"{cond}: baseline card")
    hv = doc["spec_header_variants"].get(cond)
    if hv:
        out = _replace_once(out, hv["replace"]["from"], hv["replace"]["to"], f"{cond}: header phrase")
    return out
