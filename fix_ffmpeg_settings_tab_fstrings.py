#!/usr/bin/env python3

"""
Script to fix f-string formatting issues in ffmpeg_settings_tab.py
Replaces manually quoted values in f-strings with !r formatter
"""

from pathlib import Path
import re

def fix_fstrings(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Define replacements - Line numbers from grep output
    replacements = [
        (r"f\"Unknown quality preset '([^']*)' encountered\.", 
         r"f\"Unknown quality preset {\\1!r} encountered."),
        
        (r"f\"Profile '([^']*)' is missing key: {e}", 
         r"f\"Profile {\\1!r} is missing key: {e}"),
        
        (r"f\"Error applying profile '([^']*)': {e}", 
         r"f\"Error applying profile {\\1!r}: {e}"),
        
        (r"f\"Settings drifted after applying profile '([^']*)'\. Setting to 'Custom'\.", 
         r"f\"Settings drifted after applying profile {\\1!r}. Setting to 'Custom'."),
        
        (r"f\"Settings now match profile '([^']*)', updating combo\.", 
         r"f\"Settings now match profile {\\1!r}, updating combo."),
    ]
    
    # Apply replacements
    modified_content = content
    for pattern, replacement in replacements:
        modified_content = re.sub(pattern, replacement, modified_content)
    
    # Write the modified content back to the file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(modified_content)
    
    print(f"Updated {file_path}")

if __name__ == "__main__":
    file_path = Path(__file__).parent / "goesvfi" / "gui_tabs" / "ffmpeg_settings_tab.py"
    if file_path.exists():
        fix_fstrings(file_path)
    else:
        print(f"File not found: {file_path}")