#!/usr/bin/env python3

"""
Script to fix f-string formatting issues in date_sorter/sorter.py
Replaces manually quoted values in f-strings with !r formatter
"""

from pathlib import Path

def fix_fstrings(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Lines that need updating
    changes = {
        37: "        print(f\"Error copying file {source_path!r} to {dest_path!r}: {e}\")",
        297: "                        print(f\"Could not parse date from filename {file_name!r} with format {date_format!r}: {e}\")",
        303: "                    print(f\"Error processing file {file_path!r}: {e}\")",
    }
    
    changes_made = False
    for line_num, new_line in changes.items():
        if 0 <= line_num - 1 < len(lines):
            old_line = lines[line_num - 1]
            if old_line.strip() != new_line.strip():
                lines[line_num - 1] = new_line + "\n"
                print(f"Line {line_num}: Updated")
                print(f"  Old: {old_line.strip()}")
                print(f"  New: {new_line.strip()}")
                changes_made = True
    
    if changes_made:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print(f"Updated {file_path}")
    else:
        print(f"No changes needed in {file_path}")

if __name__ == "__main__":
    file_path = Path(__file__).parent / "goesvfi" / "date_sorter" / "sorter.py"
    if file_path.exists():
        fix_fstrings(file_path)
    else:
        print(f"File not found: {file_path}")