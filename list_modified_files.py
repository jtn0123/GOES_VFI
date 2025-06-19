#!/usr/bin/env python3
"""List all modified files compared to the reference repository."""

import subprocess
from pathlib import Path


def get_modified_files():
    """Get list of modified files from git status."""
    result = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True
    )

    modified_files = []
    for line in result.stdout.strip().split("\n"):
        if line and line.strip():
            parts = line.strip().split(maxsplit=1)
            if len(parts) > 1:
                status = parts[0]
                filename = parts[1].strip('"')
                # Only include modified files (M flag), not new files (??)
                if "M" in status:
                    modified_files.append(filename)

    return sorted(modified_files)


def main():
    modified_files = get_modified_files()

    print(f"Found {len(modified_files)} modified files:\n")

    # Group by directory
    by_dir = {}
    for file_path in modified_files:
        dir_path = str(Path(file_path).parent)
        if dir_path not in by_dir:
            by_dir[dir_path] = []
        by_dir[dir_path].append(file_path)

    # Print grouped
    for dir_path in sorted(by_dir.keys()):
        files = by_dir[dir_path]
        print(f"\n{dir_path}/ ({len(files)} files):")
        for file_path in files:
            print(f"  - {Path(file_path).name}")


if __name__ == "__main__":
    main()
