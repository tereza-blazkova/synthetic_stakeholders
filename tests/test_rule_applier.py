"""
The rule applier must reproduce the paper's selection exactly when fed the human
endline medians: every verdict in selection_table.tex, and logistic regression on
(b) credits + performance as the Participatory model.
"""
import re

import pytest
import yaml

from src.rule_applier import ROOT, load_metrics, ruleset_from_medians, select

GT = yaml.safe_load((ROOT / "inputs" / "human_ground_truth.yaml").read_text())
FS_NAMES = {"(a) Credits": "a_credits", "(b) + Performance": "b_credits_performance",
            "(c) + Enrollment": "c_plus_enrollment"}
MODEL_NAMES = {"FasterRisk": "fasterrisk", "Logistic regression": "logistic_regression", "XGBoost": "xgboost"}


def human_medians(administration: str) -> dict[str, str]:
    """Human medians keyed like the survey answers (Q3.2, Q4.1.low, ...)."""
    out = {}
    for qid, v in GT["questions"].items():
        key = qid.split("_")[0]
        if key in ("Q3.5", "Q3.6", "Q4.1"):
            key += "." + qid.split("_", 1)[1]
        out[key] = v[administration]
    return out


def paper_verdicts() -> dict[tuple[str, str], tuple[str, str]]:
    """(model, feature_set) -> (data verdict, explainability verdict) from selection_table.tex."""
    tex = (ROOT / "inputs" / "source_copies" / "selection_table.tex").read_text()
    verdicts, fs = {}, None
    for line in tex.splitlines():
        cells = [re.sub(r"\\textbf\{(.*?)\}", r"\1", c).strip() for c in line.rstrip("\\ ").split("&")]
        if len(cells) != 7 or cells[0] in ("Model", "Credits policy"):
            continue
        fs = FS_NAMES.get(cells[1], fs if not cells[1] else None)
        if fs and cells[0] in MODEL_NAMES:
            verdicts[(MODEL_NAMES[cells[0]], fs)] = (cells[4], cells[5])
    return verdicts


def test_endline_rules_select_logistic_regression_on_b():
    result = select(load_metrics(), ruleset_from_medians(human_medians("endline")))
    assert (result["model"], result["feature_set"]) == ("logistic_regression", "b_credits_performance")
    assert not result["fallback"]
    assert result["recall"] == 0.623
    assert set(result["blocked_feature_sets"]) == {"d_plus_lms", "e_plus_sensitive"}
    assert result["blocked_models"] == ["mlp"]


@pytest.mark.skipif(not (ROOT / "inputs" / "source_copies" / "selection_table.tex").exists(),
                    reason="inputs/source_copies/ (copied from the manuscript) is not in the public repo")
def test_every_verdict_in_the_paper_table_is_reproduced():
    verdicts = paper_verdicts()
    assert len(verdicts) == 9          # 3 models x feature sets (a)-(c)
    cells = {(c["model"], c["feature_set"]): c
             for c in select(load_metrics(), ruleset_from_medians(human_medians("endline")))["cells"]}
    for key, (data, expl) in verdicts.items():
        assert cells[key]["data_ok"] == (data == "Pass"), key
        assert cells[key]["expl_ok"] == (expl == "Pass"), key


def test_baseline_rules_run():
    """Human baseline rules: LMS is not blocked, so the sensitive step gets a price."""
    result = select(load_metrics(), ruleset_from_medians(human_medians("baseline")))
    assert result["model"] in {"fasterrisk", "logistic_regression", "xgboost", "catboost"}
