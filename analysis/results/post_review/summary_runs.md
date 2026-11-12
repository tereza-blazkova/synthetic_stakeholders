# Post-review runs (B1-B4): exploratory, scored by `src/score_post_review.py`

## B1 card format (replay of the final assessment only)

| Family | Condition | runs | cards | with reservations [95% CI] | object | block | support | changed vs control | same as original |
|---|---|---|---|---|---|---|---|---|---|
| Gemma | baseline_replay | 20 | 240 | 96% [0.925, 0.977] | 4% | 0% | 0% | 0% | 98% |
| Gemma | conditional_label | 20 | 240 | 96% [0.925, 0.977] | 4% | 0% | 0% | 2% | 98% |
| Gemma | definitions_removed | 20 | 240 | 98% [0.947, 0.988] | 2% | 0% | 0% | 2% | 98% |
| Gemma | no_legitimacy_bullet | 20 | 240 | 98% [0.947, 0.988] | 2% | 0% | 0% | 2% | 98% |
| Gemma | no_majority_claim | 20 | 240 | 92% [0.885, 0.952] | 8% | 0% | 0% | 4% | 97% |
| Gemma | no_reservations_word | 20 | 240 | 85% [0.795, 0.886] | 15% | 0% | 0% | 11% | 89% |
| Gemma | reservations_fourth | 20 | 240 | 93% [0.89, 0.955] | 7% | 0% | 0% | 5% | 97% |
| Gemma | reversed_order | 20 | 240 | 2% [0.006, 0.042] | 98% | 0% | 0% | 94% | 6% |
| Gemma | shuffled_per_agent | 20 | 240 | 78% [0.727, 0.831] | 21% | 1% | 0% | 20% | 81% |
| Gemma | symmetric_definitions | 20 | 240 | 98% [0.947, 0.988] | 2% | 0% | 0% | 2% | 98% |
| Mistral | baseline_replay | 20 | 240 | 100% [0.984, 1.0] | 0% | 0% | 0% | 0% | 100% |
| Mistral | conditional_label | 20 | 240 | 100% [0.984, 1.0] | 0% | 0% | 0% | 0% | 100% |
| Mistral | definitions_removed | 20 | 240 | 100% [0.977, 0.999] | 0% | 0% | 0% | 0% | 100% |
| Mistral | no_legitimacy_bullet | 20 | 240 | 100% [0.984, 1.0] | 0% | 0% | 0% | 0% | 100% |
| Mistral | no_majority_claim | 20 | 240 | 100% [0.984, 1.0] | 0% | 0% | 0% | 0% | 100% |
| Mistral | no_reservations_word | 20 | 240 | 100% [0.984, 1.0] | 0% | 0% | 0% | 0% | 100% |
| Mistral | reservations_fourth | 20 | 240 | 82% [0.772, 0.868] | 18% | 0% | 0% | 18% | 82% |
| Mistral | reversed_order | 20 | 240 | 88% [0.832, 0.915] | 12% | 0% | 0% | 12% | 88% |
| Mistral | shuffled_per_agent | 20 | 240 | 95% [0.915, 0.971] | 5% | 0% | 0% | 5% | 95% |
| Mistral | symmetric_definitions | 20 | 240 | 100% [0.984, 1.0] | 0% | 0% | 0% | 0% | 100% |
| Qwen | baseline_replay | 20 | 240 | 92% [0.885, 0.952] | 7% | 0% | 0% | 0% | 91% |
| Qwen | conditional_label | 20 | 240 | 94% [0.899, 0.962] | 6% | 0% | 0% | 12% | 90% |
| Qwen | definitions_removed | 20 | 240 | 82% [0.763, 0.861] | 18% | 0% | 0% | 19% | 80% |
| Qwen | no_legitimacy_bullet | 20 | 240 | 95% [0.91, 0.968] | 5% | 0% | 0% | 10% | 92% |
| Qwen | no_majority_claim | 20 | 240 | 94% [0.899, 0.962] | 6% | 0% | 0% | 8% | 91% |
| Qwen | no_reservations_word | 20 | 240 | 95% [0.915, 0.971] | 4% | 1% | 0% | 11% | 93% |
| Qwen | reservations_fourth | 20 | 240 | 80% [0.74, 0.842] | 16% | 4% | 0% | 23% | 79% |
| Qwen | reversed_order | 20 | 240 | 77% [0.709, 0.816] | 23% | 0% | 0% | 24% | 74% |
| Qwen | shuffled_per_agent | 20 | 240 | 90% [0.86, 0.935] | 6% | 4% | 0% | 13% | 88% |
| Qwen | symmetric_definitions | 20 | 240 | 95% [0.92, 0.974] | 4% | 1% | 0% | 10% | 91% |
| pooled | baseline_replay | 60 | 720 | 96% [0.944, 0.973] | 4% | 0% | 0% | 0% | 96% |
| pooled | conditional_label | 60 | 720 | 96% [0.949, 0.976] | 3% | 0% | 0% | 5% | 96% |
| pooled | definitions_removed | 60 | 720 | 93% [0.908, 0.946] | 7% | 0% | 0% | 7% | 92% |
| pooled | no_legitimacy_bullet | 60 | 720 | 97% [0.959, 0.983] | 3% | 0% | 0% | 4% | 96% |
| pooled | no_majority_claim | 60 | 720 | 95% [0.936, 0.967] | 4% | 0% | 0% | 4% | 96% |
| pooled | no_reservations_word | 60 | 720 | 93% [0.911, 0.948] | 6% | 0% | 0% | 7% | 94% |
| pooled | reservations_fourth | 60 | 720 | 85% [0.822, 0.874] | 14% | 1% | 0% | 15% | 86% |
| pooled | reversed_order | 60 | 720 | 55% [0.518, 0.59] | 44% | 0% | 0% | 43% | 56% |
| pooled | shuffled_per_agent | 60 | 720 | 88% [0.853, 0.901] | 11% | 2% | 0% | 13% | 88% |
| pooled | symmetric_definitions | 60 | 720 | 98% [0.963, 0.985] | 2% | 0% | 0% | 4% | 96% |

