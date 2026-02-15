#!/bin/bash
set -e

echo "🔍 Starting SoulSpace Smoke Tests..."
echo "Note: Make sure this script is executable (chmod +x smoke_test.sh)"
echo ""

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✓ Virtual environment activated"
else
    echo "⚠ Warning: Virtual environment not found. Using system Python."
fi

# Run tests
echo -e "\n🧪 Running unit tests..."
pytest tests/ -v --cov --cov-report=term-missing

echo -e "\n✅ All tests passed!"
