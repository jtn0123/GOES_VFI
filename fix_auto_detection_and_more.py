# \!/usr/bin/env python3
"""Fix auto_detection.py and other remaining type issues."""

import re


def fix_auto_detection():
    """Fix auto_detection.py type issues."""
    file_path = "goesvfi/integrity_check/auto_detection.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Fix QLayout columnCount issue - cast to QGridLayout
    content = re.sub(
        r"layout\.addWidget\(self\.log_widget, 2, 0, 1, layout\.columnCount\(\)\)",
        "if isinstance(layout, QGridLayout):\n                layout.addWidget(self.log_widget, 2, 0, 1, layout.columnCount())",
        content,
    )

    # Fix QListWidgetItem None checks
    content = re.sub(
        r"item\.setForeground\(",
        "if item:\n                item.setForeground(",
        content,
    )
    content = re.sub(
        r"item\.setBackground\(",
        "if item:\n                item.setBackground(",
        content,
    )

    # Fix function type annotation on line 152
    content = re.sub(
        r"def _update_log_message_color\(self, item, level\):",
        "def _update_log_message_color(self, item: Optional[QListWidgetItem], level: str) -> None:",
        content,
    )

    # Fix dict type issues - change return type hint
    content = re.sub(r"-> Dict\[str, Optional\[str\]\]:", "-> Dict[str, Any]:", content)

    # Fix dialog.result assignment - add type annotation
    content = re.sub(
        r"dialog\.result = result",
        "dialog.result = result  # type: ignore[attr-defined]",
        content,
    )

    # Ensure imports include QGridLayout
    if "from PyQt6.QtWidgets import" in content and "QGridLayout" not in content:
        content = re.sub(
            r"(from PyQt6\.QtWidgets import[^\n]+)",
            lambda m: m.group(1) + ", QGridLayout"
            if "QGridLayout" not in m.group(1)
            else m.group(1),
            content,
        )

    # Add missing imports
    lines = content.splitlines()
    import_found = False
    for i, line in enumerate(lines):
        if line.startswith("from typing import"):
            if "Any" not in line:
                lines[i] = line.rstrip() + ", Any"
            if "Optional" not in line:
                lines[i] = lines[i].rstrip() + ", Optional"
            import_found = True
            break

    if not import_found:
        # Add after docstring
        for i, line in enumerate(lines):
            if i > 0 and lines[i - 1].strip() == '"""':
                lines.insert(i, "")
                lines.insert(i + 1, "from typing import Any, Dict, List, Optional")
                break

    content = "\n".join(lines)

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def fix_render_netcdf():
    """Fix render/netcdf.py type issues."""
    file_path = "goesvfi/integrity_check/render/netcdf.py"

    try:
        with open(file_path, "r") as f:
            content = f.read()

        # Fix numpy array type parameters
        content = re.sub(
            r"np\.ndarray\b", "np.ndarray[Any, np.dtype[np.float64]]", content
        )

        # Add numpy.typing import if needed
        if "import numpy as np" in content and "numpy.typing" not in content:
            content = re.sub(
                r"(import numpy as np)", r"\1\nimport numpy.typing as npt", content
            )
            # Use npt.NDArray instead
            content = re.sub(
                r"np\.ndarray\[Any, np\.dtype\[np\.float64\]\]",
                "npt.NDArray[np.float64]",
                content,
            )

        with open(file_path, "w") as f:
            f.write(content)

        print(f"Fixed {file_path}")
    except FileNotFoundError:
        print(f"Skipping {file_path} - not found")


def fix_gui_backup():
    """Fix gui_backup.py type issues."""
    file_path = "goesvfi/gui_backup.py"

    try:
        with open(file_path, "r") as f:
            content = f.read()

        # Add missing imports
        lines = content.splitlines()
        import_found = False

        for i, line in enumerate(lines):
            if line.startswith("from typing import"):
                needed = {"Any", "Dict", "List", "Optional"}
                existing = set(
                    imp.strip() for imp in line[len("from typing import ") :].split(",")
                )

                if not needed.issubset(existing):
                    all_imports = sorted(existing | needed)
                    lines[i] = f"from typing import {', '.join(all_imports)}"

                import_found = True
                break

        if not import_found:
            # Add after docstring
            for i, line in enumerate(lines):
                if i > 0 and lines[i - 1].strip() == '"""':
                    lines.insert(i, "")
                    lines.insert(i + 1, "from typing import Any, Dict, List, Optional")
                    break

        content = "\n".join(lines)

        with open(file_path, "w") as f:
            f.write(content)

        print(f"Fixed {file_path}")
    except FileNotFoundError:
        print(f"Skipping {file_path} - not found")


def fix_remaining_callable_issues():
    """Fix remaining callable type issues."""
    files_with_callable = [
        "goesvfi/integrity_check/reconcile_manager_refactored.py",
        "goesvfi/integrity_check/enhanced_timeline.py",
    ]

    for file_path in files_with_callable:
        try:
            with open(file_path, "r") as f:
                content = f.read()

            # Fix lowercase callable to Callable
            content = re.sub(r"\bcallable\[", "Callable[", content)

            with open(file_path, "w") as f:
                f.write(content)

            print(f"Fixed callable in {file_path}")
        except FileNotFoundError:
            print(f"Skipping {file_path} - not found")


def fix_timeline_visualization_remaining():
    """Fix remaining timeline_visualization.py issues."""
    file_path = "goesvfi/integrity_check/timeline_visualization.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Add missing type annotations
    replacements = [
        (r"def _setup_theme\(self\):", "def _setup_theme(self) -> None:"),
        (r"def _update_colors\(self\):", "def _update_colors(self) -> None:"),
        (r"def update_theme\(self\):", "def update_theme(self) -> None:"),
        (r"def refresh\(self\):", "def refresh(self) -> None:"),
    ]

    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def main():
    """Run all fixes."""
    print("Fixing remaining type issues...\n")

    fix_auto_detection()
    fix_render_netcdf()
    fix_gui_backup()
    fix_remaining_callable_issues()
    fix_timeline_visualization_remaining()

    print("\nAll fixes applied\!")


if __name__ == "__main__":
    main()
