# Poster (AES symposium, NYC, Nov 20, 2026): DRAFT v2

v2 (2026-11-08) follows Tereza's review: top-to-bottom bands, UCPH colours, logo slot,
and poster-size figures. Print around Nov 17.

## Build

```
cd /Users/kay/projects/synthetic_stakeholders
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python poster/make_figures.py   # figures -> poster/figs/
cd poster
latexmk -pdf main.tex          # pdfLaTeX, beamer + beamerposter, TeX Gyre Heros
latexmk -c                     # remove aux files (main.pdf stays)
pdftoppm -r 30 -png -singlefile main.pdf preview   # low-res layout check
```

Inputs, read only: `../analysis/tables/numbers.tex`, `../analysis/tables/numbers_post_review.tex`
and the data the figure functions read (`analysis/results/`, `runs/full/`, `inputs/`).
The poster uses only `figs/` (graphicspath), never `analysis/figures/`.

Before printing: put `\def\phfinal{}` above the two `\input` lines in `main.tex`.
Any `\PH` or `\Interim` left over then stops the build.

## Layout (top to bottom)

1. **Title band** (UCPH red): logo slot top left, title, subtitle, author, affiliation, email.
2. **Setup band** (light grey, small type, ~25 pt): Question | One human workshop (not a
   ground truth, own baseline = 3 of 7) | Design diagram (`fig_design.tex`, the abstract's
   horizontal diagram with absolute font sizes and UCPH red for the synthetic lane) + models and runs.
3. **Results band** (white, dominant, body ~30 pt): the message as a red headline
   ("Agent panels agree with each other, not with the humans"); hero figure (left) next to
   three large takeaways (right) with the hero caption; then `fig_full` (panels a, b, c) at
   full width with headings "One model, every run" / "Little movement" / "No dissent"
   and the matching text under each panel (54/60 + family chips; humans revised 10 of 23
   + A4; 97% with reservations vs humans 4/2/2/2).
4. **Robustness and context band** (light grey, ~21 pt): B1 card figure + caption (post-review,
   interim) | B2–B4 table (post-review) + limitations | two quote pairs (slots).
5. **Footer** (UCPH red): QR placeholder, "Paper, materials and code" with `\PH{websiteURL}`,
   the post-review legend, contact.

## Size

One line in `main.tex`, marked `POSTER SIZE`:
`\usepackage[size=a0,orientation=portrait,scale=1.2]{beamerposter}`.
Band and column widths are fractions of the page width. The figures are made for A0:
if the size changes, change `print_cm` in `make_figures.py` (and possibly the canvas sizes)
and rerun it. The title band and footer use some absolute lengths (cm) and font sizes.

## Colours

Defined once at the top of `main.tex` (block `COLOURS`): `ucphred` #901A1E (primary),
`ucphdark` #4D4D4D, `ucphlight` #E6E6E6, plus white/black. **Check the hex values against
the official UCPH design guide.** No other chrome colours; the post-review tag is white on
dark grey. Family colours (Qwen, Gemma, Mistral; names in text and the chips) and vote
colours are data colours from `src/figures.py`, unchanged. Red `\PH` boxes and orange
`\Interim` values come from the numbers file and stay.

## Logo slot

`\IfFileExists{logo/ucph_logo.pdf}{...}{placeholder box}` in the title band, top left, on
a white tile (so the colour or the white version both work). Tereza puts the official
file at `poster/logo/ucph_logo.pdf`. Nothing is downloaded.

## Figures: `make_figures.py`

Imports `src.figures.full_figure` and `src.figures_post_review.agreement_floor` /
`card_conditions` unchanged. For each call it temporarily multiplies the type sizes
(`src.paper_style.FONT` and the font entries of its rcParams), sets the canvas
(`width_in`/`height_in`; for `fig_full` via `src.paper_style.TEXTWIDTH_IN`, the height of
1.95 in is fixed in src), and redirects output by monkeypatching `src.figures.FIG_DIR` and
`src.figures_post_review.FIG` to `poster/figs/`. All are restored afterwards; nothing in
`src/` or `analysis/figures/` is written. The script prints the printed type sizes,
computed from each saved PDF's real width and the printed width used in `main.tex`:

| Figure | printed width | tick labels | smallest text |
|---|---|---|---|
| `fig_agreement_floor` (results) | 41.2 cm | 27 pt | 25 pt |
| `fig_full` (results) | 79.3 cm | 27 pt | 24 pt |
| `fig_card_conditions` (robustness) | 39.6 cm | 18 pt | 18 pt (titles 20 pt) |

The design diagram prints at about 20 pt (stages) and 17 pt (notes) in the setup band.

## Placeholders (red boxes)

Introduced by the poster:
- `\PH{websiteURL}`: URL of the website paper (footer).

From `numbers_post_review.tex`, in the B2–B4 table (shown as a compact red `?`,
`\PHcompact`, so the table keeps its width; the build log names each one):
- `bTwoARules{Qwen,Gemma,Mistral}`, `bTwoADecision{Qwen,Gemma,Mistral}`
- `bTwoBRules{...}`, `bTwoBDecision{...}`, `bFourRules{...}`, `bFourDecision{...}`
- `bThreeRulesQwen`, `bThreeDecisionQwen` (B3 row: Qwen only)

Interim (orange): the B1 caption (`\bOneNPooled`, `\bOneReservations{Control,NoResWord,Reversed}Pooled`,
`\bOneReservationsReversedGemma`), 49 of 60 workshops. The B1 figure titles also show interim run counts;
rerun `make_figures.py` when B1 is complete.

## Slots

- `\HumanQuoteSlot{A}`, `\HumanQuoteSlot{B}`: Tereza pastes a quote from the FAccT paper
  (role label as in the paper; consent for poster/website re-use checked). Never pasted to an LLM.
- `\AgentQuoteSlot{A}`, `\AgentQuoteSlot{B}`: drawn by the fixed seeded rule (plan section 4)
  once Tereza names the themes; verbatim, with run id and agent id.
- QR code: white square in the footer. When the URL exists, replace the node text with
  `\qrcode[height=4.4cm]{<url>}` (`\usepackage{qrcode}`, installed).
- Logo: see above.

## Open questions for Tereza

1. **Poster size and orientation** at AES (not confirmed). A0 portrait is assumed.
2. **UCPH colours and logo**: hex values to check against the design guide; logo file
   and position (top left now).
3. **Takeaway wording** (bounded?): (1) "Low agreement with the one human reference: rule
   matches within the random-panel range." (2) "Uniform choices: 54 of 60 panels chose the
   same model, not the humans'." (3) "Little movement, no dissent: few revised answers,
   97% 'support with reservations'." Numbers are macros.
4. **B1 claim** "No card reaches the human spread" rests on interim runs; re-read when complete.
5. Quote heading "Side by side: same themes" assumes each pair shares a theme.
6. The lower band text is ~21 pt and the table may shrink slightly (it is fitted to its
   column); the quote slots and table notes are the smallest type on the poster (~21 pt).
7. Section numbers were dropped in v2.
