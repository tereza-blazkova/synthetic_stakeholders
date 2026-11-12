#!/usr/bin/env bash
# Start everything for the post-review runs on ONE B200 (UCloud), in load order.
#   bash ucloud/launch_single_gpu.sh            # B1 (all) + B2 (all), three families
# Stop with: bash ucloud/run_post_review.sh stop  (run it in a separate shell call)
#
# Layout (speed only; prompts, options and seeds are unchanged):
#   CUDA MPS, so the three model servers run kernels concurrently instead of time-slicing.
#   One Ollama server per model, started in this order so Ollama's (over-)estimate of
#   Gemma's memory is checked against an empty GPU:
#     11435 Gemma   3 slots: B1 + 2 B2 streams
#     11434 Mistral 5 slots: B1 + 4 B2 streams
#     11436 Qwen    1 slot (qwen35 cannot serve parallel requests in Ollama 0.30.11)
set -euo pipefail
cd "$(dirname "$0")/.."
L=runs/post_review/_logs; mkdir -p "$L"
R="bash ucloud/run_post_review.sh"

export CUDA_MPS_PIPE_DIRECTORY=/tmp/mps-pipe CUDA_MPS_LOG_DIRECTORY=/tmp/mps-log
mkdir -p "$CUDA_MPS_PIPE_DIRECTORY" "$CUDA_MPS_LOG_DIRECTORY"
if [ "${NO_MPS:-0}" != 1 ] && ! pgrep -x nvidia-cuda-mps >/dev/null; then nvidia-cuda-mps-control -d && echo "MPS on"; fi

$R start 11435 3; $R start 11434 5; $R start 11436 1
export OLLAMA_URL_family_1=http://localhost:11436 OLLAMA_URL_family_2=http://localhost:11435 \
       OLLAMA_URL_family_3=http://localhost:11434
bg() { setsid nohup "$@" > "$L/driver_$(date +%s%N).log" 2>&1 < /dev/null & }
wait_loaded() { for _ in $(seq 1 120); do curl -s "localhost:$1/api/ps" | grep -q "$2" && return 0; sleep 5; done; echo "timeout loading $2"; }

bg $R b1 1-20 family_2
bg $R b2 "pilot,1,3,5,7,9,11,13,15,17,19" family_2
bg $R b2 "2,4,6,8,10,12,14,16,18,20" family_2
wait_loaded 11435 gemma3
bg $R b1 1-20 family_3
for s in "pilot,1,5,9,13,17" "2,6,10,14,18" "3,7,11,15,19" "4,8,12,16,20"; do bg $R b2 "$s" family_3; done
wait_loaded 11434 mistral
bg $R b1 1-20 family_1
bg $R b2 "pilot,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20" family_1
wait_loaded 11436 qwen3.5
date; nvidia-smi --query-gpu=memory.used --format=csv,noheader
echo "workers: $(pgrep -fc 'python -u -m src')"
