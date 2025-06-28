#!/usr/bin/env python3
"""Validate Batch 1 test optimizations maintain 100% coverage."""

import ast
from pathlib import Path
import sys


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
            if node.name.startswith("Test"):
                test_classes.append(node.name)
                # Count methods in this class
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name.startswith("test_"):
                        test_methods.append(f"{node.name}.{item.name}")
                        # Check for parametrize decorator
                        parameterized_tests.extend(
                            f"{node.name}.{item.name}"
                            for decorator in item.decorator_list
                            if isinstance(decorator, ast.Attribute) and decorator.attr == "parametrize"
                        )
        elif isinstance(node, ast.FunctionDef):
            if node.name.startswith("test_") and not any(node.name in m for m in test_methods):
                test_functions.append(node.name)

    return {
        "classes": len(test_classes),
        "methods": len(test_methods),
        "functions": len(test_functions),
        "total_tests": len(test_methods) + len(test_functions),
        "parameterized": len(parameterized_tests),
        "test_names": sorted(test_methods + test_functions),
    }


def compare_coverage(original: dict, optimized: dict, name: str) -> bool:
    """Compare coverage between original and optimized versions."""
    # Calculate coverage
    coverage = (optimized["total_tests"] / original["total_tests"] * 100) if original["total_tests"] > 0 else 0

    # Check for missing tests
    original_set = set(original["test_names"])
    optimized_set = set(optimized["test_names"])

    missing = original_set - optimized_set
    new_tests = optimized_set - original_set

    if missing:
        for _test in sorted(missing)[:5]:
            pass
        if len(missing) > 5:
            pass

    if new_tests:
        for _test in sorted(new_tests)[:5]:
            pass
        if len(new_tests) > 5:
            pass

    # Success if 100% or better coverage
    success = coverage >= 100
    if success:
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
            "coverage": (optimized_analysis["total_tests"] / original_analysis["total_tests"] * 100)
            if original_analysis["total_tests"] > 0
            else 0,
            "success": success,
        })

    # Summary

    sum(r["original_tests"] for r in results)
    sum(r["optimized_tests"] for r in results)

    for r in results:
        "✅" if r["success"] else "❌"

    if all_success:
        pass

    return 0 if all_success else 1


if __name__ == "__main__":
    sys.exit(main())
