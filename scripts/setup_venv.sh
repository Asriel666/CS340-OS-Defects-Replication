#!/usr/bin/env sh
set -eu
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON_BIN=${PYTHON_BIN:-python3}
"$PYTHON_BIN" -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ required; tested on 3.12.14"'
"$PYTHON_BIN" -m venv "$PROJECT_DIR/.venv"
"$PROJECT_DIR/.venv/bin/python" -m pip install -r "$PROJECT_DIR/requirements.txt"
"$PROJECT_DIR/.venv/bin/python" -c 'import shutil; assert shutil.which("pdftoppm"), "Install Poppler (pdftoppm) for figures and PDF QA"'
echo 'Environment ready. Use .venv/bin/python scripts/run_stage.py --stage 1'
