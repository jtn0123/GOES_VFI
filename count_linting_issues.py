#!/usr/bin/env python3
"""
Count linting issues in the codebase using pre-commit.
"""

import os
import subprocess
import sys
from pathlib import Path

# Directories to check
DIRS_TO_CHECK = [
    "goesvfi",
    "tests",
    "examples"
]

def count_issues_for_path(path):
    """Run pre-commit on a path and count the issues."""
    try:
        result = subprocess.run(
            ["pre-commit", "run", "flake8", "--files", path], 
            check=False, 
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            # Parse output to find issue counts if present
            output = result.stderr
            if "issues" in output:
                # Extract the numbers before 'issues'
                lines = output.strip().split('\n')
                for line in lines:
                    if "issues" in line and "❌" in line:
                        # Extract the number before "issues"
                        parts = line.split("found")
                        if len(parts) > 1:
                            number_part = parts[0].strip().split(" ")[-1]
                            try:
                                return int(number_part)
                            except ValueError:
                                pass
                        
            # Count F, E, W codes in output if we couldn't find "issues" text
            f_count = output.count(" F")
            e_count = output.count(" E")
            w_count = output.count(" W")
            b_count = output.count(" B")
            c_count = output.count(" C")
            
            total = f_count + e_count + w_count + b_count + c_count
            return total if total > 0 else 1  # At least 1 if we had an error
        
        return 0  # No issues
    except Exception as e:
        print(f"Error running pre-commit on {path}: {e}")
        return 0

def main():
    """Main function."""
    repo_root = Path(__file__).parent
    
    total_issues = 0
    for dir_path in DIRS_TO_CHECK:
        full_path = repo_root / dir_path
        if not full_path.exists():
            print(f"Directory {full_path} does not exist. Skipping.")
            continue
        
        # Process each python file in the directory
        for root, _, files in os.walk(full_path):
            for file in files:
                if file.endswith(".py"):
                    file_path = Path(root) / file
                    rel_path = file_path.relative_to(repo_root)
                    issues = count_issues_for_path(str(file_path))
                    
                    if issues > 0:
                        print(f"{rel_path}: {issues} issues")
                        total_issues += issues
    
    print(f"\nTotal issues found: {total_issues}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())