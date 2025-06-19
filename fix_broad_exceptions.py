#!/usr/bin/env python3
"""Fix broad exception handlers with more specific ones."""

import re
from pathlib import Path
from typing import Dict, List, Tuple

# Map common operations to specific exceptions
EXCEPTION_MAPPINGS = {
    # File operations
    "open(": ["FileNotFoundError", "PermissionError", "OSError"],
    "Path(": ["ValueError", "OSError"],
    ".read()": ["IOError", "OSError"],
    ".write()": ["IOError", "OSError", "PermissionError"],
    "os.": ["OSError", "FileNotFoundError"],
    # Network operations
    "requests.": ["requests.RequestException", "ConnectionError", "TimeoutError"],
    "socket.": ["socket.error", "ConnectionError", "TimeoutError"],
    "urllib": ["urllib.error.URLError", "TimeoutError"],
    # AWS/S3 operations
    "boto3": ["botocore.exceptions.ClientError", "botocore.exceptions.BotoCoreError"],
    "s3.": [
        "botocore.exceptions.ClientError",
        "botocore.exceptions.NoCredentialsError",
    ],
    # Data processing
    "json.": ["json.JSONDecodeError", "ValueError"],
    "int(": ["ValueError", "TypeError"],
    "float(": ["ValueError", "TypeError"],
    "parse": ["ValueError", "TypeError"],
    # PyQt operations
    "QWidget": ["RuntimeError", "AttributeError"],
    "signal": ["RuntimeError", "TypeError"],
    "slot": ["RuntimeError", "TypeError"],
    ".setText": ["RuntimeError", "AttributeError"],
    ".setEnabled": ["RuntimeError", "AttributeError"],
    # Subprocess
    "subprocess.": [
        "subprocess.CalledProcessError",
        "subprocess.TimeoutExpired",
        "OSError",
    ],
    "Popen": ["subprocess.CalledProcessError", "OSError"],
    # Image processing
    "Image.": ["PIL.UnidentifiedImageError", "ValueError", "IOError"],
    "PIL.": ["PIL.UnidentifiedImageError", "ValueError", "IOError"],
    # Numpy/scientific
    "numpy": ["ValueError", "IndexError", "TypeError"],
    "netCDF4": ["ValueError", "IOError", "KeyError"],
}


def analyze_try_block(try_block: str) -> List[str]:
    """Analyze a try block to determine appropriate exceptions."""
    suggested_exceptions = set()

    for pattern, exceptions in EXCEPTION_MAPPINGS.items():
        if pattern in try_block:
            suggested_exceptions.update(exceptions)

    # If no specific patterns found, suggest common ones
    if not suggested_exceptions:
        suggested_exceptions = {"ValueError", "RuntimeError", "KeyError"}

    return sorted(list(suggested_exceptions))


def fix_broad_exceptions_in_file(filepath: Path) -> int:
    """Fix broad exception handlers in a single file."""
    if not filepath.exists():
        return 0

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content
        fixes_made = 0

        # Pattern to find except Exception blocks
        pattern = r"(\s*)except\s+Exception(\s+as\s+\w+)?:\s*\n((?:\1\s+.*\n)*)"

        def replace_exception(match):
            nonlocal fixes_made
            indent = match.group(1)
            as_clause = match.group(2) or ""
            block = match.group(3)

            # Find the corresponding try block
            try_pos = content.rfind("try:", 0, match.start())
            if try_pos == -1:
                return match.group(0)

            # Extract try block content
            try_block_start = try_pos
            try_block_end = match.start()
            try_block = content[try_block_start:try_block_end]

            # Analyze and suggest exceptions
            suggested = analyze_try_block(try_block)

            # Check if it's logging the exception
            has_logging = any(
                word in block
                for word in [
                    "LOGGER.exception",
                    "logger.exception",
                    "LOGGER.error",
                    "logger.error",
                    "exc_info=True",
                ]
            )

            if not has_logging and as_clause:
                # Add proper logging
                var_name = as_clause.strip().split()[-1]
                new_block = f"{indent}    LOGGER.exception('Error occurred: %s', {var_name})\n{block}"
                block = new_block

            # For now, keep Exception but add a comment about what should be caught
            if len(suggested) > 0:
                comment = f"{indent}# TODO: Replace with specific exceptions: {', '.join(suggested[:3])}\n"
                fixes_made += 1
                return f"{comment}{indent}except Exception{as_clause}:\n{block}"
            else:
                return match.group(0)

        # Apply replacements
        content = re.sub(pattern, replace_exception, content)

        # Fix bare except clauses
        bare_pattern = r"(\s*)except:\s*\n"
        content = re.sub(
            bare_pattern,
            r"\1# TODO: Replace with specific exceptions\n\1except Exception:\n",
            content,
        )
        if "except:" not in original_content and "except Exception:" in content:
            fixes_made += 1

        if content != original_content:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Fixed {fixes_made} exception handlers in {filepath}")
            return fixes_made

        return 0

    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return 0


def main():
    """Main function to fix broad exceptions in critical files."""
    print("Fixing broad exception handlers...\n")

    # Start with the most problematic files
    files_to_fix = [
        "goesvfi/pipeline/run_vfi.py",
        "goesvfi/integrity_check/remote/s3_store.py",
        "goesvfi/integrity_check/sample_processor.py",
        "goesvfi/integrity_check/goes_imagery.py",
        "goesvfi/integrity_check/render/netcdf.py",
    ]

    total_fixed = 0

    for filepath in files_to_fix:
        path = Path(filepath)
        if path.exists():
            fixed = fix_broad_exceptions_in_file(path)
            total_fixed += fixed

    print(f"\nTotal exception handlers improved: {total_fixed}")
    print("\nNote: Added TODO comments for manual review of exception types.")
    print(
        "Review the suggested exceptions and update as appropriate for your use case."
    )


if __name__ == "__main__":
    main()
