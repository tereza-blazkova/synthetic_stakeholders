# Rule checklist (pre-registered)

Written on 2026-10-16, **before any agent output exists**. Do not edit after the
first pilot run except to fix typos; any substantive change is logged at the
bottom with date and reason.

Ground truth: `inputs/human_ground_truth.yaml` (from the paper's `tab:median-shift`).
Survey option keys: `inputs/materials/survey.yaml`.

## 1. Unit of coding and how coding is done

- **Unit:** one run = one 12-agent workshop.
- Each agent's baseline and endline survey answers are structured JSON, so every
  checklist item below is scored **by code**, deterministically. No LLM coding is
  needed for rules. Tereza's spot-check covers the aggregation: for 3 random runs
  she recomputes 3 medians by hand from the logged answers.
- LLM-assisted coding is used only for free text (Q8.1, Q10.6, assessment
  justifications), which feeds no checklist item. Free-text coding is descriptive,
  not part of this pre-registration.

## 2. Panel aggregation (identical to the paper)

For each item, over the 12 agents' answers:

1. Drop `not_sure`, `prefer_not` and unanswered (null).
2. Map the remaining answers to ranks on the item's ordinal scale (below).
3. Odd n: the middle answer. Even n: if the two middle answers are equal, that
   category. If they differ, take the one with **more responses**; if the counts
   are equal, take the **more restrictive** one.
4. If every answer was dropped, the item is `no_answer` (scored as a mismatch).

Ordinal scales, least → most restrictive:

| Items | Order |
|---|---|
| Q3.2–Q3.4, Q3.5 ×7, Q4.1 ×4 (gain) | `no_threshold` < `small` < `moderate` < `large` < `never` |
| Q3.6 ×7 | `acceptable_regardless` < `only_if_fairness_improves` < `never` |
| Q5.1 | `loss_10` < `loss_5` < `loss_1_3` < `no_decrease` |
| Q5.2 | `equal_recall` < `both` < `equal_fpr` |
| Q6.2 | `continuously` < `twice_year` < `once_year` |
| Q7.1, Q7.2 | `many` < `slightly_many` < `balance` < `slightly_fewer` < `fewer` |
| Q9.1 | `not_at_all` < `occasionally` < `half` < `often` < `always` |

"Restrictive" is defined by the paper only for gain scales (a larger required
gain). For the other scales the order above is a convention fixed here
(restrictive = less acceptance of the model or less contact). It matters only
on an equal-count tie.

Q6.1 (multi-select, up to two): the panel's top-3 options by count; options
tied for third place are all included.

## 3. Checklist items

Human value = endline median unless stated.

### Block R: selection rules (primary; 7 items)

| ID | Item | Human |
|---|---|---|
| R1 | Q3.2 course performance | `small` |
| R2 | Q3.3 admissions & enrolment | `large` |
| R3 | Q3.4 LMS (Absalon) activity | `never` |
| R4 | Q4.1 high explainability | `moderate` |
| R5 | Q4.1 moderate explainability | `small` |
| R6 | Q4.1 low explainability | `moderate` |
| R7 | Q4.1 very low explainability | `never` |

### Block S: rest of the assessed specification (secondary; 16 items)

| ID | Item | Human |
|---|---|---|
| S1–S7 | Q3.5 age, gender, nationality, disability, race/ethnicity, first-gen, financial aid | `large` (all seven) |
| S8–S14 | Q3.6, same seven attributes | `only_if_fairness_improves` (all seven) |
| S15 | Q5.1 accuracy loss for equal performance | `loss_1_3` |
| S16 | Q5.2 fairness goal | `equal_recall` |

### Block T: not in the assessed specification (tertiary; 5 items)

| ID | Item | Human |
|---|---|---|
| T1 | Q6.2 outreach frequency | `continuously` (paper: "each model update"; mapping to confirm) |
| T2 | Q7.1 selectivity, generic email | `slightly_many` |
| T3 | Q7.2 selectivity, personal contact | `slightly_many` |
| T4 | Q9.1 thinking about peers | `often` |
| T5 | Q6.1 top-3 interventions | {`generic_email`, `personalized_email`, `meeting_invitation`} |

### Block D: structural checks (binary)

| ID | Check | Human |
|---|---|---|
| D1 | LMS data blocked (R3 = `never`) | yes |
| D2 | Very low explainability blocked (R7 = `never`) | yes |
| D3 | Course performance is cheaper than enrolment data (rank R1 < rank R2) | yes |
| D4 | No sensitive attribute is acceptable at `no_threshold` or `small` (S1–S7 all ≥ `moderate`) | yes |

## 4. Scores per run

For each item in R, S, T1–T4:

- **exact**: 1 if the panel category equals the human category, else 0.
- **distance**: absolute difference in ranks (0 = exact).
- **within1**: 1 if distance ≤ 1.

For T5: Jaccard overlap between the panel's top-3 set and the human set.

Run-level scores:

- **R-coverage** (primary) = exact matches in R, out of 7.
- **S-coverage** = exact matches in S, out of 16.
- **R-within1** = within-one-step matches in R, out of 7.
- **D-score** = D checks passed, out of 4.

## 5. Decision outcomes

The panel's endline R1–R7 become a rule set, applied by
`src/rule_applier.py` to `inputs/metrics_2021.csv` with the paper's algorithm
(main.tex "Workshop-grounded model selection"):

- Gain coding: `no_threshold` 0, `small` 1 pp, `moderate` 5 pp, `large` 10 pp,
  `never` = block. Blocking a data step also blocks every later step.
- Sensitive step (e) is only reachable if LMS is not blocked. Its price is
  then the **most restrictive** of the panel's Q3.5 medians for age, gender
  and nationality (the three sensitive attributes in the data), following
  `BASELINE_RULES` in `ews_code/src/workshop_rules.py`. The paper sets no
  price for this step, because the human panel blocked LMS.
- If nothing passes: fall back to the most explainable model on credits only.
- If a selection item's median is `no_answer` (everyone left it open), the step
  is treated as `never` (no consent given).
- If every ML model is blocked (high explainability = `never`), the selection is
  the credits policy (status quo): decision_match = 0; recall and FPR gaps are
  computed for the credits policy.
- Before any run, a test must confirm that the human endline rules reproduce
  every verdict in `selection_table.tex` and select logistic regression on (b).

Outcomes per run:

- **decision_match**: selected (model, feature set) == (`logistic_regression`, `b_credits_performance`).
- **model_match** and **feature_set_match** separately.
- **recall_gap** = recall(selected) − 0.623.
- **fpr_gap** = FPR(selected) − 0.1409 (derived FPR, `inputs/metrics_2021.csv`).

The same procedure on baseline medians gives the panel's pre-deliberation
choice. Human baseline rules select (per `BASELINE_RULES`) a configuration that
is computed by the same code, not taken from the paper.

## 6. Secondary outcomes

- **Deliberation shift:** for each item in R and S plus T1–T4, the direction of
  the baseline→endline change (more restrictive / same / more permissive).
  Compare with the human direction; report the share of items with the same
  direction. Human: most changes toward more restriction; exceptions are R1
  and R6 (more permissive).
- **Acceptability:** distribution of the 12 assessments over `support`,
  `support_with_reservations`, `object_no_block`, `block`, `prefer_not`.
  Human (n = 10, no counts published): a majority `support`, a minority `block`.
  Report the share of runs with a `support` majority and with at least one `block`.
- **Q10:** share reporting more supportive / more critical (human: 6 / 5 of 11).

## 7. Stability (per model)

- **Modal-choice share:** share of runs whose selected configuration equals that
  model's most frequent configuration.
- **Spread:** range and SD of R-coverage and S-coverage across runs.
- **Item agreement:** for each R item, share of runs giving the modal category.

## 8. Reporting

Descriptive only. Proportions over n ≈ 10 runs per model with Wilson 95%
intervals. No significance tests between models.

**Chance reference.** Every agreement score is reported next to the score of
2,000 simulated panels of 12 uniformly random respondents (`src/chance.py`,
`analysis/results/chance_reference.csv`). Computed 2026-10-16, before any model
output: R-coverage 1.66 of 7, S-coverage 6.38 of 16, T-coverage 0.97 of 4,
decision match 0.139. S-coverage is high by chance because medians of random
answers on 3-option items land on the middle option, which is the human answer
for Q3.6.

**Interpretation note.** The human *baseline* rules also select logistic
regression on (b): deliberation changed the rules (LMS and sensitive data
blocked) but not the 2021 choice. Decision agreement is therefore a coarse
outcome; rule agreement (R, S, D) carries most of the information.

Pilot runs (`runs/<model>/pilot/`) are used only to check the harness and are
never scored.

## Change log

- 2026-10-16: created.
- 2026-10-16 (before any model output): design changed to deliberation-lite
  (baseline survey, one plenary round, endline survey, assessment; no tables,
  Q10.5 dropped because its options refer to tables). Added: `no_answer`
  selection items count as `never`; all-ML-blocked → credits policy; chance
  reference; pilot runs excluded from scoring.
- 2026-10-16, during the first pilot (harness only, no change to any scoring
  rule): Ollama ignored the JSON-schema constraint for qwen3.5, so no model gets
  a constraint. Answers are parsed leniently and identically for every model
  (`src/survey.py`): code fences and prose around the JSON are ignored; one-item
  lists are unwrapped; `null` = `no_answer`; a shortened key is accepted only if
  all its parts occur in exactly one option key (e.g. `loss_3` → `loss_1_3`).
  Missing or invalid items are asked again in up to 2 follow-up turns, like a
  survey tool flagging skipped questions; items still missing count as
  `no_answer`, as blank items did in the paper. The scorer rebuilds answers from
  the logs with the same code.
- 2026-10-17, after the qwen3.5 pilot (harness only): follow-ups now ask only
  for missing choice items; a missing or malformed free-text field (notes, Q8.1,
  Q10.6, assessment justification) is left empty, since no rule uses it. Same
  for every model; the scorer uses the same code.
- 2026-10-20, before any large-tier output (Tereza's decision, UCloud grant):
  two more settings, scored with exactly the same checklist, chance reference
  and rules: large tier (Qwen 3.5 27B, Gemma 3 27B, Mistral Small 3.2 24B) with
  the lite protocol, and the same large tier with the full multi-phase protocol
  (`facilitator_script.yaml`). Summaries are per (model, protocol). The full
  protocol also asks Q10.5 (its options refer to tables), which no score uses.
  Planned comparisons: size within lite (small vs large), protocol within the
  large tier (lite vs full); small-lite vs large-full is never compared directly.
- 2026-10-20, after the large-tier pilots (harness only, no scoring rule changed):
  in the full-protocol pilot, Mistral Small 3.2 sometimes kept writing past its own
  turn, scripting other speakers' and the facilitator's lines (15 of 177 spoken
  turns; 10 hit the 4,000-token cap) and pushing prompts to 98% of the context
  window. For every model, spoken and private turns (never surveys) now stop when a
  reply starts a new line with a speaker tag (`A1:`…`S9:`, `Facilitator:`) and are
  capped at 600 tokens (~450 words; the target is 120). The large-tier context
  window was raised from 40,960 to 65,536 tokens. Checked on all earlier output:
  none of the 360 small-tier spoken turns, nor any Qwen or Gemma pilot turn,
  contains such a line or exceeds 600 tokens, so the change is a no-op for them.
  The affected Mistral full pilot was archived (`runs/_superseded/`) and re-run.

## Exploratory analyses (NOT pre-registered)

Added 2026-10-20, after the small-tier results had been seen, for a Cooperative
AI reading of the results (Tereza's decision). Computed by `src/exploratory.py`
from the logs, on the 23 assessed items; always reported as exploratory:
within-panel answer spread (baseline vs endline), conformity (answers moving
toward vs away from the panel's baseline median), and speaking-order influence
(endline median vs the first plenary speaker's baseline answers, against the
other 11 agents). The checklist outcomes above are unchanged.

- **2026-10-22 (Tereza): reporting scope.** Agreement with the human workshop is
  reported only for the full-protocol runs (the only setting that replays the
  human process). Added (exploratory, post hoc, no change to the pre-registered
  items): baseline→endline movement of the panel medians on the 23 assessed items,
  split into stricter / more permissive, rules moved, and the share of the
  humans' own moves that a panel repeated in the same direction.

