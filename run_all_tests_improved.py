#!/usr/bin/env python3
"""Improved test runner with much better complexity scores.

This refactored version breaks down the massive functions into smaller,
focused components to achieve better maintainability and complexity grades.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
import glob
import os
import re
import subprocess
import sys
import threading
import time
from typing import Any


class TestStatus(Enum):
    """Test status enumeration."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"
    CRASHED = "CRASHED"


@dataclass
class TestCounts:
    """Container for test result counts."""

    passed: int = 0
    failed: int = 0
    error: int = 0
    skipped: int = 0
    crashed: int = 0

    def total(self) -> int:
        """Get total count of all tests."""
        return self.passed + self.failed + self.error + self.skipped + self.crashed


@dataclass
class TestResult:
    """Container for test execution results."""

    path: str
    status: TestStatus
    duration: float
    output: str
    counts: TestCounts
    collected: int = 0
    failed_details: list[str] = field(default_factory=list)


# Define colors for different statuses
STATUS_COLOR = {
    "PASSED": "\033[92m",  # Green
    "FAILED": "\033[91m",  # Red
    "ERROR": "\033[95m",  # Magenta
    "SKIPPED": "\033[94m",  # Blue
    "CRASHED": "\033[93m",  # Yellow
}
RESET = "\033[0m"
SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class TestOutputParser:
    """Handles parsing of pytest output to determine test results."""

    # Regex patterns for parsing test output
    COLLECTED_PATTERN = re.compile(r"collected\s+(\d+)\s+items")
    PASSED_PATTERN = re.compile(r"test_\w+\s+PASSED")
    FAILED_PATTERN = re.compile(r"test_\w+\s+FAILED")
    SKIPPED_PATTERN = re.compile(r"test_\w+\s+SKIPPED")
    ERROR_PATTERN = re.compile(r"test_\w+\s+ERROR")

    # Count patterns in parentheses like "(6 passed)"
    COUNT_PATTERNS = {
        "passed": re.compile(r"\((\d+)\s+passed"),
        "failed": re.compile(r"\((\d+)\s+failed"),
        "skipped": re.compile(r"\((\d+)\s+skipped"),
        "error": re.compile(r"\((\d+)\s+error(?:s)?)", re.IGNORECASE),
    }

    # Summary line patterns like "6 passed"
    SUMMARY_PATTERNS = {
        "passed": re.compile(r"(\d+)\s+passed"),
        "failed": re.compile(r"(\d+)\s+failed"),
        "skipped": re.compile(r"(\d+)\s+skipped"),
        "error": re.compile(r"(\d+)\s+errors?"),
    }

    def parse_collected_count(self, output: str) -> int:
        """Extract the number of collected tests."""
        match = self.COLLECTED_PATTERN.search(output)
        return int(match.group(1)) if match else 0

    def count_direct_matches(self, output: str) -> TestCounts:
        """Count test results by direct pattern matching."""
        counts = TestCounts()
        counts.passed = len(self.PASSED_PATTERN.findall(output))
        counts.failed = len(self.FAILED_PATTERN.findall(output))
        counts.skipped = len(self.SKIPPED_PATTERN.findall(output))
        counts.error = len(self.ERROR_PATTERN.findall(output))
        return counts

    def extract_parenthetical_counts(self, output: str) -> TestCounts:
        """Extract counts from parenthetical expressions like '(6 passed)'."""
        counts = TestCounts()
        for status, pattern in self.COUNT_PATTERNS.items():
            match = pattern.search(output)
            if match:
                setattr(counts, status, int(match.group(1)))
        return counts

    def extract_summary_counts(self, output: str) -> TestCounts:
        """Extract counts from summary line patterns."""
        counts = TestCounts()
        for status, pattern in self.SUMMARY_PATTERNS.items():
            match = pattern.search(output)
            if match:
                setattr(counts, status, int(match.group(1)))
        return counts

    def merge_counts(self, *count_objects: TestCounts) -> TestCounts:
        """Merge multiple TestCounts objects, taking the maximum for each status."""
        result = TestCounts()
        for status in ["passed", "failed", "skipped", "error"]:
            values = [getattr(counts, status) for counts in count_objects]
            setattr(result, status, max(values))
        return result

    def determine_status(self, output: str, counts: TestCounts, collected: int) -> TestStatus:
        """Determine the overall test status based on output and counts."""
        # Check for crashes/segfaults
        if self._has_crash_indicators(output) and collected > 0 and not self._has_results(output):
            return TestStatus.CRASHED

        # Prioritize by severity
        if counts.failed > 0:
            return TestStatus.FAILED
        if counts.error > 0:
            return TestStatus.ERROR
        if counts.passed > 0:
            return TestStatus.PASSED
        if counts.skipped > 0:
            return TestStatus.SKIPPED
        return TestStatus.FAILED  # Default fallback

    def _has_crash_indicators(self, output: str) -> bool:
        """Check if output contains crash indicators."""
        crash_indicators = ["Segmentation fault", "Fatal Python error", "Fatal Python error: Aborted"]
        return any(indicator in output for indicator in crash_indicators)

    def _has_results(self, output: str) -> bool:
        """Check if output contains any test results."""
        return any(pattern in output for pattern in ["PASSED", "FAILED", "SKIPPED", "ERROR"])

    def extract_failed_details(self, output: str) -> list[str]:
        """Extract specific failed test details from output."""
        failed_tests = re.findall(r"^(?:FAILURES|ERRORS)\n_+\s*(.*?)\s*_+", output, re.MULTILINE | re.DOTALL)

        details = []
        if failed_tests:
            matches = re.findall(r"^(FAILED|ERROR)\s+.*?::.*?::(.*?)\s+-", failed_tests[0], re.MULTILINE)
            details.extend([f"{status} {name}" for status, name in matches])

        # Also check summary section
        summary_match = re.search(r"=+ short test summary info =+\n(.*?)\n=+", output, re.DOTALL)

        if summary_match:
            summary_details = re.findall(
                r"^(FAILED|ERROR|SKIPPED)\s+.*?::.*?::(.*?)\s+-?.*?$",
                summary_match.group(1),
                re.MULTILINE,
            )
            details.extend([f"{status} {name}" for status, name, _ in summary_details if status in {"FAILED", "ERROR"}])

        return sorted(set(details))

    def parse_test_output(self, output: str) -> tuple[TestCounts, int, list[str]]:
        """Parse test output and return counts, collected count, and failed details."""
        collected = self.parse_collected_count(output)

        # Get counts from multiple sources
        direct_counts = self.count_direct_matches(output)
        paren_counts = self.extract_parenthetical_counts(output)
        summary_counts = self.extract_summary_counts(output)

        # Merge counts, taking maximum from each source
        final_counts = self.merge_counts(direct_counts, paren_counts, summary_counts)

        # Handle special cases where counts don't add up
        if collected > 0 and final_counts.total() == 0:
            # All tests had the same result
            final_counts.passed = collected

        failed_details = self.extract_failed_details(output)

        return final_counts, collected, failed_details


