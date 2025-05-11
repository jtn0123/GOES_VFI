#!/usr/bin/env python3
"""
Fix f-string formatting issues in Python files.
"""
import re
import sys
from pathlib import Path

def fix_fstring_quotes(file_path):
    """Fix manually quoted variables in f-strings by using !r conversion."""
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
    
    # Find all matches
    matches = list(re.finditer(pattern, content))
    if not matches:
        print("No f-string issues found.")
        return
    
    # Replace f-strings
    modified_content = content
    count = 0
    
    # Process matches from end to start to avoid index shifting
    for match in reversed(matches):
        var_name = match.group(2)
        start, end = match.span()
        
        # Replace this instance
        fixed = re.sub(
            r'\'([a-zA-Z0-9_]+)\'',
            r'{\1!r}',
            match.group(0)
        )
        
        modified_content = modified_content[:start] + fixed + modified_content[end:]
        count += 1
        print(f"Fixed f-string with variable: {var_name}")
    
    # Write changes back to file
    with open(file_path, 'w') as f:
        f.write(modified_content)
    
    print(f"Fixed {count} f-string formatting issues in {file_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fix_fstrings.py FILE_PATH")
        sys.exit(1)
    
    fix_fstring_quotes(sys.argv[1])