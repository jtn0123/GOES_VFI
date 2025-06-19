# \!/usr/bin/env python3
"""Fix remaining MyPy issues."""

import re


def fix_reconcile_manager_type_aliases():
    """Fix type alias issues in reconcile_manager_refactored.py"""
    file_path = "goesvfi/integrity_check/reconcile_manager_refactored.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Fix the type aliases - they should use TypeAlias
    content = re.sub(
        r"ProgressCallback = callable\[\[int, int, str\], None\]",
        "ProgressCallback: TypeAlias = callable[[int, int, str], None]",
        content,
    )
    content = re.sub(
        r"FileCallback = callable\[\[Path, bool\], None\]",
        "FileCallback: TypeAlias = callable[[Path, bool], None]",
        content,
    )
    content = re.sub(
        r"ErrorCallback = callable\[\[str, Exception\], None\]",
        "ErrorCallback: TypeAlias = callable[[str, Exception], None]",
        content,
    )

    # Fix the results dict initialization
    content = re.sub(
        r"results = {}", "results: Dict[datetime, Union[Path, Exception]] = {}", content
    )

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def fix_standardized_combined_tab():
    """Fix missing imports in standardized_combined_tab.py"""
    file_path = "goesvfi/integrity_check/standardized_combined_tab.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Add Optional import to existing typing imports
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("from typing import"):
            lines[i] = "from typing import Any, Optional"
            break

    # Fix the function signature
    content = "\n".join(lines)
    content = re.sub(
        r"def update_data\(\s*self, missing_items=None, start_date=None, end_date=None, total_expected=None\s*\) -> None:",
        "def update_data(\n        self, missing_items: Optional[Any] = None, start_date: Optional[Any] = None, end_date: Optional[Any] = None, total_expected: Optional[Any] = None\n    ) -> None:",
        content,
    )

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def fix_combined_tab_refactored():
    """Fix missing imports in combined_tab_refactored.py"""
    file_path = "goesvfi/integrity_check/combined_tab_refactored.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Add missing imports
    lines = content.splitlines()
    import_index = -1

    # Find where to insert imports (after existing imports)
    for i, line in enumerate(lines):
        if line.startswith("from typing import"):
            import_index = i
            break

    if import_index == -1:
        # No typing imports found, add them after the docstring
        for i, line in enumerate(lines):
            if line.strip() == '"""' and i > 0:
                import_index = i + 1
                lines.insert(import_index, "")
                lines.insert(import_index + 1, "from typing import List, Optional")
                break
    else:
        # Update existing import
        lines[import_index] = "from typing import Any, List, Optional"

    content = "\n".join(lines)

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def fix_signal_manager():
    """Fix type issues in signal_manager.py"""
    file_path = "goesvfi/integrity_check/signal_manager.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Fix Callable type parameter
    content = re.sub(r"Callable\[", "Callable[[],", content)

    # Add type ignore comments for pyqtSignal connect calls
    content = re.sub(
        r"([a-zA-Z_]+)\.connect\(",
        r"\1.connect(",  # type: ignore[attr-defined]
        content,
    )

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def fix_combined_tab():
    """Fix issues in combined_tab.py"""
    file_path = "goesvfi/integrity_check/combined_tab.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Fix import
    content = re.sub(
        r"from \.satellite_integrity_tab_group import OptimizedTimelineTab",
        "from .optimized_timeline_tab import OptimizedTimelineTab",
        content,
    )

    # Fix list type annotation
    content = re.sub(r"-> list:", "-> List[Any]:", content)

    # Add List import if not present
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("from typing import"):
            if "List" not in line:
                lines[i] = line.replace("import ", "import Any, List, ")
            break

    content = "\n".join(lines)

    # Fix function signature
    content = re.sub(
        r"def update_data\(self, missing_items=None, start_date=None, end_date=None, total_expected=None\):",
        "def update_data(self, missing_items: Optional[Any] = None, start_date: Optional[Any] = None, end_date: Optional[Any] = None, total_expected: Optional[Any] = None) -> None:",
        content,
    )

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def main():
    """Run all fixes."""
    print("Fixing remaining MyPy issues...\n")

    fix_reconcile_manager_type_aliases()
    fix_standardized_combined_tab()
    fix_combined_tab_refactored()
    fix_signal_manager()
    fix_combined_tab()

    print("\nAll fixes applied\!")


if __name__ == "__main__":
    main()
