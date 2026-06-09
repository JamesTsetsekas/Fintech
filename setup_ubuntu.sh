#!/bin/bash
# Setup script for Ubuntu Server
# This creates a virtual environment and installs all requirements

set -e  # Exit on error

echo "======================================================================"
echo "Fintech Reports - Ubuntu Setup"
echo "======================================================================"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Install it with: sudo apt install python3 python3-venv python3-pip"
    exit 1
fi

echo "Python version: $(python3 --version)"
echo ""

# Create virtual environment
VENV_DIR="$SCRIPT_DIR/venv"
if [ -d "$VENV_DIR" ]; then
    echo "Virtual environment already exists at: $VENV_DIR"
    read -p "Do you want to recreate it? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Removing old virtual environment..."
        rm -rf "$VENV_DIR"
    else
        echo "Using existing virtual environment..."
    fi
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo "✓ Virtual environment created at: $VENV_DIR"
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip
echo ""

# Install root requirements first (python-dotenv)
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    echo "Installing root requirements..."
    pip install -r "$SCRIPT_DIR/requirements.txt"
    echo ""
fi

# Install all project requirements
echo "Installing all project requirements..."
python "$SCRIPT_DIR/install_all_requirements.py"
echo ""

echo "======================================================================"
echo "Setup Complete!"
echo "======================================================================"
echo ""
echo "Virtual environment location: $VENV_DIR"
echo ""
echo "To use the virtual environment manually:"
echo "  source $VENV_DIR/bin/activate"
echo ""
echo "To run the reports manually:"
echo "  $VENV_DIR/bin/python run.py"
echo "  # This publishes the latest generated site to the gh-pages branch."
echo "  # Generated report outputs are ignored on main to avoid git history bloat."
echo ""
echo "For cron setup, add this to your crontab (crontab -e):"
echo ""
echo "  # Recommended: Use the wrapper script (handles venv and logging automatically)"
echo "  # Run reports every day at 2 AM"
echo "  0 2 * * * $SCRIPT_DIR/run_cron.sh"
echo ""
echo "  # Or every 6 hours:"
echo "  0 */6 * * * $SCRIPT_DIR/run_cron.sh"
echo ""
echo "  # Or every hour:"
echo "  0 * * * * $SCRIPT_DIR/run_cron.sh"
echo ""
echo "  # Alternative: Direct Python call (if you prefer)"
echo "  0 2 * * * cd $SCRIPT_DIR && $VENV_DIR/bin/python run.py >> $SCRIPT_DIR/logs/reports.log 2>&1"
echo ""
echo "Don't forget to:"
echo "  1. Create .env file with your GITHUB_TOKEN"
echo "  2. Create logs directory: mkdir -p $SCRIPT_DIR/logs"
echo ""
echo "======================================================================"
