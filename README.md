# Synthetic Stakeholders?

**Agreement and Stability of Open-Weight LLM Agent Panels in Participatory Model Selection**

Tereza Blazkova, University of Copenhagen ·
Extended abstract and poster, Agent Evaluation Science symposium, NYC, Nov 20, 2026

Can panels of LLM agents stand in for human stakeholders when a group chooses an AI
model? We replay a participatory deliberative workshop (9 students and 3 student
advisors, choosing a dropout early-warning model for student advising) with panels of
12 LLM agents. We measure **agreement** with the one human workshop and **stability**
across repeated runs. The single manipulated factor is the LLM family: Qwen 3.5 27B,
Gemma 3 27B and Mistral Small 3.2 24B, all open weights at 4-bit (Ollama `q4_K_M`),
20 seeded runs each.

The human workshop is reported in a separate manuscript (Blazkova, Kizilcec, Bjerre-Nielsen
and Koenecke, under review). This repository uses only the workshop *materials*
participants saw and the workshop *outcomes* (selection rules, chosen model, final
votes). It contains no individual-level data.

## How a run works

1. Each of 12 fictional personas (same role mix as the humans) fills in the baseline
   survey alone.
2. Scripted (non-LLM) facilitation: table discussions, plenary, open discussion.
3. Each agent fills in the endline survey alone.
4. The endline answers are aggregated **programmatically** (median, the paper's tie
   rules) into selection rules, and the rules are applied to the candidate-model metrics
   to select a model. Agents never name a model.
5. Each agent rates the resulting specification (support / support with reservations /
   object without blocking / block).

## Layout

```
config.yaml         pinned models (Ollama tags + digests), seeds, temperature 1.0
inputs/             personas, survey, facilitator scripts, framing intro, candidate-model
                    metrics, human ground truth (rules, choice, votes), SOURCES.md
src/                harness (workshop.py, workshop_full.py, llm.py), rule applier,
                    scoring, figures
tests/              pytest suite (runs with a fake backend, no model needed)
runs/               parsed outputs per run (see below)
analysis/           rule checklist (written before any output), scores, tables, figures
paper/abstract/     the 2-page extended abstract (AES template)
poster/             A0 landscape poster (main_landscape.tex) and its figures
ucloud/             launch scripts used on the GPU cluster (SDU UCloud, 1x B200)
```

`runs/full/<model>/runXX/` holds, per run: survey answers and aggregates (baseline,
endline), selections, final assessment, table reports, the full transcript and
`run_meta.json`. `runs/post_review/` holds the robustness checks (vote-card wording,
paraphrased personas, 8- and 16-bit weights, Qwen 3.5 122B). The top-level
`runs/<model>/` folders are the earlier small-tier and lite-protocol runs.

## Not included

- **Raw call logs** (`calls.jsonl`, about 5.5 GB: every prompt, response, model digest
  and timestamp). `src/score.py` rebuilds scores from these logs, so scoring, and the
  figures that re-score runs (the poster's selection grid, `src/figures_post_review.py`),
  cannot be re-run from this repository alone. The scored results are in
  `analysis/results/` and the built figures in `analysis/figures/` and `poster/figs/`.
  The logs are available on request.
- Copies of excerpts from the workshop manuscript (`inputs/source_copies/`).
  One test that checks the rule applier against the manuscript's selection table is
  skipped without them. `inputs/SOURCES.md` records where every input came from.

## Running

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests
# one workshop without a model:
.venv/bin/python -m src.run --tier large --protocol full --family family_1 --run pilot --backend fake
```

Real runs need Ollama 0.30.11 with the models pinned in `config.yaml`
(see `ucloud/README.md` for the GPU setup).
