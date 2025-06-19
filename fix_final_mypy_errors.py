# \!/usr/bin/env python3
"""Fix final MyPy strict mode errors."""

import re


def fix_signal_manager():
    """Fix signal_manager.py issues."""
    file_path = "goesvfi/integrity_check/signal_manager.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Fix Callable missing type parameters
    content = re.sub(r"handler: Callable,", "handler: Callable[..., None],", content)

    # Add type: ignore comments for pyqtSignal.connect calls
    # Lines 156, 168, 196
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if i in [155, 167, 195] and ".connect(" in lines[i]:
            lines[i] = lines[i].replace(
                ".connect(", ".connect(  # type: ignore[attr-defined]"
            )

    content = "\n".join(lines)

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def fix_reconcile_manager():
    """Fix reconcile_manager_refactored.py TypeAlias issues."""
    file_path = "goesvfi/integrity_check/reconcile_manager_refactored.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Check if TypeAlias is imported
    if "TypeAlias" not in content:
        # Add TypeAlias to imports
        content = re.sub(
            r"from typing import ([^)]+)",
            lambda m: f"from typing import {m.group(1)}, TypeAlias",
            content,
            count=1,
        )

    # Fix type alias declarations - they should use Callable with capital C
    content = re.sub(
        r"ProgressCallback = callable\[\[int, int, str\], None\]",
        "ProgressCallback: TypeAlias = Callable[[int, int, str], None]",
        content,
    )
    content = re.sub(
        r"FileCallback = callable\[\[Path, bool\], None\]",
        "FileCallback: TypeAlias = Callable[[Path, bool], None]",
        content,
    )
    content = re.sub(
        r"ErrorCallback = callable\[\[str, Exception\], None\]",
        "ErrorCallback: TypeAlias = Callable[[str, Exception], None]",
        content,
    )

    # Fix results dict annotation
    content = re.sub(
        r"results = {}", "results: Dict[datetime, Union[Path, Exception]] = {}", content
    )

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def fix_standardized_combined_tab():
    """Fix standardized_combined_tab.py missing imports."""
    file_path = "goesvfi/integrity_check/standardized_combined_tab.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Check if Optional is imported
    lines = content.splitlines()
    import_found = False
    for i, line in enumerate(lines):
        if line.startswith("from typing import"):
            if "Optional" not in line:
                lines[i] = line.rstrip() + ", Optional"
            import_found = True
            break

    if not import_found:
        # Add typing import after docstring
        for i, line in enumerate(lines):
            if i > 0 and lines[i - 1].strip() == '"""':
                lines.insert(i, "")
                lines.insert(i + 1, "from typing import Any, Optional")
                break

    content = "\n".join(lines)

    # Fix function signature with proper type annotations
    content = re.sub(
        r"def update_data\(\s*self,\s*missing_items=None,\s*start_date=None,\s*end_date=None,\s*total_expected=None\s*\)\s*->\s*None:",
        "def update_data(self, missing_items: Optional[Any] = None, start_date: Optional[Any] = None, end_date: Optional[Any] = None, total_expected: Optional[Any] = None) -> None:",
        content,
        flags=re.MULTILINE | re.DOTALL,
    )

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def fix_combined_tab_refactored():
    """Fix combined_tab_refactored.py missing imports."""
    file_path = "goesvfi/integrity_check/combined_tab_refactored.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Check and add missing imports
    lines = content.splitlines()
    import_found = False

    for i, line in enumerate(lines):
        if line.startswith("from typing import"):
            needed_imports = set()
            current_imports = line[len("from typing import ") :]

            if "List" not in current_imports:
                needed_imports.add("List")
            if "Optional" not in current_imports:
                needed_imports.add("Optional")

            if needed_imports:
                # Parse current imports
                current = [imp.strip() for imp in current_imports.split(",")]
                all_imports = sorted(set(current) | needed_imports)
                lines[i] = f"from typing import {', '.join(all_imports)}"

            import_found = True
            break

    if not import_found:
        # Add typing import after docstring
        for i, line in enumerate(lines):
            if i > 0 and lines[i - 1].strip() == '"""':
                lines.insert(i, "")
                lines.insert(i + 1, "from typing import Any, List, Optional")
                break

    content = "\n".join(lines)

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def fix_combined_tab():
    """Fix combined_tab.py issues."""
    file_path = "goesvfi/integrity_check/combined_tab.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Fix the import path
    content = re.sub(
        r"from \.satellite_integrity_tab_group import OptimizedTimelineTab",
        "from .optimized_timeline_tab import OptimizedTimelineTab",
        content,
    )

    # Fix missing List type parameter
    content = re.sub(r"-> list:", "-> List[Any]:", content)

    # Ensure imports are correct
    lines = content.splitlines()
    import_found = False

    for i, line in enumerate(lines):
        if line.startswith("from typing import"):
            needed = {"Any", "List", "Optional"}
            current = set(
                imp.strip() for imp in line[len("from typing import ") :].split(",")
            )
            if not needed.issubset(current):
                all_imports = sorted(current | needed)
                lines[i] = f"from typing import {', '.join(all_imports)}"
            import_found = True
            break

    if not import_found:
        # Add after other imports
        for i, line in enumerate(lines):
            if line.startswith("from ") and not line.startswith("from typing"):
                continue
            elif i > 0 and lines[i - 1].startswith("from "):
                lines.insert(i, "from typing import Any, List, Optional")
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
    print("Fixing final MyPy strict mode errors...\n")

    fix_signal_manager()
    fix_reconcile_manager()
    fix_standardized_combined_tab()
    fix_combined_tab_refactored()
    fix_combined_tab()

    print("\nAll fixes applied\!")


if __name__ == "__main__":
    main()
