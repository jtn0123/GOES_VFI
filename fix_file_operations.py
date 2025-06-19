#!/usr/bin/env python3
"""Fix file operations to use context managers."""

import re
from pathlib import Path
from typing import List, Tuple


def fix_image_open_patterns(content: str) -> Tuple[str, int]:
    """Fix Image.open() calls to use context managers."""
    fixes_made = 0
    lines = content.split("\n")
    new_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Pattern 1: Direct assignment with Image.open
        # e.g., img = Image.open(path)
        match = re.match(r"^(\s*)([\w_]+)\s*=\s*Image\.open\((.*?)\)(.*)$", line)
        if match:
            indent = match.group(1)
            var_name = match.group(2)
            path_expr = match.group(3)
            rest = match.group(4)

            # Check if this is already in a with statement
            if i > 0 and "with" in lines[i - 1]:
                new_lines.append(line)
                i += 1
                continue

            # Look ahead to see how the variable is used
            usage_lines = []
            j = i + 1
            block_indent = len(indent)

            while j < len(lines) and (
                not lines[j].strip()
                or len(lines[j]) - len(lines[j].lstrip()) > block_indent
            ):
                if var_name in lines[j]:
                    usage_lines.append(j)
                j += 1

            if usage_lines:
                # Convert to context manager
                new_lines.append(f"{indent}with Image.open({path_expr}) as {var_name}:")

                # Indent the following lines that use this variable
                k = i + 1
                while k <= max(usage_lines + [i]):
                    if k < len(lines):
                        if lines[k].strip():
                            new_lines.append("    " + lines[k])
                        else:
                            new_lines.append(lines[k])
                    k += 1

                i = k
                fixes_made += 1
                continue

        # Pattern 2: Image.open used in array conversion
        # e.g., np.array(Image.open(path))
        if "np.array(Image.open(" in line or "array(Image.open(" in line:
            # Extract the components
            match = re.search(r"(\s*)(.*?)np\.array\(Image\.open\((.*?)\)\)(.*)", line)
            if not match:
                match = re.search(r"(\s*)(.*?)array\(Image\.open\((.*?)\)\)(.*)", line)

            if match:
                indent = match.group(1)
                prefix = match.group(2)
                path_expr = match.group(3)
                suffix = match.group(4)

                # Generate a temporary variable name
                temp_var = "_img_temp"

                # Create context manager version
                new_lines.append(f"{indent}with Image.open({path_expr}) as {temp_var}:")
                new_lines.append(f"{indent}    {prefix}np.array({temp_var}){suffix}")

                i += 1
                fixes_made += 1
                continue

        # Pattern 3: Simple Image.open().method() calls
        # e.g., Image.open(path).verify()
        if "Image.open(" in line and ").verify()" in line:
            match = re.search(r"(\s*)Image\.open\((.*?)\)\.verify\(\)", line)
            if match:
                indent = match.group(1)
                path_expr = match.group(2)

                new_lines.append(f"{indent}with Image.open({path_expr}) as _img:")
                new_lines.append(f"{indent}    _img.verify()")

                i += 1
                fixes_made += 1
                continue

        new_lines.append(line)
        i += 1

    return "\n".join(new_lines), fixes_made


def fix_open_patterns(content: str) -> Tuple[str, int]:
    """Fix regular open() calls to use context managers."""
    fixes_made = 0
    lines = content.split("\n")
    new_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Pattern: f = open(...) followed by f.close()
        match = re.match(r"^(\s*)([\w_]+)\s*=\s*open\((.*?)\)(.*)$", line)
        if match and "with" not in line:
            indent = match.group(1)
            var_name = match.group(2)
            open_args = match.group(3)
            rest = match.group(4)

            # Look for the corresponding close
            close_found = False
            close_line = -1

            for j in range(i + 1, min(i + 50, len(lines))):
                if f"{var_name}.close()" in lines[j]:
                    close_found = True
                    close_line = j
                    break

            if close_found:
                # Convert to context manager
                new_lines.append(f"{indent}with open({open_args}) as {var_name}:")

                # Indent the lines between open and close
                for j in range(i + 1, close_line):
                    if lines[j].strip():
                        new_lines.append("    " + lines[j])
                    else:
                        new_lines.append(lines[j])

                # Skip the close line
                i = close_line + 1
                fixes_made += 1
                continue

        new_lines.append(line)
        i += 1

    return "\n".join(new_lines), fixes_made


def fix_file_in_path(filepath: Path) -> int:
    """Fix file operations in a single file."""
    if not filepath.exists():
        return 0

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content
        total_fixes = 0

        # Fix Image.open patterns
        content, image_fixes = fix_image_open_patterns(content)
        total_fixes += image_fixes

        # Fix regular open patterns
        content, open_fixes = fix_open_patterns(content)
        total_fixes += open_fixes

        if content != original_content:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Fixed {total_fixes} file operations in {filepath}")

        return total_fixes

    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return 0


def main():
    """Main function to fix file operations."""
    print("Fixing file operations to use context managers...\n")

    # Files with the most issues
    files_to_fix = [
        "goesvfi/run_vfi.py",
        "goesvfi/pipeline/run_vfi.py",
        "goesvfi/integrity_check/sample_processor.py",
        "goesvfi/gui_tabs/main_tab.py",
        "goesvfi/pipeline/sanchez_processor.py",
        "goesvfi/integrity_check/render/netcdf.py",
        "goesvfi/pipeline/interpolate.py",
    ]

    total_fixed = 0

    for filepath in files_to_fix:
        path = Path(filepath)
        if path.exists():
            fixed = fix_file_in_path(path)
            total_fixed += fixed

    print(f"\nTotal file operations fixed: {total_fixed}")
    print("\nNote: Review the changes to ensure the logic remains correct.")
    print("Some complex cases may need manual adjustment.")


if __name__ == "__main__":
    main()
