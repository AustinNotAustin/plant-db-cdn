#!/bin/bash

# Ensure we're in the virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Warning: No virtual environment detected (VIRTUAL_ENV not set)."
    echo "This script should ideally run within your .venv."
fi

# Check if 'pip-audit' is installed, install if missing
if ! command -v pip-audit &> /dev/null; then
    echo "pip-audit tool not found. Installing..."
    pip install pip-audit
fi

# Run the audit
echo "--- Running Dependency Security Audit (pip-audit) ---"
pip-audit -r requirements.txt

echo "--- Audit Complete ---"
