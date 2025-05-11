#!/usr/bin/env python3
"""
Script to check the complexity of specific functions using flake8.
"""

import os
import subprocess
import re
from pathlib import Path

# Files and functions to check
FILES_TO_CHECK = [
    # Format: (file_path, function_name_pattern)
    ("goesvfi/integrity_check/time_index_refactored.py", r"extract_timestamp_from_directory_name"),
    ("goesvfi/integrity_check/time_index_refactored.py", r"to_s3_key"),
    ("goesvfi/integrity_check/time_index_refactored.py", r"scan_directory_for_timestamps"),
    ("goesvfi/integrity_check/reconcile_manager_refactored.py", r"fetch_missing_files"),
    ("goesvfi/file_sorter/sorter_refactored.py", r"FileSorter\.sort_files"),
]

# Compare to original files/functions
ORIGINAL_FILES = [
    ("goesvfi/integrity_check/time_index.py", r"extract_timestamp_from_directory_name"),
    ("goesvfi/integrity_check/time_index.py", r"to_s3_key"),
    ("goesvfi/integrity_check/time_index.py", r"scan_directory_for_timestamps"),
    ("goesvfi/integrity_check/reconcile_manager.py", r"fetch_missing_files"),
    ("goesvfi/file_sorter/sorter.py", r"FileSorter\.sort_files"),
]

def run_flake8_on_file(file_path):
    """Run flake8 on a specific file to check for complexity issues."""
    cmd = ["flake8", "--max-complexity=10", file_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout

def parse_complexity_issues(flake8_output, function_pattern):
    """Parse flake8 output to find complexity issues for a specific function."""
    # Pattern to match: filename:line:col: C901 'function_name' is too complex (N)
    pattern = rf".*C901 '({function_pattern})' is too complex \((\d+)\)"
    issues = []

    for line in flake8_output.splitlines():
        match = re.search(pattern, line)
        if match:
            function_name = match.group(1)
            complexity = int(match.group(2))
            # Try to extract line number from the flake8 output format
            try:
                line_parts = line.split(":")
                if len(line_parts) >= 2:
                    line_num = int(line_parts[1])
                else:
                    line_num = 0  # Default if can't parse
            except (ValueError, IndexError):
                line_num = 0  # Default if can't parse

            issues.append((function_name, complexity, line_num))

    return issues

def check_files():
    """Check all specified files for complexity issues."""
    print("\n=== CHECKING REFACTORED FUNCTIONS ===\n")
    
    for file_path, function_pattern in FILES_TO_CHECK:
        full_path = Path(file_path)
        if not full_path.exists():
            print(f"File not found: {file_path}")
            continue
            
        print(f"\nChecking {file_path} for function matching '{function_pattern}':")
        flake8_output = run_flake8_on_file(file_path)
        issues = parse_complexity_issues(flake8_output, function_pattern)
        
        if issues:
            for function_name, complexity, line_num in issues:
                print(f"  - Line {line_num}: Function '{function_name}' has complexity of {complexity}")
        else:
            print(f"  - No complexity issues found! Functions matching '{function_pattern}' are under the threshold.")
    
    print("\n=== CHECKING ORIGINAL FUNCTIONS FOR COMPARISON ===\n")
    
    for file_path, function_pattern in ORIGINAL_FILES:
        full_path = Path(file_path)
        if not full_path.exists():
            print(f"File not found: {file_path}")
            continue
            
        print(f"\nChecking {file_path} for function matching '{function_pattern}':")
        flake8_output = run_flake8_on_file(file_path)
        issues = parse_complexity_issues(flake8_output, function_pattern)
        
        if issues:
            for function_name, complexity, line_num in issues:
                print(f"  - Line {line_num}: Function '{function_name}' has complexity of {complexity}")
        else:
            print(f"  - No complexity issues found! Functions matching '{function_pattern}' are under the threshold.")

if __name__ == "__main__":
    check_files()