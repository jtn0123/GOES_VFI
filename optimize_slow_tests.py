#!/usr/bin/env python3
"""Script to identify and optimize slow tests automatically."""

import ast
import re
import sys
from pathlib import Path
from typing import List, Tuple


class TestOptimizer(ast.NodeVisitor):
    """AST visitor to identify slow test patterns."""

    def __init__(self):
        self.slow_patterns = []
        self.current_function = None

    def visit_FunctionDef(self, node):
        """Track current test function."""
        if node.name.startswith('test_'):
            self.current_function = node.name
            self.generic_visit(node)
            self.current_function = None
        else:
            self.generic_visit(node)

    def visit_Call(self, node):
        """Identify slow patterns in function calls."""
        if self.current_function:
            # Check for slow patterns
            func_name = self.get_call_name(node)

            slow_patterns = {
                'MainWindow': 'Creating real MainWindow',
                'qtbot.wait': 'Real waiting in tests',
                'time.sleep': 'Sleeping in tests',
                'QApplication.processEvents': 'Processing real events',
                'boto3.client': 'Real AWS connections',
                'requests.get': 'Real HTTP requests',
                'QTimer': 'Real timers in tests',
                'open': 'File I/O in tests',
                'subprocess.run': 'Running real subprocesses',
            }

            for pattern, description in slow_patterns.items():
                if pattern in func_name:
                    self.slow_patterns.append((
                        self.current_function,
                        node.lineno,
                        pattern,
                        description
                    ))

        self.generic_visit(node)

    def get_call_name(self, node):
        """Extract the full call name from AST node."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts = []
            current = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return '.'.join(reversed(parts))
        return ''


def analyze_test_file(file_path: Path) -> List[Tuple[str, int, str, str]]:
    """Analyze a test file for slow patterns."""
    try:
        content = file_path.read_text()
        tree = ast.parse(content)

        optimizer = TestOptimizer()
        optimizer.visit(tree)

        return optimizer.slow_patterns
    except Exception as e:
        print(f"Error analyzing {file_path}: {e}")
        return []


def generate_optimization_suggestions(slow_patterns: List[Tuple[str, int, str, str]]) -> str:
    """Generate optimization suggestions based on patterns found."""
    suggestions = []

    pattern_fixes = {
        'MainWindow': '''
# Instead of:
window = MainWindow()

# Use:
window = FastQtTestHelper.mock_main_window(mocker)
''',
        'qtbot.wait': '''
# Instead of:
qtbot.wait(1000)

# Use:
FastQtTestHelper.fast_qtbot_wait(qtbot, 1000)
''',
        'time.sleep': '''
# Instead of:
time.sleep(1)

# Use:
# Remove sleep or use mock
with patch('time.sleep'):
    # your test code
''',
        'boto3.client': '''
# Instead of:
client = boto3.client('s3')

# Use:
client = create_fast_mock_s3_client()
''',
        'QTimer': '''
# Instead of:
timer = QTimer()

# Use:
timer = FastTestTimer()
''',
    }

    for func, line, pattern, desc in slow_patterns:
        fix = pattern_fixes.get(pattern, f"# Mock {pattern} to avoid {desc}")
        suggestions.append(f"""
Function: {func} (line {line})
Issue: {desc}
Fix: {fix}
""")

    return '\n'.join(suggestions)


def create_optimized_test(original_path: Path) -> Path:
    """Create an optimized version of a test file."""
    content = original_path.read_text()

    # Add optimization imports
    optimization_imports = '''from tests.utils.test_optimization_helpers import (
    FastQtTestHelper,
    optimize_test_performance,
    FastTestTimer,
    create_fast_mock_s3_client,
)

'''

    # Add imports after the first import block
    import_match = re.search(r'((?:from .+|import .+\n)+)', content)
    if import_match:
        pos = import_match.end()
        content = content[:pos] + optimization_imports + content[pos:]

    # Apply common optimizations
    replacements = [
        # Mock MainWindow creation
        (r'window = MainWindow\([^)]*\)',
         'window = FastQtTestHelper.mock_main_window(mocker)'),

        # Replace qtbot.wait
        (r'qtbot\.wait\((\d+)\)',
         r'FastQtTestHelper.fast_qtbot_wait(qtbot, \1)'),

        # Mock time.sleep
        (r'time\.sleep\([^)]+\)',
         'pass  # Sleep removed for speed'),

        # Mock QTimer
        (r'QTimer\(\)',
         'FastTestTimer()'),
    ]

    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)

    # Add decorator to test functions
    content = re.sub(
        r'(\n    def test_)',
        r'\n    @optimize_test_performance\n    def test_',
        content
    )

    # Save optimized version
    optimized_path = original_path.parent / f"{original_path.stem}_optimized.py"
    optimized_path.write_text(content)

    return optimized_path


def main():
    """Main function to optimize slow tests."""
    print("🔍 Analyzing tests for optimization opportunities...")

    # Get test files from arguments or use problematic ones
    if len(sys.argv) > 1:
        test_files = [Path(arg) for arg in sys.argv[1:]]
    else:
        # Default to known slow tests
        test_files = [
            Path("tests/gui/test_performance_ui.py"),
            Path("tests/gui/test_gui_components.py"),
            Path("tests/unit/test_main_tab.py"),
        ]

    total_issues = 0

    for test_file in test_files:
        if not test_file.exists():
            print(f"⚠️  File not found: {test_file}")
            continue

        print(f"\n📄 Analyzing {test_file}...")

        # Analyze for slow patterns
        slow_patterns = analyze_test_file(test_file)

        if slow_patterns:
            total_issues += len(slow_patterns)
            print(f"   Found {len(slow_patterns)} optimization opportunities:")

            # Generate suggestions
            suggestions = generate_optimization_suggestions(slow_patterns)
            print(suggestions)

            # Ask if user wants to create optimized version
            response = input(f"\n   Create optimized version? (y/n): ")
            if response.lower() == 'y':
                optimized_path = create_optimized_test(test_file)
                print(f"   ✅ Created: {optimized_path}")
        else:
            print("   ✅ No slow patterns found!")

    print(f"\n📊 Summary: Found {total_issues} optimization opportunities")

    if total_issues > 0:
        print("\n💡 Next steps:")
        print("1. Review the generated _optimized.py files")
        print("2. Run tests to ensure they still pass")
        print("3. Replace original files if tests pass")
        print("4. Update run_all_tests.py to remove from PROBLEMATIC_TESTS")


if __name__ == "__main__":
    main()