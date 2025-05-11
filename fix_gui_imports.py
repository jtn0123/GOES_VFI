#!/usr/bin/env python3
"""
Fix unused imports in gui.py file
"""

import re

def fix_unused_imports(file_path):
    with open(file_path, 'r') as f:
        content = f.read()
    
    # List of unused imports from flake8 errors
    unused_imports = [
        r"goesvfi\.integrity_check\.enhanced_gui_tab import EnhancedIntegrityCheckTab",
        r"goesvfi\.integrity_check\.reconcile_manager import ReconcileManager",
        r"goesvfi\.integrity_check\.time_index import SatellitePattern",
        r"goesvfi\.pipeline\.image_processing_interfaces import ImageProcessor",
        r"importlib\.resources as pkgres",
        r"json",
        r"pathlib",
        r"time",
        r"datetime\.datetime",
        r"typing\.Iterator",
        r"typing\.TypedDict",
        r"typing\.Union",
        r"typing\.cast",
        r"PyQt6\.QtCore\.QByteArray",
        r"PyQt6\.QtCore\.QPoint",
        r"PyQt6\.QtCore\.QRect",
        r"PyQt6\.QtCore\.QThread",
        r"PyQt6\.QtGui\.QIcon",
        r"PyQt6\.QtGui\.QMouseEvent",
        r"PyQt6\.QtGui\.QPen",
        r"PyQt6\.QtWidgets\.QScrollArea",
        r"PyQt6\.QtWidgets\.QDialogButtonBox",
        r"PyQt6\.QtWidgets\.QHBoxLayout",
        r"PyQt6\.QtWidgets\.QProgressBar",
        r"PyQt6\.QtWidgets\.QPushButton",
        r"PyQt6\.QtWidgets\.QRubberBand",
        r"PyQt6\.QtWidgets\.QTableWidget",
        r"PyQt6\.QtWidgets\.QTableWidgetItem",
        r"goesvfi\.utils\.config\.DEFAULT_FFMPEG_PROFILE",
        r"goesvfi\.utils\.config\.OPTIMAL_FFMPEG_PROFILE",
        r"goesvfi\.utils\.config\.OPTIMAL_FFMPEG_PROFILE_2",
    ]
    
    # Process each unused import
    for unused in unused_imports:
        # Create regex patterns to match the import in different formats
        patterns = [
            # For 'from module import Class' style
            fr"from\s+{unused}[^\n,]*?(?:,|\n)",
            # For 'import module' style
            fr"import\s+{unused}(?:\s+|,|\n)",
            # For 'from module import (Class, ...)' style 
            fr",\s*{unused.split(' ')[-1]}\s*,"
        ]
        
        for pattern in patterns:
            # If there's a match, remove it from the content
            content = re.sub(pattern, "", content, flags=re.MULTILINE)
    
    # Remove empty import statements
    content = re.sub(r"from\s+[\w.]+\s+import\s*\(\s*\)", "", content)
    content = re.sub(r"from\s+[\w.]+\s+import\s*$", "", content)
    
    # Clean up consecutive blank lines
    content = re.sub(r"\n{3,}", "\n\n", content)
    
    # Write back the cleaned content
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"Removed unused imports from {file_path}")

if __name__ == "__main__":
    fix_unused_imports("goesvfi/gui.py")