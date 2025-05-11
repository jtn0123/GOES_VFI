#!/usr/bin/env python3
"""
Fix f-string formatting issues in goesvfi/integrity_check module.
"""
import re
from pathlib import Path

def fix_fstrings_in_file(file_path):
    """Fix manually quoted variables in f-strings by using !r conversion in a file."""
    print(f"Fixing f-string quotes in {file_path}")
    
    # Create backup
    path = Path(file_path)
    backup_path = path.with_suffix(path.suffix + ".fstring.bak")
    backup_path.write_text(path.read_text())
    print(f"Backup created at {backup_path}")
    
    # Read file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find f-strings with manually quoted variables
    pattern = r'f"([^"]*?)\'([a-zA-Z0-9_]+)\'([^"]*?)"'
    replacement = r'f"\1{\2!r}\3"'
    
    # Apply replacement
    modified_content = re.sub(pattern, replacement, content)
    
    # Write changes back to file
    with open(file_path, 'w') as f:
        f.write(modified_content)
    
    print(f"Fixed f-string formatting issues in {file_path}")

# Specific files to fix
files_to_fix = [
    "goesvfi/integrity_check/enhanced_gui_tab.py",
    "goesvfi/integrity_check/render/netcdf.py"
]

for file_path in files_to_fix:
    fix_fstrings_in_file(file_path)