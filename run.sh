#!/usr/bin/env bash
# ==============================================================================
# Empório da Música - Unified Evaluator Launcher
# Automatically activates virtual environment (.venv) if present and launches
# the 3-Stage Evaluator CLI, which branches into Terminal CLI or Streamlit Web App.
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 1. Resolve Python Binary (prioritize project .venv)
if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
elif [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
else
    echo "[ERROR] Python 3 not found on system PATH. Please install python3."
    exit 1
fi

# 2. Execute Evaluator CLI with any forwarded arguments
exec "$PYTHON_BIN" "$SCRIPT_DIR/src/cli.py" "$@"
