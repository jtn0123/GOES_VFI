#!/usr/bin/env python3
"""Analyze files for syntax and formatting issues."""

import ast
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class FileAnalyzer:
    """Analyze Python files for various issues."""

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.content = ""
        self.issues: Dict[str, List[str]] = {
            "syntax": [],
            "formatting": [],
            "imports": [],
            "indentation": [],
            "other": [],
        }

    def analyze(self) -> Dict[str, List[str]]:
        """Run all analysis checks."""
        if not self.file_path.exists():
            self.issues["other"].append("File not found")
            return self.issues

        # Read file content
        try:
            self.content = self.file_path.read_text(encoding="utf-8")
        except Exception as e:
            self.issues["other"].append(f"Cannot read file: {e}")
            return self.issues

        # Check various issues
        self._check_syntax()
        self._check_formatting()
        self._check_imports()
        self._check_indentation()

        return self.issues

    def _check_syntax(self) -> None:
        """Check for Python syntax errors."""
        try:
            ast.parse(self.content)
        except SyntaxError as e:
            self.issues["syntax"].append(f"Line {e.lineno}: {e.msg}")
            # Try to identify specific syntax patterns
            lines = self.content.split("\n")
            if e.lineno and e.lineno <= len(lines):
                problem_line = lines[e.lineno - 1]

                # Check for common syntax issues
                if "#!/usr / bin / env python3" in problem_line:
                    self.issues["syntax"].append("Shebang line has extra spaces")
                elif problem_line.strip().endswith(":") and e.lineno < len(lines):
                    next_line = lines[e.lineno] if e.lineno < len(lines) else ""
                    if next_line.strip() and not next_line.startswith((" ", "\t")):
                        self.issues["syntax"].append("Missing indentation after colon")

    def _check_formatting(self) -> None:
        """Check for formatting issues."""
        lines = self.content.split("\n")

        for i, line in enumerate(lines, 1):
            # Check for unusual spacing in imports
            if line.strip().startswith(("from ", "import ")):
                if "  " in line or "\t" in line:
                    self.issues["formatting"].append(
                        f"Line {i}: Unusual spacing in import"
                    )

            # Check for mixed indentation
            if line and line[0] in " \t":
                indent = line[: len(line) - len(line.lstrip())]
                if " " in indent and "\t" in indent:
                    self.issues["formatting"].append(f"Line {i}: Mixed tabs and spaces")

    def _check_imports(self) -> None:
        """Check for import issues."""
        lines = self.content.split("\n")

        for i, line in enumerate(lines, 1):
            # Check for malformed imports
            if "from" in line and "import" in line and "(" in line:
                # Multi-line import check
                if line.count("(") != line.count(")"):
                    self.issues["imports"].append(
                        f"Line {i}: Unclosed multi-line import"
                    )

    def _check_indentation(self) -> None:
        """Check for indentation issues."""
        lines = self.content.split("\n")
        indent_stack = [0]

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # Calculate indentation
            indent = len(line) - len(line.lstrip())

            # Check for unusual indentation
            if indent % 4 != 0 and "\t" not in line[:indent]:
                self.issues["indentation"].append(
                    f"Line {i}: Non-standard indentation ({indent} spaces)"
                )


def analyze_file(file_path: str) -> Tuple[bool, Dict[str, List[str]]]:
    """Analyze a single file and return status and issues."""
    analyzer = FileAnalyzer(file_path)
    issues = analyzer.analyze()

    # Determine if file is broken
    is_broken = bool(issues["syntax"])

    return is_broken, issues


def format_issues(file_path: str, is_broken: bool, issues: Dict[str, List[str]]) -> str:
    """Format issues for markdown output."""
    status = (
        "🔴 Broken" if is_broken else "🟡 Damaged" if any(issues.values()) else "🟢 OK"
    )

    output = [f"\n### {file_path} - {status}"]

    for category, issue_list in issues.items():
        if issue_list:
            output.append(f"\n**{category.title()} Issues:**")
            for issue in issue_list:
                output.append(f"- {issue}")

    if not any(issues.values()):
        output.append("\nNo issues detected.")

    return "\n".join(output)


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python file_analyzer.py <file_path> [file_path2 ...]")
        sys.exit(1)

    results = []
    broken_count = 0
    damaged_count = 0
    ok_count = 0

    for file_path in sys.argv[1:]:
        if Path(file_path).suffix == ".py":
            is_broken, issues = analyze_file(file_path)
            results.append(format_issues(file_path, is_broken, issues))

            if is_broken:
                broken_count += 1
            elif any(issues.values()):
                damaged_count += 1
            else:
                ok_count += 1

    # Print results
    print("\n" + "=" * 60)
    print("FILE ANALYSIS RESULTS")
    print("=" * 60)

    for result in results:
        print(result)

    print("\n" + "=" * 60)
    print(f"Summary: {broken_count} broken, {damaged_count} damaged, {ok_count} ok")
    print("=" * 60)


if __name__ == "__main__":
    main()
