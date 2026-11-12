"""Post-review B1/B2: card variants, step-8 replay, persona variants (fake backend only)."""
import json

import pytest
import yaml

from src import personas, variants as V
from src.llm import FakeBackend
from src.replay_assessment import replay_run
from src.workshop import ROOT
from src.workshop_full import FullWorkshop

DOC = V.load()


def test_baseline_card_is_byte_identical():
    assert V.card_text(DOC, "baseline_replay", 101, "A1") == DOC["baseline_text"].strip()


def test_baseline_card_matches_facilitator_script():
    script = yaml.safe_load((ROOT / "inputs/materials/facilitator_script.yaml").read_text())
    text = next(s["text"] for p in script["phases"] if p["id"] == "8_final_assessment"
                for s in p["steps"] if s.get("structured"))
    assert text.strip() == DOC["baseline_text"].strip()


@pytest.mark.parametrize("cond", V.conditions(DOC))
def test_every_condition_keeps_all_five_options(cond):
    order = V.card_order(DOC, cond, 101, "S1")
    text = V.card_text(DOC, cond, 101, "S1")
    assert sorted(order) == sorted(V.BASELINE_ORDER) and order[-1] == "prefer_not"
    pos = [text.index(f"[{k}]") for k in order]
    assert pos == sorted(pos)                       # shown in exactly the logged order


def test_shuffle_is_seeded_per_agent():
    a = V.card_order(DOC, "shuffled_per_agent", 101, "S1")
    assert a == V.card_order(DOC, "shuffled_per_agent", 101, "S1")
    orders = {tuple(V.card_order(DOC, "shuffled_per_agent", 101, x)) for x in ["A1", "A2", "S1", "S2", "S3"]}
    assert len(orders) > 1


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    root = tmp_path_factory.mktemp("src")
    d = root / "fake" / "run01"
    FullWorkshop(FakeBackend(), d, run_seed=101, log=lambda *_: None).run()
    return d


def test_replay_changes_only_the_condition(source, tmp_path):
    out = tmp_path / "card"
    replay_run(FakeBackend(), source, out, V.conditions(DOC), DOC, log=lambda *_: None)
    orig = {}
    for l in (source / "calls.jsonl").open():
        c = json.loads(l)
        if c["phase"] == "assessment" and c["attempt"] == 1:
            orig[c["agent"]] = c["request"]["messages"]
    for cond in V.conditions(DOC):
        d = out / cond / "fake" / "run01"
        assessment = json.loads((d / "assessment.json").read_text())
        assert sorted(assessment) == sorted(orig)
        for l in (d / "calls.jsonl").open():
            c = json.loads(l)
            if c["attempt"] != 1:
                continue
            new, old = c["request"]["messages"], orig[c["agent"]]
            assert new[:-1] == old[:-1]                     # whole history unchanged
            expected = V.apply_condition(old[-1]["content"], DOC, cond, 101, c["agent"])
            assert new[-1]["content"] == expected
            assert (new == old) == (cond == "baseline_replay")
            assert c["condition"] == cond and c["card_order"] == V.card_order(DOC, cond, 101, c["agent"])


def test_replay_resumes_and_redoes_incomplete(source, tmp_path):
    out = tmp_path / "card"
    replay_run(FakeBackend(), source, out, ["baseline_replay", "reversed_order"], DOC, log=lambda *_: None)
    done = out / "baseline_replay" / "fake" / "run01" / "assessment.json"
    before = done.read_text()
    (out / "reversed_order" / "fake" / "run01" / "assessment.json").unlink()   # simulate an interruption
    replay_run(FakeBackend(), source, out, ["baseline_replay", "reversed_order"], DOC, log=lambda *_: None)
    assert done.read_text() == before
    calls = (out / "reversed_order" / "fake" / "run01" / "calls.jsonl").read_text().splitlines()
    assert len(calls) == 12                                       # redone from scratch, not appended


@pytest.mark.parametrize("variant", ["a", "b"])
def test_persona_variants_change_backstories_only(variant):
    orig = personas.load_personas()
    path = ROOT / f"inputs/variants/personas_paraphrase_{variant}.yaml"
    new = personas.load_personas(path)
    personas.check_marginals(new)
    for k in ("system_prompt", "profile_template", "labels"):
        assert new[k] == orig[k]
    for key in ("advisors", "students"):
        for o, n in zip(orig[key], new[key]):
            assert {**o, "backstory": None} == {**n, "backstory": None}
            assert o["backstory"] != n["backstory"]


def test_workshop_uses_and_hashes_persona_variant(tmp_path):
    path = ROOT / "inputs/variants/personas_paraphrase_a.yaml"
    w = FullWorkshop(FakeBackend(), tmp_path, run_seed=101, log=lambda *_: None, personas_path=path)
    out = w.run()
    first = next(json.loads(l) for l in (tmp_path / "calls.jsonl").open())
    assert "You advise students on how to plan their studies" in first["request"]["messages"][-1]["content"] \
        or any("You advise students on how to plan" in json.loads(l)["request"]["messages"][-1]["content"]
               for l in (tmp_path / "calls.jsonl").open())
    hashes = out["run_meta"]["input_sha256"]
    assert "inputs/variants/personas_paraphrase_a.yaml" in hashes and "inputs/personas.yaml" not in hashes


class FlakyBackend(FakeBackend):
    """Invalid JSON on the first try of each prompt, valid afterwards (exercises follow-ups)."""

    def chat(self, messages, schema, seed, extra=None):
        r = super().chat(messages, schema, seed, extra)
        if "Some answers were missing" not in messages[-1]["content"]:
            r["text"] = "I support it with reservations, but I forgot the JSON."
        return r


def test_replay_followups_match_workshop_rule(source, tmp_path):
    from src import survey as sv
    out = tmp_path / "card"
    replay_run(FlakyBackend(), source, out, ["reversed_order"], DOC, log=lambda *_: None)
    calls = [json.loads(l) for l in (out / "reversed_order" / "fake" / "run01" / "calls.jsonl").open()]
    assert len(calls) == 24 and {c["attempt"] for c in calls} == {1, 2}
    a1 = [c for c in calls if c["agent"] == "A1"]
    first, second = a1[0]["request"]["messages"], a1[1]["request"]["messages"]
    order = V.card_order(DOC, "reversed_order", 101, "A1")
    flds = [sv.Field("choice", "single", order), sv.Field("justification", "text")]
    assert second[:-2] == first
    assert second[-2] == {"role": "assistant", "content": a1[0]["response"]}
    assert second[-1] == {"role": "user", "content": sv.followup_instruction(flds, ["choice"])}
    assert "options: block, object_no_block, support_with_reservations, support, prefer_not" in second[-1]["content"]
    assessment = json.loads((out / "reversed_order" / "fake" / "run01" / "assessment.json").read_text())
    assert all(v["choice"] in order for v in assessment.values())


def test_resume_refuses_changed_inputs(source, tmp_path):
    out = tmp_path / "card"
    replay_run(FakeBackend(), source, out, ["baseline_replay"], DOC, log=lambda *_: None)
    meta_path = out / "baseline_replay" / "fake" / "run01" / "replay_meta.json"
    meta = json.loads(meta_path.read_text())
    meta["variants_sha256"] = "something else"
    meta_path.write_text(json.dumps(meta))
    with pytest.raises(SystemExit):
        replay_run(FakeBackend(), source, out, ["baseline_replay"], DOC, log=lambda *_: None)
