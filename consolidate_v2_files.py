#!/usr/bin/env python3
"""Consolidate v2 files by choosing the best version when duplicates exist."""

import ast
from pathlib import Path


def count_test_functions(filepath: Path) -> int:
    """Count test functions in a file."""
    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content)
        test_count = 0

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith("test_"):
                test_count += 1

        return test_count
    except Exception:
        return -1


def main() -> None:
    """Consolidate v2 files."""
    # Files to consolidate
    consolidations = [
        {
            "base": "full_application_workflow",
            "files": [
                "tests/integration/test_full_application_workflow_v2.py",
                "tests/integration/test_full_application_workflow_optimized_v2.py",
            ],
        },
        {"base": "main_tab", "files": ["tests/unit/test_main_tab_v2.py", "tests/unit/test_main_tab_optimized_v2.py"]},
        {
            "base": "model_manager",
            "files": ["tests/unit/test_model_manager_v2.py", "tests/unit/test_model_manager_optimized_v2.py"],
        },
        {
            "base": "network_failure_simulation",
            "files": [
                "tests/unit/test_network_failure_simulation_v2.py",
                "tests/unit/test_network_failure_simulation_optimized_v2.py",
            ],
        },
        {"base": "security", "files": ["tests/unit/test_security_v2.py", "tests/unit/test_security_optimized_v2.py"]},
    ]

    for item in consolidations:
        # Count tests in each file
        file_info = []
        for filepath in item["files"]:
            path = Path(filepath)
            if path.exists():
                count = count_test_functions(path)
                size = path.stat().st_size
                file_info.append({"path": path, "count": count, "size": size})

        # Recommend which to keep
        if len(file_info) == 2:
            # Choose the one with more tests
            if file_info[0]["count"] > file_info[1]["count"]:
                keep, _remove = file_info[0], file_info[1]
            elif file_info[1]["count"] > file_info[0]["count"]:
                keep, _remove = file_info[1], file_info[0]
            # Same test count, choose larger file
            elif file_info[0]["size"] > file_info[1]["size"]:
                keep, _remove = file_info[0], file_info[1]
            else:
                keep, _remove = file_info[1], file_info[0]

            # If we're keeping the optimized version, suggest renaming
            if "_optimized_v2" in keep["path"].name:
                keep["path"].name.replace("_optimized_v2", "_v2")

    # Handle other duplicates

    # Check operation_history_tab
    files = list(Path().glob("**/test_operation_history_tab_v2.py"))
    if len(files) > 1:
        for f in files:
            count = count_test_functions(f)

    # Check rife_analyzer
    files = list(Path().glob("**/test_rife_analyzer_v2.py"))
    if len(files) > 1:
        for f in files:
            count = count_test_functions(f)

    # Summary of missing file mappings

    # Commands to execute


if __name__ == "__main__":
    main()
