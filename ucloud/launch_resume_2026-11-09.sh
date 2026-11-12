#!/usr/bin/env bash
# Resume the unfinished post-review runs on two UCloud jobs that share /work (2026-11-09).
#   job with 3 GPUs:  bash ucloud/launch_resume_2026-11-09.sh jobA
#   job with 2 GPUs:  bash ucloud/launch_resume_2026-11-09.sh jobB
# Stop (one job only): bash ucloud/run_post_review.sh stop
#
# Done before this launch: B1 (600/600), all Mistral runs, 122B pilot + runs 1-11,
# Gemma/Qwen B2 pilot (a) + runs 2-3, Gemma/Qwen q8 pilot + runs 1, 2, 4.
# Each job owns whole model folders, so the two jobs never write the same folder:
#   jobA  GPU0 Gemma q4 B2 (5 streams)    GPU1 Gemma q8 (4 streams)
#         GPU2 Qwen 122B runs 12-20 (2 servers), then Gemma q4 B2 personas_b 10-20 (4 streams)
#   jobB  GPU0 Qwen 27B q4 B2 (6 one-slot servers)   GPU1 Qwen 27B q8 (4 one-slot servers)
# Within a job, every run number appears in exactly one stream.
# Speed settings only: weights, digests, Ollama 0.30.11, options, prompts and seeds are unchanged.
# Finished folders are skipped; an interrupted one is moved to _incomplete_* and redone.
set -euo pipefail
cd "$(dirname "$0")/.."
L=runs/post_review/_logs; mkdir -p "$L"
R="bash ucloud/run_post_review.sh"

export CUDA_MPS_PIPE_DIRECTORY=/tmp/mps-pipe CUDA_MPS_LOG_DIRECTORY=/tmp/mps-log
mkdir -p "$CUDA_MPS_PIPE_DIRECTORY" "$CUDA_MPS_LOG_DIRECTORY"
if [ "${NO_MPS:-0}" != 1 ] && ! pgrep -x nvidia-cuda-mps >/dev/null; then nvidia-cuda-mps-control -d && echo "MPS on"; fi

bg() { setsid nohup "$@" > "$L/driver_rs_$(date +%s%N).log" 2>&1 < /dev/null & }
serve() { CUDA_VISIBLE_DEVICES="$1" $R start "$2" "$3"; }          # gpu port slots

case "${1:?jobA|jobB}" in
jobA)
  # GPU 0: Gemma q4, personas_a runs 1,4-20 (3 streams) and personas_b pilot-9 (2 streams)
  serve 0 11440 5
  for s in "1,4,7,10,13,16" "5,8,11,14,17,20" "6,9,12,15,18,19"; do
    bg env OLLAMA_URL_family_2=http://localhost:11440 $R b2v a "$s" family_2; done
  for s in "pilot,1,3,5,7" "2,4,6,8,9"; do
    bg env OLLAMA_URL_family_2=http://localhost:11440 $R b2v b "$s" family_2; done
  # GPU 1: Gemma q8, runs 3,5-20
  serve 1 11441 4
  for s in "3,6,10,14,18" "5,9,13,17" "7,11,15,19" "8,12,16,20"; do
    bg env OLLAMA_URL=http://localhost:11441 $R b34 precision_q8 "$s" q8_gemma; done
  # GPU 2: chain (122B, then Gemma q4 personas_b 10-20)
  bg bash "$0" gpu2_chain
  ;;
gpu2_chain)
  serve 2 11450 1; serve 2 11451 1
  env OLLAMA_URL=http://localhost:11450 $R b34 larger_qwen122 "12,14,16,18,20" large_qwen122 &
  env OLLAMA_URL=http://localhost:11451 $R b34 larger_qwen122 "13,15,17,19" large_qwen122 &
  wait
  # stop just the two 122B servers (found by their port), then reuse GPU 2 for Gemma
  for pid in $(pgrep -f "olla[m]a serve"); do
    tr '\0' '\n' < /proc/$pid/environ | grep -qE '^OLLAMA_HOST=127.0.0.1:1145[01]$' && kill "$pid" || true
  done
  sleep 15
  serve 2 11452 4
  for s in "10,14,18" "11,15,19" "12,16,20" "13,17"; do
    env OLLAMA_URL_family_2=http://localhost:11452 $R b2v b "$s" family_2 &
  done
  wait
  ;;
jobB)
  # GPU 0: Qwen 27B q4, personas a and b for runs 1,4-20 (6 one-slot servers, 3 runs x 2 variants each)
  p=11442
  for s in "1,10,16" "4,11,17" "5,12,18" "6,13,19" "7,14,20" "8,9,15"; do
    serve 0 $p 1; bg env OLLAMA_URL_family_1=http://localhost:$p $R b2 "$s" family_1; p=$((p+1))
  done
  # GPU 1: Qwen 27B q8, runs 3,5-20 (4 one-slot servers)
  p=11460
  for s in "3,6,10,14,18" "5,9,13,17" "7,11,15,19" "8,12,16,20"; do
    serve 1 $p 1; bg env OLLAMA_URL=http://localhost:$p $R b34 precision_q8 "$s" q8_qwen; p=$((p+1))
  done
  ;;
esac
sleep 5; echo "workers: $(pgrep -fc 'python -u -m src' || true)"
