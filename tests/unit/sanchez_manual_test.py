"""
Sanchez Test Script

This script tests the Sanchez binary with different options and configurations
to diagnose issues with image processing.

Usage: python test_sanchez.py path/to/input/image.png
"""

import argparse
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

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
        ("Darwin", "x86_64"): bin_dir / "osx-x64" / "Sanchez",
        ("Darwin", "arm64"): bin_dir / "osx-x64" / "Sanchez",
        ("Windows", "AMD64"): bin_dir / "win-x64" / "Sanchez.exe",
    }

    key = (platform.system(), platform.machine())
    try:
        path = lookup[key]
    except KeyError:
        msg = f"Sanchez not packaged for {key}"
        raise RuntimeError(msg)

    if not path.exists():
        msg = f"Binary missing: {path}"
        raise RuntimeError(msg)

    return path


def test_basic_call(input_path, res_km=4) -> bool | None:
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
    logger.info("Running basic test: %s", " ".join(cmd))

    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=binary_dir)

        logger.info("Return code: %s", result.returncode)
        if result.stdout:
            logger.info("Stdout: %s", result.stdout)
        else:
            logger.info("No stdout output")

        if result.stderr:
            logger.info("Stderr: %s", result.stderr)
        else:
            logger.info("No stderr output")

        if temp_output.exists():
            logger.info("Output file created successfully: %s", temp_output)
            logger.info("Output file size: %s bytes", temp_output.stat().st_size)
            return True
        logger.error("Output file not created: %s", temp_output)
        return False
    except Exception:
        pass
    except Exception as e:
        logger.exception("Error running Sanchez: %s", e)
        return False
    finally:
        if temp_output.exists():
            os.remove(temp_output)


def test_with_verbose(input_path, res_km=4) -> bool | None:
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
    logger.info("Running verbose test: %s", " ".join(cmd))

    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=binary_dir)

        logger.info("Return code: %s", result.returncode)
        if result.stdout:
            logger.info("Stdout: %s", result.stdout)
        else:
            logger.info("No stdout output")

        if result.stderr:
            logger.info("Stderr: %s", result.stderr)
        else:
            logger.info("No stderr output")

        if temp_output.exists():
            logger.info("Output file created successfully: %s", temp_output)
            logger.info("Output file size: %s bytes", temp_output.stat().st_size)
            return True
        logger.error("Output file not created: %s", temp_output)
        return False
    except Exception:
        pass
    except Exception as e:
        logger.exception("Error running Sanchez: %s", e)
        return False
    finally:
        if temp_output.exists():
            os.remove(temp_output)


def test_with_v_flag(input_path, res_km=4) -> bool | None:
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
    logger.info("Running -v test: %s", " ".join(cmd))

    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=binary_dir)

        logger.info("Return code: %s", result.returncode)
        if result.stdout:
            logger.info("Stdout: %s", result.stdout)
        else:
            logger.info("No stdout output")

        if result.stderr:
            logger.info("Stderr: %s", result.stderr)
        else:
            logger.info("No stderr output")

        if temp_output.exists():
            logger.info("Output file created successfully: %s", temp_output)
            logger.info("Output file size: %s bytes", temp_output.stat().st_size)
            return True
        logger.error("Output file not created: %s", temp_output)
        return False
    except Exception:
        pass
    except Exception as e:
        logger.exception("Error running Sanchez: %s", e)
        return False
    finally:
        if temp_output.exists():
            os.remove(temp_output)


def test_with_renamed_input(input_path, res_km=4) -> bool | None:
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
    logger.info("Running renamed input test: %s", " ".join(cmd))

    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=binary_dir)

        logger.info("Return code: %s", result.returncode)
        if result.stdout:
            logger.info("Stdout: %s", result.stdout)
        else:
            logger.info("No stdout output")

        if result.stderr:
            logger.info("Stderr: %s", result.stderr)
        else:
            logger.info("No stderr output")

        if temp_output.exists():
            logger.info("Output file created successfully: %s", temp_output)
            logger.info("Output file size: %s bytes", temp_output.stat().st_size)
            return True
        logger.error("Output file not created: %s", temp_output)
        return False
    except Exception:
        pass
    except Exception as e:
        logger.exception("Error running Sanchez: %s", e)
        return False
    finally:
        if temp_input.exists():
            os.remove(temp_input)
        if temp_output.exists():
            os.remove(temp_output)


def test_sanchez_help() -> bool | None:
    """Test Sanchez help command to check available options."""
    bin_path = get_sanchez_binary()
    binary_dir = bin_path.parent

    cmd = [str(bin_path), "--help"]
    logger.info("Running help command: %s", " ".join(cmd))

    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=binary_dir)

        logger.info("Return code: %s", result.returncode)
        if result.stdout:
            logger.info("Help output: %s", result.stdout)
        else:
            logger.info("No stdout output from help command")

        if result.stderr:
            logger.info("Stderr from help: %s", result.stderr)
        else:
            logger.info("No stderr output from help command")

        return True
    except Exception as e:
        logger.exception("Error running Sanchez help: %s", e)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Test Sanchez binary with different options")
    parser.add_argument("input_file", help="Path to input image file to test with Sanchez")
    parser.add_argument("--res", type=int, default=4, help="Resolution in km (default: 4)")

    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        logger.error("Input file does not exist: %s", args.input_file)
        return 1

    logger.info("=== Testing Sanchez Binary ===")
    logger.info("Input file: %s", args.input_file)

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
    logger.info("Basic test: %s", "SUCCESS" if basic_result else "FAILED")
    logger.info("Verbose test: %s", "SUCCESS" if verbose_result else "FAILED")
    logger.info("v-flag test: %s", "SUCCESS" if v_flag_result else "FAILED")
    logger.info("Renamed input test: %s", "SUCCESS" if renamed_result else "FAILED")

    return 0


if __name__ == "__main__":
    sys.exit(main())
