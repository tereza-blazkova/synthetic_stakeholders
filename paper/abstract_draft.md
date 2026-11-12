# Abstract drafts (for Tereza to edit)

Numbers below are final (all 150 workshops, scored 2026-10-21); the paper
itself takes them from `analysis/tables/numbers.tex`.

## Title options

1. Synthetic Stakeholders? Agreement and Stability of Open-Weight LLM Agent Panels in Participatory Model Selection (current)
2. Can a Laptop Stand In for a Workshop? Small Open-Weight LLM Panels in Participatory Model Selection

## OpenReview abstract (final; identical to the paper's abstract; due Sun Oct 25, 23:59 UTC)

LLM agents are proposed as synthetic participants, but rarely compared with a real
deliberation. We replay a three-hour workshop in which 9 students and 3 advisors set
the rules for selecting a university dropout early-warning model, using 12-agent
panels from three open-weight model families under the same scripted protocol (20
runs each). On average, the panels matched only one to three of the seven rules the
humans set, and two of the three families chose the same model, not the humans' one, in every run. Deliberation barely changed the agents' answers (a
few of 23 items; humans: 10), and they hedged: 97% of their final votes were "support
with reservations", while the humans' votes ranged from support to block.

## Two-page outline

1. **Motivation.** Synthetic participants in participatory AI; risk of
   replacing, not supplementing, stakeholders; need for evaluation against real
   deliberation outcomes. Cite the prior human workshop study.
2. **Human ground truth.** 9 students + 3 advisors, baseline and endline survey,
   median rules on two ladders (data, explainability), applied to 2021 metrics →
   logistic regression on credits + performance (recall 62% vs 24% for the
   credits rule). Note: the human baseline rules select the same model, so
   rule agreement is the more informative outcome.
3. **Design.** One factor: LLM family (3 open-weight families, 3-4B, same
   4-bit quantisation, local). Fixed personas built from the human panel's
   demographic counts; scripted facilitator; deliberation-lite protocol (survey,
   one plenary round, survey, acceptability card); 10 seeded runs per family,
   speaking orders matched across families. Rules applied programmatically.
4. **Results.** Figure: per-rule agreement and decision agreement vs a random
   panel. Table: rule coverage, decision match with Wilson intervals, modal-choice
   share (stability), recall gap, format failures.
5. **Bounded claims and limitations.** Small local models; abridged
   deliberation; personas from marginals; one workshop, one university; JSON
   format failures handled by follow-ups.
6. **Ongoing work.** Full multi-phase protocol and larger models (UCloud GPU
   application submitted); closed frontier models; persona detail; mixed-model
   panels; prompt-wording robustness; comparing deliberation content (subject to
   consent).
