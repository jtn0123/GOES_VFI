#!/usr/bin/env python3

"""
Script to fix f-string formatting issues in main_tab.py.
Replaces manually quoted values in f-strings with !r formatter.
"""

import re
from pathlib import Path

def fix_fstrings(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Define replacements for each type of pattern
    # Pattern: f"Something '{variable}' more text"
    pattern1 = r"f\"([^\"]*)'([^{}]+){([^}]+)}'([^\"]*)\""
    replacement1 = r'f"\1{\3!r}\4"'
    
    # Pattern: f"Something: '{args.get('key')}'"
    pattern2 = r"f\"([^\"]*)'([^{}]+){([^}]+\.[^}]+\([^}]+\))}'([^\"]*)\""
    replacement2 = r'f"\1{\3!r}\4"'
    
    # Fix the string content
    modified_content = re.sub(pattern1, replacement1, content)
    modified_content = re.sub(pattern2, replacement2, modified_content)
    
    # Special handling for specific cases that aren't caught by the general patterns
    replacements = [
        (r"print\(f\"SuperButton callback set: {callback\.__name__ if callback else 'None'}\"\)", 
         r"print(f\"SuperButton callback set: {callback.__name__ if callback else None!r}\")"),
        
        (r"print\(f\"Args keys: {list\(args\.keys\(\)\) if args else 'None'}\"\)", 
         r"print(f\"Args keys: {list(args.keys()) if args else None!r}\")"),
        
        (r"print\(f\"In directory path: {args\.get\('in_dir'\)}\"\)", 
         r"print(f\"In directory path: {args.get('in_dir')!r}\")"),
        
        (r"print\(f\"Out file path: {args\.get\('out_file'\)}\"\)", 
         r"print(f\"Out file path: {args.get('out_file')!r}\")"),
        
        (r"print\(f\"Encoder type: {args\.get\('encoder'\)}\"\)", 
         r"print(f\"Encoder type: {args.get('encoder')!r}\")"),
    ]
    
    for old, new in replacements:
        modified_content = re.sub(old, new, modified_content)
    
    # If changes were made, write back to the file
    if modified_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(modified_content)
        print(f"Updated {file_path}")
    else:
        print(f"No changes needed in {file_path}")

if __name__ == "__main__":
    file_path = Path(__file__).parent / "goesvfi" / "gui_tabs" / "main_tab.py"
    if file_path.exists():
        fix_fstrings(file_path)
    else:
        print(f"File not found: {file_path}")