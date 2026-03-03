#!/bin/bash

# Supply chain security scan script (A06:2025)
# This script runs vulnerability scanners for CDN service and Container Images.

set -e

# Configuration
# Get the absolute path of the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PATH="$PROJECT_ROOT/.venv"

echo "=== Starting Supply Chain Security Scan ==="
echo ""

# 1. CDN Scanning (Python)
echo "[1/2] Scanning CDN Dependencies (pip-audit)..."
if [ -d "$VENV_PATH" ]; then
    source "$VENV_PATH/bin/activate"
    if command -v pip-audit &> /dev/null; then
        pip-audit -r "$PROJECT_ROOT/requirements.txt" || echo "Vulnerabilities found in CDN!"
    else
        echo "Error: pip-audit not found in venv. Run ./scripts/install-depends.sh first."
    fi
else
    # Fallback to checking for global pip-audit if venv doesn't exist (useful for some environments)
    if command -v pip-audit &> /dev/null; then
        pip-audit -r "$PROJECT_ROOT/requirements.txt" || echo "Vulnerabilities found in CDN!"
    else
        echo "Error: Virtual environment not found at $VENV_PATH and pip-audit not found globally."
    fi
fi
echo ""

# 2. Container Scanning (Docker Scout)
echo "[2/2] Scanning Docker Images (Docker Scout)..."
if docker scout version &> /dev/null; then
    echo "Scanning Mock CDN Image (Local)..."
    docker scout cves local://plant-db-cdn-mock-cdn:latest --only-severity high,critical --exit-code || echo "High/Critical vulnerabilities found in Mock CDN Image!"
else
    echo "Docker Scout plugin not found."
    echo "To install, run: curl -sSfL https://raw.githubusercontent.com/docker/scout-cli/main/install.sh | sh"
fi

echo ""
echo "=== Security Scan Complete ==="
echo "Note: Review logs above for specific CVE details."
