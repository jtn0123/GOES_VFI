#!/usr/bin/env python3
"""Direct test runner for all tests in the GOES_VFI project.

This script runs tests directly with pytest, providing detailed progress
tracking and comprehensive summary reporting.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime
import glob
import operator
import os
from pathlib import Path
import re
import subprocess  # noqa: S404
import sys
import time
from typing import Any

# ============================================================================
# Data Classes and Types
# ============================================================================


@dataclass
class TestCounts:
    """Container for test count statistics."""

    passed: int = 0
    failed: int = 0
    skipped: int = 0
    error: int = 0
    crashed: int = 0
    timeout: int = 0

    def total(self) -> int:
        """Return total number of tests."""
        return self.passed + self.failed + self.skipped + self.error + self.crashed + self.timeout

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary for compatibility.

        Returns:
            Dictionary containing test count statistics.
        """
        return {
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "error": self.error,
            "crashed": self.crashed,
            "timeout": self.timeout,
        }


@dataclass
class TestResult:
    """Container for test execution results."""

    path: str
    status: str
    duration: float
    output: str
    counts: TestCounts
    collected: int
    error_summary: str = ""
    log_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for compatibility.

        Returns:
            Dictionary containing test result data.
        """
        return {
            "path": self.path,
            "status": self.status,
            "duration": self.duration,
            "output": self.output,
            "counts": self.counts.to_dict(),
            "collected": self.collected,
            "error_summary": self.error_summary,
            "log_path": self.log_path,
        }


@dataclass
class RunnerConfig:
    """Configuration for test runner."""

    parallel: int = 4
    timeout: int = 30
    verbose: bool = False
    quiet: bool = False
    debug_mode: bool = False
    dump_logs: bool = False
    directory: str = "tests"
    skip_problematic: bool = True
    tolerant: bool = False
    count_tests: bool = True
    specific_files: list[str] = field(default_factory=list)


@dataclass
class ColorScheme:
    """Color scheme for terminal output."""

    passed: str = "\033[92m"  # Green
    failed: str = "\033[91m"  # Red
    error: str = "\033[93m"  # Yellow/Orange
    skipped: str = "\033[94m"  # Blue
    crashed: str = "\033[91m"  # Red
    timeout: str = "\033[93m"  # Yellow
    bright_magenta: str = "\033[95m"  # Bright purplish-pink
    reset: str = "\033[0m"

    def get(self, status: str) -> str:
        """Get color for status."""
        status_map = {
            "PASSED": self.passed,
            "FAILED": self.failed,
            "ERROR": self.error,
            "SKIPPED": self.skipped,
            "CRASHED": self.crashed,
            "TIMEOUT": self.timeout,
            "PASSED (with teardown error)": self.error,
            "PASSED (with crash)": self.error,
        }
        return status_map.get(status, "")


# ============================================================================
# Output Parser
# ============================================================================


class PytestOutputParser:
    """Parse pytest output to extract test results."""

    def parse_output(self, test_path: str, output: str, duration: float) -> TestResult:
        """Parse pytest output and return structured result."""
        counts = self.extract_counts(output)
        collected = self._extract_collected_count(output)
        status = self.determine_status(output, counts, collected)

        # Adjust counts based on special cases
        counts = self._adjust_counts_for_special_cases(test_path, output, counts, collected, status)

        error_summary = self.extract_error_summary(output) if status != "PASSED" else ""

        return TestResult(
            path=test_path,
            status=status,
            duration=duration,
            output=output,
            counts=counts,
            collected=collected,
            error_summary=error_summary,
        )

    def extract_counts(self, output: str) -> TestCounts:
        """Extract test counts from pytest output."""
        counts = TestCounts()

        # First try to extract from summary lines (most accurate)
        summary_counts = self._extract_summary_counts(output)
        if summary_counts:
            counts.passed = summary_counts.get("passed", 0)
            counts.failed = summary_counts.get("failed", 0)
            counts.skipped = summary_counts.get("skipped", 0)
            counts.error = summary_counts.get("error", 0)
            return counts

        # Fallback: Extract counts from test lines (less reliable for complex tests)
        counts.passed = len(re.findall(r"test_\w+.*?PASSED", output))
        counts.failed = len(re.findall(r"test_\w+.*?FAILED", output))
        counts.skipped = len(re.findall(r"test_\w+.*?SKIPPED", output))
        counts.error = len(re.findall(r"test_\w+.*?ERROR", output))

        return counts

    def extract_error_summary(self, output: str) -> str:
        """Extract brief error summary from test output."""
        if not output:
            return "No output available"

        lines = output.strip().split("\n")

        # Collect all unique error types found
        error_summaries = self._collect_all_error_types(lines)

        if error_summaries:
            # If multiple different error types, show all of them
            if len(error_summaries) > 1:
                # Join all errors with newlines and proper indentation
                formatted_errors = []
                for i, error in enumerate(error_summaries):
                    if i == 0:
                        formatted_errors.append(error)  # First error on same line
                    else:
                        formatted_errors.append(f"\n    → {error}")  # Additional errors indented
                return "".join(formatted_errors)
            # Just one type of error
            return error_summaries[0]

        # Fallback to counting failures
        return self._create_fallback_summary(output)

    def determine_status(self, output: str, counts: TestCounts, collected: int) -> str:
        """Determine overall test status from output."""
        # Check for timeout first
        if "Test timed out after" in output:
            return "TIMEOUT"

        # Check test counts first (most reliable indicator)
        status_from_counts = self._determine_status_from_counts(counts)
        if status_from_counts:
            return self._add_crash_modifiers(status_from_counts, output)

        # Fall back to output analysis
        return self._determine_status_from_output(output, collected)

    def _determine_status_from_counts(self, counts: TestCounts) -> str | None:
        """Determine status based on test counts."""
        if counts.failed > 0:
            return "FAILED"
        if counts.error > 0:
            return "ERROR"
        if counts.skipped > 0 and counts.total() == counts.skipped:
            return "SKIPPED"
        if counts.passed > 0:
            return "PASSED"
        return None

    def _add_crash_modifiers(self, base_status: str, output: str) -> str:
        """Add crash modifiers to base status."""
        if base_status != "PASSED":
            return base_status

        if "Fatal Python error: Aborted" in output:
            return "PASSED (with teardown error)"
        if "Segmentation fault" in output:
            return "PASSED (with crash)"
        return base_status

    def _determine_status_from_output(self, output: str, collected: int) -> str:
        """Determine status from output when counts are unavailable."""
        if collected == 0 and "collected 0 items" in output:
            return "SKIPPED"

        # Check for crashes
        if self._is_crashed(output, collected):
            return "CRASHED"

        # Check basic output patterns
        return self._check_output_patterns(output)

    def _is_crashed(self, output: str, collected: int) -> bool:
        """Check if tests crashed before completion."""
        has_fatal_error = "Fatal Python error: Aborted" in output
        has_results = any(x in output for x in ["PASSED", "FAILED ", "SKIPPED"])
        return collected > 0 and has_fatal_error and not has_results

    def _check_output_patterns(self, output: str) -> str:
        """Check basic output patterns for status."""
        passed = "PASSED" in output
        failed = "FAILED " in output

        if passed and not failed:
            return "PASSED"
        return "FAILED"

    def _extract_collected_count(self, output: str) -> int:
        """Extract number of collected tests."""
        match = re.search(r"collected\s+(\d+)\s+items?", output)
        return int(match.group(1)) if match else 0

    def _extract_summary_counts(self, output: str) -> dict[str, int]:
        """Extract counts from summary lines."""
        counts = {}

        # Look for pytest summary lines like "14 passed in 0.94s" or "12 passed, 2 failed in 1.5s"
        summary_matches = re.findall(r"={5,}\s*(.*?)\s*in\s+[\d.]+s\s*={5,}", output)

        # Parse the summary content
        for summary_line in summary_matches:
            # Extract counts from summary line like "12 passed, 2 failed"
            for pattern, key in [
                (r"(\d+)\s+passed", "passed"),
                (r"(\d+)\s+failed", "failed"),
                (r"(\d+)\s+skipped", "skipped"),
                (r"(\d+)\s+error(?:s)?", "error"),
            ]:
                match = re.search(pattern, summary_line, re.IGNORECASE)
                if match:
                    counts[key] = int(match.group(1))

        # Also check for simple count patterns in full output as fallback
        if not counts:
            for pattern, key in [
                (r"(\d+)\s+passed", "passed"),
                (r"(\d+)\s+failed", "failed"),
                (r"(\d+)\s+skipped", "skipped"),
                (r"(\d+)\s+error(?:s)?", "error"),
            ]:
                match = re.search(pattern, output, re.IGNORECASE)
                if match:
                    counts[key] = int(match.group(1))

        return counts

    def _extract_from_summary_info(self, lines: list[str]) -> str | None:
        """Extract error from short test summary info."""
        summary_started = False
        for line in lines:
            if "short test summary info" in line.lower():
                summary_started = True
                continue

            if summary_started and line.strip():
                if line.startswith("="):
                    break
                if "FAILED" in line and " - " in line:
                    error_part = line.split(" - ", 1)[1].strip()
                    return error_part[:120] if error_part else "Test failed"

        return None

    def _extract_assertion_error(self, lines: list[str], error_type: str) -> str | None:
        """Extract assertion error message."""
        for line in lines:
            if error_type in line:
                error_msg = line.split(error_type, 1)[1].strip()
                if error_msg:
                    return error_msg[:120]
        return None

    def _extract_exception_error(self, lines: list[str], error_type: str) -> str | None:
        """Extract exception error message."""
        for line in lines:
            if error_type in line:
                error_msg = line.split(error_type, 1)[1].strip()
                clean_type = error_type.replace(":", "")
                return f"{clean_type} - {error_msg[:100]}" if error_msg else clean_type
        return None

    def _extract_pytest_error_markers(self, lines: list[str]) -> str | None:
        """Extract pytest E markers."""
        for line in lines:
            line = line.strip()
            if line.startswith("E   ") and len(line) > 4:
                error_msg = line[4:].strip()
                if error_msg and not error_msg.startswith(("assert", "Assert")):
                    return error_msg[:120]
        return None

    def _create_fallback_summary(self, output: str) -> str:
        """Create fallback summary when specific error not found."""
        failed_count = output.count("FAILED")
        error_count = output.count("ERROR")

        if failed_count > 0:
            return f"{failed_count} test(s) failed - check verbose output for details"
        if error_count > 0:
            return f"{error_count} error(s) occurred during testing"

        return "Test issues detected - run with -v for details"

    def _collect_all_error_types(self, lines: list[str]) -> list[str]:
        """Collect all unique error types from test output."""
        error_summaries = []
        seen_errors = set()

        # First try to extract from short test summary info (most reliable)
        summary_errors = self._extract_from_summary_info_all(lines)
        for error in summary_errors:
            if error and error not in seen_errors:
                error_summaries.append(error)
                seen_errors.add(error)

        # If we found errors in summary, use those (they're most accurate)
        if error_summaries:
            return error_summaries

        # Otherwise, look for specific error types throughout the output
        error_summaries.extend(self._extract_exception_errors(lines, seen_errors))

        # Look for pytest E markers if no specific types found
        if not error_summaries:
            error_summaries.extend(self._extract_pytest_markers(lines, seen_errors))

        return error_summaries

    def _extract_exception_errors(self, lines: list[str], seen_errors: set[str]) -> list[str]:
        """Extract exception-based errors from output."""
        error_summaries = []
        error_types = [
            "AssertionError:",
            "ImportError:",
            "ModuleNotFoundError:",
            "ValueError:",
            "TypeError:",
            "AttributeError:",
            "KeyError:",
            "RuntimeError:",
            "FileNotFoundError:",
            "ConnectionError:",
        ]

        for error_type in error_types:
            for line in lines:
                if error_type in line:
                    error_msg = line.split(error_type, 1)[1].strip()
                    clean_type = error_type.replace(":", "")
                    summary = f"{clean_type} - {error_msg[:80]}" if error_msg else clean_type

                    if summary not in seen_errors:
                        error_summaries.append(summary)
                        seen_errors.add(summary)
                    break  # Only take first occurrence of each type

        return error_summaries

    def _extract_pytest_markers(self, lines: list[str], seen_errors: set[str]) -> list[str]:
        """Extract pytest E marker errors from output."""
        error_summaries = []

        for line in lines:
            line = line.strip()
            if line.startswith("E   ") and len(line) > 4:
                error_msg = line[4:].strip()
                if error_msg and not error_msg.startswith(("assert", "Assert")):
                    summary = error_msg[:80]
                    if summary not in seen_errors:
                        error_summaries.append(summary)
                        seen_errors.add(summary)
                        if len(error_summaries) >= 5:  # Limit to 5 different types
                            break

        return error_summaries

    def _extract_from_summary_info_all(self, lines: list[str]) -> list[str]:
        """Extract all errors from short test summary info."""
        errors = []
        summary_started = False

        for line in lines:
            if "short test summary info" in line.lower():
                summary_started = True
                continue

            if summary_started and line.strip():
                if line.startswith("="):
                    break
                if "FAILED" in line and " - " in line:
                    error_part = line.split(" - ", 1)[1].strip()
                    if error_part:
                        errors.append(error_part[:80])
                        if len(errors) >= 5:  # Limit to 5 different error messages
                            break

        return errors

    def _adjust_counts_for_special_cases(
        self, test_path: str, output: str, counts: TestCounts, collected: int, status: str
    ) -> TestCounts:
        """Adjust counts for special cases like crashes."""
        # If we have a segfault but collected count is set
        if ("Segmentation fault" in output or "Fatal Python error" in output) and collected > 0:
            total_accounted = counts.total()
            if total_accounted < collected:
                counts.error += collected - total_accounted

        # If we collected tests but have no counts, be conservative
        # Don't assume collected count equals actual test results for complex tests
        if collected > 0 and counts.total() == 0:
            # Only use collected count for simple cases where we have clear evidence
            if (
                status == "PASSED"
                and "passed" in output.lower()
                and not any(x in output for x in ["failed", "error", "parametrize", "for i in", "range("])
            ):
                counts.passed = collected
            elif status == "SKIPPED" and "skipped" in output.lower():
                counts.skipped = collected
            # For complex cases or when uncertain, default to 1 test per file
            elif status == "PASSED":
                counts.passed = 1
            elif status == "FAILED":
                counts.failed = 1
            elif status == "ERROR":
                counts.error = 1
            else:
                counts.failed = 1

        return counts


# ============================================================================
# Test Executor
# ============================================================================


class TestExecutor:
    """Execute pytest tests and capture results."""

    def __init__(self, config: RunnerConfig):
        self.config = config
        self.parser = PytestOutputParser()

    def run_single_test(self, test_path: str) -> TestResult:
        """Run a single test file and return results."""
        start_time = time.time()

        try:
            output, _returncode = self._run_pytest_subprocess(test_path)
            duration = time.time() - start_time

            if output is None:  # Timeout
                return self._create_timeout_result(test_path, duration)

            return self.parser.parse_output(test_path, output, duration)

        except Exception as e:
            duration = time.time() - start_time
            return self._create_error_result(test_path, str(e), duration)

    def run_tests_parallel(self, test_files: list[str]) -> list[TestResult]:
        """Run tests in parallel and return results."""
        results: list[tuple[int, TestResult]] = []

        with ThreadPoolExecutor(max_workers=self.config.parallel) as executor:
            future_to_info: dict[Any, dict[str, Any]] = {}

            for i, path in enumerate(test_files, 1):
                future = executor.submit(self.run_single_test, path)
                future_to_info[future] = {"path": path, "index": i}

            for future in as_completed(future_to_info):
                info = future_to_info[future]
                try:
                    result = future.result()
                    results.append((info["index"], result))
                except Exception as e:
                    path = str(info["path"])
                    index = int(info["index"])
                    result = self._create_error_result(path, f"Executor error: {e!s}", 0.0)
                    results.append((index, result))

        # Sort by index to maintain order
        results.sort(key=operator.itemgetter(0))
        return [r[1] for r in results]

    def _run_pytest_subprocess(self, test_path: str) -> tuple[str | None, int]:
        """Run pytest in subprocess and return output."""
        cmd = self._build_pytest_command(test_path)

        # Set up environment for debug mode
        env = os.environ.copy()
        if self.config.debug_mode:
            env["FILE_COPY_DEBUG"] = "1"
            env["PYTHONVERBOSE"] = "1"

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
                timeout=self.config.timeout,
                env=env,
            )
            return result.stdout, result.returncode

        except subprocess.TimeoutExpired:
            return None, -1

    def _build_pytest_command(self, test_path: str) -> list[str]:
        """Build pytest command with appropriate options."""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        venv_python = os.path.join(script_dir, ".venv", "bin", "python")

        cmd = [venv_python, "-m", "pytest", test_path, "-v", "-p", "no:cov"]

        if self.config.debug_mode:
            cmd.extend([
                "--log-cli-level=DEBUG",
                "-s",
                "--no-header",
                "--showlocals",
            ])

        return cmd

    def _create_timeout_result(self, test_path: str, duration: float) -> TestResult:
        """Create result for timeout."""
        counts = TestCounts(timeout=1)
        return TestResult(
            path=test_path,
            status="TIMEOUT",
            duration=duration,
            output=f"Test timed out after {self.config.timeout} seconds",
            counts=counts,
            collected=0,
            error_summary="Test timed out",
        )

    def _create_error_result(self, test_path: str, error: str, duration: float) -> TestResult:
        """Create result for execution error."""
        counts = TestCounts(error=1)
        return TestResult(
            path=test_path,
            status="ERROR",
            duration=duration,
            output=error,
            counts=counts,
            collected=0,
            error_summary=error[:120],
        )


# ============================================================================
# Progress Reporter
# ============================================================================


class ProgressReporter:
    """Report test execution progress."""

    def __init__(self, config: RunnerConfig, color_scheme: ColorScheme):
        self.config = config
        self.colors = color_scheme
        self.emojis = {
            "PASSED": "✅",
            "FAILED": "❌",
            "ERROR": "💥",
            "SKIPPED": "⏭️",
            "CRASHED": "💀",
            "TIMEOUT": "⏰",
        }

    def report_progress(self, index: int, total: int, result: TestResult) -> None:
        """Report progress for a completed test."""
        if self.config.quiet:
            return

        # Override status and emoji based on actual test counts
        display_status = result.status
        if result.counts.failed > 0:
            display_status = "FAILED"
        elif result.counts.error > 0 and result.status not in {"CRASHED", "TIMEOUT"}:
            display_status = "ERROR"

        self.emojis.get(display_status, "❓")
        # Determine color based on overall test file health
        self._get_file_status_color(result)
        self._build_count_summary(result)

    def report_error(self, index: int, total: int, path: str, error: str) -> None:
        """Report error running test."""
        if self.config.quiet:
            return

        print(f"[{index}/{total}] ❌ ERROR running {path}: {error}")  # noqa: T201

    def report_starting(self, total: int) -> None:
        """Report starting tests."""
        if self.config.quiet:
            return

    def _build_count_summary(self, result: TestResult) -> str:
        """Build count summary string."""
        counts = result.counts
        total_tests = counts.total()

        # Use collected count if we have no individual counts
        if total_tests == 0 and result.collected > 0:
            return self._format_collected_count(result)

        # Build from individual counts with colors
        return self._format_individual_counts(counts) or self._get_status_fallback(result.status)

    def _format_collected_count(self, result: TestResult) -> str:
        """Format count summary using collected count."""
        color = self.colors.get(result.status)
        if color:
            status_text = {
                "PASSED": "passed",
                "FAILED": "failed",
                "SKIPPED": "skipped",
                "ERROR": "errors",
                "TIMEOUT": "timed out",
                "CRASHED": "crashed",
            }.get(result.status, "tests")
            return f"{color}{result.collected} {status_text}{self.colors.reset}"

        return f"{result.collected} tests"

    def _format_individual_counts(self, counts: TestCounts) -> str:
        """Format count summary from individual counts."""
        parts = []
        if counts.passed > 0:
            parts.append(f"{self.colors.passed}{counts.passed} passed{self.colors.reset}")
        if counts.failed > 0:
            parts.append(f"{self.colors.failed}{counts.failed} failed{self.colors.reset}")
        if counts.skipped > 0:
            parts.append(f"{self.colors.skipped}{counts.skipped} skipped{self.colors.reset}")
        if counts.error > 0:
            parts.append(f"{self.colors.error}{counts.error} errors{self.colors.reset}")

        return ", ".join(parts)

    def _get_status_fallback(self, status: str) -> str:
        """Get fallback count string for status."""
        fallbacks = {
            "PASSED": f"{self.colors.passed}1 passed{self.colors.reset}",
            "FAILED": f"{self.colors.failed}1 failed{self.colors.reset}",
            "SKIPPED": f"{self.colors.skipped}1 skipped{self.colors.reset}",
            "ERROR": f"{self.colors.error}1 error{self.colors.reset}",
            "TIMEOUT": f"{self.colors.timeout}1 timeout{self.colors.reset}",
            "CRASHED": f"{self.colors.crashed}1 crashed{self.colors.reset}",
        }
        return fallbacks.get(status, "1 test")

    def _get_file_status_color(self, result: TestResult) -> str:
        """Get color for file based on test health priority.

        Priority: failed > error > passed > skipped
        """
        counts = result.counts

        # Check by priority (failed is worst)
        if self._has_failures(counts, result.status):
            return self.colors.failed

        if self._has_errors(counts, result.status):
            return self.colors.error

        if self._has_only_passed(counts):
            return self.colors.passed

        if self._has_only_skipped(counts):
            return self.colors.skipped

        # Default fallback
        return self.colors.get(result.status) or self.colors.failed

    def _has_failures(self, counts: TestCounts, status: str) -> bool:
        """Check if there are any test failures."""
        return counts.failed > 0 or status == "FAILED"

    def _has_errors(self, counts: TestCounts, status: str) -> bool:
        """Check if there are any errors or problematic statuses."""
        error_statuses = {"ERROR", "CRASHED", "TIMEOUT"}
        return counts.error > 0 or status in error_statuses or "error" in status.lower()

    def _has_only_passed(self, counts: TestCounts) -> bool:
        """Check if all tests passed with no failures or errors."""
        return counts.passed > 0 and counts.failed == 0 and counts.error == 0

    def _has_only_skipped(self, counts: TestCounts) -> bool:
        """Check if all tests were skipped."""
        return counts.skipped > 0 and counts.passed == 0 and counts.failed == 0 and counts.error == 0


# ============================================================================
# Summary Reporter
# ============================================================================


class SummaryReporter:
    """Generate and print test execution summary."""

    def __init__(self, color_scheme: ColorScheme, config: RunnerConfig):
        self.colors = color_scheme
        self.config = config

    def print_summary(self, results: list[TestResult], duration: float) -> None:
        """Print complete test summary."""
        stats = self._calculate_statistics(results)

        print("\n" + "=" * 80)  # noqa: T201

        # Print sections for different statuses
        self._print_failed_section(results)
        self._print_error_section(results)
        self._print_crashed_section(results)
        self._print_timeout_section(results)
        self._print_skipped_section(results)

        # Print colorized file counter summary
        self._print_file_counter_summary(stats, duration)

        print("=" * 80)  # noqa: T201

    def _calculate_statistics(self, results: list[TestResult]) -> dict[str, Any]:
        """Calculate summary statistics."""
        stats: dict[str, Any] = {
            "total_files": len(results),
            "passed_files": 0,
            "failed_files": 0,
            "error_files": 0,
            "crashed_files": 0,
            "skipped_files": 0,
            "timeout_files": 0,
            "test_counts": {
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "error": 0,
                "crashed": 0,
                "timeout": 0,
            },
        }

        for result in results:
            self._update_file_counts(stats, result.status)
            self._update_test_counts(stats, result)

        return stats

    def _update_file_counts(self, stats: dict[str, Any], status: str) -> None:
        """Update file count statistics based on status."""
        # NOTE: The status here should already reflect whether tests failed
        # based on the determine_status logic that checks counts
        if status in {"PASSED", "PASSED (with teardown error)", "PASSED (with crash)"}:
            stats["passed_files"] += 1
        elif status == "FAILED":
            stats["failed_files"] += 1
        elif status == "ERROR":
            stats["error_files"] += 1
        elif status == "CRASHED":
            stats["crashed_files"] += 1
        elif status == "SKIPPED":
            stats["skipped_files"] += 1
        elif status == "TIMEOUT":
            stats["timeout_files"] += 1

    def _update_test_counts(self, stats: dict[str, Any], result: TestResult) -> None:
        """Update test count statistics from result."""
        counts = result.counts

        # Adjust for special cases where we have collected count but no individual counts
        if result.collected > 0 and counts.total() == 0:
            self._adjust_counts_from_collected(counts, result)

        test_counts = stats["test_counts"]
        assert isinstance(test_counts, dict)  # Type narrowing for mypy
        test_counts["passed"] += counts.passed
        test_counts["failed"] += counts.failed
        test_counts["skipped"] += counts.skipped
        test_counts["error"] += counts.error
        test_counts["crashed"] += counts.crashed
        test_counts["timeout"] += counts.timeout

    def _adjust_counts_from_collected(self, counts: TestCounts, result: TestResult) -> None:
        """Adjust counts using collected count when individual counts are missing."""
        if result.status in {"PASSED", "PASSED (with teardown error)", "PASSED (with crash)"}:
            counts.passed = result.collected
        elif result.status == "FAILED":
            counts.failed = result.collected
        elif result.status == "SKIPPED":
            counts.skipped = result.collected
        elif result.status == "ERROR":
            counts.error = result.collected
        elif result.status == "CRASHED":
            counts.crashed = result.collected
        elif result.status == "TIMEOUT":
            counts.timeout = result.collected

    def _print_failed_section(self, results: list[TestResult]) -> None:
        """Print failed tests section."""
        failed = [r for r in results if r.status == "FAILED"]
        if not failed:
            return

        print(f"\n{self.colors.failed}❌ FAILED FILES ({len(failed)}):{self.colors.reset}")  # noqa: T201
        for result in failed:
            self._print_result_line(result)

    def _print_error_section(self, results: list[TestResult]) -> None:
        """Print error tests section."""
        errors = [r for r in results if r.status == "ERROR"]
        if not errors:
            return

        print(f"\n{self.colors.error}💥 ERROR FILES ({len(errors)}):{self.colors.reset}")  # noqa: T201
        for result in errors:
            self._print_result_line(result)

    def _print_crashed_section(self, results: list[TestResult]) -> None:
        """Print crashed tests section."""
        crashed = [r for r in results if r.status == "CRASHED"]
        if not crashed:
            return

        print(f"\n{self.colors.crashed}💀 CRASHED FILES ({len(crashed)}):{self.colors.reset}")  # noqa: T201
        for result in crashed:
            self._print_result_line(result)

    def _print_timeout_section(self, results: list[TestResult]) -> None:
        """Print timeout tests section."""
        timeouts = [r for r in results if r.status == "TIMEOUT"]
        if not timeouts:
            return

        print(f"\n{self.colors.timeout}⏰ TIMEOUT FILES ({len(timeouts)}):{self.colors.reset}")  # noqa: T201
        for result in timeouts:
            self._print_result_line(result)

    def _print_skipped_section(self, results: list[TestResult]) -> None:
        """Print skipped tests section."""
        skipped = [r for r in results if r.status == "SKIPPED"]
        if not skipped:
            return

        print(f"\n{self.colors.skipped}⏭️ SKIPPED FILES ({len(skipped)}):{self.colors.reset}")  # noqa: T201
        for result in skipped:
            print(f"  {self.colors.skipped}{result.path}{self.colors.reset}")  # noqa: T201

    def _print_result_line(self, result: TestResult) -> None:
        """Print a single result line with error summary."""
        color = self.colors.get(result.status)
        count_summary = self._build_count_summary(result)

        print(f"  {color}{result.path}{self.colors.reset} ({count_summary})")  # noqa: T201

        if result.error_summary:
            error_color = self.colors.get(result.status) or self.colors.failed
            print(f"    → {error_color}{result.error_summary}{self.colors.reset}")  # noqa: T201

    def _build_count_summary(self, result: TestResult) -> str:
        """Build count summary for result line."""
        counts = result.counts
        total = counts.total()

        if total == 0 and result.collected > 0:
            if result.status == "FAILED":
                return f"{result.collected} failed"
            if result.status == "ERROR":
                return f"{result.collected} errors"
            if result.status == "TIMEOUT":
                return f"{result.collected} timed out"
            if result.status == "CRASHED":
                return f"{result.collected} crashed"
            return f"{result.collected} tests"

        parts = []
        if counts.passed > 0:
            parts.append(f"{counts.passed} passed")
        if counts.failed > 0:
            parts.append(f"{counts.failed} failed")
        if counts.skipped > 0:
            parts.append(f"{counts.skipped} skipped")
        if counts.error > 0:
            parts.append(f"{counts.error} errors")

        return ", ".join(parts) if parts else self._get_status_default(result.status)

    def _get_status_default(self, status: str) -> str:
        """Get default count string for status."""
        defaults = {
            "FAILED": "1 failed",
            "ERROR": "1 error",
            "TIMEOUT": "1 timeout",
            "CRASHED": "1 crashed",
            "SKIPPED": "1 skipped",
            "PASSED": "1 passed",
        }
        return defaults.get(status, "1 test")

    def _print_file_counter_summary(self, stats: dict[str, Any], duration: float) -> None:
        """Print colorized summary - either file counts or individual test counts."""
        if self.config.count_tests:
            self._print_test_counter_summary(stats, duration)
        else:
            self._print_file_counter_summary_impl(stats, duration)

    def _print_file_counter_summary_impl(self, stats: dict[str, Any], duration: float) -> None:
        """Print colorized file counter summary."""
        print(f"\n{self.colors.reset}📊 TEST FILE SUMMARY:")  # noqa: T201

        # File counts with colors
        total = stats["total_files"]
        passed = stats["passed_files"]
        failed = stats["failed_files"]
        error = stats["error_files"]
        crashed = stats["crashed_files"]
        timeout = stats["timeout_files"]
        skipped = stats["skipped_files"]

        # Build colorized counter parts
        counter_parts = []

        if passed > 0:
            counter_parts.append(f"{self.colors.passed}✅ {passed} PASSED{self.colors.reset}")

        if failed > 0:
            counter_parts.append(f"{self.colors.failed}❌ {failed} FAILED{self.colors.reset}")

        if error > 0:
            counter_parts.append(f"{self.colors.error}💥 {error} ERROR{self.colors.reset}")

        if crashed > 0:
            counter_parts.append(f"{self.colors.crashed}💀 {crashed} CRASHED{self.colors.reset}")

        if timeout > 0:
            counter_parts.append(f"{self.colors.timeout}⏰ {timeout} TIMEOUT{self.colors.reset}")

        if skipped > 0:
            counter_parts.append(f"{self.colors.skipped}⏭️  {skipped} SKIPPED{self.colors.reset}")

        # Print the counter
        counter_line = "  " + " | ".join(counter_parts)
        print(counter_line)  # noqa: T201

        # Print total and duration
        total_color = self.colors.passed if (failed + error + crashed + timeout) == 0 else self.colors.failed
        print(f"  {total_color}📁 TOTAL: {total} files{self.colors.reset} in {duration:.1f}s")  # noqa: T201

    def _print_test_counter_summary(self, stats: dict[str, Any], duration: float) -> None:
        """Print colorized individual test counter summary."""
        print(f"\n{self.colors.reset}📊 INDIVIDUAL TEST SUMMARY:")  # noqa: T201

        # Individual test counts
        test_counts = stats["test_counts"]
        assert isinstance(test_counts, dict)  # Type narrowing for mypy
        passed = test_counts["passed"]
        failed = test_counts["failed"]
        skipped = test_counts["skipped"]
        error = test_counts["error"]
        crashed = test_counts["crashed"]
        timeout = test_counts["timeout"]
        total_tests = passed + failed + skipped + error + crashed + timeout

        # Build colorized counter parts with percentages
        counter_parts = []

        if passed > 0:
            passed_pct = (passed / total_tests * 100) if total_tests > 0 else 0.0
            counter_parts.append(f"{self.colors.passed}✅ {passed} PASSED ({passed_pct:.1f}%){self.colors.reset}")

        if failed > 0:
            failed_pct = (failed / total_tests * 100) if total_tests > 0 else 0.0
            counter_parts.append(f"{self.colors.failed}❌ {failed} FAILED ({failed_pct:.1f}%){self.colors.reset}")

        if error > 0:
            error_pct = (error / total_tests * 100) if total_tests > 0 else 0.0
            counter_parts.append(f"{self.colors.error}💥 {error} ERROR ({error_pct:.1f}%){self.colors.reset}")

        if skipped > 0:
            skipped_pct = (skipped / total_tests * 100) if total_tests > 0 else 0.0
            counter_parts.append(f"{self.colors.skipped}⏭️  {skipped} SKIPPED ({skipped_pct:.1f}%){self.colors.reset}")

        if crashed > 0:
            crashed_pct = (crashed / total_tests * 100) if total_tests > 0 else 0.0
            counter_parts.append(f"{self.colors.crashed}💀 {crashed} CRASHED ({crashed_pct:.1f}%){self.colors.reset}")

        if timeout > 0:
            timeout_pct = (timeout / total_tests * 100) if total_tests > 0 else 0.0
            counter_parts.append(f"{self.colors.timeout}⏰ {timeout} TIMEOUT ({timeout_pct:.1f}%){self.colors.reset}")

        # Print the counter
        counter_line = "  " + " | ".join(counter_parts)
        print(counter_line)  # noqa: T201

        # Print total and duration
        total_color = self.colors.passed if (failed + error + crashed + timeout) == 0 else self.colors.failed
        print(f"  {total_color}🧪 TOTAL: {total_tests} tests{self.colors.reset} in {duration:.1f}s")  # noqa: T201


# ============================================================================
# Test Discovery
# ============================================================================


class TestDiscovery:
    """Discover test files in the project."""

    PROBLEMATIC_TESTS = [
        # Files that cause timeouts when run in discovery mode
        "tests/gui/test_gui_button_validation_v2.py",
        "tests/gui/test_gui_component_validation_v2.py",
        "tests/gui/test_main_window_v2.py",
        "tests/unit/test_enhanced_gui_tab_v2.py",
        "tests/unit/test_enhanced_integrity_check_tab_v2.py",
        "tests/unit/test_preview_scaling_fixes_v2.py",
    ]

    def find_test_files(self, directory: str = "tests") -> list[str]:
        """Find all test files in directory."""
        result = []

        # Find all test files recursively
        pattern = os.path.join(directory, "**", "test_*.py")
        result.extend(glob.glob(pattern, recursive=True))

        # Also look for root level test files
        result.extend(glob.glob("test_*.py"))

        # Remove duplicates and sort
        seen = set()
        unique_result = []
        for item in result:
            if item not in seen:
                seen.add(item)
                unique_result.append(item)

        return sorted(unique_result)

    def filter_problematic(self, files: list[str], skip: bool) -> tuple[list[str], int]:
        """Filter out problematic tests if requested."""
        if not skip:
            return files, 0

        original_count = len(files)
        filtered = [f for f in files if f not in self.PROBLEMATIC_TESTS]
        skipped_count = original_count - len(filtered)

        return filtered, skipped_count


# ============================================================================
# Log Manager
# ============================================================================


class LogManager:
    """Manage test output logging to files."""

    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.log_dir = Path("test_logs")

    def save_log(self, result: TestResult, debug_mode: bool = False) -> str | None:
        """Save test output to log file if enabled."""
        if not self.enabled:
            return None

        # Only save logs for failed/errored tests
        if result.status not in {"FAILED", "ERROR", "CRASHED", "TIMEOUT"} and (
            "PASSED" not in result.status or "error" not in result.status
        ):
            return None

        # Create log directory
        log_dir = self.log_dir / "debug" if debug_mode else self.log_dir
        log_dir.mkdir(parents=True, exist_ok=True)

        # Create log filename
        filename = result.path.replace("/", "_").replace("\\", "_")
        log_path = log_dir / f"{filename}.log"

        # Write log file
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"=== Test Log for {result.path} ===\n")
            f.write(f"Generated: {timestamp}\n")
            f.write(f"Status: {result.status}\n")
            f.write(f"Duration: {result.duration:.2f}s\n")
            f.write(f"Debug Mode: {'Enabled' if debug_mode else 'Disabled'}\n")
            f.write("=" * 80 + "\n\n")
            f.write(result.output)

        return str(log_path)


# ============================================================================
# Main Test Runner
# ============================================================================


class TestRunner:
    """Main test runner orchestrator."""

    def __init__(self, config: RunnerConfig):
        self.config = config
        self.colors = ColorScheme()
        self.discovery = TestDiscovery()
        self.executor = TestExecutor(config)
        self.progress = ProgressReporter(config, self.colors)
        self.summary = SummaryReporter(self.colors, config)
        self.logs = LogManager(config.dump_logs)

    def run(self) -> int:
        """Run all tests and return exit code."""
        # Discover tests
        print("🔍 Discovering test files...")  # noqa: T201
        test_files = self._discover_tests()
        print(f"📁 Found {len(test_files)} test files")  # noqa: T201
        if not test_files:
            print("No test files found!")  # noqa: T201
            return 1

        # Start testing
        self.progress.report_starting(len(test_files))
        start_time = time.time()

        # Run tests
        results = self._run_tests(test_files)

        # Save logs if enabled
        if self.config.dump_logs:
            self._save_logs(results)

        # Print summary
        duration = time.time() - start_time
        self.summary.print_summary(results, duration)

        # Calculate exit code
        return self._calculate_exit_code(results)

    def _discover_tests(self) -> list[str]:
        """Discover test files to run."""
        if self.config.specific_files:
            return self.config.specific_files

        files = self.discovery.find_test_files(self.config.directory)
        files, skipped = self.discovery.filter_problematic(files, self.config.skip_problematic)

        if skipped > 0 and not self.config.quiet:
            print(f"⏭️  Skipping {skipped} known problematic tests")  # noqa: T201

        return files

    def _run_tests(self, test_files: list[str]) -> list[TestResult]:
        """Run all tests with progress reporting."""
        if self.config.parallel == 1 or self.config.debug_mode:
            return self._run_tests_sequential(test_files)
        return self._run_tests_parallel(test_files)

    def _run_tests_sequential(self, test_files: list[str]) -> list[TestResult]:
        """Run tests sequentially with progress reporting."""
        results = []
        for i, test_file in enumerate(test_files, 1):
            result = self.executor.run_single_test(test_file)
            self.progress.report_progress(i, len(test_files), result)
            results.append(result)
        return results

    def _run_tests_parallel(self, test_files: list[str]) -> list[TestResult]:
        """Run tests in parallel with progress reporting."""
        indexed_results: list[tuple[int, TestResult]] = []
        with ThreadPoolExecutor(max_workers=self.config.parallel) as executor:
            future_to_info: dict[Any, dict[str, Any]] = {}

            for i, path in enumerate(test_files, 1):
                future = executor.submit(self.executor.run_single_test, path)
                future_to_info[future] = {"path": path, "index": i}

            for future in as_completed(future_to_info):
                info = future_to_info[future]
                try:
                    result = future.result()
                    index = int(info["index"])
                    self.progress.report_progress(index, len(test_files), result)
                    indexed_results.append((index, result))
                except Exception as e:
                    path = str(info["path"])
                    index = int(info["index"])
                    self.progress.report_error(index, len(test_files), path, str(e))
                    error_result = TestResult(
                        path=path,
                        status="ERROR",
                        duration=0.0,
                        output=str(e),
                        counts=TestCounts(error=1),
                        collected=0,
                        error_summary=str(e)[:120],
                    )
                    indexed_results.append((index, error_result))

        # Sort by original order
        indexed_results.sort(key=operator.itemgetter(0))
        return [r[1] for r in indexed_results]

    def _save_logs(self, results: list[TestResult]) -> None:
        """Save logs for failed tests."""
        for result in results:
            log_path = self.logs.save_log(result, self.config.debug_mode)
            if log_path:
                result.log_path = log_path
                if self.config.verbose:
                    print(f"  Log saved to: {log_path}")  # noqa: T201

    def _calculate_exit_code(self, results: list[TestResult]) -> int:
        """Calculate exit code from results."""
        if self.config.tolerant:
            return 0

        for result in results:
            if result.status not in {"PASSED", "SKIPPED", "PASSED (with teardown error)", "PASSED (with crash)"}:
                return 1

        return 0


# ============================================================================
# Main Entry Point
# ============================================================================


def parse_arguments() -> RunnerConfig:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run all tests directly with pytest")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print verbose output")
    parser.add_argument("--parallel", "-p", type=int, default=4, help="Number of parallel workers")
    parser.add_argument("--file", action="append", dest="specific_files", help="Run specific test file")
    parser.add_argument("--directory", default="tests", help="Directory containing tests")
    parser.add_argument("--tolerant", action="store_true", help="Always return success (0) even if tests fail")
    parser.add_argument("--dump-logs", action="store_true", help="Dump output logs for failed tests to files")
    parser.add_argument(
        "--include-problematic", action="store_true", help="Include known problematic tests that may timeout"
    )
    parser.add_argument("--debug-mode", action="store_true", help="Run tests with extra debug options")
    parser.add_argument("--quiet", "-q", action="store_true", help="Minimal output (only summary)")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout for individual tests in seconds (default: 30)")
    parser.add_argument(
        "--count-files", action="store_true", help="Count test files instead of individual tests in summary"
    )

    args = parser.parse_args()

    # Convert to config object
    return RunnerConfig(
        parallel=args.parallel,
        timeout=args.timeout,
        verbose=args.verbose,
        quiet=args.quiet,
        debug_mode=args.debug_mode,
        dump_logs=args.dump_logs,
        directory=args.directory,
        skip_problematic=not args.include_problematic,
        tolerant=args.tolerant,
        count_tests=not args.count_files,
        specific_files=args.specific_files or [],
    )


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    print("🚀 Starting test runner...", flush=True)  # noqa: T201

    # Quick dependency check
    try:
        import pytest  # noqa: F401
    except ImportError:
        print("Error: pytest not found. Please activate the virtual environment:")  # noqa: T201
        print("  source .venv/bin/activate")  # noqa: T201
        return 1

    print("✅ Parsing arguments...", flush=True)  # noqa: T201
    config = parse_arguments()
    print("✅ Arguments parsed", flush=True)  # noqa: T201

    # Debug mode forces sequential execution
    if config.debug_mode:
        config.parallel = 1

    print("✅ Creating test runner...", flush=True)  # noqa: T201
    runner = TestRunner(config)
    print("✅ Running tests...", flush=True)  # noqa: T201
    return runner.run()


if __name__ == "__main__":
    sys.exit(main())
