#!/usr/bin/env python3
"""Fix typing imports that are incorrectly placed inside docstrings."""

import re
from pathlib import Path


def fix_docstring_import(file_path):
    """Fix a file with typing import inside docstring."""
    with open(file_path, "r") as f:
        content = f.read()

    # Pattern to match docstring with typing import inside
    pattern = r'^"""[^"]*?\nfrom typing import ([^\n]+)\n([^"]+?)"""\n'

    match = re.match(pattern, content, re.MULTILINE | re.DOTALL)
    if match:
        imports = match.group(1)
        rest_of_docstring = match.group(2)

        # Remove the import line from docstring and reconstruct
        new_content = f'"""\n{rest_of_docstring}"""\n\nfrom typing import {imports}\n'

        # Replace the beginning of the file
        content = re.sub(pattern, new_content, content, count=1)

        with open(file_path, "w") as f:
            f.write(content)
        print(f"Fixed {file_path}")
        return True
    return False


# Files to fix
files_to_fix = [
    "goesvfi/integrity_check/enhanced_timeline.py",
    "goesvfi/integrity_check/gui_tab.py",
    "goesvfi/integrity_check/optimized_timeline_tab.py",
    "goesvfi/integrity_check/shared_components.py",
    "goesvfi/integrity_check/tasks.py",
    "goesvfi/integrity_check/sample_processor.py",
    "goesvfi/integrity_check/satellite_integrity_tab_group.py",
    "goesvfi/integrity_check/timeline_visualization.py",
    "goesvfi/integrity_check/view_model.py",
    "goesvfi/integrity_check/visualization_manager.py",
    "goesvfi/integrity_check/remote/cdn_store.py",
    "goesvfi/view_models/processing_view_model.py",
    "goesvfi/gui_backup.py",
]

fixed = 0
for file_path in files_to_fix:
    if Path(file_path).exists():
        if fix_docstring_import(file_path):
            fixed += 1

print(f"\nFixed {fixed} files")
