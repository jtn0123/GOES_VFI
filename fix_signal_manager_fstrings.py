#!/usr/bin/env python3

"""
Script to fix f-string formatting issues in signal_manager.py
Replaces manually quoted values in f-strings with !r formatter and fixes missing placeholders
"""

from pathlib import Path
import re

def fix_fstrings(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix strings with manually quoted variables
    pattern = r"f\"([^\"]*)'([^{}]+){([^}]+)}'([^\"]*)\""
    replacement = r'f"\1{\3!r}\4"'
    modified_content = re.sub(pattern, replacement, content)
    
    # Fix f-strings with missing placeholders
    f_string_pattern = r'LOGGER\.debug\(f"Updated directory in view model"\)'
    fixed_string = 'LOGGER.debug("Updated directory in view model")'
    modified_content = modified_content.replace(f_string_pattern, fixed_string)
    
    f_string_pattern = r'LOGGER\.debug\(f"Updated date range in view model"\)'
    fixed_string = 'LOGGER.debug("Updated date range in view model")'
    modified_content = modified_content.replace(f_string_pattern, fixed_string)
    
    # Fix line that's too long
    long_line = 'This diagram shows the flow of signals between the different tabs in the integrity check system.\n\n'
    split_line = '"This diagram shows the flow of signals between " \\\n        "the different tabs in the integrity check system.\\n\\n"'
    modified_content = modified_content.replace(f'"{long_line}"', split_line)
    
    # Fix exception chaining
    old_except = r'raise SignalConnectionError(\n                            f"Failed to connect {signal_name}: {e}"\n                        )'
    new_except = r'raise SignalConnectionError(\n                            f"Failed to connect {signal_name}: {e}"\n                        ) from e'
    modified_content = modified_content.replace(old_except, new_except)
    
    # Write changes
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(modified_content)
    
    print(f"Updated {file_path}")

if __name__ == "__main__":
    file_path = Path(__file__).parent / "goesvfi" / "integrity_check" / "signal_manager.py"
    if file_path.exists():
        fix_fstrings(file_path)
    else:
        print(f"File not found: {file_path}")