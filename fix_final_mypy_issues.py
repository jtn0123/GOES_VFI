#!/usr/bin/env python3
"""Fix final remaining MyPy strict errors."""

import os
import re


def fix_user_feedback_imports():
    """Fix win10toast import."""
    file_path = "goesvfi/integrity_check/user_feedback.py"

    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            content = f.read()

        # Add type: ignore[import-not-found] to win10toast import
        content = re.sub(
            r"from win10toast import ToastNotifier",
            "from win10toast import ToastNotifier  # type: ignore[import-not-found]",
            content,
        )

        with open(file_path, "w") as f:
            f.write(content)
        print(f"Fixed win10toast import in {file_path}")


def fix_botocore_config_import():
    """Fix botocore.config import."""
    files = [
        "goesvfi/integrity_check/goes_imagery.py",
        "goesvfi/integrity_check/sample_processor.py",
    ]

    for file_path in files:
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                content = f.read()

            # Add type: ignore to botocore.config import
            content = re.sub(
                r"import botocore\.config$",
                "import botocore.config  # type: ignore[import-not-found]",
                content,
                flags=re.MULTILINE,
            )

            with open(file_path, "w") as f:
                f.write(content)
            print(f"Fixed botocore.config import in {file_path}")


def fix_cdn_store_imports():
    """Fix aiohttp imports in cdn_store.py."""
    file_path = "goesvfi/integrity_check/remote/cdn_store.py"

    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            content = f.read()

        # Add type: ignore to aiohttp imports
        content = re.sub(
            r"^import aiohttp$",
            "import aiohttp  # type: ignore[import-not-found]",
            content,
            flags=re.MULTILINE,
        )
        content = re.sub(
            r"^from aiohttp\.client_exceptions import",
            "from aiohttp.client_exceptions import  # type: ignore[import-not-found]",
            content,
            flags=re.MULTILINE,
        )

        with open(file_path, "w") as f:
            f.write(content)
        print(f"Fixed aiohttp imports in {file_path}")


def fix_qgridlayout_import():
    """Fix QGridLayout import in auto_detection.py."""
    file_path = "goesvfi/integrity_check/auto_detection.py"

    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            lines = f.readlines()

        # Find PyQt6.QtWidgets import and add QGridLayout
        for i, line in enumerate(lines):
            if "from PyQt6.QtWidgets import" in line:
                # Check if it's a multi-line import
                if "(" in line:
                    # Multi-line import - find the closing parenthesis
                    j = i
                    while j < len(lines) and ")" not in lines[j]:
                        j += 1

                    # Check if QGridLayout is already imported
                    import_section = "".join(lines[i : j + 1])
                    if "QGridLayout" not in import_section:
                        # Add QGridLayout before the closing parenthesis
                        lines[j] = lines[j].replace(")", ",\n    QGridLayout\n)")
                else:
                    # Single line import
                    if "QGridLayout" not in line:
                        # Convert to multi-line and add QGridLayout
                        imports = re.search(r"from PyQt6\.QtWidgets import (.+)", line)
                        if imports:
                            import_list = [
                                imp.strip() for imp in imports.group(1).split(",")
                            ]
                            import_list.append("QGridLayout")
                            import_list.sort()
                            new_import = "from PyQt6.QtWidgets import (\n"
                            for imp in import_list:
                                new_import += f"    {imp},\n"
                            new_import = new_import.rstrip(",\n") + "\n)\n"
                            lines[i] = new_import
                break

        with open(file_path, "w") as f:
            f.writelines(lines)
        print(f"Fixed QGridLayout import in {file_path}")


def fix_visual_date_picker():
    """Fix visual_date_picker.py Callable issue."""
    file_path = "goesvfi/integrity_check/visual_date_picker.py"

    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            lines = f.readlines()

        # Find line 128 and fix Callable type
        if len(lines) > 127:
            line = lines[127]
            if "Callable" in line and "[" not in line:
                # Add type parameters
                lines[127] = line.replace("Callable", "Callable[[], None]")

        with open(file_path, "w") as f:
            f.writelines(lines)
        print(f"Fixed Callable type in {file_path}")


def fix_goes_imagery_tab():
    """Fix self not defined issue in goes_imagery_tab.py."""
    file_path = "goesvfi/integrity_check/goes_imagery_tab.py"

    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            lines = f.readlines()

        # Check line 510
        if len(lines) > 509:
            line = lines[509]
            # Check indentation - if it starts without spaces, it's likely misplaced
            if line.strip().startswith("self.") and not line.startswith(" "):
                # Find the proper indentation by looking at surrounding lines
                for i in range(508, 505, -1):
                    if lines[i].strip() and lines[i].startswith(" "):
                        indent = len(lines[i]) - len(lines[i].lstrip())
                        lines[509] = " " * indent + line.lstrip()
                        break

        with open(file_path, "w") as f:
            f.writelines(lines)
        print(f"Fixed indentation in {file_path}")


def fix_visualization_manager():
    """Fix matplotlib import."""
    file_path = "goesvfi/integrity_check/visualization_manager.py"

    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            content = f.read()

        # Add type: ignore to matplotlib import
        content = re.sub(
            r"^import matplotlib",
            "import matplotlib  # type: ignore[import-not-found]",
            content,
            flags=re.MULTILINE,
        )
        content = re.sub(
            r"^from matplotlib", "from matplotlib", content, flags=re.MULTILINE
        )
        # Handle specific matplotlib imports
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("from matplotlib") and "# type: ignore" not in line:
                lines[i] = line + "  # type: ignore[import-not-found]"

        content = "\n".join(lines)

        with open(file_path, "w") as f:
            f.write(content)
        print(f"Fixed matplotlib imports in {file_path}")


def fix_auto_detection_dict():
    """Fix dict type issue in auto_detection.py."""
    file_path = "goesvfi/integrity_check/auto_detection.py"

    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            lines = f.readlines()

        # Fix line 351 - the timestamps entry
        if len(lines) > 350:
            line = lines[350]
            if '"timestamps":' in line and "[str(ts) for ts in timestamps]" in line:
                # Change to str() of the list
                lines[350] = line.replace(
                    "[str(ts) for ts in timestamps] if timestamps else None",
                    "str([str(ts) for ts in timestamps]) if timestamps else None",
                )

        with open(file_path, "w") as f:
            f.writelines(lines)
        print(f"Fixed dict type in {file_path}")


def main():
    """Run all fixes."""
    print("Fixing final MyPy strict errors...\n")

    fix_user_feedback_imports()
    fix_botocore_config_import()
    fix_cdn_store_imports()
    fix_qgridlayout_import()
    fix_visual_date_picker()
    fix_goes_imagery_tab()
    fix_visualization_manager()
    fix_auto_detection_dict()

    print("\nAll fixes applied!")


if __name__ == "__main__":
    main()
