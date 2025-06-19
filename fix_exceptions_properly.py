#!/usr/bin/env python3
"""Replace broad exception handlers with specific ones."""

import re
from pathlib import Path

# Mapping of specific operations to appropriate exceptions
EXCEPTION_MAPPINGS = {
    # run_vfi.py specific mappings based on analysis
    "goesvfi/pipeline/run_vfi.py": {
        176: ["KeyError", "RuntimeError", "ValueError"],
        379: ["IOError", "OSError"],
        504: ["IOError", "PIL.UnidentifiedImageError", "ValueError"],
        563: ["OSError", "PermissionError"],
        571: ["subprocess.CalledProcessError", "IOError", "RuntimeError"],
        602: ["ValueError", "TypeError"],
        814: ["TypeError", "ValueError", "AttributeError"],
        1081: ["FileNotFoundError", "IOError", "OSError"],
        1229: ["OSError", "AttributeError"],
        1247: ["IOError", "OSError"],
        1367: ["FileNotFoundError", "IOError", "OSError"],
        1391: ["FileNotFoundError", "IOError", "OSError"],
        1429: ["IOError", "OSError"],
        1599: ["FileNotFoundError", "IOError", "OSError"],
        1639: ["FileNotFoundError", "IOError", "OSError", "RuntimeError"],
        1660: [
            "FileNotFoundError",
            "IOError",
            "OSError",
            "subprocess.CalledProcessError",
            "RuntimeError",
        ],
    },
    # s3_store.py specific mappings
    "goesvfi/integrity_check/remote/s3_store.py": {
        336: ["FileNotFoundError", "OSError", "PermissionError"],
        354: ["socket.gaierror", "socket.timeout", "ConnectionError"],
        756: ["OSError", "RuntimeError"],
        776: ["socket.gaierror", "socket.timeout", "socket.error"],
        782: ["socket.gaierror", "socket.timeout", "socket.error"],
        918: ["TypeError", "ValueError", "AttributeError"],
        973: ["TypeError", "ValueError", "AttributeError"],
        1257: ["TypeError", "ValueError", "botocore.exceptions.ClientError", "OSError"],
        1586: ["TypeError", "ValueError", "botocore.exceptions.ClientError", "OSError"],
        1763: ["TypeError", "ValueError", "KeyError", "AttributeError"],
        1842: ["TypeError", "ValueError", "OSError", "IOError"],
    },
    # Other files
    "goesvfi/integrity_check/sample_processor.py": {
        298: ["botocore.exceptions.ClientError", "KeyError", "RuntimeError"],
        340: ["botocore.exceptions.ClientError", "OSError", "IOError"],
        358: ["OSError", "ValueError", "RuntimeError"],
        396: ["KeyError", "RuntimeError", "ValueError"],
        728: ["FileNotFoundError", "IOError", "OSError", "PIL.UnidentifiedImageError"],
        811: ["KeyError", "RuntimeError", "ValueError"],
        880: ["OSError", "PermissionError", "RuntimeError"],
    },
    "goesvfi/integrity_check/goes_imagery.py": {
        297: ["ConnectionError", "requests.RequestException", "OSError"],
        382: ["KeyError", "RuntimeError", "ValueError"],
        414: ["botocore.exceptions.ClientError", "OSError"],
        482: ["KeyError", "RuntimeError", "ValueError"],
        514: ["FileNotFoundError", "OSError", "PermissionError"],
        545: ["FileNotFoundError", "OSError", "PermissionError"],
    },
}


def fix_exceptions_in_file(filepath: Path, line_mappings: dict) -> int:
    """Fix exceptions in a specific file based on line mappings."""
    if not filepath.exists():
        return 0

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    fixes_made = 0

    # Sort line numbers in reverse to avoid offset issues
    for line_num in sorted(line_mappings.keys(), reverse=True):
        exceptions = line_mappings[line_num]

        # Adjust for 0-based indexing
        idx = line_num - 1

        # Look for the except line near the TODO comment
        for offset in range(0, 5):  # Check up to 5 lines after TODO
            if idx + offset < len(lines):
                line = lines[idx + offset]

                if "except Exception" in line:
                    # Extract indentation and as clause
                    indent = len(line) - len(line.lstrip())
                    indent_str = " " * indent

                    as_match = re.search(r"except Exception(\s+as\s+\w+)?:", line)
                    if as_match:
                        as_clause = as_match.group(1) or ""

                        # Build new except line
                        if len(exceptions) == 1:
                            new_line = (
                                f"{indent_str}except {exceptions[0]}{as_clause}:\n"
                            )
                        else:
                            new_line = f"{indent_str}except ({', '.join(exceptions)}){as_clause}:\n"

                        # Replace the line
                        lines[idx + offset] = new_line
                        fixes_made += 1
                        break

    if fixes_made > 0:
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print(f"Fixed {fixes_made} exception handlers in {filepath}")

    return fixes_made


def main():
    """Fix exceptions in all mapped files."""
    total_fixed = 0

    for filepath, mappings in EXCEPTION_MAPPINGS.items():
        path = Path(filepath)
        fixed = fix_exceptions_in_file(path, mappings)
        total_fixed += fixed

    print(f"\nTotal exception handlers fixed: {total_fixed}")

    # Also need to add imports for specific exceptions
    print("\nAdding necessary imports...")
    add_imports()


def add_imports():
    """Add necessary imports for the new exception types."""
    import_additions = {
        "goesvfi/pipeline/run_vfi.py": [
            "import socket",
            "from PIL import UnidentifiedImageError",
        ],
        "goesvfi/integrity_check/remote/s3_store.py": [
            "import socket",
        ],
        "goesvfi/integrity_check/sample_processor.py": [
            "from PIL import UnidentifiedImageError",
        ],
        "goesvfi/integrity_check/goes_imagery.py": [
            "import socket",
        ],
    }

    for filepath, imports_to_add in import_additions.items():
        path = Path(filepath)
        if path.exists():
            with open(path, "r") as f:
                content = f.read()

            # Find the import section
            lines = content.split("\n")
            import_end = 0

            for i, line in enumerate(lines):
                if line.strip() and not line.startswith(("import ", "from ", "#")):
                    if i > 10:  # Past the initial docstring and imports
                        import_end = i
                        break

            # Check which imports are missing
            new_imports = []
            for imp in imports_to_add:
                if imp not in content:
                    new_imports.append(imp)

            if new_imports:
                # Insert the new imports
                for imp in reversed(new_imports):
                    lines.insert(import_end, imp)

                with open(path, "w") as f:
                    f.write("\n".join(lines))

                print(f"Added {len(new_imports)} imports to {filepath}")


if __name__ == "__main__":
    main()
