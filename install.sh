#!/bin/bash
set -e

echo "=========================================="
echo "Protein Evaluator Installation Script"
echo "=========================================="

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "1. Checking prerequisites..."
command -v python3 >/dev/null 2>&1 || { echo "Python 3 is required but not installed. Aborting." >&2; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node.js is required but not installed. Aborting." >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "npm is required but not installed. Aborting." >&2; exit 1; }

echo "   Python 3: $(python3 --version)"
echo "   Node.js: $(node --version)"
echo "   npm: $(npm --version)"

# Create virtual environment if it doesn't exist
echo ""
echo "2. Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "   Virtual environment created."
else
    echo "   Virtual environment already exists."
fi

# Activate virtual environment
source .venv/bin/activate

# Install Python dependencies
echo ""
echo "3. Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "   Python dependencies installed."

# Install frontend dependencies
echo ""
echo "4. Installing frontend dependencies..."
cd frontend
npm install
cd ..
echo "   Frontend dependencies installed."

# Setup environment file
echo ""
echo "5. Setting up environment configuration..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "   Created .env from .env.example"
    echo "   Please edit .env and add your API keys!"
else
    echo "   .env already exists, skipping."
fi

echo ""
echo "=========================================="
echo "Installation complete!"
echo "=========================================="
echo ""
echo "To start the server:"
echo "  source .venv/bin/activate"
echo "  FLASK_APP=app.py python3 -m flask run --port 5002"
echo ""
echo "To start the frontend (in another terminal):"
echo "  cd frontend && npm run dev"
echo ""