## B2-B4 full reruns vs reference (large tier, full protocol)

| Condition | Model | runs | rules matched (ref) | diff [95% CI] | human model (ref) | modal share | with reservations (ref) |
|---|---|---|---|---|---|---|---|
| larger_qwen122 | qwen3.5:122b-a10b-q4_K_M | 20 | 2.3 (1.9) | 0.4 [0.05, 0.75] | 2/20 (0/20) | 18/20 | 73% (94%) |
| personas_a | gemma3:27b-it-q4_K_M | 20 | 1.45 (1.35) | 0.1 [-0.3, 0.55] | 0/20 (0/20) | 20/20 | 99% (96%) |
| personas_a | mistral-small3.2:24b-instruct-2506-q4_K_M | 20 | 2.6 (3.1) | -0.5 [-0.9, -0.1] | 3/20 (3/20) | 16/20 | 100% (100%) |
| personas_a | qwen3.5:27b-q4_K_M | 20 | 1.85 (1.9) | -0.05 [-0.4, 0.3] | 0/20 (0/20) | 20/20 | 95% (94%) |
| personas_b | gemma3:27b-it-q4_K_M | 20 | 1.3 (1.35) | -0.05 [-0.45, 0.3] | 0/20 (0/20) | 20/20 | 95% (96%) |
| personas_b | mistral-small3.2:24b-instruct-2506-q4_K_M | 20 | 2.75 (3.1) | -0.35 [-0.75, 0.05] | 4/20 (3/20) | 14/20 | 100% (100%) |
| personas_b | qwen3.5:27b-q4_K_M | 20 | 2.05 (1.9) | 0.15 [-0.25, 0.5] | 2/20 (0/20) | 18/20 | 91% (94%) |
| precision_fp16 | gemma3:27b-it-fp16 | 20 | 2.8 (1.35) | 1.45 [1.1, 1.75] | 0/20 (0/20) | 9/20 | 25% (96%) |
| precision_q8 | gemma3:27b-it-q8_0 | 20 | 2.6 (1.35) | 1.25 [0.9, 1.6] | 0/20 (0/20) | 10/20 | 25% (96%) |
| precision_q8 | mistral-small3.2:24b-instruct-2506-q8_0 | 20 | 2.25 (3.1) | -0.85 [-1.2, -0.5] | 2/20 (3/20) | 18/20 | 100% (100%) |
| precision_q8 | qwen3.5:27b-q8_0 | 20 | 1.65 (1.9) | -0.25 [-0.65, 0.15] | 0/20 (0/20) | 20/20 | 98% (94%) |
