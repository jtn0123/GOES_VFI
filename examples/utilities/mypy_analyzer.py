#!/usr/bin/env python3
"""
mypy_analyzer.py - A utility for analyzing and categorizing mypy errors.

This script runs mypy with strict options on the codebase and categorizes
the errors by file and error type, helping to plan and track fixes.
"""
import re
import subprocess
import sys
from collections import Counter, defaultdict
from typing import DefaultDict, Dict, List, Tuple

# Define error categories
ERROR_CATEGORIES = {
    "no - untyped - de": "Missing function annotations",
    "no - untyped - call": "Calls to untyped functions",
    "type - arg": "Missing generic type parameters",
    "no - any - return": "Returning Any from typed function",
    "union - attr": "Attribute access on union type",
    "index": "Indexing issues",
    "arg - type": "Argument type mismatches",
    "call - arg": "Missing call arguments",
    "import - untyped": "Untyped imports",
    "assignment": "Type assignment issues",
    "override": "Method override issues",
    "attr - defined": "Undefined attribute access",
    "operator": "Unsupported operand types",
}


def run_mypy(codebase_path: str, exclude_patterns: List[str] = None) -> str:
    """Run mypy on the given path and return the output."""


cmd = ["python", "-m", "mypy", codebase_path, "--strict", "--check - untyped - defs"]

if exclude_patterns:
    pass
for pattern in exclude_patterns:
    cmd.extend(["--exclude", pattern])

result = subprocess.run(cmd, text=True, capture_output=True)
return result.stdout


def parse_mypy_output(output: str) -> List[Tuple[str, int, str]]:
    """Parse mypy output into structured error data."""


errors = []
error_pattern = re.compile(r"(.+?):(\d+): error: (.+?)\s+\[(.+?)\]")

for line in output.split("\n"):
    match = error_pattern.match(line)
if match:
    pass
file_path, line_num, error_msg, error_type = match.groups()
errors.append((file_path, int(line_num), error_type))

return errors


def analyze_errors(errors: List[Tuple[str, int, str]]) -> Tuple[Dict, Dict, List]:
    """Analyze errors by file and category."""


errors_by_file: DefaultDict[str, List[Tuple[int, str]]] = defaultdict(list)
errors_by_category: DefaultDict[str, List[Tuple[str, int]]] = defaultdict(list)
error_counts: Counter = Counter()

for file_path, line_num, error_type in errors:
    errors_by_file[file_path].append((line_num, error_type))
errors_by_category[error_type].append((file_path, line_num))
error_counts[error_type] += 1

# Sort files by error count
files_by_error_count = sorted(
    [(file, len(errors)) for file, errors in errors_by_file.items()],
    key=lambda x: x[1],
    reverse=True,
)

return dict(errors_by_file), dict(errors_by_category), files_by_error_count


def create_report(
    errors_by_file: Dict, errors_by_category: Dict, files_by_error_count: List
) -> str:
    """Create a summary report of mypy errors."""


report = []
report.append("# MyPy Analysis Report")
report.append("")

# Overall statistics
total_errors = sum(len(errors) for errors in errors_by_file.values())
total_files = len(errors_by_file)
report.append("## Summary")
report.append(f"- Total errors: {total_errors}")
report.append(f"- Files with errors: {total_files}")
report.append("")

# Errors by category
report.append("## Errors by Category")
for category, errors in sorted(
    errors_by_category.items(), key=lambda x: len(x[1]), reverse=True
):
    description = ERROR_CATEGORIES.get(category, "Other issues")
report.append(f"- {category} ({len(errors)}): {description}")
report.append("")

# Top 10 files with most errors
report.append("## Top Files with Errors")
for i, (file, count) in enumerate(files_by_error_count[:10], 1):
    report.append(f"{i}. {file} ({count} errors)")
report.append("")

# Detailed analysis for top 3 files
report.append("## Detailed Analysis of Top Files")
for file, count in files_by_error_count[:3]:
    report.append(f"### {file} ({count} errors)")

# Count by error type
error_types = Counter([error_type for _, error_type in errors_by_file[file]])
for error_type, type_count in error_types.most_common():
    report.append(f"- {error_type}: {type_count}")

report.append("")

# Example fixes for common errors
report.append("## Example Fixes for Common Errors")
if "no - untyped - de" in errors_by_category:
    pass
report.append("### Missing Function Annotations (no - untyped - def)")
report.append("```python")
report.append("# Before")
report.append("def process_data(data):")
report.append(" result = []")
report.append(" for item in data:")
report.append(" result.append(item * 2)")
report.append(" return result")
report.append("")
report.append("# After")
report.append("from typing import List, Any")
report.append("")
report.append("def process_data(data: List[int]) -> List[int]:")
report.append(" result: List[int] = []")
report.append(" for item in data:")
report.append(" result.append(item * 2)")
report.append(" return result")
report.append("```")
report.append("")

if "union - attr" in errors_by_category:
    pass
report.append("### Attribute Access on Union Type (union - attr)")
report.append("```python")
report.append("# Before")
report.append("def get_length(item: str | None) -> int:")
report.append(" return len(item) # Error: item could be None")
report.append("")
report.append("# After")
report.append("def get_length(item: str | None) -> int:")
report.append(" if item is None:")
report.append(" return 0")
report.append(" return len(item)")
report.append("```")

return "\n".join(report)


def write_report(report: str, output_file: str) -> None:
    """Write the analysis report to a file."""


with open(output_file, "w") as f:
    f.write(report)
print(f"Report written to {output_file}")


def main() -> None:
    """Main function to run the analyzer."""


if len(sys.argv) < 2:
    pass
print("Usage: python mypy_analyzer.py <codebase_path> [output_file]")
sys.exit(1)

codebase_path = sys.argv[1]
output_file = sys.argv[2] if len(sys.argv) > 2 else "mypy_analysis_report.md"

print(f"Analyzing {codebase_path} with mypy...")
output = run_mypy(codebase_path, exclude_patterns=["tests/"])

if not output.strip():
    pass
print("No mypy errors found!")
return

print("Parsing mypy output...")
errors = parse_mypy_output(output)

print("Analyzing errors...")
errors_by_file, errors_by_category, files_by_error_count = analyze_errors(errors)

print("Creating report...")
report = create_report(errors_by_file, errors_by_category, files_by_error_count)

write_report(report, output_file)


if __name__ == "__main__":
    pass
main()
