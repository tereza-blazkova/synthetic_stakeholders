"""Lenient parsing of survey replies (the same code the workshop and scorer use)."""
from src import survey as sv

FLDS = [sv.Field("Q3.2", "single", ["small", "large", sv.NO_ANSWER]),
        sv.Field("Q3.3", "single", ["small", "large", sv.NO_ANSWER]),
        sv.Field("Q3.4", "single", ["small", "large", sv.NO_ANSWER]),
        sv.Field("Q6.1", "multi", ["a", "b", "c"], 2),
        sv.Field("notes.Q3", "text")]


def test_fences_lists_and_nulls_are_tolerated():
    # Shape of a real qwen3.5 reply: code fence, one-item lists, [null]
    reply = '```json\n{"Q3.2": ["small"], "Q3.3": [null], "Q3.4": "large", "Q6.1": "a", "notes.Q3": "x"}\n```'
    got, bad = sv.parse_answers(reply, FLDS)
    assert got == {"Q3.2": "small", "Q3.3": sv.NO_ANSWER, "Q3.4": "large", "Q6.1": ["a"], "notes.Q3": "x"}
    assert bad == []


def test_invalid_and_missing_keys_are_reported():
    got, bad = sv.parse_answers('{"Q3.2": "loss_3", "Q6.1": ["a", "b", "c"]}', FLDS)
    assert bad == ["Q3.2", "Q3.3", "Q3.4", "Q6.1", "notes.Q3"]


def test_shortened_keys_resolve_only_when_unambiguous():
    f = sv.Field("Q5.1", "single", ["no_decrease", "loss_1_3", "loss_5", "loss_10", "not_sure", sv.NO_ANSWER])
    assert sv.parse_answers('{"Q5.1": "loss_3"}', [f])[0] == {"Q5.1": "loss_1_3"}
    assert sv.parse_answers('{"Q5.1": "loss"}', [f])[1] == ["Q5.1"]          # ambiguous
    assert sv.parse_answers('{"Q5.1": "loss_7"}', [f])[1] == ["Q5.1"]        # no such option


def test_followups_fill_gaps_and_the_rest_counts_as_unanswered():
    first = '{"Q3.2": "small", "Q6.1": [], "notes.Q3": ""}'
    followup = 'Sure! {"Q3.3": "large"}'
    answers, missing = sv.merge_replies([first, followup], FLDS)
    assert answers["Q3.2"] == "small" and answers["Q3.3"] == "large"
    assert missing == ["Q3.4"] and answers["Q3.4"] == sv.NO_ANSWER


def test_one_syntax_slip_costs_only_its_own_item():
    # Real qwen3.5 slip: a comma instead of a colon after "notes.Q3"
    reply = '{\n  "Q3.2": "small",\n  "notes.Q3", "",\n  "Q3.3": "large",\n  "Q3.4": "[large]",\n  "Q6.1": ["a"]\n}'
    got, bad = sv.parse_answers(reply, FLDS)
    assert got == {"Q3.2": "small", "Q3.3": "large", "Q3.4": "large", "Q6.1": ["a"]}
    assert bad == ["notes.Q3"]


def test_missing_free_text_is_not_asked_again():
    answers, missing = sv.merge_replies(['{"Q3.2": "small", "Q3.3": "large", "Q3.4": "large", "Q6.1": []}'], FLDS)
    assert missing == [] and answers["notes.Q3"] == ""
