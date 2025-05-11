#!/usr/bin/env python3

"""
Script to fix f-string formatting issues in main_tab.py - version 2.
Uses line-by-line replacement for more targeted fixes.
"""

from pathlib import Path

def fix_fstrings(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Define specific line replacements
    replacements = {
        1684: "            LOGGER.debug(f\"Sample FFmpeg command with crop/fps: {' '.join(command)}\")",  # This is fine, the quotes are inside a join operation
        2300: "                    f\"RIFE executable not found for model {key!r} in {model_dir}\"",
        2315: "                LOGGER.info(f\"Analyzing RIFE executable for model {key!r}: {rife_exe}\")",
        2326: "                        f\"Analysis complete for {key}. Capabilities: {details.get('capabilities')}\"",
        2330: "                        f\"Failed to analyze RIFE executable for model {key!r}: {e}\"",
        2347: "            display_name = f\"{key} (v{details.get('version', 'Unknown')})\"",
        2558: "                LOGGER.debug(f\"Raw input directory from settings: {in_dir_str!r}\")",
        2634: "            LOGGER.debug(f\"Raw output file from settings: {out_file_str!r}\")",
        2737: "            LOGGER.debug(f\"Setting thread spec: {thread_spec_value!r}\")",
        2796: "                LOGGER.debug(f\"Raw crop rectangle from settings: {crop_rect_str!r}\")",
        2870: "                            f\"Saving input directory from text field: {text_dir_path!r}\"",
        2890: "                        f\"Saving input directory from MainWindow (absolute): {in_dir_str!r}\"",
        2912: "                        f\"Saving output file path (absolute): {out_file_str!r}\"",
        2922: "                        f\"Saving output file path (non-resolved): {out_file_str!r}\"",
        2960: "            LOGGER.debug(f\"Saving thread spec: {thread_spec!r}\")",
        2979: "            LOGGER.debug(f\"Saving resolution km: {res_km!r}\")",
    }
    
    changes_made = False
    for line_num, replacement in replacements.items():
        # Convert to 0-indexed for list access
        idx = line_num - 1
        if 0 <= idx < len(lines):
            if lines[idx].strip() != replacement.strip():
                lines[idx] = replacement + "\n"
                print(f"Line {line_num}: fixed")
                changes_made = True
    
    if changes_made:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print(f"Updated {file_path}")
    else:
        print(f"No changes needed in {file_path}")

if __name__ == "__main__":
    file_path = Path(__file__).parent / "goesvfi" / "gui_tabs" / "main_tab.py"
    if file_path.exists():
        fix_fstrings(file_path)
    else:
        print(f"File not found: {file_path}")