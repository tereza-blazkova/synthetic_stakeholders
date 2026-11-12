# Sources

Everything in `inputs/` and where it came from. Copies were made on 2026-10-16
with `cp`/`sed` (read-only on the source side). Source repos:
`~/projects/ews-paper/` (paper, real aggregate numbers) and `~/projects/ews_code/`
(pipeline on synthetic data; used for logic only, never for numbers).
**When code and paper disagree, the paper wins.**

## Verbatim copies (`inputs/source_copies/`)

| File | Source | Notes |
|---|---|---|
| `workshop_plan_of_events.pdf` | `ews-paper/supplemental_material/workshop_plan_of_events.pdf` | Facilitator protocol, 6 pp |
| `survey_baseline_endline.pdf` | `ews-paper/supplemental_material/base+end_line.pdf` | Blank Qualtrics instrument, 19 pp (renamed) |
| `results_table1.tex` | `ews-paper/descriptive_text/results_table1.tex` | 2021 metrics, all models × feature sets (md5 fa3918a9…) |
| `selection_table.tex` | `ews-paper/descriptive_text/selection_table.tex` | Rule verdicts per cell; test target for the rule applier |
| `selection_robustness.tex` | `ews-paper/descriptive_text/selection_robustness.tex` | Threshold sensitivity of the selection |
| `selection_by_cohort.tex` | `ews-paper/descriptive_text/selection_by_cohort.tex` | Selection per test year |
| `stability_table.tex` | `ews-paper/descriptive_text/stability_table.tex` | Recall/AUC by year |
| `main_tex_SI_workshop_tables_L676-800.tex` | `ews-paper/main.tex` lines 676–800 | Demographics table + median-shift table |
| `main_tex_methods_workshop_L198-240_L263-317.tex` | `ews-paper/main.tex` lines 198–240, 263–317 | Workshop phases, description, rule derivation, selection algorithm |
| `main_tex_model_candidates_L342-358.tex` | `ews-paper/main.tex` lines 342–358 | Model classes ↔ explainability levels, feature sets |
| `main_tex_selection_results_L449-461.tex` | `ews-paper/main.tex` lines 449–461 | Selection result prose |
| `workshop_rules_REFERENCE_ONLY.py` | `ews_code/src/workshop_rules.py` | Selection algorithm reference; not imported |

These excerpts contain no participant quotes. Never copy from `main.tex`
Results (lines ~399–437), the Stage 5 handover figure, or
`supplemental_material/discussion.pdf` (workshop notes).

## Derived files

| File | Built from | How |
|---|---|---|
| `metrics_2021.csv` | `source_copies/results_table1.tex` | `src/build_metrics_table.py`; adds derived prevalence and FPR |
| `human_ground_truth.yaml` | median-shift table, demographics table, main.tex 263–317, 396–422, 449–461 (aggregate statements only) | Hand-transcribed |
| `personas.yaml` | demographics table (marginal counts only) | Fictional composites, assignment by hand |
| `materials/survey.yaml` | `source_copies/survey_baseline_endline.pdf` | Verbatim text; figures → text descriptions; deviations listed in file header |
| `materials/framing_intro.md` | protocol §1 + survey intro | Reconstructed (original slides not preserved); additions marked [ADDED] |
| `materials/facilitator_script.yaml` | protocol §1–10 + main.tex 3a–3f | Reconstructed scripted facilitator; departures listed in file header |
| `materials/specification_template.md` | protocol §9 + main.tex 3f, 288–298 | Reconstructed final-assessment specification |

## Paper

| File | Source | Notes |
|---|---|---|
| `paper/aes_template/` | git clone of https://github.com/agent-evalscience/AES-Latex-Template (2026-10-17, approved by Tereza) | Pristine; working copy in `paper/abstract/` |
| `paper/abstract/references.bib` | entries `fishkin2009people` (ews-paper/references-2.bib), `birhanePowerPeopleOpportunities2022`, `delgadoParticipatoryTurnAI2023` (ews-paper/references.bib), copied verbatim | Other entries written by hand; marked VERIFY |
- `human_ground_truth.yaml` → `acceptability.counts`: final assessment counts (4 support, 2 support with reservations, 2 object without blocking, 2 block; n = 10; corrected by Tereza the same day), given by Tereza from the workshop records on 2026-10-22; not in the paper.
- `inputs/source_copies/paper_style.py` ← `~/projects/ews_code/figures/scripts/paper_style.py` (FAccT figure style; adapted as `src/paper_style.py`, 2026-10-22)
- `src/fonts/Helvetica.ttf` ← `~/projects/ews_code/figures/fonts/Helvetica.ttf` (font used by the FAccT figures)
