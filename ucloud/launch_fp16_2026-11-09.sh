#!/usr/bin/env bash
# Exploratory B4 extension (post hoc, approved 2026-11-09): Gemma 3 27B unquantised, pilot + 20 runs.
#   job with 3 GPUs:  bash ucloud/launch_fp16_2026-11-09.sh jobA   (pilot, runs 1-14: 5 per GPU)
#   job with 2 GPUs:  bash ucloud/launch_fp16_2026-11-09.sh jobB   (runs 15-20: 3 per GPU)
# One workshop per stream; the two jobs write different run folders. Speed settings only.
set -euo pipefail
cd "$(dirname "$0")/.."
L=runs/post_review/_logs; mkdir -p "$L"
R="bash ucloud/run_post_review.sh"
export CUDA_MPS_PIPE_DIRECTORY=/tmp/mps-pipe CUDA_MPS_LOG_DIRECTORY=/tmp/mps-log
mkdir -p "$CUDA_MPS_PIPE_DIRECTORY" "$CUDA_MPS_LOG_DIRECTORY"
pgrep -x nvidia-cuda-mps >/dev/null || nvidia-cuda-mps-control -d
bg() { setsid nohup "$@" > "$L/driver_fp16_$(date +%s%N).log" 2>&1 < /dev/null & }
go() {   # gpu port run...
  local gpu=$1 port=$2; shift 2
  CUDA_VISIBLE_DEVICES=$gpu $R start "$port" "$#"
  for k in "$@"; do bg env OLLAMA_URL=http://localhost:$port $R b34 precision_fp16 "$k" fp16_gemma; done
}
case "${1:?jobA|jobB}" in
jobA) go 0 11480 pilot 1 2 3 4; go 1 11481 5 6 7 8 9; go 2 11482 10 11 12 13 14 ;;
jobB) go 0 11480 15 16 17; go 1 11481 18 19 20 ;;
esac
sleep 5; echo "workers: $(pgrep -fc 'python -u -m src[.]' || true)"
