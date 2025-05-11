#!/bin/bash
# This script fixes linting issues in specific files only

echo "Fixing trailing whitespace..."
# Fix trailing whitespace in specific files
sed -i '' 's/[[:space:]]*$//' .github/workflows/linting.yml
sed -i '' 's/[[:space:]]*$//' fix_common_lints.sh
sed -i '' 's/[[:space:]]*$//' bulk_lint_fix.py
sed -i '' 's/[[:space:]]*$//' test_precommit.py

echo "Fixing end-of-file newlines..."
# Make sure files end with a newline
for file in docs/LINTING_SETUP.md .github/workflows/linting.yml fix_common_lints.sh LINTING_PROGRESS.md bulk_lint_fix.py test_precommit.py; do
    if [ -f "$file" ]; then
        # Check if file doesn't end with newline
        if [ "$(tail -c 1 "$file" | wc -l)" -eq 0 ]; then
            echo "" >> "$file"
            echo "Added newline to $file"
        fi
    else
        echo "File not found: $file"
    fi
done

echo "Done fixing basic linting issues"