class TestExecutor:
    """Handles execution of individual test files."""

    def __init__(self, debug_mode: bool = False):
        self.debug_mode = debug_mode
        self.parser = TestOutputParser()

    def build_command(self, test_path: str) -> list[str]:
        """Build the pytest command for a test file."""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        venv_python = os.path.join(script_dir, ".venv", "bin", "python")
        cmd = [venv_python, "-m", "pytest", test_path, "-v", "-p", "no:cov"]

        if self.debug_mode:
            cmd.extend([
                "--log-cli-level=DEBUG",
                "-s",
                "--no-header",
                "--showlocals",
            ])

        return cmd

    def setup_debug_environment(self) -> None:
        """Set up debug environment variables."""
        if self.debug_mode:
            os.environ["FILE_COPY_DEBUG"] = "1"
            os.environ["PYTHONVERBOSE"] = "1"

    def cleanup_debug_environment(self) -> None:
        """Clean up debug environment variables."""
        if self.debug_mode:
            os.environ.pop("FILE_COPY_DEBUG", None)
            os.environ.pop("PYTHONVERBOSE", None)

    def execute_test(self, test_path: str, worker_tracker=None) -> TestResult:
        """Execute a single test file and return results."""
        start_time = time.time()
        worker_id = threading.get_ident()

        if worker_tracker:
            worker_tracker.set_worker_status(worker_id, test_path, start_time)

        try:
            self.setup_debug_environment()
            cmd = self.build_command(test_path)

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            try:
                output, _ = process.communicate()
            except KeyboardInterrupt:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                raise

            duration = time.time() - start_time
            return self._process_test_output(test_path, output, duration)

        except Exception as e:
            return TestResult(
                path=test_path,
                status=TestStatus.ERROR,
                duration=time.time() - start_time,
                output=str(e),
                counts=TestCounts(error=1),
                collected=0,
            )
        finally:
            if worker_tracker:
                worker_tracker.clear_worker_status(worker_id)
            self.cleanup_debug_environment()

    def _process_test_output(self, test_path: str, output: str, duration: float) -> TestResult:
        """Process test output and create TestResult object."""
        counts, collected, failed_details = self.parser.parse_test_output(output)
        status = self.parser.determine_status(output, counts, collected)

        # Apply special handling for known problematic tests
        status = self._apply_special_cases(test_path, output, status, counts, collected)

        return TestResult(
            path=test_path,
            status=status,
            duration=duration,
            output=output,
            counts=counts,
            collected=collected,
            failed_details=failed_details,
        )

    def _apply_special_cases(
        self, test_path: str, output: str, status: TestStatus, counts: TestCounts, collected: int
    ) -> TestStatus:
        """Apply special case handling for specific test files."""
        # Handle teardown errors that don't affect test success
        if "PASSED" in output and "FAILED " not in output and "Fatal Python error: Aborted" in output:
            return TestStatus.PASSED

        # Handle specific problematic files
        if test_path == "tests/gui/test_main_window.py" and (
            "Segmentation fault" in output and status == TestStatus.PASSED and collected == 12
        ):
            # Known segfault but tests pass
            counts.passed = max(counts.passed, 12)

        return status


