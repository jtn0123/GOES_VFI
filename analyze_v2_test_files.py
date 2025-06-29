#!/usr/bin/env python3
"""Analyze v2 test files to compare with original files and identify missing files.

This script:
1. Finds all v2 test files
2. Identifies their corresponding original files
3. Compares test function counts
4. Reports on missing files mentioned in tracking document
5. Identifies any additional files created
"""

import ast
import operator
from pathlib import Path
import sys


class TestAnalyzer(ast.NodeVisitor):
    """Analyze test files to count test methods."""

    def __init__(self) -> None:
        self.test_methods = []
        self.test_classes = []
        self.current_class = None

    def visit_ClassDef(self, node) -> None:
        """Track test classes."""
        if node.name.startswith("Test"):
            self.test_classes.append(node.name)
            old_class = self.current_class
            self.current_class = node.name
            self.generic_visit(node)
            self.current_class = old_class
        else:
            self.generic_visit(node)

    def visit_FunctionDef(self, node) -> None:
        """Track test methods."""
        if node.name.startswith("test_"):
            self.test_methods.append({
                "class": self.current_class,
                "method": node.name,
                "async": isinstance(node, ast.AsyncFunctionDef),
            })
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node) -> None:
        """Track async test methods."""
        self.visit_FunctionDef(node)


def count_test_functions(filepath: Path) -> int:
    """Count test functions in a file."""
    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content)
        analyzer = TestAnalyzer()
        analyzer.visit(tree)

        return len(analyzer.test_methods)
    except Exception:
        return -1


def find_original_file(v2_file: Path) -> Path:
    """Find the original file for a v2 file."""
    # Handle different v2 naming patterns
    name = v2_file.stem

    # Remove various v2 suffixes
    if name.endswith("_v2"):
        original_name = name[:-3]
    elif name.endswith("_optimized_v2"):
        original_name = name[:-13]
    elif name.endswith("_optimized"):
        original_name = name[:-10]
    else:
        return None

    # Try to find the original file
    original_path = v2_file.parent / f"{original_name}.py"
    if original_path.exists():
        return original_path

    return None


def get_claimed_files_from_tracking() -> set[str]:
    """Extract files claimed to be optimized from tracking document."""
    tracking_file = Path("TEST_OPTIMIZATION_TRACKING.md")
    claimed_files = set()

    if not tracking_file.exists():
        return claimed_files

    with open(tracking_file, encoding="utf-8") as f:
        content = f.read()

    # Look for patterns like "test_*.py → test_*_v2.py"
    import re

    pattern = r"`(tests/[^`]+\.py)`\s*→\s*`([^`]+_v2\.py)`"
    matches = re.findall(pattern, content)

    claimed_files.update(v2.split("/")[-1] for original, v2 in matches)  # Just the filename

    return claimed_files


def main():
    """Analyze all v2 test files."""
    # Find all v2 test files
    v2_files = []
    for pattern in ["**/*_v2.py", "**/*_optimized_v2.py", "**/*_optimized.py"]:
        v2_files.extend(Path().glob(pattern))

    # Filter to only test files
    v2_test_files = [f for f in v2_files if "/test" in str(f) and f.stem.startswith("test_")]

    # Get claimed files from tracking document
    claimed_files = get_claimed_files_from_tracking()

    # Analyze each v2 file
    results = []
    missing_originals = []
    total_v2_functions = 0
    total_original_functions = 0

    for v2_file in sorted(v2_test_files):
        v2_count = count_test_functions(v2_file)
        if v2_count < 0:
            continue

        original_file = find_original_file(v2_file)

        if original_file and original_file.exists():
            original_count = count_test_functions(original_file)
            if original_count >= 0:
                total_v2_functions += v2_count
                total_original_functions += original_count

                results.append({
                    "v2_file": v2_file,
                    "original_file": original_file,
                    "v2_count": v2_count,
                    "original_count": original_count,
                    "difference": v2_count - original_count,
                    "percentage": (v2_count / original_count * 100) if original_count > 0 else 0,
                })
        else:
            missing_originals.append(v2_file)
            total_v2_functions += v2_count

    # Find v2 files mentioned in tracking but not found
    actual_v2_names = {f.name for f in v2_test_files}
    missing_from_claimed = claimed_files - actual_v2_names

    # Print results

    for r in sorted(results, key=operator.itemgetter("difference"), reverse=True):
        r["v2_file"].name

    # V2 files without originals
    if missing_originals:
        for f in sorted(missing_originals):
            count_test_functions(f)

    # Files claimed but missing
    if missing_from_claimed:
        for f in sorted(missing_from_claimed):
            pass

    # Summary statistics

    # Coverage analysis
    [r for r in results if r["difference"] > 0]
    [r for r in results if r["difference"] == 0]
    files_with_fewer_tests = [r for r in results if r["difference"] < 0]

    if files_with_fewer_tests:
        for r in files_with_fewer_tests:
            pass

    return len(missing_from_claimed) == 0 and len(files_with_fewer_tests) == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
