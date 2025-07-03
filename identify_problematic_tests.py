#!/usr/bin/env python3
"""Identify problematic test files that cause hangs or failures."""

from concurrent.futures import ThreadPoolExecutor, as_completed
import glob
import subprocess
import time


def test_single_file(test_file: str, timeout: int = 10) -> dict:
    """Test a single test file with timeout.

    Args:
        test_file: Path to test file
        timeout: Timeout in seconds

    Returns:
        Dictionary with test results
    """
    start_time = time.time()

    try:
        # Try to run pytest on the single file using virtual environment
        venv_python = ".venv/bin/python"
        result = subprocess.run(
            [venv_python, "-m", "pytest", test_file, "-v", "--tb=no"],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=".",
            check=False,
        )

        duration = time.time() - start_time

        if result.returncode == 0:
            return {
                "file": test_file,
                "status": "PASS",
                "duration": duration,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        return {
            "file": test_file,
            "status": "FAIL",
            "duration": duration,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }

    except subprocess.TimeoutExpired:
        return {"file": test_file, "status": "TIMEOUT", "duration": timeout}
    except Exception as e:
        return {"file": test_file, "status": "ERROR", "error": str(e)}


def main() -> None:
    """Main function to test all files."""
    # Find all test files
    test_files = []
    test_files.extend(glob.glob("tests/**/test_*.py", recursive=True))
    test_files.extend(glob.glob("test_*.py"))

    # Remove duplicates and sort
    test_files = sorted(set(test_files))

    results = []
    problematic_files = []
    completed_count = 0

    # Use ThreadPoolExecutor for parallel testing
    with ThreadPoolExecutor(max_workers=4) as executor:
        # Submit all test jobs
        future_to_file = {executor.submit(test_single_file, test_file, 15): test_file for test_file in test_files}

        # Process completed tests as they finish
        for future in as_completed(future_to_file):
            test_file = future_to_file[future]
            completed_count += 1

            try:
                result = future.result()
                results.append(result)

                if result["status"] == "PASS" or result["status"] == "FAIL":
                    pass
                elif result["status"] == "TIMEOUT" or result["status"] == "ERROR":
                    problematic_files.append(test_file)

            except Exception as e:
                problematic_files.append(test_file)
                results.append({"file": test_file, "status": "ERROR", "error": str(e)})

    # Summary

    sum(1 for r in results if r["status"] == "PASS")
    sum(1 for r in results if r["status"] == "FAIL")
    sum(1 for r in results if r["status"] == "TIMEOUT")
    sum(1 for r in results if r["status"] == "ERROR")

    if problematic_files:
        for file in problematic_files:
            status = next(r["status"] for r in results if r["file"] == file)

        # Write problematic files to a file
        with open("problematic_tests.txt", "w", encoding="utf-8") as f:
            f.write("# Problematic test files that timeout or error\n")
            for file in problematic_files:
                status = next(r["status"] for r in results if r["file"] == file)
                f.write(f"{status}: {file}\n")

    else:
        pass


if __name__ == "__main__":
    main()
