#!/usr/bin/env python3
"""
Run mypy type checking on key files.

This script runs mypy checks on specified files or directories,
making it easier to verify type annotations.

Usage:
    ./run_mypy_checks.py [options]

Options:
    --all           Check all directories, not just core files
    --strict        Use strict mode for type checking
    --install-stubs Install all required type stubs (or --install)
"""

import os
import sys
import subprocess
from pathlib import Path

# Core files that should pass mypy checks
CORE_FILES = [
    "goesvfi/integrity_check/enhanced_imagery_tab.py",
    "goesvfi/integrity_check/sample_processor.py",
    "goesvfi/integrity_check/goes_imagery.py",
    "goesvfi/integrity_check/remote/s3_store.py",
]

# All files to check when --all flag is provided
ALL_DIRS = [
    "goesvfi/integrity_check",
    "goesvfi/gui_tabs",
    "goesvfi/pipeline",
    "goesvfi/utils",
]


def run_mypy(target_files, strict=False):
    """Run mypy on the specified target files."""
    cmd = ["python", "-m", "mypy", "--disable-error-code=import-untyped"]
    
    if strict:
        cmd.append("--strict")
        
    cmd.extend(target_files)
    print(f"Running: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Success! No type errors found.")
    else:
        print("❌ Type errors found:")
        print(result.stdout or result.stderr)
    
    return result.returncode


def install_type_stubs():
    """Install necessary type stubs."""
    print("Installing required type stubs...")

    stubs = [
        "types-requests",
        "types-Pillow",
        "types-aiofiles",
        "types-tqdm",
        "types-boto3",
    ]

    try:
        # Install mypy-extensions
        subprocess.run(["python", "-m", "pip", "install", "--upgrade", "mypy-extensions"],
                      check=True, capture_output=True)

        # Install type stubs
        cmd = ["python", "-m", "pip", "install", "--upgrade"] + stubs
        subprocess.run(cmd, check=True, capture_output=True)

        # Also run mypy's built-in install-types
        subprocess.run(["python", "-m", "mypy", "--install-types", "--non-interactive"],
                      check=True, capture_output=True)

        print("✅ Type stubs installed successfully.")
    except subprocess.SubprocessError as e:
        print(f"❌ Error installing type stubs: {e}")
        return False

    return True


def main():
    """Run mypy checks based on command line arguments."""
    # Check if Python executable is available in the environment
    try:
        subprocess.run(["python", "--version"],
                       check=True, capture_output=True)
    except (subprocess.SubprocessError, FileNotFoundError):
        print("Error: Python executable not found. Please activate your virtual environment.")
        print("   source venv-py313/bin/activate")
        return 1

    # Determine which files to check and mode
    check_all = "--all" in sys.argv
    strict_mode = "--strict" in sys.argv
    install_stubs = "--install-stubs" in sys.argv or "--install" in sys.argv

    if install_stubs:
        if not install_type_stubs():
            return 1

    if strict_mode:
        print("Running in strict mode...")

    if check_all:
        print("Checking all files...")
        return run_mypy(ALL_DIRS, strict=strict_mode)
    else:
        print("Checking core files...")
        return run_mypy(CORE_FILES, strict=strict_mode)


if __name__ == "__main__":
    sys.exit(main())