#!/usr/bin/env bash
# Build synthetic_stakeholders_ucloud.zip for upload to UCloud: code, inputs,
# config and tests only. Excludes the laptop venv, model files, earlier runs,
# the paper and any results archives.
set -euo pipefail
cd "$(dirname "$0")/../.."
name=synthetic_stakeholders
out="$name/synthetic_stakeholders_ucloud.zip"
rm -f "$out"
zip -qr "$out" "$name" \
  -x "$name/.venv/*" "$name/.venv-ucloud/*" "$name/runs/*" "$name/paper/*" "$name/analysis/*" \
     "$name/ollama_models/*" "$name/*.zip" "$name/*.tgz" "*/__pycache__/*" "*.DS_Store"
echo "wrote $out ($(du -h "$out" | cut -f1))"
