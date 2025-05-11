#!/usr/bin/env python3

"""
Script to fix unused imports in main_tab.py.
"""

import re
from pathlib import Path

def fix_imports(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Define import lines to remove or modify
    unused_imports = [
        (r"import logging\n", ""),
        (r"import tempfile\n", ""),
        (r"from typing import .*Set,", r"from typing import"),
        (r"NotRequired,", ""),
        (r"import PIL.Image\n", ""),
        (r"from PyQt6.QtCore import (\n.*QPointF,\n", r"from PyQt6.QtCore import (\n"),
        (r"QColor, ", ""),
        (r"QCursor, ", ""),
        (r"QPixmap, ", ""),
        (r"QDoubleSpinBox, ", ""),
    ]
    
    # Apply the replacements
    modified_content = content
    for pattern, replacement in unused_imports:
        modified_content = re.sub(pattern, replacement, modified_content)
    
    # Check if we made any changes
    if modified_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(modified_content)
        print(f"Updated {file_path} - removed unused imports")
    else:
        print(f"No import changes needed in {file_path}")

if __name__ == "__main__":
    file_path = Path(__file__).parent / "goesvfi" / "gui_tabs" / "main_tab.py"
    if file_path.exists():
        fix_imports(file_path)
    else:
        print(f"File not found: {file_path}")