#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
APP_PY="$ROOT/gui/app.py"
ENV_NAME="qPCR_pack"

SLIM=1
ONEFILE=1

for arg in "$@"; do
  case "$arg" in
    --full) SLIM=0 ;;
    --no-onefile) ONEFILE=0 ;;
    *) echo "Unknown arg: $arg" >&2; exit 2 ;;
  esac
done

CMD=(python "$APP_PY" --build)
(( SLIM ))    && CMD+=("--slim")
(( ONEFILE )) && CMD+=("--onefile")

echo "[INFO] Running: conda run -n ${ENV_NAME} ${CMD[*]}"
conda run -n "$ENV_NAME" "${CMD[@]}"

if [[ "$(uname -s)" == "Darwin" ]]; then
  open "$ROOT/dist" || true
fi
