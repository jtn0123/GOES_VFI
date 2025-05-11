#!/usr/bin/env python3

"""
Script to fix f-string formatting issues in file_sorter/sorter.py
Replaces manually quoted values in f-strings with !r formatter
"""

from pathlib import Path

def fix_fstrings(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Lines that need updating
    changes = {
        57: "            print(f\"Error copying file {source_path!r} to {dest_path!r}: {e}\")",
        108: "            print(f\"Error retrieving date folders from source directory: {e}\")",
        112: "        print(f\"Found {total_folders} date folders in source directory.\")",
        151: "                print(\"Cancellation requested during file collection.\")",
        161: "                print(\"Encountered a null folder entry. Skipping...\")",
        181: "                print(f\"Error retrieving files in folder {folder.name!r}: {e}\")",
        188: "        print(f\"Total files to process: {total_files}\")",
        202: "                print(\"Cancellation requested during file processing.\")",
        238: "                        print(f\"Error creating folder {target_folder!r}: {e}\")",
        337: "                print(\n                    f\"\\nError processing file {file_path.name!r}: {e}\"\n                )",
        348: "        print(\"Script execution completed.\")",
        349: "        print(f\"Total execution time: {total_duration}\")",
        350: "        print(f\"Files copied: {self.files_copied}\")",
        351: "        print(f\"Files skipped: {self.files_skipped}\")",
        354: "        print(f\"Total data copied: {size_in_mb} MB\")",
        362: "        print(f\"Average time per file: {average_time_per_file} seconds\")",
        374: "        print(\"Returning stats:\", final_stats)",
        375: "        print(\"\\nAnalysis complete!\")",
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
    file_path = Path(__file__).parent / "goesvfi" / "file_sorter" / "sorter.py"
    if file_path.exists():
        fix_fstrings(file_path)
    else:
        print(f"File not found: {file_path}")