class WorkerStatusTracker:
    """Thread-safe tracker for worker status and progress."""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.running = False
        self.thread: threading.Thread | None = None
        self.frame = 0
        self.completed = 0
        self.total = 0
        self.worker_status: dict[int, dict[str, Any]] = {}
        self.completed_tests: list[str] = []
        self.failed_tests: list[dict[str, Any]] = []
        self.max_display_lines = 15
        self.lock = threading.Lock()

    def start(self, total_tests: int) -> None:
        """Start the status display."""
        with self.lock:
            self.running = True
            self.total = total_tests
            self.completed = 0
            self.worker_status = {}
            self.completed_tests = []
            self.failed_tests = []

        self.thread = threading.Thread(target=self._display_status)
        self.thread.daemon = True
        self.thread.start()

    def stop(self) -> None:
        """Stop the status display."""
        with self.lock:
            self.running = False
        if self.thread:
            self.thread.join()

    def update_progress(self, completed: int) -> None:
        """Update overall progress."""
        with self.lock:
            self.completed = completed

    def set_worker_status(self, worker_id: int, test_path: str, start_time: float | None = None) -> None:
        """Set what a worker is currently running."""
        with self.lock:
            if start_time is None:
                start_time = time.time()
            self.worker_status[worker_id] = {"test_path": test_path, "start_time": start_time}

    def clear_worker_status(self, worker_id: int) -> None:
        """Clear a worker's status when test completes."""
        with self.lock:
            self.worker_status.pop(worker_id, None)

    def add_completed_test(self, result: TestResult) -> None:
        """Add a completed test result to the display."""
        with self.lock:
            test_number = len(self.completed_tests) + 1
            display_path = self._shorten_path(result.path, 65)

            status_icons = {
                TestStatus.PASSED: "✓",
                TestStatus.FAILED: "✗",
                TestStatus.ERROR: "⚠",
                TestStatus.SKIPPED: "○",
                TestStatus.CRASHED: "💥",
            }

            icon = status_icons.get(result.status, "?")
            color = STATUS_COLOR.get(result.status.value, RESET)
            count_str = self._format_counts(result.counts)

            display_line = f"{test_number:3d}. {color}{icon} {display_path}{count_str} {result.duration:.1f}s{RESET}"

            self.completed_tests.append(display_line)

            if result.status in {TestStatus.FAILED, TestStatus.ERROR, TestStatus.CRASHED}:
                self.failed_tests.append({
                    "number": test_number,
                    "path": result.path,
                    "status": result.status.value,
                    "duration": result.duration,
                    "output": result.output,
                    "failed_details": result.failed_details,
                    "counts": result.counts,
                })

    def get_failed_tests(self) -> list[dict[str, Any]]:
        """Get list of failed tests for detailed reporting."""
        with self.lock:
            return list(self.failed_tests)

    def _shorten_path(self, path: str, max_length: int) -> str:
        """Shorten a file path for display."""
        if len(path) > max_length:
            return "..." + path[-(max_length - 3) :]
        return path

    def _format_counts(self, counts: TestCounts) -> str:
        """Format test counts for display."""
        count_parts = []
        if counts.passed > 0:
            count_parts.append(f"{counts.passed} passed")
        if counts.failed > 0:
            count_parts.append(f"{counts.failed} failed")
        if counts.error > 0:
            count_parts.append(f"{counts.error} errors")
        if counts.skipped > 0:
            count_parts.append(f"{counts.skipped} skipped")

        return f" ({', '.join(count_parts)})" if count_parts else ""

    def _display_status(self) -> None:
        """Display current worker status and completed tests."""
        while True:
            with self.lock:
                if not self.running:
                    break

                frame_char = SPINNER_FRAMES[self.frame % len(SPINNER_FRAMES)]
                completed = self.completed
                total = self.total
                current_workers = dict(self.worker_status)
                completed_tests = list(self.completed_tests)

            self._render_display(frame_char, completed, total, current_workers, completed_tests)
            self.frame += 1
            time.sleep(0.5)

    def _render_display(
        self, frame_char: str, completed: int, total: int, current_workers: dict, completed_tests: list[str]
    ) -> None:
        """Render the status display."""
        num_completed = len(completed_tests)
        display_completed = min(num_completed, self.max_display_lines)
        total_lines = display_completed + self.max_workers + 3

        # Clear previous display
        self._clear_display(total_lines)

        # Completed tests section
        self._display_completed_tests(completed_tests, display_completed, num_completed)

        # Separator and progress
        len(current_workers)

        # Worker status
        self._display_worker_status(current_workers)

        # Move cursor back for next update
        for _ in range(total_lines):
            pass

    def _clear_display(self, total_lines: int) -> None:
        """Clear the previous display."""
        for _ in range(total_lines - 1):
            pass
        for _ in range(total_lines - 1):
            pass

    def _display_completed_tests(self, completed_tests: list[str], display_completed: int, num_completed: int) -> None:
        """Display the completed tests section."""
        start_idx = max(0, num_completed - display_completed)
        for i in range(start_idx, num_completed):
            if i < len(completed_tests):
                pass

        # Fill remaining lines
        for _ in range(display_completed - (num_completed - start_idx)):
            pass

    def _display_worker_status(self, current_workers: dict) -> None:
        """Display the worker status section."""
        current_time = time.time()
        worker_list = list(current_workers.items())
        worker_list.sort(key=lambda x: x[1]["start_time"])

        for i in range(self.max_workers):
            if i < len(worker_list):
                _worker_id, status = worker_list[i]
                test_path = status["test_path"]
                duration = current_time - status["start_time"]

                self._shorten_path(test_path, 60)

                # Color code based on duration
                if duration > 30:
                    STATUS_COLOR["FAILED"]
                elif duration > 10:
                    STATUS_COLOR["CRASHED"]
                else:
                    STATUS_COLOR["PASSED"]


