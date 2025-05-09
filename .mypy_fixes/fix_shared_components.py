#!/usr/bin/env python3
"""
Script to fix mypy type issues in the shared_components.py file.

This script adds proper type hints to functions and methods that are missing them,
focusing on the issues identified by mypy in strict mode.
"""

import re
import sys
from pathlib import Path

# Define the source file
source_file = Path("goesvfi/integrity_check/shared_components.py")
output_file = source_file

# Ensure the file exists
if not source_file.exists():
    print(f"Error: Source file {source_file} not found!")
    sys.exit(1)

# Read the file content
content = source_file.read_text()

# 1. Add TypedDict for PreviewMetadata
preview_metadata_def = """
class PreviewMetadata(TypedDict, total=False):
    \"\"\"Type definition for preview metadata.\"\"\"
    channel: Union[int, str]
    product_type: str
    date_time: datetime
    source: str
    filename: Optional[str]
    resolution: Optional[str]
    additional_info: Dict[str, Any]
"""

# 2. Update imports
imports_regex = r"from typing import Dict, Optional, Union, Any, Tuple"
updated_imports = "from typing import Dict, Optional, Union, Any, Tuple, Set, List, TypedDict, cast, Callable"
content = re.sub(imports_regex, updated_imports, content)

# 3. Add PreviewMetadata definition after imports
logger_line = "logger = logging.getLogger(__name__)"
content = content.replace(
    logger_line,
    f"{logger_line}\n\n{preview_metadata_def}"
)

# 4. Fix missing type annotations for __init__ methods

# SharedPreviewPanel.__init__
init_regex = r"def __init__\(self, parent=None\):"
fixed_init = "def __init__(self, parent: Optional[QWidget] = None) -> None:"
content = re.sub(init_regex, fixed_init, content)

# 5. Fix missing return type for initUI method
initui_regex = r"def initUI\(self\):"
fixed_initui = "def initUI(self) -> None:"
content = re.sub(initui_regex, fixed_initui, content)

# 6. Fix other missing return types (pattern: 'def method_name(self, ...):', add '-> None:')
method_regex_pattern = r"def ([a-zA-Z0-9_]+)\(self(?:, [^)]+)?\):"
method_return_type = r"def \1(self\2) -> None:"

methods_to_fix = [
    (r"def setImage\(self, key, pixmap, metadata\):", 
     r"def setImage(self, key: str, pixmap: QPixmap, metadata: PreviewMetadata) -> None:"),
    (r"def clearImage\(self\):", 
     r"def clearImage(self) -> None:"),
    (r"def showMetadata\(self, key, metadata\):", 
     r"def showMetadata(self, key: str, metadata: PreviewMetadata) -> None:"),
    (r"def bookmarkImage\(self, key, is_bookmarked=None\):", 
     r"def bookmarkImage(self, key: str, is_bookmarked: Optional[bool] = None) -> None:"),
    (r"def updateButtonStatus\(self\):", 
     r"def updateButtonStatus(self) -> None:"),
    (r"def clearMetadata\(self\):", 
     r"def clearMetadata(self) -> None:"),
    (r"def setInfoText\(self, message, status_type='info'\):", 
     r"def setInfoText(self, message: str, status_type: str = 'info') -> None:"),
    (r"def updateLayout\(self\):", 
     r"def updateLayout(self) -> None:"),
]

for old_pattern, new_pattern in methods_to_fix:
    content = re.sub(old_pattern, new_pattern, content)

# 7. Fix missing type annotations for section creation methods
section_methods = [
    (r"def create_presets_section\(self\):", 
     r"def create_presets_section(self) -> QWidget:"),
    (r"def create_data_section\(self\):", 
     r"def create_data_section(self) -> QWidget:"),
    (r"def create_visualization_section\(self\):", 
     r"def create_visualization_section(self) -> QWidget:"),
    (r"def create_processing_section\(self\):", 
     r"def create_processing_section(self) -> QWidget:"),
    (r"def create_advanced_section\(self\):", 
     r"def create_advanced_section(self) -> QWidget:"),
    (r"def create_output_section\(self\):", 
     r"def create_output_section(self) -> QWidget:"),
    (r"def create_controls_section\(self\):", 
     r"def create_controls_section(self) -> QWidget:"),
    (r"def create_network_section\(self\):", 
     r"def create_network_section(self) -> QWidget:"),
]

for old_pattern, new_pattern in section_methods:
    content = re.sub(old_pattern, new_pattern, content)

# 8. Fix return types for remaining methods
remaining_methods = [
    (r"def resetSettings\(self\):", 
     r"def resetSettings(self) -> None:"),
    (r"def applySettings\(self\):", 
     r"def applySettings(self) -> None:"),
]

for old_pattern, new_pattern in remaining_methods:
    content = re.sub(old_pattern, new_pattern, content)

# Fix class property annotations
previews_cache_pattern = r"self.preview_cache = {}"
fixed_previews_cache = "self.preview_cache: Dict[str, Dict[str, Union[QPixmap, PreviewMetadata]]] = {}"
content = re.sub(previews_cache_pattern, fixed_previews_cache, content)

bookmarks_pattern = r"self.bookmarks = set\(\)"
fixed_bookmarks = "self.bookmarks: Set[str] = set()"
content = re.sub(bookmarks_pattern, fixed_bookmarks, content)

current_key_pattern = r"self.current_key = None"
fixed_current_key = "self.current_key: Optional[str] = None"
content = re.sub(current_key_pattern, fixed_current_key, content)

# 9. Write the updated content back to the file
output_file.write_text(content)

print(f"Successfully updated {output_file} with type annotations.")