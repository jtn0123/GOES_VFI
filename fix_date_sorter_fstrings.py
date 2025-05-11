#!/usr/bin/env python3

"""
Script to fix f-string formatting issues in date_sorter/sorter.py
Replaces manually quoted values in f-strings with !r formatter
"""

import re
from pathlib import Path

def fix_fstrings(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Define replacements
    replacements = [
        # Line 37
        (r"f\"Error copying file '{source_path}' to '{dest_path}': {e}\"", 
         r"f\"Error copying file {source_path!r} to {dest_path!r}: {e}\""),
        
        # Line 127
        (r"f\"\\nDate: {day_str}\"", 
         r"f\"\\nDate: {day_str}\""),  # This one looks fine as is (no quotes inside)
        
        # Line 129-132 - No change needed, these are using terminal color codes with fixed strings
        
        # Line 140
        (r"f\"  \\033[31mMissing:\\033[0m {dt_obj.strftime('%Y-%m-%d %H:%M:%S')}\"",
         r"f\"  \\033[31mMissing:\\033[0m {dt_obj.strftime('%Y-%m-%d %H:%M:%S')}\""),  # Using strftime with format, keep as is
        
        # Line 235
        (r"f\"Source directory not found: {source}\"",
         r"f\"Source directory not found: {source}\""),  # No quotes, keep as is
        
        # Line 246
        (r"\"Sorting cancelled.\"",
         r"\"Sorting cancelled.\""),  # Not an f-string, keep as is
        
        # Line 297-298 - Multi-line f-string with quotes
        (r"f\"Could not parse date from filename {file_name} with format {date_format}: {e}\"",
         r"f\"Could not parse date from filename {file_name!r} with format {date_format!r}: {e}\""),
        
        # Line 303
        (r"f\"Error processing file {file_path}: {e}\"",
         r"f\"Error processing file {file_path!r}: {e}\""),
        
        # Line 320
        (r"\"DateSorter class is intended to be used as a module.\"",
         r"\"DateSorter class is intended to be used as a module.\"")  # Not an f-string, keep as is
    ]
    
    modified_content = content
    changes_made = False
    
    for old, new in replacements:
        if old != new:  # Only apply when there's an actual change
            old_count = modified_content.count(old)
            if old_count > 0:
                modified_content = modified_content.replace(old, new)
                changes_made = True
                print(f"Replaced {old_count} instance(s) of: {old}")
                print(f"With: {new}")
    
    if changes_made:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(modified_content)
        print(f"Updated {file_path}")
    else:
        print(f"No changes needed in {file_path}")

if __name__ == "__main__":
    file_path = Path(__file__).parent / "goesvfi" / "date_sorter" / "sorter.py"
    if file_path.exists():
        fix_fstrings(file_path)
    else:
        print(f"File not found: {file_path}")