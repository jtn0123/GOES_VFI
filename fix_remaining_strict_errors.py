# \!/usr/bin/env python3
"""Fix remaining MyPy strict mode errors."""

import re


def fix_reconcile_manager_semaphore():
    """Fix reconcile_manager_refactored.py Semaphore Optional issues."""
    file_path = "goesvfi/integrity_check/reconcile_manager_refactored.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Fix semaphore parameter defaults
    content = re.sub(
        r"semaphore: Semaphore = None", "semaphore: Optional[Semaphore] = None", content
    )

    # Also ensure Semaphore is imported
    if "from threading import" in content and "Semaphore" not in content:
        content = re.sub(
            r"from threading import ([^)]+)",
            lambda m: f"from threading import {m.group(1)}, Semaphore",
            content,
            count=1,
        )

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def fix_standardized_combined_tab_imports():
    """Fix standardized_combined_tab.py missing imports."""
    file_path = "goesvfi/integrity_check/standardized_combined_tab.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Check if Optional and Any are imported
    lines = content.splitlines()
    import_found = False

    for i, line in enumerate(lines):
        if line.startswith("from typing import"):
            # Update to include missing imports
            imports = []
            if "Any" not in line:
                imports.append("Any")
            if "Optional" not in line:
                imports.append("Optional")

            if imports:
                # Parse existing imports
                existing = line[len("from typing import ") :]
                current = [imp.strip() for imp in existing.split(",")]
                all_imports = sorted(set(current + imports))
                lines[i] = f"from typing import {', '.join(all_imports)}"

            import_found = True
            break

    if not import_found:
        # Add after docstring
        for i, line in enumerate(lines):
            if i > 0 and lines[i - 1].strip() == '"""':
                lines.insert(i, "")
                lines.insert(i + 1, "from typing import Any, Optional")
                break

    content = "\n".join(lines)

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def fix_combined_tab_refactored_imports():
    """Fix combined_tab_refactored.py missing imports."""
    file_path = "goesvfi/integrity_check/combined_tab_refactored.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Same approach as above
    lines = content.splitlines()
    import_found = False

    for i, line in enumerate(lines):
        if line.startswith("from typing import"):
            needed = {"List", "Optional"}
            existing = set(
                imp.strip() for imp in line[len("from typing import ") :].split(",")
            )

            if not needed.issubset(existing):
                all_imports = sorted(existing | needed)
                lines[i] = f"from typing import {', '.join(all_imports)}"

            import_found = True
            break

    if not import_found:
        # Add after other imports
        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                continue
            else:
                lines.insert(i, "from typing import Any, List, Optional")
                break

    content = "\n".join(lines)

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def fix_combined_tab_import():
    """Fix combined_tab.py import and type issues."""
    file_path = "goesvfi/integrity_check/combined_tab.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Try to find if OptimizedTimelineTab is defined in optimized_timeline_tab module
    # For now, change the import path
    content = re.sub(
        r"from \.satellite_integrity_tab_group import OptimizedTimelineTab",
        "from .optimized_timeline_tab import OptimizedTimelineTab",
        content,
    )

    # Fix list type parameter
    content = re.sub(r"-> list:", "-> List[Any]:", content)

    # Fix function missing type annotations
    content = re.sub(
        r"def update_data\(self, missing_items=None, start_date=None, end_date=None, total_expected=None\):",
        "def update_data(self, missing_items: Optional[Any] = None, start_date: Optional[Any] = None, end_date: Optional[Any] = None, total_expected: Optional[Any] = None) -> None:",
        content,
    )

    # Ensure imports
    lines = content.splitlines()
    import_found = False

    for i, line in enumerate(lines):
        if line.startswith("from typing import"):
            needed = {"Any", "List", "Optional"}
            existing = set(
                imp.strip() for imp in line[len("from typing import ") :].split(",")
            )

            if not needed.issubset(existing):
                all_imports = sorted(existing | needed)
                lines[i] = f"from typing import {', '.join(all_imports)}"

            import_found = True
            break

    if not import_found:
        # Add after other imports
        for i, line in enumerate(lines):
            if line.startswith("from ") and "PyQt" in line:
                continue
            elif i > 0 and lines[i - 1].startswith("from ") and "PyQt" in lines[i - 1]:
                lines.insert(i, "from typing import Any, List, Optional")
                break

    content = "\n".join(lines)

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def main():
    """Run all fixes."""
    print("Fixing remaining MyPy strict mode errors...\n")

    fix_reconcile_manager_semaphore()
    fix_standardized_combined_tab_imports()
    fix_combined_tab_refactored_imports()
    fix_combined_tab_import()

    print("\nAll fixes applied\!")


if __name__ == "__main__":
    main()
