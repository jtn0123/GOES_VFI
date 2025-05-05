#!/usr/bin/env python
"""
Script to run only the fixed integration tests for GOES-VFI.
"""

import sys
import pathlib
import subprocess

if __name__ == "__main__":
    python_executable = sys.executable
    
    # Only run tests that are known to work
    cmd = [
        python_executable, "-m", "pytest",
        # Integration tests that are fixed
        "tests/integration/test_pipeline.py::test_basic_interpolation",
    ]
    
    print(f"Running fixed integration tests with: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    sys.exit(result.returncode)