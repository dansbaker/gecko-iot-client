#!/bin/bash
# Build script for Gecko IoT Client documentation

set -e  # Exit on any error

echo "🔧 Building Gecko IoT Client Documentation"
echo "=========================================="

# Navigate to project root
cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d "../../venv" ]; then
    echo "❌ Virtual environment not found. Please run:"
    echo "   cd ../../ && python -m venv venv && source venv/bin/activate"
    exit 1
fi

# Activate virtual environment
echo "📦 Activating virtual environment..."
source ../../venv/bin/activate

# Install documentation dependencies
echo "📥 Installing documentation dependencies..."
pip install -e ".[docs]" > /dev/null 2>&1

# Clean previous build
echo "🧹 Cleaning previous build..."
make clean > /dev/null 2>&1

# Build documentation
echo "🏗️  Building HTML documentation..."
make html

# Check if build was successful
if [ -f "build/html/index.html" ]; then
    echo "✅ Documentation built successfully!"
    echo "📂 Documentation available at: docs/build/html/index.html"
    echo "🌐 Open with: open docs/build/html/index.html"
else
    echo "❌ Documentation build failed!"
    exit 1
fi