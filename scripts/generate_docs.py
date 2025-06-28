#!/usr/bin/env python3
"""Script to generate documentation for the GOES_VFI project."""

import argparse
from pathlib import Path
import subprocess
import sys


def main() -> None:
    """Main entry point for documentation generation."""
    parser = argparse.ArgumentParser(description="Generate GOES_VFI documentation")
    parser.add_argument("--build", action="store_true", help="Build the documentation")
    parser.add_argument(
        "--format",
        choices=["html", "pdf", "epub"],
        default="html",
        help="Output format (default: html)",
    )
    parser.add_argument(
        "--clean", action="store_true", help="Clean build directory before building"
    )

    args = parser.parse_args()

    # Find project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    docs_dir = project_root / "docs"

    if not docs_dir.exists():
        print(f"Error: Documentation directory not found at {docs_dir}")
        sys.exit(1)

    # Change to docs directory
    import os

    os.chdir(docs_dir)

    if args.clean:
        print("Cleaning build directory...")
        subprocess.run(["rm", "-rf", "_build"], check=False)

    if args.build:
        print(f"Building {args.format} documentation...")

        # Run sphinx-build
        cmd = [
            "sphinx-build",
            "-b",
            args.format,
            ".",  # source dir
            f"_build/{args.format}",  # output dir
        ]

        result = subprocess.run(cmd, check=False)
        if result.returncode == 0:
            print(f"Documentation built successfully in _build/{args.format}")
        else:
            print("Documentation build failed")
            sys.exit(1)
    else:
        print("No action specified. Use --build to build documentation.")


if __name__ == "__main__":
    main()
