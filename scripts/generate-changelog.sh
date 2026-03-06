#!/bin/bash

# Generate changelog automatically from git history
# This script uses auto-changelog to create a CHANGELOG.md file

set -e

echo "Generating changelog from git history..."

# Ensure we're in the project root
cd "$(dirname "$0")/.."

# Install auto-changelog if not present
if ! command -v auto-changelog &> /dev/null; then
    echo "Installing auto-changelog..."
    pip install auto-changelog
fi

# Generate the changelog using the .auto-changelog config file
auto-changelog

echo "Changelog generated successfully at CHANGELOG.md"
