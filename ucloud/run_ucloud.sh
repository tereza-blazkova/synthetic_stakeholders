#!/usr/bin/env bash
# UCloud (SDU, 1x NVIDIA B200): large-tier runs, lite and full protocol.
# Run from the project root inside a UCloud terminal job:
#
#   bash ucloud/run_ucloud.sh setup        # install Ollama + Python env, pull 3 models (~50 GB)
#   bash ucloud/run_ucloud.sh pilot        # 1 lite + 1 full pilot per family, then pack results
#   bash ucloud/run_ucloud.sh main 1-10    # main runs (later: main 11-20), then pack results
#   bash ucloud/run_ucloud.sh status       # progress
#
# The three families run in parallel (one process each, all models stay in GPU
# memory); within a family, runs are interleaved lite k, full k, lite k+1, ...
# so stopping early leaves every family and protocol with equal numbers of runs.
# Existing run folders are skipped, so any stage can simply be restarted.
# No API keys or personal data are involved.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
export PYTHONDONTWRITEBYTECODE=1
export OLLAMA_MODELS="$ROOT/ollama_models"        # model weights live on UCloud storage
export OLLAMA_MAX_LOADED_MODELS=3                  # all three families resident at once
export OLLAMA_NUM_PARALLEL=1                       # one request per model at a time (as on the laptop)
export OLLAMA_KEEP_ALIVE=24h
export PATH="$HOME/ollama/bin:$PATH"
OLLAMA_VERSION="0.30.11"                           # same as the laptop runs
FAMILIES=(family_1 family_2 family_3)
LOGS="$ROOT/runs/_logs"; mkdir -p "$LOGS"
PY="$ROOT/.venv-ucloud/bin/python"

start_ollama() {
  if ! curl -s localhost:11434/api/version >/dev/null 2>&1; then
    nohup ollama serve > "$LOGS/ollama_serve.log" 2>&1 &
    for _ in $(seq 1 60); do curl -s localhost:11434/api/version >/dev/null 2>&1 && break; sleep 1; done
  fi
  echo "ollama $(curl -s localhost:11434/api/version)"
}

model_ids() {
  "$PY" -c "import yaml;c=yaml.safe_load(open('config.yaml'));print(' '.join(c['models_large'][f]['model_id'] for f in ('family_1','family_2','family_3')))"
}

pack() {   # results archive to download back to the laptop
  local name="results_$1_$(date +%Y%m%d_%H%M).tgz"
  tar -czf "$name" runs/qwen3.5_27b* runs/gemma3_27b* runs/mistral-small3.2* runs/full runs/_logs ucloud/digests.txt 2>/dev/null || true
  echo "packed $name ($(du -h "$name" | cut -f1)); download it from the UCloud file browser"
}

case "${1:-}" in
setup)
  python3 -m venv .venv-ucloud
  .venv-ucloud/bin/pip install -q -r requirements.txt zstandard
  # Use the pinned version even if the image ships another one (same engine as the laptop runs).
  if [ "$(ollama --version 2>/dev/null | grep -o '[0-9]*\.[0-9]*\.[0-9]*' | tail -1)" != "$OLLAMA_VERSION" ]; then
    echo "installing ollama $OLLAMA_VERSION to ~/ollama (no root needed)"
    mkdir -p "$HOME/ollama"
    asset=ollama-linux-amd64.tar.zst      # the v0.30.11 Linux release asset
    curl -fsSL "https://github.com/ollama/ollama/releases/download/v$OLLAMA_VERSION/$asset" -o "/tmp/$asset"
    tar --zstd -xf "/tmp/$asset" -C "$HOME/ollama" 2>/dev/null || \
      "$PY" -c "import sys,tarfile,zstandard; tarfile.open(fileobj=zstandard.ZstdDecompressor().stream_reader(open(sys.argv[1],'rb')),mode='r|').extractall(sys.argv[2])" "/tmp/$asset" "$HOME/ollama"
    if ! command -v ollama >/dev/null && sudo -n true 2>/dev/null; then
      echo "tarball install failed; trying the official installer with sudo"
      curl -fsSL https://ollama.com/install.sh | OLLAMA_VERSION="$OLLAMA_VERSION" sh
    fi
    [ -x "$HOME/ollama/bin/ollama" ] || { echo "ollama install failed: see ucloud/README.md"; exit 1; }
  fi
  hash -r
  echo "using $(command -v ollama)"; ollama --version
  nvidia-smi --query-gpu=name,memory.total --format=csv
  start_ollama
  for m in $(model_ids); do echo "pulling $m"; ollama pull "$m"; done
  curl -s localhost:11434/api/tags | "$PY" -c "import json,sys;[print(m['name'],m['digest']) for m in json.load(sys.stdin)['models']]" | tee ucloud/digests.txt
  "$PY" -m pytest -q -p no:cacheprovider tests
  echo "setup done"
  ;;
pilot)
  start_ollama
  for f in "${FAMILIES[@]}"; do
    ( for proto in lite full; do
        rc=0; "$PY" -u -m src.run --tier large --protocol $proto --family $f --run pilot \
          >> "$LOGS/ucloud_pilot_${f}.log" 2>&1 || rc=$?
        echo "PILOT_DONE $f $proto exit=$rc $(date +%H:%M)" >> "$LOGS/ucloud_progress.log"
      done ) &
  done
  wait
  pack pilot
  ;;
main)
  # One Ollama server per GPU (family_1 -> GPU 0, family_2 -> GPU 1, family_3 -> GPU 2),
  # two workshops at a time per family. Each stream alternates lite k, full k; the two
  # streams take odd and even run numbers, so stopping early leaves the families and
  # protocols balanced. This changes speed only, not prompts or sampling settings.
  range="${2:?usage: main 1-10}"
  lo="${range%-*}"; hi="${range#*-}"
  pkill -f "ollama serve" 2>/dev/null || true; sleep 3
  for i in 0 1 2; do
    CUDA_VISIBLE_DEVICES=$i OLLAMA_HOST="127.0.0.1:$((11440 + i))" OLLAMA_NUM_PARALLEL=2 \
      nohup ollama serve > "$LOGS/ollama_serve_gpu$i.log" 2>&1 &
  done
  for i in 0 1 2; do
    for _ in $(seq 1 60); do curl -s "localhost:$((11440 + i))/api/version" >/dev/null 2>&1 && break; sleep 1; done
  done
  for i in 0 1 2; do
    f="family_$((i + 1))"
    for parity in 0 1; do
      ( for k in $(seq "$lo" "$hi"); do
          [ $((k % 2)) -eq $parity ] || continue
          for proto in lite full; do
            rc=0; OLLAMA_URL="http://localhost:$((11440 + i))" "$PY" -u -m src.run --tier large \
              --protocol $proto --family $f --run "$k" >> "$LOGS/ucloud_main_${f}_s${parity}.log" 2>&1 || rc=$?
            echo "MAIN_DONE run=$k $f $proto exit=$rc $(date +%H:%M)" >> "$LOGS/ucloud_progress.log"
          done
        done ) &
    done
  done
  wait
  pack "main_$range"
  ;;
status)
  tail -n 12 "$LOGS/ucloud_progress.log" 2>/dev/null || echo "no progress yet"
  for f in "${FAMILIES[@]}"; do echo "--- $f"; tail -q -n 1 "$LOGS"/ucloud_*_"$f"*.log 2>/dev/null; done
  nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader
  ;;
*)
  sed -n '2,15p' "$0"; exit 1 ;;
esac
