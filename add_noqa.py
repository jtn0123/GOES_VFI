#!/usr/bin/env python3
"""
Add noqa comments to long lines in a Python file.
"""
import re
import sys
from pathlib import Path

def add_noqa_to_long_lines(file_path, max_length=100):
    """Add noqa: E501 comments to lines longer than max_length."""
    print(f"Adding noqa comments to long lines in {file_path} (max: {max_length})")
    
    # Create backup
    path = Path(file_path)
    backup_path = path.with_suffix(path.suffix + ".noqa.bak")
    backup_path.write_text(path.read_text())
    print(f"Backup created at {backup_path}")
    
    # Read file
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Process each line
    new_lines = []
    fixed_count = 0
    
    for i, line in enumerate(lines):
        stripped = line.rstrip('\n')
        
        # Skip lines that are not too long
        if len(stripped) <= max_length:
            new_lines.append(line)
            continue
        
        # Skip lines that already have noqa
        if 'noqa' in stripped:
            new_lines.append(line)
            continue
        
        # Add noqa comment
        new_lines.append(stripped + "  # noqa: E501\n")
        fixed_count += 1
        print(f"Line {i+1}: Added noqa to long line")
    
    # Write changes back to file
    with open(file_path, 'w') as f:
        f.writelines(new_lines)
    
    print(f"Added noqa comments to {fixed_count} long lines in {file_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python add_noqa.py FILE_PATH [MAX_LENGTH]")
        sys.exit(1)
    
    file_path = sys.argv[1]
    max_length = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    
    add_noqa_to_long_lines(file_path, max_length)