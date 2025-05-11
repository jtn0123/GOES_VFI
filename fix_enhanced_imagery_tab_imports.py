#!/usr/bin/env python3

"""
Script to fix unused imports in enhanced_imagery_tab.py.
"""

from pathlib import Path

def fix_imports(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Define replacements for imports
    replacements = [
        ("from datetime import datetime, timedelta", "from datetime import datetime"),
        ("from typing import Any, Dict, List, Optional, Union", "from typing import Any, Dict, Optional"),
        ("from PyQt6.QtCore import (\n    QDate,\n    QDateTime,", "from PyQt6.QtCore import (\n    QDate,"),
        ("    QTime,\n    QTimer,\n    pyqtSignal,\n    pyqtSlot,", "    QTime,\n    QTimer,\n    pyqtSignal,"),
        ("from PyQt6.QtGui import QFont, QIcon, QImage, QMovie, QPainter, QPixmap", 
         "from PyQt6.QtGui import QFont, QImage, QPainter, QPixmap"),
        (", QRadioButton, QSpacerItem, QStackedWidget", ""),
    ]
    
    # Apply replacements
    modified_content = content
    for old, new in replacements:
        modified_content = modified_content.replace(old, new)
    
    # Write back if changes were made
    if modified_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(modified_content)
        print(f"Updated {file_path} - removed unused imports")
    else:
        print(f"No import changes needed in {file_path}")

if __name__ == "__main__":
    file_path = Path(__file__).parent / "goesvfi" / "integrity_check" / "enhanced_imagery_tab.py"
    if file_path.exists():
        fix_imports(file_path)
    else:
        print(f"File not found: {file_path}")