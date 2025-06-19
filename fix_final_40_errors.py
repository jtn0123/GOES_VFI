#!/usr/bin/env python3
"""Fix the final 40 MyPy strict errors."""

import os
import re


def fix_xarray_matplotlib_imports():
    """Fix import-not-found errors for xarray and matplotlib."""
    files_to_fix = [
        ("goesvfi/integrity_check/render/netcdf.py", ["xarray", "matplotlib"]),
        ("goesvfi/integrity_check/sample_processor.py", ["xarray"]),
    ]

    for file_path, modules in files_to_fix:
        if not os.path.exists(file_path):
            continue

        with open(file_path, "r") as f:
            content = f.read()

        # Add type: ignore to imports
        for module in modules:
            # Handle different import patterns
            content = re.sub(
                rf"^import {module}$",
                f"import {module}  # type: ignore[import-not-found]",
                content,
                flags=re.MULTILINE,
            )
            content = re.sub(
                rf"^from {module}",
                f"from {module}",  # Keep as is, will handle below
                content,
                flags=re.MULTILINE,
            )

        # Handle matplotlib specific imports
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "from matplotlib" in line and "# type: ignore" not in line:
                lines[i] = line + "  # type: ignore[import-not-found]"
            elif line.strip() == "import xarray as xr" and "# type: ignore" not in line:
                lines[i] = "import xarray as xr  # type: ignore[import-not-found]"

        content = "\n".join(lines)

        with open(file_path, "w") as f:
            f.write(content)
        print(f"Fixed imports in {file_path}")


def fix_reconcile_manager_annotations():
    """Fix missing annotations and Optional issues in reconcile_manager_refactored.py."""
    file_path = "goesvfi/integrity_check/reconcile_manager_refactored.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        content = f.read()

    # Add proper type annotations to __init__
    content = re.sub(
        r"def __init__\(self, cache_db, cdn_store, s3_store, max_concurrency=10\) -> None:",
        "def __init__(self, cache_db: Any, cdn_store: Any, s3_store: Any, max_concurrency: int = 10) -> None:",
        content,
    )

    # Fix semaphore: Semaphore = None to use Optional
    content = re.sub(
        r"semaphore: Semaphore = None", "semaphore: Optional[Semaphore] = None", content
    )

    # Fix missing return statements
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if "def " in line and "pass" in lines[i + 1] if i + 1 < len(lines) else "":
            # Replace pass with return
            if i + 1 < len(lines) and lines[i + 1].strip() == "pass":
                lines[i + 1] = lines[i + 1].replace("pass", "return")

    content = "\n".join(lines)

    # Add imports if needed
    if "from typing import" in content and "Optional" not in content:
        content = re.sub(
            r"from typing import ([^)]+)",
            lambda m: f"from typing import {m.group(1)}, Optional",
            content,
        )

    with open(file_path, "w") as f:
        f.write(content)
    print(f"Fixed annotations in {file_path}")


def fix_run_vfi_issues():
    """Fix issues in run_vfi.py."""
    file_path = "goesvfi/run_vfi.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        lines = f.readlines()

    # Remove unused type: ignore comment on line 38
    if len(lines) > 37:
        if "# type: ignore" in lines[37]:
            lines[37] = lines[37].replace("# type: ignore", "").rstrip() + "\n"

    with open(file_path, "w") as f:
        f.writelines(lines)
    print(f"Fixed unused type: ignore in {file_path}")


def fix_pipeline_run_vfi():
    """Fix issues in pipeline/run_vfi.py."""
    file_path = "goesvfi/pipeline/run_vfi.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        content = f.read()

    # Fix Popen type parameters
    content = re.sub(r": Popen(?!\[)", ": Popen[bytes]", content)

    # Fix Optional argument issue - add assertion or check
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if "rife_exe_path" in line and "run_vfi" in line and i == 311:
            # Add assertion before the call
            indent = len(line) - len(line.lstrip())
            lines.insert(i, " " * indent + "assert rife_exe_path is not None\n")
            break

    content = "\n".join(lines)

    with open(file_path, "w") as f:
        f.write(content)
    print(f"Fixed pipeline/run_vfi.py")


def fix_timeline_visualization_hourcell():
    """Fix HourCell class issues in timeline_visualization.py."""
    file_path = "goesvfi/integrity_check/timeline_visualization.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        lines = f.readlines()

    # Find line 1260 and add type annotation
    if len(lines) > 1259:
        line = lines[1259]
        if "def __init__" in line and "->" not in line:
            lines[1259] = line.rstrip()[:-1] + " -> None:\n"

    # Fix line 1368 - missing type annotation
    if len(lines) > 1367:
        line = lines[1367]
        if "def " in line and "parent" in line and "->" not in line:
            lines[1367] = line.rstrip()[:-1] + " -> None:\n"

    with open(file_path, "w") as f:
        f.writelines(lines)
    print(f"Fixed timeline_visualization.py")


def fix_auto_detection_final():
    """Fix final issues in auto_detection.py."""
    file_path = "goesvfi/integrity_check/auto_detection.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        lines = f.readlines()

    # Fix line 155 - missing type annotation
    if len(lines) > 154:
        line = lines[154]
        if "def __init__" in line and "parent" in line and "->" not in line:
            lines[154] = line.rstrip()[:-1] + " -> None:\n"

    # Fix dict type issue on line 353 - convert list to JSON string properly
    if len(lines) > 352:
        line = lines[352]
        if '"timestamps":' in line and "json.dumps" in line:
            # Already using json.dumps, good
            pass
        elif '"timestamps":' in line:
            # Replace with proper JSON serialization
            lines[352] = line.replace(
                "str([str(ts) for ts in timestamps]) if timestamps else None",
                'json.dumps([ts.isoformat() if hasattr(ts, "isoformat") else str(ts) for ts in timestamps]) if timestamps else None',
            )

    with open(file_path, "w") as f:
        f.writelines(lines)
    print(f"Fixed auto_detection.py")


def main():
    """Run all fixes."""
    print("Fixing final 40 MyPy strict errors...\n")

    fix_xarray_matplotlib_imports()
    fix_reconcile_manager_annotations()
    fix_run_vfi_issues()
    fix_pipeline_run_vfi()
    fix_timeline_visualization_hourcell()
    fix_auto_detection_final()

    print("\nAll fixes applied!")


if __name__ == "__main__":
    main()
