"""Full protocol with the fake backend: structure, who hears what, re-scorability."""
import json

import pytest

from src.llm import FakeBackend
from src.score import score_run
from src.workshop_full import FullWorkshop


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    d = tmp_path_factory.mktemp("full")
    out = FullWorkshop(FakeBackend(), d, run_seed=7, log=lambda *_: None).run()
    return d, out, [json.loads(l) for l in (d / "calls.jsonl").open()]


def _seen(call) -> str:
    return "\n".join(m["content"] for m in call["request"]["messages"])


def test_structure(run):
    _, out, calls = run
    assert len(calls) == 213
    assert {k: len(v) for k, v in out["table_reports"].items()} == {"T1": 2, "T2": 2, "T3": 2}


def test_shared_prefix_until_profile(run):
    _, _, calls = run
    first = [c["request"]["messages"][1]["content"] for c in calls if c["phase"] == "baseline"]
    assert len({f.split("=== Your profile ===")[0] for f in first}) == 1


def test_tables_do_not_hear_each_other(run):
    _, _, calls = run
    t2 = ["A2", "S4", "S5", "S6"]
    for c in calls:
        if c["phase"].startswith("3_table_discussion.T1"):
            assert not any(f"\n{a}: (fake turn" in "\n" + _seen(c) for a in t2), c["phase"]


def test_plenary_hears_table_reports(run):
    _, _, calls = run
    first_plenary = next(c for c in calls if c["phase"] == "4_plenary")
    seen = _seen(first_plenary)
    assert all(f"Report from Table {t}" in seen for t in "123")


def test_pairs_hear_only_their_partner(run):
    _, _, calls = run
    p1 = [c for c in calls if c["phase"] == "6_open_discussion.P1"]
    assert p1 and all(c["agent"] in ("A1", "S4") for c in p1)
    # S4 hears A1's pair turn, but no turn from another pair in this phase
    later = [c for c in p1 if c["agent"] == "S4"][-1]
    assert "A1: (fake turn" in _seen(later)


def test_private_reflections_stay_private(run):
    _, out, calls = run
    priv = [t for t in out["transcript"] if t["room"].startswith("private:")]
    assert priv
    for t in priv[:5]:
        others = [c for c in calls if c["agent"] != t["agent"]]
        assert not any(t["text"] in _seen(c) for c in others)


def test_rescoring_from_log(run):
    d, out, _ = run
    row = score_run(d)
    sel = out["selection_endline"]
    assert row["protocol"] == "full"
    assert row["endline_selected"] == f"{sel['model']}+{sel['feature_set']}"


def test_stop_sequences_only_on_spoken_turns(run):
    _, _, calls = run
    for c in calls:
        opts = c["request"]["options"]
        if c["phase"] in ("baseline", "endline", "assessment"):
            assert "stop" not in opts, c["phase"]
        else:
            assert "\nFacilitator:" in opts["stop"] and opts["num_predict"] == 600, c["phase"]
