#!/bin/bash
# Script to fix common linting issues in the codebase

# Exit on error
set -e

# Print commands before execution
set -x

# Create backup directory
mkdir -p linting_backups

# Fix trailing whitespace and ensure files end with newline
find goesvfi -name "*.py" -type f | while read -r file; do
    # Create backup
    rel_path=$(realpath --relative-to=. "$file")
    backup_path="linting_backups/$rel_path"
    mkdir -p "$(dirname "$backup_path")"
    cp "$file" "$backup_path"
    
    # Fix trailing whitespace and ensure final newline
    sed -i 's/[[:space:]]*$//' "$file"
    
    # Ensure file ends with a newline if it doesn't already
    if [ "$(tail -c1 "$file" | wc -l)" -eq 0 ]; then
        echo "" >> "$file"
    fi
    
    echo "Fixed whitespace in $file"
done

# Sort imports with isort
python -m isort --profile black goesvfi

# Format code with black
python -m black --line-length=88 goesvfi

# Run flake8 to see remaining issues
python -m flake8 goesvfi --count --select=E9,F63,F7,F82 --show-source --statistics

echo "Linting fixes applied. Check for remaining issues with flake8."