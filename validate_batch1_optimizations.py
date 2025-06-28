#!/usr/bin/env python3
"""
Validate Batch 1 test optimizations maintain 100% coverage.
"""

import ast
import sys
from pathlib import Path
from typing import Dict, Set


def analyze_test_file(filepath: Path) -> Dict:
    """Analyze a test file and extract metrics."""
    with open(filepath, 'r') as f:
        content = f.read()

    tree = ast.parse(content)

    test_classes = []
    test_methods = []
    test_functions = []
    parameterized_tests = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if node.name.startswith('Test'):
                test_classes.append(node.name)
                # Count methods in this class
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name.startswith('test_'):
                        test_methods.append(f"{node.name}.{item.name}")
                        # Check for parametrize decorator
                        for decorator in item.decorator_list:
                            if isinstance(decorator, ast.Attribute) and decorator.attr == 'parametrize':
                                parameterized_tests.append(f"{node.name}.{item.name}")
        elif isinstance(node, ast.FunctionDef):
            if node.name.startswith('test_') and not any(node.name in m for m in test_methods):
                test_functions.append(node.name)

    return {
        'classes': len(test_classes),
        'methods': len(test_methods),
        'functions': len(test_functions),
        'total_tests': len(test_methods) + len(test_functions),
        'parameterized': len(parameterized_tests),
        'test_names': sorted(test_methods + test_functions),
    }


def compare_coverage(original: Dict, optimized: Dict, name: str) -> bool:
    """Compare coverage between original and optimized versions."""
    print(f"\n{'='*60}")
    print(f"📊 {name}")
    print('='*60)

    print(f"Original: {original['total_tests']} tests ({original['classes']} classes, {original['parameterized']} parameterized)")
    print(f"Optimized: {optimized['total_tests']} tests ({optimized['classes']} classes, {optimized['parameterized']} parameterized)")

    # Calculate coverage
    coverage = (optimized['total_tests'] / original['total_tests'] * 100) if original['total_tests'] > 0 else 0

    print(f"Coverage: {coverage:.1f}%")

    # Check for missing tests
    original_set = set(original['test_names'])
    optimized_set = set(optimized['test_names'])

    missing = original_set - optimized_set
    new_tests = optimized_set - original_set

    if missing:
        print(f"\n⚠️  Missing tests: {len(missing)}")
        for test in sorted(missing)[:5]:
            print(f"  - {test}")
        if len(missing) > 5:
            print(f"  ... and {len(missing) - 5} more")

    if new_tests:
        print(f"\n✨ New tests: {len(new_tests)}")
        for test in sorted(new_tests)[:5]:
            print(f"  + {test}")
        if len(new_tests) > 5:
            print(f"  ... and {len(new_tests) - 5} more")

    # Success if 100% or better coverage
    success = coverage >= 100
    if success:
        print(f"\n✅ Coverage maintained at {coverage:.1f}%")
    else:
        print(f"\n❌ Coverage below 100% threshold")

    return success


def main():
    """Validate Batch 1 optimizations."""
    print("🚀 Batch 1 Test Optimization Validation")
    print("=" * 80)

    batch1_tests = [
        ("S3 Unsigned Access", "test_s3_unsigned_access.py", "test_s3_unsigned_access_v2.py"),
        ("Optimized Timeline Tab", "test_optimized_timeline_tab.py", "test_optimized_timeline_tab_v2.py"),
        ("Processing View Model FFmpeg", "test_processing_view_model_ffmpeg.py", "test_processing_view_model_ffmpeg_v2.py"),
        ("RIFE Analyzer", "test_rife_analyzer.py", "test_rife_analyzer_v2.py"),
        ("Date Utils", "test_date_utils.py", "test_date_utils_v2.py"),
    ]

    all_success = True
    results = []

    for name, original_file, optimized_file in batch1_tests:
        original_path = Path("tests/unit") / original_file
        optimized_path = Path("tests/unit") / optimized_file

        if not original_path.exists():
            print(f"\n❌ Original not found: {original_path}")
            continue

        if not optimized_path.exists():
            print(f"\n❌ Optimized not found: {optimized_path}")
            continue

        original_analysis = analyze_test_file(original_path)
        optimized_analysis = analyze_test_file(optimized_path)

        success = compare_coverage(original_analysis, optimized_analysis, name)
        all_success = all_success and success

        results.append({
            'name': name,
            'original_tests': original_analysis['total_tests'],
            'optimized_tests': optimized_analysis['total_tests'],
            'coverage': (optimized_analysis['total_tests'] / original_analysis['total_tests'] * 100) if original_analysis['total_tests'] > 0 else 0,
            'success': success
        })

    # Summary
    print("\n" + "="*80)
    print("📈 BATCH 1 SUMMARY")
    print("="*80)

    total_original = sum(r['original_tests'] for r in results)
    total_optimized = sum(r['optimized_tests'] for r in results)

    print(f"\nTotal original tests: {total_original}")
    print(f"Total optimized tests: {total_optimized}")
    print(f"Overall coverage: {total_optimized/total_original*100:.1f}%")

    print("\nIndividual results:")
    for r in results:
        status = "✅" if r['success'] else "❌"
        print(f"  {status} {r['name']}: {r['coverage']:.1f}% ({r['optimized_tests']}/{r['original_tests']} tests)")

    if all_success:
        print("\n✅ All Batch 1 tests maintain 100% or better coverage!")
    else:
        print("\n❌ Some tests need improvement to reach 100% coverage")

    return 0 if all_success else 1


if __name__ == "__main__":
    sys.exit(main())