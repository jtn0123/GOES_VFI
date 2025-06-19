#!/usr/bin/env python3
"""Fix remaining MyPy strict errors comprehensively."""

import os
import re


def fix_import_type_ignores():
    """Fix import-not-found errors with proper type: ignore comments."""
    files_to_fix = [
        ("goesvfi/integrity_check/user_feedback.py", ["win10toast"]),
        ("goesvfi/integrity_check/goes_imagery.py", ["boto3", "botocore"]),
        ("goesvfi/integrity_check/remote/cdn_store.py", ["aiohttp"]),
        ("goesvfi/integrity_check/remote/s3_store.py", ["boto3", "botocore"]),
        ("goesvfi/integrity_check/sample_processor.py", ["boto3", "botocore"]),
    ]

    for file_path, modules in files_to_fix:
        if not os.path.exists(file_path):
            continue

        with open(file_path, "r") as f:
            lines = f.readlines()

        modified = False
        for i, line in enumerate(lines):
            for module in modules:
                # Match import statements with existing type: ignore
                if re.match(rf"^\s*import {module}\s*#\s*type:\s*ignore\s*$", line):
                    lines[i] = re.sub(
                        r"#\s*type:\s*ignore.*$",
                        "# type: ignore[import-not-found]",
                        line,
                    )
                    modified = True
                elif (
                    re.match(rf"^\s*import {module}", line) and "# type: ignore" in line
                ):
                    lines[i] = re.sub(
                        r"#\s*type:\s*ignore.*$",
                        "# type: ignore[import-not-found]",
                        line,
                    )
                    modified = True
                elif re.match(rf"^\s*from {module}", line) and "# type: ignore" in line:
                    lines[i] = re.sub(
                        r"#\s*type:\s*ignore.*$",
                        "# type: ignore[import-not-found]",
                        line,
                    )
                    modified = True

        if modified:
            with open(file_path, "w") as f:
                f.writelines(lines)
            print(f"Fixed import type ignores in {file_path}")


def fix_missing_type_import():
    """Add missing Type import where needed."""
    files_needing_type = [
        "goesvfi/integrity_check/cache_db.py",
        "goesvfi/integrity_check/remote/cdn_store.py",
    ]

    for file_path in files_needing_type:
        if not os.path.exists(file_path):
            continue

        with open(file_path, "r") as f:
            content = f.read()

        # Check if Type is used but not imported
        if (
            "Type[" in content
            and "from typing import" in content
            and "Type" not in content.split("from typing import")[1].split("\n")[0]
        ):
            # Find the typing import line
            lines = content.splitlines()
            for i, line in enumerate(lines):
                if line.startswith("from typing import"):
                    # Extract current imports
                    match = re.match(r"from typing import (.+)", line)
                    if match:
                        imports = match.group(1)
                        # Add Type if not present
                        import_list = [imp.strip() for imp in imports.split(",")]
                        if "Type" not in import_list:
                            import_list.append("Type")
                            import_list.sort()
                            lines[i] = f"from typing import {', '.join(import_list)}"

                            with open(file_path, "w") as f:
                                f.write("\n".join(lines) + "\n")
                            print(f"Added Type import to {file_path}")
                            break


def fix_qgridlayout_import():
    """Fix missing QGridLayout import."""
    file_path = "goesvfi/integrity_check/auto_detection.py"

    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            content = f.read()

        if "QGridLayout" in content and "QGridLayout" not in content:
            # Find the PyQt6.QtWidgets import line
            lines = content.splitlines()
            for i, line in enumerate(lines):
                if "from PyQt6.QtWidgets import" in line and "QGridLayout" not in line:
                    # Extract current imports
                    match = re.search(
                        r"from PyQt6\.QtWidgets import \(([^)]+)\)",
                        line,
                        re.MULTILINE | re.DOTALL,
                    )
                    if match:
                        # Multi-line import
                        import_section = match.group(1)
                        imports = [imp.strip() for imp in import_section.split(",")]
                        if "QGridLayout" not in imports:
                            imports.append("QGridLayout")
                            imports.sort()
                            # Reconstruct the import
                            new_import = "from PyQt6.QtWidgets import (\n"
                            for imp in imports:
                                new_import += f"    {imp},\n"
                            new_import = new_import.rstrip(",\n") + "\n)"

                            # Replace the old import
                            start = line.find("from PyQt6.QtWidgets import")
                            end = content.find(")", start) + 1
                            content = content[:start] + new_import + content[end:]

                            with open(file_path, "w") as f:
                                f.write(content)
                            print(f"Added QGridLayout import to {file_path}")
                            break


