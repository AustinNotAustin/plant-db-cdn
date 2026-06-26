#!/bin/bash

# Simple Starter Script for Mock S3
# Usage: ./starter.sh [start|stop]

set -e

# Load environment variables if .env exists
if [ -f .env ]; then
  # Strip inline comments and whitespace before exporting
  export $(grep -v '^#' .env | sed 's/#.*//' | xargs)
fi

# Validation: Ensure all required variables are set after loading .env
REQUIRED_VARS=("SRV_MOCK_S3_PORT" "SRV_MOCK_S3_URL")
for VAR in "${REQUIRED_VARS[@]}"; do
  if [ -z "${!VAR}" ]; then
    echo "Error: Required environment variable '$VAR' is not set in .env"
    exit 1
  fi
done

COMMAND=$1
OPTION=$2

case $COMMAND in
  start)
    echo "--- Starting Mock S3 via Docker Compose (Port: $SRV_MOCK_S3_PORT) ---"
    if [ "$OPTION" == "--build" ]; then
      docker compose build
    fi
    docker compose up -d
    ;;
  stop)
    echo "--- Stopping Mock S3 ---"
    docker compose down || true
    exit 0
    ;;
  *)
    echo "Usage: $0 [start|stop] (optional: --build)"
    exit 1
    ;;
esac

# Summary
echo ""
echo "Mock S3 started successfully."
echo "   S3 Endpoint: http://localhost:$SRV_MOCK_S3_PORT"
echo "   Public shortcut: http://localhost:$SRV_MOCK_S3_PORT/cdn"
echo ""
echo "API Documentation:"
echo "   Swagger UI: http://localhost:$SRV_MOCK_S3_PORT/docs"
echo "   ReDoc:      http://localhost:$SRV_MOCK_S3_PORT/redoc"
echo ""
echo "To stop the service, run: ./starter.sh stop"
