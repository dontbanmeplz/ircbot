#!/bin/bash
# Quick start script for the IRC DCC Bot

echo "IRC DCC Bot - Quick Start"
echo "========================="
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q irc flask

echo ""
echo "Setup complete!"
echo ""
echo "Choose how to run the bot:"
echo ""
echo "1. Simple example (command line):"
echo "   python example.py"
echo ""
echo "2. Web interface:"
echo "   python web_interface.py"
echo "   Then open http://localhost:5000 in your browser"
echo ""
