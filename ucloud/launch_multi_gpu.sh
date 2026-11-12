#!/usr/bin/env bash
# Second UCloud job (3x B200), running ALONGSIDE the single-GPU job on the same /work folder.
#   bash ucloud/launch_multi_gpu.sh
# Stop with: bash ucloud/run_post_review.sh stop   (in a separate shell call; this job only)
#
# Division of work, so the two jobs never write the same folders:
#   old job (1 GPU): B1 card replays, Mistral B2 (personas a/b), Mistral q8 (B4)
#   this job:
#     GPU 0  Gemma q4 (B2, 3 streams), then Gemma q8 (B4, 2 streams)
#     GPU 1  Qwen 27B q4 (B2, 3 one-slot servers), then Qwen q8 (B4, 2 one-slot servers)
#     GPU 2  Qwen 122B (B3), two servers
# Speed settings only; weights, digests, Ollama 0.30.11, options, prompts and seeds are unchanged.
# Each stream starts with the pilot where one is due, so the pilot output can be checked early.
set -euo pipefail
cd "$(dirname "$0")/.."
L=runs/post_review/_logs; mkdir -p "$L"
R="bash ucloud/run_post_review.sh"

export CUDA_MPS_PIPE_DIRECTORY=/tmp/mps-pipe CUDA_MPS_LOG_DIRECTORY=/tmp/mps-log
mkdir -p "$CUDA_MPS_PIPE_DIRECTORY" "$CUDA_MPS_LOG_DIRECTORY"
if [ "${NO_MPS:-0}" != 1 ] && ! pgrep -x nvidia-cuda-mps >/dev/null; then nvidia-cuda-mps-control -d && echo "MPS on"; fi

bg() { setsid nohup "$@" > "$L/driver_mg_$(date +%s%N).log" 2>&1 < /dev/null & }
serve() { CUDA_VISIBLE_DEVICES="$1" $R start "$2" "$3"; }          # gpu port slots
wait_loaded() { for _ in $(seq 1 180); do curl -s "localhost:$1/api/ps" | grep -q "$2" && return 0; sleep 5; done; echo "timeout loading $2 on $1"; }
B2_SPLIT=("pilot,1,4,7,10,13,16,19" "2,5,8,11,14,17,20" "3,6,9,12,15,18")
B4_SPLIT=("pilot,1,3,5,7,9,11,13,15,17,19" "2,4,6,8,10,12,14,16,18,20")

# GPU 0: Gemma
serve 0 11440 3
for s in "${B2_SPLIT[@]}"; do bg env OLLAMA_URL_family_2=http://localhost:11440 $R b2 "$s" family_2; done
# GPU 1: Qwen 27B q4, one server per stream (qwen35 serves one request at a time)
p=11442; for s in "${B2_SPLIT[@]}"; do serve 1 $p 1; bg env OLLAMA_URL_family_1=http://localhost:$p $R b2 "$s" family_1; p=$((p+1)); done
# GPU 2: Qwen 122B (two servers)
serve 2 11450 1      # two 122B copies (~83 GB each) fit on one B200: odd and even runs
bg env OLLAMA_URL=http://localhost:11450 $R b34 larger_qwen122 "pilot,1,3,5,7,9,11,13,15,17,19" large_qwen122
serve 2 11451 1
bg env OLLAMA_URL=http://localhost:11451 $R b34 larger_qwen122 "2,4,6,8,10,12,14,16,18,20" large_qwen122

wait_loaded 11440 gemma3
serve 0 11441 2
for s in "${B4_SPLIT[@]}"; do bg env OLLAMA_URL=http://localhost:11441 $R b34 precision_q8 "$s" q8_gemma; done

wait_loaded 11444 qwen3.5
p=11446; for s in "${B4_SPLIT[@]}"; do serve 1 $p 1; bg env OLLAMA_URL=http://localhost:$p $R b34 precision_q8 "$s" q8_qwen; p=$((p+1)); done

wait_loaded 11450 qwen3.5:122b; wait_loaded 11441 gemma3:27b-it-q8_0
wait_loaded 11446 qwen3.5:27b-q8_0; wait_loaded 11447 qwen3.5:27b-q8_0
date; nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader
echo "workers: $(pgrep -fc 'python -u -m src')"
