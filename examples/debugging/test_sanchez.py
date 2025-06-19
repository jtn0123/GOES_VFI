"""
Sanchez Test Script

This script tests the Sanchez binary with different options and configurations
to diagnose issues with image processing.

Usage: python test_sanchez.py path / to / input / image.png
"""

import argparse
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Configure logging
logging.basicConfig(
level=logging.INFO,
format="%(asctime)s - %(levelname)s - %(message)s",
handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("sanchez_test")


# Path to Sanchez binary
def get_sanchez_binary():
    """Get the path to the Sanchez binary based on OS and architecture."""
import platform

bin_dir = Path(__file__).parent / "goesvfi" / "sanchez" / "bin"

lookup = {
("Darwin", "x86_64"): bin_dir / "osx - x64" / "Sanchez",
("Darwin", "arm64"): bin_dir / "osx - x64" / "Sanchez",
("Windows", "AMD64"): bin_dir / "win - x64" / "Sanchez.exe",
}

key = (platform.system(), platform.machine())
try:
     path = lookup[key]
except KeyError:
     pass
raise RuntimeError(f"Sanchez not packaged for {key}")

if not path.exists():
     pass
raise RuntimeError(f"Binary missing: {path}")

return path


def test_basic_call(input_path, res_km=4):
    """Basic test of Sanchez with default options."""
bin_path = get_sanchez_binary()
binary_dir = bin_path.parent
temp_output = Path(tempfile.gettempdir()) / "sanchez_test_output.png"

cmd = [
str(bin_path),
"-s",
str(input_path),
"-o",
str(temp_output),
"-r",
str(res_km),
]
logger.info(f"Running basic test: {' '.join(cmd)}")

try:
     result = subprocess.run(
cmd, check=False, capture_output=True, text=True, cwd=binary_dir
)

logger.info(f"Return code: {result.returncode}")
if result.stdout:
     pass
logger.info(f"Stdout: {result.stdout}")
else:
     logger.info("No stdout output")

if result.stderr:
     pass
logger.info(f"Stderr: {result.stderr}")
else:
     logger.info("No stderr output")

if temp_output.exists():
     pass
logger.info(f"Output file created successfully: {temp_output}")
logger.info(f"Output file size: {temp_output.stat().st_size} bytes")
return True
else:
     logger.error(f"Output file not created: {temp_output}")
return False
except Exception as e:
     pass
logger.error(f"Error running Sanchez: {e}")
return False
finally:
     if temp_output.exists():
         pass
     pass
os.remove(temp_output)


def test_with_verbose(input_path, res_km=4):
    """Test Sanchez with verbose flag."""
bin_path = get_sanchez_binary()
binary_dir = bin_path.parent
temp_output = Path(tempfile.gettempdir()) / "sanchez_test_verbose_output.png"

cmd = [
str(bin_path),
"-s",
str(input_path),
"-o",
str(temp_output),
"-r",
str(res_km),
"--verbose",
]
logger.info(f"Running verbose test: {' '.join(cmd)}")

try:
     result = subprocess.run(
cmd, check=False, capture_output=True, text=True, cwd=binary_dir
)

logger.info(f"Return code: {result.returncode}")
if result.stdout:
     pass
logger.info(f"Stdout: {result.stdout}")
else:
     logger.info("No stdout output")

if result.stderr:
     pass
logger.info(f"Stderr: {result.stderr}")
else:
     logger.info("No stderr output")

if temp_output.exists():
     pass
logger.info(f"Output file created successfully: {temp_output}")
logger.info(f"Output file size: {temp_output.stat().st_size} bytes")
return True
else:
     logger.error(f"Output file not created: {temp_output}")
return False
except Exception as e:
     pass
logger.error(f"Error running Sanchez: {e}")
return False
finally:
     if temp_output.exists():
         pass
     pass
os.remove(temp_output)


def test_with_v_flag(input_path, res_km=4):
    """Test Sanchez with -v flag."""
bin_path = get_sanchez_binary()
binary_dir = bin_path.parent
temp_output = Path(tempfile.gettempdir()) / "sanchez_test_v_output.png"

cmd = [
str(bin_path),
"-s",
str(input_path),
"-o",
str(temp_output),
"-r",
str(res_km),
"-v",
]
logger.info(f"Running -v test: {' '.join(cmd)}")

try:
     result = subprocess.run(
cmd, check=False, capture_output=True, text=True, cwd=binary_dir
)

logger.info(f"Return code: {result.returncode}")
if result.stdout:
     pass
logger.info(f"Stdout: {result.stdout}")
else:
     logger.info("No stdout output")

if result.stderr:
     pass
logger.info(f"Stderr: {result.stderr}")
else:
     logger.info("No stderr output")

if temp_output.exists():
     pass
logger.info(f"Output file created successfully: {temp_output}")
logger.info(f"Output file size: {temp_output.stat().st_size} bytes")
return True
else:
     logger.error(f"Output file not created: {temp_output}")
return False
except Exception as e:
     pass
logger.error(f"Error running Sanchez: {e}")
return False
finally:
     if temp_output.exists():
         pass
     pass
os.remove(temp_output)


def test_with_renamed_input(input_path, res_km=4):
    """Test Sanchez with input renamed to .ir.png."""
bin_path = get_sanchez_binary()
binary_dir = bin_path.parent

# Create a renamed copy of the input file with .ir.png extension
temp_dir = Path(tempfile.gettempdir()) / "sanchez_test"
os.makedirs(temp_dir, exist_ok=True)

input_file = Path(input_path)
temp_input = temp_dir / f"{input_file.stem}.ir.png"
temp_output = temp_dir / f"{input_file.stem}.output.png"

shutil.copy2(input_path, temp_input)

cmd = [
str(bin_path),
"-s",
str(temp_input),
"-o",
str(temp_output),
"-r",
str(res_km),
]
logger.info(f"Running renamed input test: {' '.join(cmd)}")

try:
     result = subprocess.run(
cmd, check=False, capture_output=True, text=True, cwd=binary_dir
)

logger.info(f"Return code: {result.returncode}")
if result.stdout:
     pass
logger.info(f"Stdout: {result.stdout}")
else:
     logger.info("No stdout output")

if result.stderr:
     pass
logger.info(f"Stderr: {result.stderr}")
else:
     logger.info("No stderr output")

if temp_output.exists():
     pass
logger.info(f"Output file created successfully: {temp_output}")
logger.info(f"Output file size: {temp_output.stat().st_size} bytes")
return True
else:
     logger.error(f"Output file not created: {temp_output}")
return False
except Exception as e:
     pass
logger.error(f"Error running Sanchez: {e}")
return False
finally:
     if temp_input.exists():
         pass
     pass
os.remove(temp_input)
if temp_output.exists():
     pass
os.remove(temp_output)


def test_sanchez_help():
    """Test Sanchez help command to check available options."""
bin_path = get_sanchez_binary()
binary_dir = bin_path.parent

cmd = [str(bin_path), "--help"]
logger.info(f"Running help command: {' '.join(cmd)}")

try:
     result = subprocess.run(
cmd, check=False, capture_output=True, text=True, cwd=binary_dir
)

logger.info(f"Return code: {result.returncode}")
if result.stdout:
     pass
logger.info(f"Help output: {result.stdout}")
else:
     logger.info("No stdout output from help command")

if result.stderr:
     pass
logger.info(f"Stderr from help: {result.stderr}")
else:
     logger.info("No stderr output from help command")

return True
except Exception as e:
     pass
logger.error(f"Error running Sanchez help: {e}")
return False


def main():
    parser = argparse.ArgumentParser(
description="Test Sanchez binary with different options"
)
parser.add_argument(
"input_file", help="Path to input image file to test with Sanchez"
)
parser.add_argument(
"--res", type=int, default=4, help="Resolution in km (default: 4)"
)

args = parser.parse_args()

if not os.path.exists(args.input_file):
     pass
logger.error(f"Input file does not exist: {args.input_file}")
return 1

logger.info("=== Testing Sanchez Binary ===")
logger.info(f"Input file: {args.input_file}")

# Try to get help info first
logger.info("\n=== Testing help command ===")
test_sanchez_help()

# Test basic call
logger.info("\n=== Testing basic call ===")
basic_result = test_basic_call(args.input_file, args.res)

# Test with verbose flag
logger.info("\n=== Testing with --verbose flag ===")
verbose_result = test_with_verbose(args.input_file, args.res)

# Test with -v flag
logger.info("\n=== Testing with -v flag ===")
v_flag_result = test_with_v_flag(args.input_file, args.res)

# Test with renamed input
logger.info("\n=== Testing with renamed input (.ir.png) ===")
renamed_result = test_with_renamed_input(args.input_file, args.res)

# Summary
logger.info("\n=== Summary ===")
logger.info(f"Basic test: {'SUCCESS' if basic_result else 'FAILED'}")
logger.info(f"Verbose test: {'SUCCESS' if verbose_result else 'FAILED'}")
logger.info(f"v - flag test: {'SUCCESS' if v_flag_result else 'FAILED'}")
logger.info(f"Renamed input test: {'SUCCESS' if renamed_result else 'FAILED'}")

return 0


if __name__ == "__main__":
    pass
sys.exit(main())
