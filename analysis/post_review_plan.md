# Post-review analysis plan (fixed before any post-review run or re-score)

Written 2026-11-07, 05:00 UTC, **before** any post-review model call and before any new
re-scoring. The poster and the website paper use these analyses after the reviews
(accepted as a poster, Nov 5). Everything here is **exploratory / post-review**. It is
reported apart from the pre-registered results (`analysis/rule_checklist.md`), and the checklist,
the aggregation and the scoring code stay unchanged. Changes to this file after the first
post-review call are logged at the bottom with date and reason.

Reference setting for every comparison: **large tier, full protocol, 20 runs per family**
(`runs/full/<model>/run01..run20`), the only setting compared with the humans in the paper.

## A. Re-scoring of existing runs (no model calls)

- **A1 Random-panel floor.** `src/chance.py` (2000 panels, unchanged). Report the mean and 2.5/97.5
  percentiles of rules matched (of 7) and the decision-match rate, next to each family and the
  humans' own baseline→endline match (3 of 7).
- **A2 What counts as a match.** Primary (as pre-registered): the panel's endline median equals
  the human endline category (`R_coverage`). Sensitivity: within one ladder step (`R_within1`,
  already computed by `src/score.py`).
- **A3 Within-family spread.** Per family: SD and range of `R_coverage` over the 20 runs, a bootstrap
  95% CI of the mean (10,000 resamples, seed 1), and the number of distinct (7-rule configuration,
  selected model) pairs.
- **A4 Start vs change.** Per family: rules matched at baseline (panel baseline medians vs human
  endline) and at endline. Per item (23 items): did the panel median move, and was the direction the
  same as the humans'? Report the share of the endline gap already present at baseline.
- **A5 Votes vs own answers.** Cross-tab each agent's vote with whether the panel's specification
  agrees with that agent's own endline answers on the 7 rules (count of agreeing rules: 0–7).
- **A6 Content (descriptive).** Agent text only (turns and justifications), never human text. Fixed
  keyword lists per theme, written before reading: purpose ("why predict", "should the university",
  "purpose"), surveillance/privacy ("surveil", "privacy", "monitor"), disagreement ("disagree",
  "object", "oppose"), stigma/harm ("stigma", "label", "flagged"). Report the share of runs and of agents
  that raise each theme at least once. Tereza spot-checks 20 random hits.

## B. Post-review runs (UCloud, approved by Tereza 2026-11-06/07)

All runs: same pinned Ollama version (0.30.11), temperature 1.0, reasoning off, num_ctx 65536, same
prompts and scoring as the reference setting, except the one change named. Logs under
`runs/post_review/<condition>/...`.

### B1 Card format (replay of the final assessment only)
Design and analysis as fixed in `inputs/variants/card_variants.yaml`: 7 card conditions
(incl. the `baseline_replay` control) and 3 header variants. For each of the 60 reference workshops,
each agent's logged final-assessment prompt is re-sent with only the card or header text replaced;
fresh seeds; same follow-up rule for invalid answers. Outcome: share of each option (Wilson 95%
intervals) per family and pooled; paired agent-level comparison with `baseline_replay`
(share of agents who change their vote, and in which direction). Also reported: how far
`baseline_replay` reproduces the original votes (sampling noise).

### B2 Persona wording (full reruns)
Two independent paraphrases of the backstories (`inputs/variants/personas_paraphrase_{a,b}.yaml`),
20 runs per family each, same seeds 101–120 as the reference. Outcomes: rules matched (mean, bootstrap
CI), human model chosen (k/20, Wilson), modal-choice share, vote distribution. Each paraphrase is compared
with the reference (difference in means, bootstrap CI), and the two paraphrases with each other.
Claim allowed: "with these two alternative wordings, results changed / did not change by …".
Never "results are insensitive to persona wording" in general.

### B3 A larger open-weight model
One larger open-weight model (exact version proposed to Tereza before the full batch), full protocol,
20 runs, seeds 101–120. Same outcomes as B2, compared descriptively with the three reference families.
It is an additional model, not a size manipulation within a family, unless the same family is used.

### B4 Higher precision
The three reference models at 8-bit (q8_0) instead of 4-bit (q4_K_M), full protocol, 20 runs each,
seeds 101–120. Same outcomes as B2, each compared with its own 4-bit reference.

## C. Reporting rules
- n = 20 per cell: proportions with Wilson intervals, means with bootstrap CIs, descriptive only;
  no significance tests, no claims beyond the conditions run.
- Every post-review number is labelled "post-review" in the paper and on the poster.
- Agreement with the human workshop is "agreement with one human reference", never validity.

## Change log
- 2026-11-07 (compute only, no change to conditions, prompts, seeds or outcomes): runs are split
  over two UCloud jobs on the same storage. Job 1 (1x B200, all models time-sliced with CUDA MPS):
  B1, Mistral B2, Mistral q8. Job 2 (3x B200, from ~15:30 CET): Gemma and Qwen B2, Gemma and Qwen
  q8, Qwen 122B. Several Ollama servers and parallel slots per GPU change speed only; batch
  composition can change floating-point results, as in the reference runs.
- 2026-11-09 (compute only, no change to conditions, prompts, seeds or outcomes): both jobs ended
  on Nov 7/8 with Gemma and Qwen B2, Gemma and Qwen q8 and 122B runs 12-20 unfinished. Resumed at
  01:30 CET on two new jobs (3x and 2x B200) with `ucloud/launch_resume_2026-11-09.sh`; each job
  owns whole model folders. Interrupted workshops were moved to `_incomplete_*` and redone from scratch.
- 2026-11-09 (**new exploratory condition, added after seeing results**): B4 showed Gemma at q8
  departing strongly from Gemma at q4 (25% vs 96% "with reservations"; 10/20 modal choice). Tereza
  approved one extra condition: Gemma 3 27B unquantised (`gemma3:27b-it-fp16`, condition
  `precision_fp16`), pilot + 20 runs, same seeds, options, prompts and scoring as B4. It is reported
  as post hoc and exploratory, never as part of the pre-specified B1-B4.
