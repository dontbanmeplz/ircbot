#!/bin/bash
# Start IRC Book Downloader Web Interface

echo "=========================================="
echo " IRC Book Downloader Web Interface"
echo "=========================================="
echo ""

# Check if config.py exists
if [ ! -f "config.py" ]; then
    echo "ERROR: config.py not found!"
    echo "Please make sure config.py exists in the current directory."
    exit 1
fi

# Create required directories
echo "Creating required directories..."
mkdir -p downloads/library downloads/temp
echo "✓ Directories created"
echo ""

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "ERROR: uv is not installed!"
    echo "Please install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
uv sync
echo "✓ Dependencies installed"
echo ""

# Start the application
echo "Starting web interface..."
echo ""
echo "=========================================="
echo " Server starting..."
echo " Default login password: admin123"
echo " (Change this in config.py!)"
echo "=========================================="
echo ""

uv run python app.py
