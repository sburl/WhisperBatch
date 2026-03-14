#!/usr/bin/env bash
# Cross-platform setup script for WhisperBatch
#  • Creates a virtual environment using the default python3 on the system
#  • Installs dependencies from requirements.txt
#  • Ensures the correct PyTorch wheel is installed for Apple-Silicon macOS
#
# Usage: ./setup.sh
set -euo pipefail

PROJECT_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$PROJECT_DIR"

# Pick the python interpreter: prefer python3 from PATH
PYTHON_BIN=${PYTHON_BIN:-$(command -v python3 || true)}
if [[ -z "$PYTHON_BIN" ]]; then
  echo "❌ python3 not found in PATH. Please install Python 3.9+ first." >&2
  exit 1
fi

# Print versions for debug
$PYTHON_BIN -V
uname -a

VENV_DIR=".venv"
if [[ -d "$VENV_DIR" ]]; then
  echo "ℹ️  Removing existing virtual-env $VENV_DIR"
  rm -rf "$VENV_DIR"
fi

echo "➡️  Creating virtual-env ($VENV_DIR)"
$PYTHON_BIN -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Upgrade pip + wheel
pip install --upgrade pip wheel

echo "➡️  Installing Python requirements"
pip install -r requirements.txt

echo "✅ Setup complete! Activate the environment with: source $VENV_DIR/bin/activate" 