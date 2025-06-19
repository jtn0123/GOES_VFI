# \!/usr/bin/env python3
"""Fix final remaining MyPy strict mode errors."""

import re


def fix_visual_date_picker():
    """Fix visual_date_picker.py type issues."""
    file_path = "goesvfi/integrity_check/visual_date_picker.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Fix Callable missing type parameters
    content = re.sub(r"callback: Callable\)", "callback: Callable[..., None])", content)

    # Fix list missing type parameters
    content = re.sub(r"-> list:", "-> List[Any]:", content)

    # Ensure imports include Any
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("from typing import") and "Any" not in line:
            lines[i] = line.rstrip() + ", Any"
            break

    content = "\n".join(lines)

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def fix_user_feedback():
    """Fix user_feedback.py union type issues."""
    file_path = "goesvfi/integrity_check/user_feedback.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Add type: ignore for win10toast import
    content = re.sub(
        r"from win10toast import ToastNotifier",
        "from win10toast import ToastNotifier  # type: ignore[import-not-found]",
        content,
    )

    # Fix clipboard setText calls
    content = re.sub(r"clipboard\.setText\(", "clipboard.setText(", content)

    # Add None checks before clipboard operations
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if "clipboard.setText(" in line and "if clipboard" not in lines[i - 1]:
            indent = len(line) - len(line.lstrip())
            lines[i] = (
                " " * indent + "if clipboard:\n" + " " * (indent + 4) + line.strip()
            )

    content = "\n".join(lines)

    # Fix scrollbar operations
    content = re.sub(
        r"scrollbar\.setValue\(",
        "if scrollbar:\n            scrollbar.setValue(",
        content,
    )
    content = re.sub(
        r"scrollbar\.maximum\(\)", "scrollbar.maximum() if scrollbar else 0", content
    )

    # Fix item.text() calls
    content = re.sub(r"item\.text\(\)", 'item.text() if item else ""', content)

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def fix_ffmpeg_settings_tab():
    """Fix ffmpeg_settings_tab.py default parameter."""
    file_path = "goesvfi/gui_tabs/ffmpeg_settings_tab.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Fix default parameter type
    content = re.sub(
        r"current_settings: Optional\[Dict\[str, Any\]\] = None",
        "current_settings: Optional[Dict[str, Any]] = None",
        content,
    )

    # Also fix the function signature
    content = re.sub(
        r"def save_preset\(self, name: str, current_settings: Dict\[str, Any\] = None\) -> None:",
        "def save_preset(self, name: str, current_settings: Optional[Dict[str, Any]] = None) -> None:",
        content,
    )

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def fix_time_index_refactored():
    """Fix time_index_refactored.py Pattern type parameters."""
    file_path = "goesvfi/integrity_check/time_index_refactored.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Fix Pattern missing type parameters
    content = re.sub(
        r"patterns: List\[re\.Pattern\]", "patterns: List[Pattern[str]]", content
    )

    content = re.sub(
        r"-> Tuple\[bool, Optional\[re\.Pattern\]\]:",
        "-> Tuple[bool, Optional[Pattern[str]]]:",
        content,
    )

    # Fix dictionary type issue on line 662
    content = re.sub(r'"year": year,', '"year": str(year),', content)
    content = re.sub(
        r'"start_sec": start_sec,', '"start_sec": str(start_sec),', content
    )

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def fix_cache_db():
    """Fix cache_db.py missing imports."""
    file_path = "goesvfi/integrity_check/cache_db.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Add missing imports
    lines = content.splitlines()
    import_added = False

    for i, line in enumerate(lines):
        if line.startswith("from typing import"):
            # Check what's already imported
            if "Optional" not in line:
                lines[i] = line.rstrip() + ", Optional"
            if "List" not in line:
                lines[i] = lines[i].rstrip() + ", List"
            if "Dict" not in line:
                lines[i] = lines[i].rstrip() + ", Dict"
            import_added = True
            break

    if not import_added:
        # Find where to add import after docstring
        for i, line in enumerate(lines):
            if i > 0 and lines[i - 1].strip() == '"""':
                lines.insert(i, "")
                lines.insert(i + 1, "from typing import Dict, List, Optional")
                break

    content = "\n".join(lines)

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def fix_goes_imagery():
    """Fix goes_imagery.py third-party import issues."""
    file_path = "goesvfi/integrity_check/goes_imagery.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Add type: ignore for untyped imports
    content = re.sub(
        r"import boto3$",
        "import boto3  # type: ignore[import-untyped]",
        content,
        flags=re.MULTILINE,
    )
    content = re.sub(
        r"import botocore$",
        "import botocore  # type: ignore[import-untyped]",
        content,
        flags=re.MULTILINE,
    )
    content = re.sub(
        r"from botocore\.config import Config$",
        "from botocore.config import Config  # type: ignore[import-untyped]",
        content,
        flags=re.MULTILINE,
    )

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def main():
    """Run all fixes."""
    print("Fixing final remaining MyPy strict mode errors...\n")

    fix_visual_date_picker()
    fix_user_feedback()
    fix_ffmpeg_settings_tab()
    fix_time_index_refactored()
    fix_cache_db()
    fix_goes_imagery()

    print("\nAll fixes applied\!")


if __name__ == "__main__":
    main()
