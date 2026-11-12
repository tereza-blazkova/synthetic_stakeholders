#!/usr/bin/env bash
# UCloud, 1x NVIDIA B200: post-review robustness runs (analysis/post_review_plan.md).
# Run from the project root inside the UCloud job (Claude starts it over ssh):
#
#   bash ucloud/run_post_review.sh start            # one Ollama 0.30.11 server, all models on one GPU
#   bash ucloud/run_post_review.sh b1 1-20          # B1: replay final assessment, 10 card conditions
#   bash ucloud/run_post_review.sh b2 pilot|1-20    # B2: persona paraphrases a and b, full protocol
#   bash ucloud/run_post_review.sh b34 <cond> pilot|1-20 <key> ...   # B3/B4: keys under models_post_review
#   bash ucloud/run_post_review.sh status
#
# Per-family servers: export OLLAMA_URL_family_N=http://localhost:<port> before b1/b2.
# Same Ollama version, options, prompts and scoring as the reference runs; only the
# named condition changes. Speed settings (how many requests run at once) change
# speed only. Every command can simply be re-run: finished folders are kept.
# No API keys or personal data are involved.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
export PYTHONDONTWRITEBYTECODE=1
export OLLAMA_MODELS="$ROOT/ollama_models"
export OLLAMA_MAX_LOADED_MODELS=3        # the three families resident at once on the B200
export OLLAMA_NUM_PARALLEL=2             # one slot for the B1 replay, one for B2 (speed only)
export OLLAMA_KEEP_ALIVE=24h
export PATH="$HOME/ollama/bin:$PATH"
FAMILIES=(family_1 family_2 family_3)
LOGS="$ROOT/runs/post_review/_logs"; mkdir -p "$LOGS"
PY="$ROOT/.venv-ucloud/bin/python"
progress() { echo "$* $(date -u +%m-%dT%H:%M)" >> "$LOGS/progress.log"; }

retry() {   # run a command until it exits 0 (finished folders are skipped), at most 5 times
  local name="$1"; shift
  for i in 1 2 3 4 5; do
    if "$@" >> "$LOGS/$name.log" 2>&1; then progress "DONE $name"; return 0; fi
    progress "RETRY $name ($i)"; sleep 60
  done
  progress "GAVE_UP $name"
}

url_for() {   # per-family server: OLLAMA_URL_family_2=http://localhost:11435 etc.; default 11434
  local v="OLLAMA_URL_$1"; echo "${!v:-http://localhost:11434}"
}

runs_of() {   # "pilot" | "1-20" | "1,3,5" -> list of run arguments for src.run
  case "$1" in pilot) echo pilot ;; *-*) seq "${1%-*}" "${1#*-}" ;; *) echo "${1//,/ }" ;; esac
}

case "${1:-}" in
start)       # start [port] [num_parallel]: extra servers (e.g. a second Qwen copy) on other ports
  port="${2:-11434}"; [ -n "${3:-}" ] && export OLLAMA_NUM_PARALLEL="$3"
  [ "$(ollama --version 2>&1 | grep -o '0\.30\.11' | head -1)" = "0.30.11" ] || { echo "need ollama 0.30.11 in ~/ollama/bin"; exit 1; }
  if ! curl -s "localhost:$port/api/version" >/dev/null 2>&1; then
    OLLAMA_HOST="127.0.0.1:$port" nohup ollama serve > "$LOGS/ollama_serve_$port.log" 2>&1 &
    for _ in $(seq 1 60); do curl -s "localhost:$port/api/version" >/dev/null 2>&1 && break; sleep 1; done
  fi
  echo "ollama on $port: $(curl -s "localhost:$port/api/version")"
  ;;
b1)
  range="${2:?usage: b1 1-20 [family ...]}"; shift 2
  fams=("$@"); [ ${#fams[@]} -eq 0 ] && fams=("${FAMILIES[@]}")
  for f in "${fams[@]}"; do
    retry "b1_${f}" env OLLAMA_URL="$(url_for "$f")" "$PY" -u -m src.replay_assessment --family "$f" --runs "$range" &
  done
  wait
  ;;
b2)   # b2 pilot|1-20|1,3,5 [family ...]; OLLAMA_URL in the environment picks the server
  spec="${2:?usage: b2 pilot|1-20|1,3,5 [family ...]}"; shift 2
  runs=($(runs_of "$spec")); fams=("$@"); [ ${#fams[@]} -eq 0 ] && fams=("${FAMILIES[@]}")
  tag="${spec//,/_}"
  for f in "${fams[@]}"; do
    ( for k in "${runs[@]}"; do         # a k, b k, a k+1, ...: stopping early stays balanced
        for v in a b; do
          retry "b2_${f}_${v}_${tag}" env OLLAMA_URL="$(url_for "$f")" "$PY" -u -m src.run --tier large --protocol full --family "$f" \
            --personas "inputs/variants/personas_paraphrase_${v}.yaml" --condition "personas_${v}" --run "$k"
        done
      done ) &
  done
  wait
  ;;
b2v)  # b2v a|b pilot|1-20|1,3,5 family: one persona variant only (same command as b2)
  v="${2:?usage: b2v a|b spec family}"; spec="${3:?}"; f="${4:?}"
  for k in $(runs_of "$spec"); do
    retry "b2_${f}_${v}_${spec//,/_}" env OLLAMA_URL="$(url_for "$f")" "$PY" -u -m src.run --tier large --protocol full --family "$f" \
      --personas "inputs/variants/personas_paraphrase_${v}.yaml" --condition "personas_${v}" --run "$k"
  done
  ;;
b34)
  cond="${2:?usage: b34 <condition> pilot|1-20|1,3,5 <key under models_post_review> ...}"; spec="${3:?}"; shift 3
  for f in "$@"; do
    ( for k in $(runs_of "$spec"); do
        retry "b34_${cond}_${f}_${spec//,/_}" "$PY" -u -m src.run --tier post_review --protocol full \
          --family "$f" --condition "$cond" --run "$k"
      done ) &
  done
  wait
  ;;
stop)        # stop drivers, then workers, then every Ollama server (patterns never match this shell)
  pkill -f "run_post_revie[w].sh (b1|b2|b34) " || true; sleep 1
  pkill -f "python -u -m src[.](run|replay_assessment) " || true; sleep 3
  pkill -f "olla[m]a serve" || true; sleep 8
  nvidia-smi --query-gpu=memory.used --format=csv,noheader
  ;;
status)
  tail -n 15 "$LOGS/progress.log" 2>/dev/null || echo "no progress yet"
  echo "B1 done: $(find runs/post_review/card -name assessment.json 2>/dev/null | wc -l) of 600 condition folders"
  for d in runs/post_review/*/full/*/; do [ -d "$d" ] && echo "$d $(ls "$d"/*/run_meta.json 2>/dev/null | wc -l) finished"; done
  for f in "$LOGS"/*.log; do echo "--- $(basename "$f"): $(tail -n 1 "$f")"; done
  nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader
  curl -s localhost:11434/api/ps | "$PY" -c "import json,sys;[print(m['name'],round(m['size_vram']/1e9,1),'GB vram of',round(m['size']/1e9,1)) for m in json.load(sys.stdin)['models']]"
  ;;
*)
  sed -n '2,14p' "$0"; exit 1 ;;
esac
