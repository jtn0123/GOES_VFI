#!/bin/bash
# Script to run isort on specific files

source .venv/bin/activate

echo "Running isort on specific files..."

# Create backups first
mkdir -p linting_backups/goesvfi
cp goesvfi/gui.py linting_backups/goesvfi/gui.py
cp goesvfi/integrity_check/enhanced_view_model.py linting_backups/goesvfi/integrity_check/enhanced_view_model.py

# Run isort on specific files
isort --profile black goesvfi/gui.py
isort --profile black goesvfi/integrity_check/enhanced_view_model.py

echo "Done running isort on specific files"