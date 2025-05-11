#!/usr/bin/env python3
"""
Fix specific f-string formatting issues in goesvfi/gui.py.
"""
import re
from pathlib import Path

def fix_specific_fstrings():
    """Fix specific manually quoted variables in f-strings by using !r conversion."""
    file_path = "goesvfi/gui.py"
    print(f"Fixing specific f-string issues in {file_path}")
    
    # Create backup
    path = Path(file_path)
    backup_path = path.with_suffix(path.suffix + ".specific.bak")
    backup_path.write_text(path.read_text())
    print(f"Backup created at {backup_path}")
    
    # Read file
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Specific replacements (line number, original text, replacement text)
    replacements = [
        (520, "f\"Saving input directory directly (absolute): '{in_dir_str}'\"", 
              "f\"Saving input directory directly (absolute): {in_dir_str!r}\""),
        
        (563, "f\"Verification - Input directory after direct save: '{saved_dir}'\"", 
              "f\"Verification - Input directory after direct save: {saved_dir!r}\""),
        
        (629, "f\"Final verification - Input directory: '{saved_dir}'\"", 
              "f\"Final verification - Input directory: {saved_dir!r}\""),
        
        (652, "f\"Saving crop rectangle directly: '{rect_str}'\"", 
              "f\"Saving crop rectangle directly: {rect_str!r}\""),
        
        (692, "f\"Verification - Crop rectangle after direct save: '{saved_rect}'\"", 
              "f\"Verification - Crop rectangle after direct save: {saved_rect!r}\""),
        
        (756, "f\"Final verification - Crop rectangle: '{saved_rect}'\"", 
              "f\"Final verification - Crop rectangle: {saved_rect!r}\""),
        
        (1090, "f\"Key '{key}' in profile but not in current settings.\"", 
               "f\"Key {key!r} in profile but not in current settings.\"")
    ]
    
    # Apply replacements
    fixed_count = 0
    
    for line_num, old_text, new_text in replacements:
        # Line numbers in the file are 1-based, but list indices are 0-based
        line_idx = line_num - 1
        
        if line_idx < len(lines):
            line = lines[line_idx]
            if old_text in line:
                lines[line_idx] = line.replace(old_text, new_text)
                fixed_count += 1
                print(f"Fixed line {line_num}")
            else:
                print(f"Warning: Expected text not found in line {line_num}")
    
    # Write changes back to file
    with open(file_path, 'w') as f:
        f.writelines(lines)
    
    print(f"Fixed {fixed_count} specific f-string issues in {file_path}")

if __name__ == "__main__":
    fix_specific_fstrings()