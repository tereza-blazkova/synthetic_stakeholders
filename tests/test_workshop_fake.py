"""End-to-end workshop with the fake backend: structure, logging and re-scorability."""
import json

from src.llm import FakeBackend
from src.score import score_run
from src.workshop import Workshop


def test_fake_workshop_end_to_end(tmp_path):
    out = Workshop(FakeBackend(), tmp_path, run_seed=7, log=lambda *_: None).run()
    calls = [json.loads(l) for l in (tmp_path / "calls.jsonl").open()]

    # 12 agents x 4 calls, every call logged with its full prompt
    assert len(calls) == 48
    assert sorted({c["phase"] for c in calls}) == ["assessment", "baseline", "endline", "plenary"]
    assert all(c["request"]["messages"] for c in calls)

    # All 12 baseline prompts share the same system prompt and materials prefix;
    # only the profile part differs.
    first = [c["request"]["messages"][1]["content"] for c in calls if c["phase"] == "baseline"]
    prefixes = {p.split("=== Your profile ===")[0] for p in first}
    assert len(prefixes) == 1 and len(set(first)) == 12

    # Plenary speakers see exactly the turns before theirs
    plen = [c for c in calls if c["phase"] == "plenary"]
    assert "You are the first to speak." in plen[0]["request"]["messages"][-1]["content"]
    assert plen[0]["agent"] + ":" in plen[1]["request"]["messages"][-1]["content"]

    # Re-scoring from the raw log reproduces the run's own selection
    row = score_run(tmp_path)
    sel = out["selection_endline"]
    assert row["endline_selected"] == f"{sel['model']}+{sel['feature_set']}"
