#!/usr/bin/env python
"""Final comprehensive syntax fixer."""

import ast
import re
from pathlib import Path


def fix_file_aggressively(file_path: Path) -> bool:
    """Fix a file with aggressive patterns."""
    try:
        content = file_path.read_text(encoding="utf-8")
        original = content

        # 1. Fix docstrings with code mixed in
        # Pattern: """text\nfrom module or """text\nQWidget
        lines = content.split("\n")
        fixed_lines = []
        in_docstring = False

        for i, line in enumerate(lines):
            if '"""' in line and line.count('"""') == 1:
                if not in_docstring:
                    in_docstring = True
                else:
                    in_docstring = False

            # If we see code-like patterns in docstring, close it
            if (
                in_docstring
                and i > 0
                and (
                    line.strip().startswith(("from ", "import ", "class ", "def "))
                    or (
                        line.strip() and not line[0].isspace() and i > 2
                    )  # Unindented non-empty line
                )
            ):
                # Close docstring on previous line
                if fixed_lines and '"""' not in fixed_lines[-1]:
                    fixed_lines[-1] = fixed_lines[-1] + '"""'
                fixed_lines.append("")  # blank line
                in_docstring = False

            # Also check for orphaned widget names
            if not in_docstring and re.match(r"^[A-Z]\w+,$", line.strip()):
                # This is likely part of an import statement
                if i > 0 and "from" in lines[i - 5 : i]:
                    # Find the from statement and fix it
                    pass
                else:
                    continue  # Skip orphaned lines

            fixed_lines.append(line)

        content = "\n".join(fixed_lines)

        # 2. Fix logging format errors
        content = re.sub(r"(\w+):(\.?\d+)f\)", r"\1)", content)

        # 3. Fix decimal literal errors (1st, 2nd, 3rd in strings)
        content = re.sub(r"\b1st\b", "first", content)
        content = re.sub(r"\b2nd\b", "second", content)
        content = re.sub(r"\b3rd\b", "third", content)
        content = re.sub(r"\b(\d+)th\b", r"\1th", content)

        # 4. Fix split function calls more aggressively
        content = re.sub(r"(\w+)\(\)\s*\n\s*\(", r"\1(", content)
        content = re.sub(r'(\w+)\(\)\s*\n\s*"', r'\1("', content)
        content = re.sub(r"(\w+)\(\)\s*\n\s*\'", r"\1('", content)
        content = re.sub(r'(\w+)\(\)\s*\n\s*f"', r'\1(f"', content)
        content = re.sub(r"(\w+)\(\)\s*\n\s*f\'", r"\1(f'", content)

        # 5. Fix unmatched parentheses by removing orphaned closing parens
        lines = content.split("\n")
        fixed_lines = []
        for i, line in enumerate(lines):
            # Skip lines that are just ) or ),
            if line.strip() in [")", "),", ");", "},", "],"]:
                # Check if previous line needs it
                if i > 0 and fixed_lines:
                    prev = fixed_lines[-1]
                    # Count open/close
                    opens = prev.count("(") + prev.count("[") + prev.count("{")
                    closes = prev.count(")") + prev.count("]") + prev.count("}")
                    if opens > closes:
                        fixed_lines[-1] = prev.rstrip() + line.strip()
                        continue
                # Otherwise skip
                continue
            fixed_lines.append(line)

        content = "\n".join(fixed_lines)

        # 6. Fix empty except/try blocks
        content = re.sub(r"(try:\s*\n)(\s*except)", r"\1    pass\n\2", content)
        content = re.sub(
            r"(except[^:]*:\s*\n)(\s*(?:except|else|finally|class|def|\Z))",
            r"\1    pass\n\2",
            content,
        )

        # 7. Fix unterminated strings
        lines = content.split("\n")
        fixed_lines = []
        for line in lines:
            # Check for odd number of quotes
            if line.count('"') % 2 == 1:
                # Check if it's an f-string or raw string
                if ('f"' in line or 'r"' in line) and not line.rstrip().endswith('"'):
                    line = line.rstrip() + '"'
            if line.count("'") % 2 == 1:
                if ("f'" in line or "r'" in line) and not line.rstrip().endswith("'"):
                    line = line.rstrip() + "'"
            fixed_lines.append(line)

        content = "\n".join(fixed_lines)

        # 8. Fix __future__ imports
        lines = content.split("\n")
        future_imports = []
        other_lines = []

        for line in lines:
            if "from __future__ import" in line:
                future_imports.append(line)
            else:
                other_lines.append(line)

        if future_imports:
            # Remove empty lines at start of other_lines
            while other_lines and not other_lines[0].strip():
                other_lines.pop(0)
            content = "\n".join(future_imports + [""] + other_lines)

        # Try to parse
        try:
            ast.parse(content)
            if content != original:
                file_path.write_text(content, encoding="utf-8")
                return True
        except SyntaxError:
            # One more attempt - remove all orphaned widget names
            lines = content.split("\n")
            fixed_lines = []
            for line in lines:
                # Skip lines that look like orphaned widget names
                if re.match(r"^[A-Z][a-zA-Z]+,$", line.strip()):
                    continue
                fixed_lines.append(line)

            content = "\n".join(fixed_lines)

            try:
                ast.parse(content)
                file_path.write_text(content, encoding="utf-8")
                return True
            except:
                pass

        return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Fix all files with syntax errors."""
    # Process all Python files in goesvfi
    all_files = list(Path("goesvfi").rglob("*.py"))

    print(f"Checking {len(all_files)} Python files...")
    print("=" * 80)

    fixed = 0
    still_broken = []

    for file_path in sorted(all_files):
        try:
            # Try to parse the file
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            ast.parse(content)
            # File is OK
        except SyntaxError:
            # File needs fixing
            if fix_file_aggressively(file_path):
                fixed += 1
                print(f"✓ Fixed: {file_path}")
            else:
                still_broken.append(file_path)
        except Exception as e:
            print(f"Error checking {file_path}: {e}")

    print("=" * 80)
    print(f"Fixed {fixed} files")
    print(f"{len(still_broken)} files still have syntax errors")

    if still_broken:
        print("\nFiles still broken:")
        for f in still_broken[:20]:  # Show first 20
            print(f"  - {f}")


if __name__ == "__main__":
    main()