def fix_optional_attributes():
    """Fix union-attr errors by adding proper None checks."""
    fixes = [
        {
            "file": "goesvfi/integrity_check/user_feedback.py",
            "line": 785,
            "old": "text = item.text()",
            "new": 'text = item.text() if item else ""',
        },
        {
            "file": "goesvfi/integrity_check/user_feedback.py",
            "line": 998,
            "old": "vbar.setValue(vbar.maximum())",
            "new": "if vbar:\n                vbar.setValue(vbar.maximum())",
        },
    ]

    for fix in fixes:
        file_path = fix["file"]
        if not os.path.exists(file_path):
            continue

        with open(file_path, "r") as f:
            lines = f.readlines()

        # Adjust for 0-based indexing
        line_idx = fix["line"] - 1
        if line_idx < len(lines) and fix["old"] in lines[line_idx]:
            lines[line_idx] = lines[line_idx].replace(fix["old"], fix["new"])

            with open(file_path, "w") as f:
                f.writelines(lines)
            print(f"Fixed optional attribute in {file_path} at line {fix['line']}")


def fix_goes_imagery_tab_self_issue():
    """Fix the 'self' not defined issue in goes_imagery_tab.py."""
    file_path = "goesvfi/integrity_check/goes_imagery_tab.py"

    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            lines = f.readlines()

        # Line 510 has issue - likely indentation problem
        if len(lines) > 509:
            # Check if line 510 is improperly indented
            line_510 = lines[509]
            if "self" in line_510 and not line_510.startswith(" "):
                # This line should be indented as part of a method
                lines[509] = "        " + line_510  # Add proper indentation

                with open(file_path, "w") as f:
                    f.writelines(lines)
                print(f"Fixed indentation in {file_path} at line 510")


def fix_visual_date_picker_callable():
    """Fix Callable type parameter issue."""
    file_path = "goesvfi/integrity_check/visual_date_picker.py"

    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            content = f.read()

        # Replace Callable without parameters with proper typing
        content = re.sub(r":\s*Callable\s*=", ": Callable[[], None] =", content)
        content = re.sub(
            r":\s*Optional\[Callable\]\s*=", ": Optional[Callable[[], None]] =", content
        )

        with open(file_path, "w") as f:
            f.write(content)
        print(f"Fixed Callable type parameters in {file_path}")


def fix_auto_detection_dict_types():
    """Fix dict type mismatches in auto_detection.py."""
    file_path = "goesvfi/integrity_check/auto_detection.py"

    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            lines = f.readlines()

        # Find the problematic dict assignment around lines 349-351
        for i in range(len(lines)):
            if i >= 348 and i <= 351:
                # These lines have datetime values being assigned to str | None
                if (
                    "start_date" in lines[i]
                    or "end_date" in lines[i]
                    or "timestamps" in lines[i]
                ):
                    # These need to be converted to strings
                    lines[i] = lines[i].replace(
                        ": start_date", ": str(start_date) if start_date else None"
                    )
                    lines[i] = lines[i].replace(
                        ": end_date", ": str(end_date) if end_date else None"
                    )
                    lines[i] = lines[i].replace(
                        ": timestamps",
                        ": [str(ts) for ts in timestamps] if timestamps else None",
                    )

        with open(file_path, "w") as f:
            f.writelines(lines)
        print(f"Fixed dict type issues in {file_path}")


def main():
    """Run all fixes."""
    print("Fixing remaining MyPy strict errors comprehensively...\n")

    fix_import_type_ignores()
    fix_missing_type_import()
    fix_qgridlayout_import()
    fix_optional_attributes()
    fix_goes_imagery_tab_self_issue()
    fix_visual_date_picker_callable()
    fix_auto_detection_dict_types()

    print("\nAll fixes applied!")


if __name__ == "__main__":
    main()
