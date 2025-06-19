#!/usr/bin/env python3
"""Fix subprocess management issues."""

import re
from pathlib import Path
from typing import Tuple


def add_subprocess_timeout(content: str) -> Tuple[str, int]:
    """Add timeouts to subprocess.run calls."""
    fixes_made = 0

    # Pattern for subprocess.run without timeout
    pattern = r"(subprocess\.run\([^)]+)(\))"

    def add_timeout(match):
        nonlocal fixes_made
        args = match.group(1)
        close_paren = match.group(2)

        # Check if timeout already exists
        if "timeout=" in args:
            return match.group(0)

        # Add timeout parameter
        fixes_made += 1
        # Determine appropriate timeout based on context
        if "ffmpeg" in args.lower() or "encode" in args.lower():
            timeout_val = 600  # 10 minutes for encoding
        elif "rife" in args.lower():
            timeout_val = 300  # 5 minutes for RIFE
        else:
            timeout_val = 120  # 2 minutes default

        return f"{args}, timeout={timeout_val}{close_paren}"

    content = re.sub(pattern, add_timeout, content)
    return content, fixes_made


def fix_popen_cleanup(content: str) -> Tuple[str, int]:
    """Add proper cleanup for Popen calls."""
    fixes_made = 0
    lines = content.split("\n")
    new_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Look for Popen assignments
        if "subprocess.Popen" in line and "=" in line and "with" not in line:
            # Extract variable name and indentation
            match = re.match(r"^(\s*)([\w_]+)\s*=\s*subprocess\.Popen", line)
            if match:
                indent = match.group(1)
                var_name = match.group(2)

                # Look for the end of the Popen call
                popen_lines = [line]
                j = i + 1
                paren_count = line.count("(") - line.count(")")

                while j < len(lines) and paren_count > 0:
                    popen_lines.append(lines[j])
                    paren_count += lines[j].count("(") - lines[j].count(")")
                    j += 1

                # Check if there's already a try/finally for cleanup
                has_cleanup = False
                for k in range(j, min(j + 20, len(lines))):
                    if "finally:" in lines[k] and var_name in lines[k : k + 5]:
                        has_cleanup = True
                        break

                if not has_cleanup:
                    # Add try/finally for cleanup
                    new_lines.append(
                        f"{indent}# TODO: Consider using 'with' statement for automatic cleanup"
                    )
                    new_lines.append(f"{indent}{var_name} = None")
                    new_lines.append(f"{indent}try:")
                    for pline in popen_lines:
                        new_lines.append(f"    {pline}")

                    # Skip past the original Popen lines
                    i = j
                    fixes_made += 1

                    # Add cleanup in finally block at appropriate location
                    cleanup_added = False
                    while i < len(lines):
                        line = lines[i]

                        # Look for end of the code block that uses this process
                        if (
                            line.strip()
                            and not line.startswith(indent + " ")
                            and not line.startswith(indent + "\t")
                        ):
                            # Insert finally block before this line
                            new_lines.append(f"{indent}finally:")
                            new_lines.append(f"{indent}    if {var_name}:")
                            new_lines.append(f"{indent}        try:")
                            new_lines.append(
                                f"{indent}            {var_name}.terminate()"
                            )
                            new_lines.append(
                                f"{indent}            {var_name}.wait(timeout=5)"
                            )
                            new_lines.append(
                                f"{indent}        except subprocess.TimeoutExpired:"
                            )
                            new_lines.append(f"{indent}            {var_name}.kill()")
                            new_lines.append(f"{indent}        except Exception:")
                            new_lines.append(f"{indent}            pass")
                            cleanup_added = True
                            break

                        new_lines.append(line)
                        i += 1

                    if cleanup_added:
                        continue
                else:
                    # Already has cleanup, just copy the lines
                    new_lines.extend(popen_lines)
                    i = j
                    continue

        new_lines.append(line)
        i += 1

    return "\n".join(new_lines), fixes_made


def fix_file(filepath: Path) -> int:
    """Fix subprocess issues in a single file."""
    if not filepath.exists():
        return 0

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content
        total_fixes = 0

        # Add timeouts to subprocess.run
        content, timeout_fixes = add_subprocess_timeout(content)
        total_fixes += timeout_fixes

        # Fix Popen cleanup
        content, popen_fixes = fix_popen_cleanup(content)
        total_fixes += popen_fixes

        if content != original_content:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Fixed {total_fixes} subprocess issues in {filepath}")

        return total_fixes

    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return 0


def main():
    """Main function to fix subprocess issues."""
    print("Fixing subprocess management issues...\n")

    # Files with subprocess issues
    files_to_fix = [
        "goesvfi/pipeline/run_vfi.py",
        "goesvfi/pipeline/encode.py",
        "goesvfi/sanchez/runner.py",
        "goesvfi/pipeline/raw_encoder.py",
        "goesvfi/pipeline/interpolate.py",
    ]

    total_fixed = 0

    for filepath in files_to_fix:
        path = Path(filepath)
        if path.exists():
            fixed = fix_file(path)
            total_fixed += fixed

    print(f"\nTotal subprocess issues addressed: {total_fixed}")
    print(
        "\nNote: Review the changes and convert to 'with' statements where appropriate."
    )
    print("The TODO comments indicate where manual review is recommended.")


if __name__ == "__main__":
    main()
