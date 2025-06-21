#!/usr/bin/env python3
"""
Run all tests except GUI tests to avoid segmentation faults.
"""

import os
import subprocess
import sys

if __name__ == "__main__":
    # Get the path to Python in the current virtual environment
    python_executable = sys.executable

    # Run without a display server
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    # Use pytest directly to exclude GUI tests
    cmd = [python_executable, "-m", "pytest", "tests", "--ignore=tests/gui"]

    result = subprocess.run(cmd, check=False)
    sys.exit(result.returncode)
