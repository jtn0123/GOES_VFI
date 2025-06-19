#!/usr/bin/env python
"""Comprehensive syntax error fixer for the GOES-VFI codebase."""

import ast
import re
from pathlib import Path
from typing import List, Optional, Tuple


class SyntaxFixer:
    def __init__(self):
        self.fixes_applied = 0

    def fix_file(self, file_path: Path) -> Tuple[bool, str]:
        """Fix syntax errors in a single file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            original_content = content

            # Apply fixes
            content = self.fix_future_imports(content)
            content = self.fix_empty_imports(content)
            content = self.fix_split_function_calls(content)
            content = self.fix_unmatched_parentheses(content)
            content = self.fix_duplicate_except(content)
            content = self.fix_empty_except_blocks(content)
            content = self.fix_docstring_placement(content)
            content = self.fix_f_string_errors(content)
            content = self.fix_indentation_after_colon(content)

            # Check if we fixed anything
            if content != original_content:
                # Verify the fix by parsing
                try:
                    ast.parse(content)
                    # Write back the fixed content
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    return True, "Fixed"
                except SyntaxError as e:
                    # If still has errors, try line-by-line fixes
                    content = self.fix_line_by_line(original_content)
                    try:
                        ast.parse(content)
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(content)
                        return True, "Fixed with line-by-line"
                    except SyntaxError:
                        return False, f"Still has errors: {e}"

            # Check if file already has syntax errors
            try:
                ast.parse(content)
                return False, "No changes needed"
            except SyntaxError as e:
                return False, f"Unfixable error: {e}"

        except Exception as e:
            return False, f"Error processing file: {e}"

    def fix_future_imports(self, content: str) -> str:
        """Move __future__ imports to the top of the file."""
        lines = content.split("\n")
        future_imports = []
        other_lines = []

        for line in lines:
            if "from __future__ import" in line:
                future_imports.append(line)
            else:
                other_lines.append(line)

        if future_imports:
            # Put future imports at the very top
            result = future_imports + [""] + other_lines
            return "\n".join(result)

        return content

    def fix_empty_imports(self, content: str) -> str:
        """Fix empty import statements like 'from module import ()'"""
        # Pattern: from module import ()
        content = re.sub(r"from\s+[\w.]+\s+import\s+\(\s*\)\s*\n", "", content)
        return content

    def fix_split_function_calls(self, content: str) -> str:
        """Fix function calls split across lines."""
        # Pattern: function() \n "string"
        content = re.sub(r'(\w+)\(\)\s*\n\s*(["\'])', r"\1(\2", content)

        # Pattern: .method() \n "string"
        content = re.sub(r'\.(\w+)\(\)\s*\n\s*(["\'])', r".\1(\2", content)

        # Pattern: raise Exception() \n "message"
        content = re.sub(r'(raise\s+\w+)\(\)\s*\n\s*(["\'])', r"\1(\2", content)

        return content

    def fix_unmatched_parentheses(self, content: str) -> str:
        """Fix unmatched closing parentheses."""
        lines = content.split("\n")
        fixed_lines = []

        for i, line in enumerate(lines):
            # Skip if line is just whitespace and )
            if re.match(r"^\s*\)\s*$", line):
                # Check if previous line needs it
                if i > 0 and fixed_lines:
                    prev_line = fixed_lines[-1]
                    open_count = prev_line.count("(")
                    close_count = prev_line.count(")")
                    if open_count > close_count:
                        # Append ) to previous line
                        fixed_lines[-1] = prev_line.rstrip() + ")"
                        continue
                # Otherwise skip this line
                continue
            fixed_lines.append(line)

        return "\n".join(fixed_lines)

    def fix_duplicate_except(self, content: str) -> str:
        """Fix duplicate except statements."""
        content = re.sub(
            r"except\s+(\w+)\s+as\s+(\w+):\s*\n\s*except\s+\1\s+as\s+\2:",
            r"except \1 as \2:",
            content,
        )
        return content

    def fix_empty_except_blocks(self, content: str) -> str:
        """Add pass to empty except blocks."""
        lines = content.split("\n")
        fixed_lines = []

        for i, line in enumerate(lines):
            fixed_lines.append(line)

            # If this is an except line
            if re.match(r"\s*except.*:", line):
                # Check if next line is another except, else, finally, or dedent
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    if re.match(r"\s*(except|else|finally|class|def|\S)", next_line):
                        # Add pass with proper indentation
                        indent = re.match(r"(\s*)", line).group(1)
                        fixed_lines.append(indent + "    pass")

        return "\n".join(fixed_lines)

    def fix_docstring_placement(self, content: str) -> str:
        """Fix docstrings that contain code."""
        # Pattern: """text\nfrom module import"""
        content = re.sub(r'("""[^"]*)\nfrom\s+', r'\1"""\n\nfrom ', content)

        # Pattern: """text\nimport module"""
        content = re.sub(r'("""[^"]*)\nimport\s+', r'\1"""\n\nimport ', content)

        return content

    def fix_f_string_errors(self, content: str) -> str:
        """Fix f-string literal errors."""
        # Fix unterminated f-strings by ensuring quotes match
        lines = content.split("\n")
        fixed_lines = []

        for line in lines:
            if 'f"' in line or "f'" in line:
                # Count quotes
                double_quotes = line.count('"')
                single_quotes = line.count("'")

                # Fix obvious unterminated strings
                if line.strip().startswith('f"') and double_quotes % 2 == 1:
                    line = line.rstrip() + '"'
                elif line.strip().startswith("f'") and single_quotes % 2 == 1:
                    line = line.rstrip() + "'"

            fixed_lines.append(line)

        return "\n".join(fixed_lines)

    def fix_indentation_after_colon(self, content: str) -> str:
        """Fix missing indentation after colons."""
        lines = content.split("\n")
        fixed_lines = []

        for i, line in enumerate(lines):
            fixed_lines.append(line)

            # If line ends with : and next line has same or less indentation
            if line.strip().endswith(":") and i + 1 < len(lines):
                current_indent = len(line) - len(line.lstrip())
                next_line = lines[i + 1]
                next_indent = len(next_line) - len(next_line.lstrip())

                if next_line.strip() and next_indent <= current_indent:
                    # Add a pass statement
                    indent = " " * (current_indent + 4)
                    fixed_lines.append(indent + "pass")

        return "\n".join(fixed_lines)

    def fix_line_by_line(self, content: str) -> str:
        """Try to fix syntax errors line by line."""
        lines = content.split("\n")
        fixed_lines = []

        for line in lines:
            # Skip obviously broken lines
            if line.strip() == ")":
                continue
            if line.strip() == "from typing import PathLike":
                continue
            if (
                re.match(r"^\s+CropManager,", line)
                and "import" not in content[: content.find(line)]
            ):
                continue

            fixed_lines.append(line)

        return "\n".join(fixed_lines)


def main():
    """Fix all syntax errors in the codebase."""
    fixer = SyntaxFixer()
    project_root = Path(__file__).parent

    # Get all Python files with syntax errors (from our previous scan)
    error_files = [
        "goesvfi/gui_tabs/ffmpeg_settings_tab.py",
        "goesvfi/gui_components/settings_manager.py",
        "goesvfi/integrity_check/remote/base.py",
        "goesvfi/integrity_check/remote/cdn_store.py",
        "goesvfi/integrity_check/remote/s3_store.py",
        "goesvfi/sanchez/health_check.py",
        "goesvfi/utils/resource_manager.py",
    ]

    print("Fixing syntax errors in critical files...")
    print("=" * 80)

    fixed_count = 0
    still_broken = []

    for file_path in error_files:
        full_path = project_root / file_path
        if full_path.exists():
            success, message = fixer.fix_file(full_path)
            if success:
                fixed_count += 1
                print(f"✓ Fixed: {file_path}")
            else:
                still_broken.append((file_path, message))
                print(f"✗ Failed: {file_path} - {message}")

    print("=" * 80)
    print(f"Fixed {fixed_count} out of {len(error_files)} files")

    if still_broken:
        print("\nFiles still needing manual fixes:")
        for path, error in still_broken:
            print(f"  - {path}: {error}")


if __name__ == "__main__":
    main()
