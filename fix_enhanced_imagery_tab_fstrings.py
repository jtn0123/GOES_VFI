#!/usr/bin/env python3

"""
Script to fix f-string formatting issues in enhanced_imagery_tab.py.
Replaces manually quoted values in f-strings with !r formatter.
"""

from pathlib import Path

def fix_fstrings(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Define specific line replacements
    replacements = {
        106: '            f"Preview: {ExtendedChannelType.get_display_name(self.request[\'channel\'])}"',  # This is fine as is - quotes in a dict key
        1892: '            f"Processing {ExtendedChannelType.get_display_name(request[\'channel\'])}..."',  # This is fine as is - quotes in a dict key
    }
    
    # Check for any changes needed
    changes_made = False
    for line_num, replacement in replacements.items():
        # Convert to 0-indexed for list access
        idx = line_num - 1
        if 0 <= idx < len(lines):
            if lines[idx].strip() != replacement.strip():
                lines[idx] = replacement + "\n"
                print(f"Line {line_num}: fixed")
                changes_made = True
    
    # No changes needed for this file, since the quotes are part of dictionary access
    if changes_made:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print(f"Updated {file_path}")
    else:
        print(f"No changes needed in {file_path} - quotes are part of dictionary keys")
    
    # Let's check for unused imports as well
    check_unused_imports(file_path)

def check_unused_imports(file_path):
    # Run pre-commit to check for unused imports
    import subprocess
    
    try:
        result = subprocess.run(
            ["pre-commit", "run", "flake8", "--files", str(file_path)],
            capture_output=True,
            text=True,
            check=False
        )
        
        if "F401" in result.stderr:
            print("\nUnused imports detected. You might want to fix these:")
            for line in result.stderr.splitlines():
                if "F401" in line:
                    print(line)
    except Exception as e:
        print(f"Error checking for unused imports: {e}")

if __name__ == "__main__":
    file_path = Path(__file__).parent / "goesvfi" / "integrity_check" / "enhanced_imagery_tab.py"
    if file_path.exists():
        fix_fstrings(file_path)
    else:
        print(f"File not found: {file_path}")