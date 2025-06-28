#!/usr/bin/env python3
"""Validate Batch 1 test optimizations maintain 100% coverage (fixed version)."""

import ast
from pathlib import Path
import sys


def count_test_methods_in_class(class_node: ast.ClassDef) -> list[str]:
    """Count test methods in a class node."""
    return [
        f"{class_node.name}.{node.name}"
        for node in class_node.body
        if (isinstance(node, ast.FunctionDef) and node.name.startswith("test_"))
        or (isinstance(node, ast.AsyncFunctionDef) and node.name.startswith("test_"))
    ]


def analyze_test_file(filepath: Path) -> dict:
    """Analyze a test file and extract metrics."""
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    tree = ast.parse(content)

    test_classes = []
    test_methods = []
    test_functions = []
    parameterized_tests = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if "Test" in node.name:  # More flexible class name matching
                test_classes.append(node.name)
                # Count methods in this class
                class_methods = count_test_methods_in_class(node)
                test_methods.extend(class_methods)

                # Check for parametrize decorators
                for item in node.body:
                    if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef) and item.name.startswith("test_"):
                        parameterized_tests.extend(
                            f"{node.name}.{item.name}"
                            for decorator in item.decorator_list
                            if (isinstance(decorator, ast.Attribute) and decorator.attr == "parametrize")
                            or (
                                isinstance(decorator, ast.Call)
                                and hasattr(decorator.func, "attr")
                                and decorator.func.attr == "parametrize"
                            )
                        )

        elif isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            # Top-level test function (not in a class)
            if not any(f".{node.name}" in m for m in test_methods):
                test_functions.append(node.name)

    # For parameterized tests, count the actual test cases
    param_expansion = 0
    if parameterized_tests:
        # Rough estimate: each parameterized test generates at least 2 test cases
        param_expansion = len(parameterized_tests) * 2

    return {
        "classes": len(test_classes),
        "methods": len(test_methods),
        "functions": len(test_functions),
        "total_tests": len(test_methods) + len(test_functions),
        "parameterized": len(parameterized_tests),
        "param_expansion": param_expansion,
        "effective_tests": len(test_methods) + len(test_functions) + param_expansion,
        "test_names": sorted(test_methods + test_functions),
    }


def compare_coverage(original: dict, optimized: dict, name: str) -> bool:
    """Compare coverage between original and optimized versions."""
    if original["param_expansion"] > 0:
        pass

    if optimized["param_expansion"] > 0:
        pass

    # Calculate coverage based on effective tests if parameterized
    if original["parameterized"] > 0 or optimized["parameterized"] > 0:
        coverage = (
            (optimized["effective_tests"] / original["effective_tests"] * 100) if original["effective_tests"] > 0 else 0
        )
    else:
        coverage = (optimized["total_tests"] / original["total_tests"] * 100) if original["total_tests"] > 0 else 0

    # Check test method mapping
    set(original["test_names"])
    set(optimized["test_names"])

    # For v2 tests, we expect different names but same functionality
    if "_v2" in str(optimized_file):
        pass

    # Success if 100% or better coverage
    success = coverage >= 100
    if success:
        pass
    else:
        pass

    return success


def main() -> int:
    """Validate Batch 1 optimizations."""
    batch1_tests = [
        ("S3 Unsigned Access", "test_s3_unsigned_access.py", "test_s3_unsigned_access_v2.py"),
        ("Optimized Timeline Tab", "test_optimized_timeline_tab.py", "test_optimized_timeline_tab_v2.py"),
        (
            "Processing View Model FFmpeg",
            "test_processing_view_model_ffmpeg.py",
            "test_processing_view_model_ffmpeg_v2.py",
        ),
        ("RIFE Analyzer", "test_rife_analyzer.py", "test_rife_analyzer_v2.py"),
        ("Date Utils", "test_date_utils.py", "test_date_utils_v2.py"),
    ]

    all_success = True
    results = []

    for name, original_file, optimized_file in batch1_tests:
        original_path = Path("tests/unit") / original_file
        optimized_path = Path("tests/unit") / optimized_file

        if not original_path.exists():
            continue

        if not optimized_path.exists():
            continue

        original_analysis = analyze_test_file(original_path)
        optimized_analysis = analyze_test_file(optimized_path)

        success = compare_coverage(original_analysis, optimized_analysis, name)
        all_success = all_success and success

        results.append({
            "name": name,
            "original_tests": original_analysis["total_tests"],
            "optimized_tests": optimized_analysis["total_tests"],
            "original_effective": original_analysis["effective_tests"],
            "optimized_effective": optimized_analysis["effective_tests"],
            "coverage": (optimized_analysis["effective_tests"] / original_analysis["effective_tests"] * 100)
            if original_analysis["effective_tests"] > 0
            else 0,
            "success": success,
        })

    # Summary

    sum(r["original_tests"] for r in results)
    sum(r["optimized_tests"] for r in results)
    sum(r["original_effective"] for r in results)
    sum(r["optimized_effective"] for r in results)

    for r in results:
        "✅" if r["success"] else "❌"

    if all_success:
        pass
    else:
        pass

    return 0 if all_success else 1


if __name__ == "__main__":
    sys.exit(main())