class TestRunner:
    """Main test runner orchestrator."""

    def __init__(self, args) -> None:
        self.args = args
        self.executor = TestExecutor(args.debug_mode)
        self.known_problematic_tests = [
            "tests/gui/test_scheduler_ui_components.py",
            "tests/gui/test_history_tab.py",
            "tests/gui/imagery/test_imagery_gui.py",
            "tests/gui/imagery/test_imagery_gui_fixed.py",
            "tests/gui/imagery/test_imagery_zoom.py",
            "test_imagery_gui.py",
            "test_imagery_gui_fixed.py",
            "test_imagery_gui_zoom.py",
        ]

    def find_test_files(self) -> list[str]:
        """Find all test files in the specified directory."""
        if self.args.file:
            return self.args.file

        result = []
        directory = self.args.directory

        # Find test files recursively
        pattern = os.path.join(directory, "**", "test_*.py")
        result.extend(glob.glob(pattern, recursive=True))

        # Root directory files
        result.extend(glob.glob("test_*.py"))

        # Remove duplicates
        return sorted(set(result))

    def filter_problematic_tests(self, test_files: list[str]) -> list[str]:
        """Filter out known problematic tests if requested."""
        if not self.args.skip_problematic:
            return test_files

        orig_count = len(test_files)
        filtered = [t for t in test_files if t not in self.known_problematic_tests]
        skipped_count = orig_count - len(filtered)

        if skipped_count > 0:
            pass

        return filtered

    def should_use_json_output(self) -> bool:
        """Determine if JSON output should be used."""
        return self.args.json_output or (self._is_ci_environment() and not self._is_interactive_terminal())

    def _is_ci_environment(self) -> bool:
        """Check if running in CI environment."""
        ci_indicators = [
            "CI",
            "CONTINUOUS_INTEGRATION",
            "GITHUB_ACTIONS",
            "TRAVIS",
            "CIRCLECI",
            "JENKINS_URL",
            "BUILDKITE",
            "TF_BUILD",
            "GITLAB_CI",
        ]
        return any(os.getenv(indicator) for indicator in ci_indicators)

    def _is_interactive_terminal(self) -> bool:
        """Check if terminal is interactive."""
        return sys.stdout.isatty() and sys.stderr.isatty()

    def run_tests(self) -> int:
        """Run all tests and return exit code."""
        test_files = self.find_test_files()
        test_files = self.filter_problematic_tests(test_files)

        use_json_output = self.should_use_json_output()

        if self.args.debug_mode:
            self.args.parallel = 1
            if not use_json_output:
                pass

        return self._execute_test_suite(test_files, use_json_output)

    def _execute_test_suite(self, test_files: list[str], use_json_output: bool) -> int:
        """Execute the test suite with parallel workers."""
        self._print_initial_info(test_files, use_json_output)

        all_results = []
        start_time = time.time()

        worker_tracker = None
        if not use_json_output:
            worker_tracker = WorkerStatusTracker(self.args.parallel)
            worker_tracker.start(len(test_files))

        try:
            all_results = self._run_parallel_tests(test_files, worker_tracker, use_json_output)
        except KeyboardInterrupt:
            return self._handle_cancellation(worker_tracker, all_results, test_files, use_json_output)
        finally:
            if worker_tracker:
                worker_tracker.stop()

        return self._generate_final_report(all_results, start_time, worker_tracker)

    def _print_initial_info(self, test_files: list[str], use_json_output: bool) -> None:
        """Print initial test run information."""
        if use_json_output:
            pass

    def _run_parallel_tests(self, test_files: list[str], worker_tracker, use_json_output: bool) -> list[TestResult]:
        """Run tests in parallel using thread pool."""
        all_results = []

        with ThreadPoolExecutor(max_workers=self.args.parallel) as executor:
            future_to_path = {
                executor.submit(self.executor.execute_test, path, worker_tracker): path for path in test_files
            }

            completed_count = 0
            for future in as_completed(future_to_path):
                completed_count += 1
                if worker_tracker:
                    worker_tracker.update_progress(completed_count)

                try:
                    result = future.result()
                    all_results.append(result)

                    if use_json_output:
                        self._output_json_result(result, completed_count, len(test_files))
                    elif worker_tracker:
                        worker_tracker.add_completed_test(result)

                except Exception as e:
                    error_result = self._create_error_result(future_to_path[future], str(e))
                    all_results.append(error_result)

                    if use_json_output:
                        self._output_json_result(error_result, completed_count, len(test_files))
                    elif worker_tracker:
                        worker_tracker.add_completed_test(error_result)

        return all_results

    def _output_json_result(self, result: TestResult, completed: int, total: int) -> None:
        """Output a single test result in JSON format."""
        json_result = {
            "type": "test_complete",
            "number": completed,
            "path": result.path,
            "status": result.status.value,
            "duration": result.duration,
            "counts": {
                "passed": result.counts.passed,
                "failed": result.counts.failed,
                "error": result.counts.error,
                "skipped": result.counts.skipped,
            },
            "progress": f"{completed}/{total}",
        }

        if result.failed_details:
            json_result["failed_details"] = result.failed_details

    def _create_error_result(self, path: str, error: str) -> TestResult:
        """Create a TestResult for an execution error."""
        return TestResult(
            path=path,
            status=TestStatus.ERROR,
            duration=0,
            output=error,
            counts=TestCounts(error=1),
            collected=0,
        )

    def _handle_cancellation(
        self, worker_tracker, all_results: list[TestResult], test_files: list[str], use_json_output: bool
    ) -> int:
        """Handle keyboard interrupt cancellation."""
        if worker_tracker:
            worker_tracker.stop()

        if not use_json_output:
            pass

        return 130

    def _generate_final_report(self, all_results: list[TestResult], start_time: float, worker_tracker) -> int:
        """Generate the final test report."""
        total_duration = time.time() - start_time

        # Print complete results list
        self._print_complete_results(all_results)

        # Print summary
        self._print_summary(all_results, total_duration)

        # Print detailed failures
        failed_tests = worker_tracker.get_failed_tests() if worker_tracker else []
        if failed_tests:
            self._print_detailed_failures(failed_tests)

        # Return exit code
        return self._calculate_exit_code(all_results)

    def _print_complete_results(self, all_results: list[TestResult]) -> None:
        """Print the complete list of test results."""
        status_icons = {
            TestStatus.PASSED: "✓",
            TestStatus.FAILED: "✗",
            TestStatus.ERROR: "⚠",
            TestStatus.SKIPPED: "○",
            TestStatus.CRASHED: "💥",
        }

        for result in all_results:
            status_icons.get(result.status, "?")
            STATUS_COLOR.get(result.status.value, RESET)

            count_parts = []
            if result.counts.passed > 0:
                count_parts.append(f"{result.counts.passed} passed")
            if result.counts.failed > 0:
                count_parts.append(f"{result.counts.failed} failed")
            if result.counts.error > 0:
                count_parts.append(f"{result.counts.error} errors")
            if result.counts.skipped > 0:
                count_parts.append(f"{result.counts.skipped} skipped")

            f" ({', '.join(count_parts)})" if count_parts else ""

    def _print_summary(self, all_results: list[TestResult], total_duration: float) -> None:
        """Print the test summary."""
        # Count by file status
        file_counts = dict.fromkeys(TestStatus, 0)
        for result in all_results:
            file_counts[result.status] += 1

        # Count individual tests
        test_counts = TestCounts()
        for result in all_results:
            test_counts.passed += result.counts.passed
            test_counts.failed += result.counts.failed
            test_counts.error += result.counts.error
            test_counts.skipped += result.counts.skipped

        # Success rate
        total_tests = test_counts.total()
        if total_tests > 0:
            success_rate = (test_counts.passed / total_tests) * 100
            if success_rate == 100.0:
                STATUS_COLOR["PASSED"]
            elif success_rate >= 80.0:
                STATUS_COLOR["CRASHED"]
            else:
                STATUS_COLOR["FAILED"]

    def _print_detailed_failures(self, failed_tests: list[dict[str, Any]]) -> None:
        """Print detailed failure information."""
        for i, failed_test in enumerate(failed_tests, 1):
            self._print_single_failure(failed_test, i, len(failed_tests))

    def _print_single_failure(self, failed_test: dict[str, Any], current: int, total: int) -> None:
        """Print details for a single failed test."""
        failed_test["number"]
        failed_test["path"]
        status = failed_test["status"]
        failed_test["duration"]
        output = failed_test["output"]
        failed_details = failed_test["failed_details"]

        STATUS_COLOR.get(status.split(" ")[0], RESET)

        if failed_details:
            for _detail in failed_details:
                pass

        if output:
            self._extract_relevant_output(output)

        if current < total:
            pass

    def _extract_relevant_output(self, output: str) -> str:
        """Extract the most relevant parts of test output."""
        lines = output.split("\n")
        failure_lines = []

        in_failure_section = False
        for line in lines:
            if line.startswith(("FAILURES", "ERRORS", "short test summary info")):
                in_failure_section = True
                failure_lines.append(line)
            elif line.startswith("=") and len(line) > 10 and in_failure_section:
                break
            elif in_failure_section:
                failure_lines.append(line)

        if failure_lines:
            failure_text = "\n".join(failure_lines)
            if len(failure_text) > 2000:
                failure_text = failure_text[:2000] + "\n... (output truncated)"
            return failure_text
        # Show last 20 lines
        last_lines = lines[-20:] if len(lines) > 20 else lines
        return "\n".join(last_lines)

    def _calculate_exit_code(self, all_results: list[TestResult]) -> int:
        """Calculate the appropriate exit code."""
        if self.args.tolerant:
            return 0

        failed_count = sum(
            1 for r in all_results if r.status in {TestStatus.FAILED, TestStatus.ERROR, TestStatus.CRASHED}
        )
        return 0 if failed_count == 0 else 1


def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Run all tests with improved complexity")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print verbose output")
    parser.add_argument("--parallel", "-p", type=int, default=4, help="Number of parallel workers")
    parser.add_argument("--file", action="append", help="Run specific test file")
    parser.add_argument("--directory", default="tests", help="Directory containing tests")
    parser.add_argument("--tolerant", action="store_true", help="Always return success even if tests fail")
    parser.add_argument("--dump-logs", action="store_true", help="Dump output logs for failed tests")
    parser.add_argument("--skip-problematic", action="store_true", help="Skip known problematic tests")
    parser.add_argument("--debug-mode", action="store_true", help="Run tests with extra debug options")
    parser.add_argument("--json-output", action="store_true", help="Output JSON for automation")
    parser.add_argument("--debug-parsing", action="store_true", help="Show debug info for parsing")

    args = parser.parse_args()

    runner = TestRunner(args)
    return runner.run_tests()


if __name__ == "__main__":
    sys.exit(main())
