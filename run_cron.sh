#!/bin/bash
# Cron-ready wrapper script for automated report generation
# This script ensures venv is used and handles logging

set -e  # Exit on error (for cron, you might want to remove this)

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Set up logging
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/reports.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
LOCK_FILE="$SCRIPT_DIR/.report_generation.lock"
PUBLISH_SOURCE_BRANCH="${PUBLISH_SOURCE_BRANCH:-main}"

# Function to log with timestamp
log() {
    echo "[$TIMESTAMP] $1" | tee -a "$LOG_FILE"
}

CURRENT_BRANCH="$(git -C "$SCRIPT_DIR" branch --show-current 2>/dev/null || true)"
if [ "$CURRENT_BRANCH" != "$PUBLISH_SOURCE_BRANCH" ]; then
    log "Skipping scheduled refresh on branch '${CURRENT_BRANCH:-unknown}'; expected '$PUBLISH_SOURCE_BRANCH'."
    exit 0
fi

if ! git -C "$SCRIPT_DIR" diff --quiet || ! git -C "$SCRIPT_DIR" diff --cached --quiet; then
    log "ERROR: Refusing scheduled refresh with uncommitted tracked source changes."
    exit 1
fi

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    log "Another report generation run is already active; exiting without starting a second run."
    exit 0
fi

log "============================================================"
log "Starting automated report generation"
log "Mode: Bitcoin-only (stock and experimental ML reports disabled)"
log "============================================================"

# Check if venv exists
VENV_PYTHON="$SCRIPT_DIR/venv/bin/python"
if [ ! -f "$VENV_PYTHON" ]; then
    log "ERROR: Virtual environment not found at $VENV_PYTHON"
    log "Please run setup_ubuntu.sh first to create the virtual environment"
    exit 1
fi

# Check if .env exists
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    log "WARNING: .env file not found. GitHub operations may fail."
fi

# Run the main script using venv Python
log "Running report generation script..."
if "$VENV_PYTHON" "$SCRIPT_DIR/run.py" >> "$LOG_FILE" 2>&1; then
    log "============================================================"
    log "Report generation completed successfully"
    log "============================================================"
    exit 0
else
    EXIT_CODE=$?
    log "============================================================"
    log "ERROR: Report generation failed with exit code $EXIT_CODE"
    log "============================================================"
    exit $EXIT_CODE
fi
