#!/bin/bash

# Ensure we are in the project root
PROJECT_ROOT=$(dirname "$(dirname "$0")")
cd "$PROJECT_ROOT" || exit 1

# Check if .venv exists
if [ ! -d ".venv" ]; then
    echo "Error: .venv not found. Please create it first: python -m venv .venv"
    exit 1
fi

PYTHON_EXEC="./.venv/bin/python"
PIP_COMPILE="./.venv/bin/pip-compile"

# 1. Update/Lock Dependencies if requirements.in is newer than requirements.txt
if [[ requirements.in -nt requirements.txt ]]; then
    echo "--- requirements.in changed. Re-locking dependencies with hashes ---"
    $PIP_COMPILE --generate-hashes --allow-unsafe requirements.in --output-file requirements.txt
fi

# 2. Install dependencies with hash verification
echo "--- Installing dependencies from requirements.txt with --require-hashes ---"
$PYTHON_EXEC -m pip install --require-hashes -r requirements.txt

echo "--- Dependency update and installation successful ---"
