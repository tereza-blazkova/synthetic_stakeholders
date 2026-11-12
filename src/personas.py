"""
Personas: rendering each agent's profile and checking the panel against the
paper's participant table.

Source: inputs/personas.yaml. The expected counts below are the paper's
tab:demographics_workshop (inputs/source_copies/main_tex_SI_workshop_tables_L676-800.tex).
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PERSONAS_PATH = ROOT / "inputs" / "personas.yaml"

# Paper, tab:demographics_workshop. Danish/Faroese is one category there.
EXPECTED_STUDENTS = {
    "gender": {"female": 6, "male": 2, "non-binary": 1},
    "degree": {"bachelor": 4, "master": 5},
    "stage": {"first_year": 3, "mid_programme": 4, "near_completion": 2},
    "faculty": {"Humanities": 1, "Social Sciences": 1, "Natural Sciences": 4, "Law": 1,
                "Health and Medical Sciences": 2},
    "nationality_group": {"danish_or_faroese": 5, "other_eu": 1, "non_eu": 3},
    "disability": {"yes": 4, "no": 5},
    "prior_dropout": {"yes": 4, "no": 5},
}
EXPECTED_ADVISORS = {"gender": {"female": 2, "male": 1}}


def load_personas(path: Path = PERSONAS_PATH) -> dict:
    return yaml.safe_load(path.read_text())


def agents(doc: dict) -> list[dict]:
    """All 12 agents, advisors first (A1-A3), then students (S1-S9)."""
    return ([{**a, "role": "advisor"} for a in doc["advisors"]]
            + [{**s, "role": "student"} for s in doc["students"]])


def check_marginals(doc: dict) -> None:
    """Raise if the persona counts differ from the paper's participant table."""
    students = doc["students"]
    for attr, expected in EXPECTED_STUDENTS.items():
        if attr == "nationality_group":
            got = Counter("danish_or_faroese" if s["nationality"] in ("danish", "faroese")
                          else s["nationality"] for s in students)
        else:
            got = Counter(s[attr] for s in students)
        if dict(got) != expected:
            raise ValueError(f"students {attr}: {dict(got)} != paper {expected}")
    got = Counter(a["gender"] for a in doc["advisors"])
    if dict(got) != EXPECTED_ADVISORS["gender"]:
        raise ValueError(f"advisors gender: {dict(got)} != paper {EXPECTED_ADVISORS['gender']}")


def profile_text(doc: dict, agent: dict) -> str:
    """The profile block for one agent, filled from the templates in personas.yaml."""
    labels = doc["labels"]
    if agent["role"] == "advisor":
        profile = doc["profile_template"]["advisor"].format(**agent)
    else:
        profile = doc["profile_template"]["student"].format(
            **agent,
            degree_label=labels["degree"][agent["degree"]],
            stage_label=labels["stage"][agent["stage"]],
            nationality_label=labels["nationality"][agent["nationality"]],
        )
    return (f"Your name tag: {agent['id']}\n{profile.strip()}\n\n"
            f"{' '.join(agent['backstory'].split())}")
