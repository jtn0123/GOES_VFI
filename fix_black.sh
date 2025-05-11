#!/bin/bash
# Script to run black on specific files

source .venv/bin/activate

echo "Running black on specific files..."

# Create backups first if they don't exist
mkdir -p linting_backups/goesvfi
mkdir -p linting_backups/goesvfi/integrity_check
mkdir -p linting_backups/goesvfi/pipeline

if [ ! -f linting_backups/goesvfi/gui.py ]; then
    cp goesvfi/gui.py linting_backups/goesvfi/gui.py
fi

if [ ! -f linting_backups/goesvfi/integrity_check/enhanced_view_model.py ]; then
    cp goesvfi/integrity_check/enhanced_view_model.py linting_backups/goesvfi/integrity_check/enhanced_view_model.py
fi

if [ ! -f linting_backups/goesvfi/pipeline/sanchez_processor.py ]; then
    cp goesvfi/pipeline/sanchez_processor.py linting_backups/goesvfi/pipeline/sanchez_processor.py
fi

# Run black on specific files
black --line-length=88 goesvfi/gui.py
black --line-length=88 goesvfi/integrity_check/enhanced_view_model.py
black --line-length=88 goesvfi/pipeline/sanchez_processor.py
black --line-length=88 bulk_lint_fix.py
black --line-length=88 test_precommit.py

echo "Done running black on specific files"