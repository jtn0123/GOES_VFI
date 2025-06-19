#!/usr/bin/env python3
"""Fix common mock attribute issues in tests."""

import re
import sys
from pathlib import Path

# Common mock attributes that need to be added
MOCK_ATTRIBUTES = {
    # Pattern -> Fix
    r"AttributeError: Mock object has no attribute 'db_path'": "mock.db_path = '/tmp/test.db'",
    r"AttributeError: Mock object has no attribute 'base_directory'": "mock.base_directory = Path('/tmp')",
    r"AttributeError: Mock object has no attribute 'satellite'": "mock.satellite = SatellitePattern.GOES_16",
}


def add_mock_attributes(content, mock_var_name, attributes):
    """Add attributes to a mock object after its creation."""
    # Find where mock is created
    pattern = rf"{mock_var_name}\s*=\s*(?:Mock|MagicMock|AsyncMock)\([^)]*\)"

    matches = list(re.finditer(pattern, content))
    if not matches:
        return content, False

    # Add attributes after each mock creation
    offset = 0
    for match in matches:
        insert_pos = match.end() + offset

        # Find the end of the line
        next_newline = content.find("\n", insert_pos)
        if next_newline == -1:
            next_newline = len(content)

        # Get indentation
        line_start = content.rfind("\n", 0, match.start()) + 1
        indent = len(content[line_start : match.start()])
        indent_str = " " * indent

        # Add attributes
        additions = []
        for attr in attributes:
            additions.append(f"\n{indent_str}{mock_var_name}.{attr}")

        addition_text = "".join(additions)
        content = content[:next_newline] + addition_text + content[next_newline:]
        offset += len(addition_text)

    return content, True


def fix_file(file_path):
    """Fix mock attribute issues in a file."""
    print(f"\nProcessing {file_path}...")

    # First, run the test to see what errors we get
    import subprocess

    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(file_path), "-x", "--tb=short"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    if "AttributeError" not in result.stdout:
        print("  ✓ No mock attribute errors found")
        return False

    with open(file_path, "r") as f:
        content = f.read()

    original_content = content
    changes_made = []

    # Common patterns
    if "Mock object has no attribute 'db_path'" in result.stdout:
        # Find cache_db mocks and add db_path
        content, changed = add_mock_attributes(
            content, "mock_cache_db", ['db_path = Path("/tmp/test.db")']
        )
        if changed:
            changes_made.append("Added db_path to mock_cache_db")

        # Also check for self.cache_db
        content, changed = add_mock_attributes(
            content, "self.cache_db", ['db_path = Path("/tmp/test.db")']
        )
        if changed:
            changes_made.append("Added db_path to self.cache_db")

    # Ensure imports
    if "Path(" in content and "from pathlib import Path" not in content:
        import_pattern = r"((?:from .* import .*\n|import .*\n)+)"
        content = re.sub(
            import_pattern, r"\1from pathlib import Path\n", content, count=1
        )
        changes_made.append("Added Path import")

    if content != original_content:
        with open(file_path, "w") as f:
            f.write(content)
        print(f"  ✓ Fixed {len(changes_made)} issues:")
        for change in changes_made:
            print(f"    - {change}")
        return True
    else:
        print("  ✓ No fixes applied")
        return False


def main():
    """Main function."""
    if len(sys.argv) > 1:
        files = [Path(f) for f in sys.argv[1:]]
    else:
        # Test files known to have mock issues
        files = [
            Path("tests/unit/test_enhanced_view_model.py"),
            Path("tests/unit/test_cache.py"),
        ]

    fixed_count = 0
    for file_path in files:
        if file_path.exists():
            try:
                if fix_file(file_path):
                    fixed_count += 1
            except Exception as e:
                print(f"  ✗ Error processing file: {e}")
        else:
            print(f"File not found: {file_path}")

    print(f"\n✓ Fixed {fixed_count} files")


if __name__ == "__main__":
    main()
