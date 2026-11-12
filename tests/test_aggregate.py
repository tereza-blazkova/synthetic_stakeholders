"""Median and tie rules (analysis/rule_checklist.md section 2)."""
from src.aggregate import GAIN, panel_median


def test_odd_n_takes_middle():
    assert panel_median(["small", "large", "moderate"], GAIN) == ("moderate", None)


def test_even_n_equal_middles():
    assert panel_median(["small", "moderate", "moderate", "large"], GAIN) == ("moderate", None)


def test_tie_resolved_by_count():
    # middles are small | moderate; small has 3 responses, moderate 1
    assert panel_median(["small"] * 3 + ["moderate", "large", "large"], GAIN) == ("small", "count")


def test_tie_resolved_conservatively():
    # middles are small | large, each with 2 responses -> the more restrictive
    assert panel_median(["small", "small", "large", "large"], GAIN) == ("large", "conservative")


def test_excluded_answers_are_dropped():
    assert panel_median(["no_answer", "not_sure", "never"], GAIN) == ("never", None)
    assert panel_median(["no_answer", "prefer_not"], GAIN) == ("no_answer", None)
