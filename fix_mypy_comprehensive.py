# \!/usr/bin/env python3
"""Comprehensive fix for remaining MyPy strict mode errors."""

import re
from pathlib import Path


def fix_results_organization():
    """Fix results_organization.py issues."""
    file_path = "goesvfi/integrity_check/results_organization.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Add missing imports
    lines = content.splitlines()
    import_index = -1

    # Find where to add imports
    for i, line in enumerate(lines):
        if line.startswith("from typing import"):
            import_index = i
            break

    if import_index == -1:
        # No typing imports found, add after docstring
        for i, line in enumerate(lines):
            if i > 0 and lines[i - 1].strip() == '"""':
                import_index = i
                lines.insert(import_index, "")
                lines.insert(import_index + 1, "from typing import Any, List, Optional")
                break
    else:
        # Check what's missing and add
        current = lines[import_index]
        needed = []
        if "Any" not in current:
            needed.append("Any")
        if "List" not in current:
            needed.append("List")
        if "Optional" not in current:
            needed.append("Optional")

        if needed:
            # Parse existing imports
            existing = current[len("from typing import ") :]
            imports = [imp.strip() for imp in existing.split(",")]
            all_imports = sorted(set(imports + needed))
            lines[import_index] = f"from typing import {', '.join(all_imports)}"

    content = "\n".join(lines)

    # Fix implicit Optional in function signatures
    # Pattern: argument has type "QModelIndex" with default None
    content = re.sub(
        r"parent: QModelIndex = None", "parent: Optional[QModelIndex] = None", content
    )

    # Fix other implicit Optional patterns
    content = re.sub(r"(\w+): QWidget = None", r"\1: Optional[QWidget] = None", content)

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def fix_cache_db():
    """Fix cache_db.py type issues."""
    file_path = "goesvfi/integrity_check/cache_db.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Fix missing return type annotations
    # Pattern: functions without return type
    lines = content.splitlines()

    for i, line in enumerate(lines):
        # Fix __enter__ method
        if "def __enter__(self):" in line:
            lines[i] = line.replace(
                "def __enter__(self):", 'def __enter__(self) -> "CacheDB":'
            )

        # Fix execute methods without return types
        if "def execute(" in line and "->" not in line:
            lines[i] = line.rstrip(":") + " -> sqlite3.Cursor:"

    content = "\n".join(lines)

    # Fix thread type annotations
    content = re.sub(
        r"thread: threading.Thread = None",
        "thread: Optional[threading.Thread] = None",
        content,
    )

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def fix_reconcile_manager():
    """Fix reconcile_manager_refactored.py issues."""
    file_path = "goesvfi/integrity_check/reconcile_manager_refactored.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Fix TypeAlias usage - ensure proper imports
    if "from typing import" in content and "TypeAlias" not in content:
        content = re.sub(
            r"from typing import ([^)]+)",
            lambda m: f"from typing import {m.group(1)}, TypeAlias",
            content,
            count=1,
        )

    # Fix type alias declarations to use proper format
    content = re.sub(
        r"ProgressCallback: TypeAlias = Callable\[\[int, int, str\], None\]",
        "ProgressCallback = Callable[[int, int, str], None]",
        content,
    )
    content = re.sub(
        r"FileCallback: TypeAlias = Callable\[\[Path, bool\], None\]",
        "FileCallback = Callable[[Path, bool], None]",
        content,
    )
    content = re.sub(
        r"ErrorCallback: TypeAlias = Callable\[\[str, Exception\], None\]",
        "ErrorCallback = Callable[[str, Exception], None]",
        content,
    )

    # Fix Semaphore Optional issue
    content = re.sub(
        r"_semaphore: Semaphore = None",
        "_semaphore: Optional[Semaphore] = None",
        content,
    )

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def fix_auto_detection():
    """Fix auto_detection.py issues."""
    file_path = "goesvfi/integrity_check/auto_detection.py"

    if not Path(file_path).exists():
        print(f"Skipping {file_path} - file not found")
        return

    with open(file_path, "r") as f:
        content = f.read()

    # Add missing imports
    if "from typing import" not in content:
        lines = content.splitlines()
        # Add after docstring
        for i, line in enumerate(lines):
            if i > 0 and lines[i - 1].strip() == '"""':
                lines.insert(i, "")
                lines.insert(
                    i + 1, "from typing import Any, Dict, List, Optional, Tuple"
                )
                break
        content = "\n".join(lines)

    # Fix missing return type annotations
    content = re.sub(
        r"def detect_features\(([^)]+)\):",
        r"def detect_features(\1) -> Dict[str, Any]:",
        content,
    )

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def fix_timeline_visualization():
    """Fix timeline_visualization.py missing type annotations."""
    file_path = "goesvfi/integrity_check/timeline_visualization.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Fix missing type annotations for common methods
    patterns = [
        # Add return type for methods without it
        (
            r"def paintEvent\(self, event\):",
            "def paintEvent(self, event: Any) -> None:",
        ),
        (r"def sizeHint\(self\):", "def sizeHint(self) -> Any:"),
        (
            r"def mousePressEvent\(self, event\):",
            "def mousePressEvent(self, event: Any) -> None:",
        ),
        (
            r"def mouseReleaseEvent\(self, event\):",
            "def mouseReleaseEvent(self, event: Any) -> None:",
        ),
        (
            r"def mouseMoveEvent\(self, event\):",
            "def mouseMoveEvent(self, event: Any) -> None:",
        ),
        (r"def update_view\(self\):", "def update_view(self) -> None:"),
        (
            r"def HourCell\(hour, x, y, width, height\):",
            "def HourCell(hour: int, x: int, y: int, width: int, height: int) -> Dict[str, Any]:",
        ),
    ]

    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content)

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def fix_user_feedback_remaining():
    """Fix remaining user_feedback.py issues."""
    file_path = "goesvfi/integrity_check/user_feedback.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Fix remaining scrollbar issues - need better None checks
    lines = content.splitlines()

    for i, line in enumerate(lines):
        # Fix scrollbar.maximum() calls
        if "scrollbar.maximum()" in line and "if scrollbar else" not in line:
            # Find the assignment or usage
            if "=" in line:
                lines[i] = line.replace(
                    "scrollbar.maximum()", "scrollbar.maximum() if scrollbar else 0"
                )

        # Fix scrollbar.setValue calls
        if (
            "scrollbar.setValue(" in line
            and i > 0
            and "if scrollbar:" not in lines[i - 1]
        ):
            indent = len(line) - len(line.lstrip())
            lines[i] = (
                " " * indent + "if scrollbar:\n" + " " * (indent + 4) + line.strip()
            )

    content = "\n".join(lines)

    # Fix QListWidgetItem text() calls
    content = re.sub(
        r"(\w+)\.text\(\) for \1 in", r'\1.text() if \1 else "" for \1 in', content
    )

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def fix_run_vfi():
    """Fix run_vfi.py type issues."""
    file_path = "goesvfi/pipeline/run_vfi.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Add type: ignore for tqdm import
    content = re.sub(
        r"from tqdm import tqdm$",
        "from tqdm import tqdm  # type: ignore[import-untyped]",
        content,
        flags=re.MULTILINE,
    )

    # Fix Popen type parameters
    content = re.sub(r"Popen\[", "Popen[str]", content)

    # Fix Optional Path argument
    content = re.sub(
        r"rife_exe_path: Path\)", "rife_exe_path: Optional[Path])", content
    )

    # Add Optional import if needed
    if "Optional" not in content and "from typing import" in content:
        content = re.sub(
            r"from typing import ([^)]+)",
            lambda m: f"from typing import {m.group(1)}, Optional"
            if "Optional" not in m.group(1)
            else m.group(0),
            content,
            count=1,
        )

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def main():
    """Run all fixes."""
    print("Applying comprehensive MyPy fixes...\n")

    fix_results_organization()
    fix_cache_db()
    fix_reconcile_manager()
    fix_auto_detection()
    fix_timeline_visualization()
    fix_user_feedback_remaining()
    fix_run_vfi()

    print("\nAll fixes applied\!")


if __name__ == "__main__":
    main()
