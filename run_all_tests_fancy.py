#!/usr/bin/env python3
"""
Fancy test runner for the GOES VFI project with enhanced progress tracking.

This script runs tests with pytest using JSON reporting and provides
real-time progress visualization with worker status and test results.
"""

import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional


class Config:
    """Configuration for test runner."""
    # Colors for different statuses
    STATUS_COLORS = {
        "passed": "\033[92m",   # Green
        "failed": "\033[91m",   # Red
        "error": "\033[95m",    # Magenta
        "skipped": "\033[94m",  # Blue
        "crashed": "\033[93m",  # Yellow
    }
    RESET = "\033[0m"

    # Status icons
    STATUS_ICONS = {
        "passed": "✓",
        "failed": "✗",
        "error": "⚠",
        "skipped": "○",
        "crashed": "💥",
    }

    # Spinner animation frames
    SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']

    # Known problematic tests (configurable)
    PROBLEMATIC_TESTS = [
        "tests/gui/test_scheduler_ui_components.py",
        "tests/gui/test_history_tab.py",
        "tests/gui/imagery/test_imagery_gui.py",
        "tests/gui/imagery/test_imagery_gui_fixed.py",
        "tests/gui/imagery/test_imagery_zoom.py",
        "test_imagery_gui.py",
        "test_imagery_gui_fixed.py", 
        "test_imagery_gui_zoom.py",
    ]


class FancyProgressTracker:
    """Enhanced progress tracker with real-time display of worker status and test results."""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.frame = 0
        self.completed = 0
        self.total = 0
        self.active_tests: Dict[str, Dict[str, Any]] = {}
        self.completed_results: List[Dict[str, Any]] = []
        self.lock = threading.Lock()

        # Terminal optimization
        self.terminal_width, self.terminal_height = self._get_terminal_size()
        self.max_display_lines = min(8, max(3, (self.terminal_height - 10) // 2))  # Adaptive display size
        self.last_display_hash = None
        self.last_update_time = 0
        self.min_update_interval = 0.2  # Minimum time between updates
        self.current_display_lines = 0  # Track how many lines we're using

    def start(self, total_tests: int) -> None:
        """Start progress tracking."""
        with self.lock:
            self.running = True
            self.total = total_tests
            self.completed = 0
            self.active_tests = {}
            self.completed_results = []

        self.thread = threading.Thread(target=self._display_progress, daemon=True)
        self.thread.start()

    def update_active_test(self, worker_id: str, test_path: str) -> None:
        """Update what a worker is currently running."""
        with self.lock:
            self.active_tests[worker_id] = {
                'test_path': test_path,
                'start_time': time.time()
            }

    def complete_test(self, worker_id: str, result: Dict[str, Any]) -> None:
        """Mark a test as completed."""
        with self.lock:
            self.active_tests.pop(worker_id, None)
            self.completed_results.append(result)
            self.completed = len(self.completed_results)

    def stop(self) -> None:
        """Stop progress tracking and clean up display."""
        with self.lock:
            self.running = False
        if self.thread:
            self.thread.join()

        # Clean up display
        if self.current_display_lines > 0:
            print(f"\033[{self.current_display_lines}A", end="")
            for _ in range(self.current_display_lines):
                print("\033[2K")  # Clear line
        print()  # Add final newline

    def get_results(self) -> List[Dict[str, Any]]:
        """Get all completed results."""
        with self.lock:
            return list(self.completed_results)

    def _display_progress(self) -> None:
        """Display enhanced progress with adaptive refresh and reduced flicker."""
        while True:
            current_time = time.time()

            with self.lock:
                if not self.running:
                    break

                # Check if enough time has passed or if there's significant change
                if (current_time - self.last_update_time < self.min_update_interval and 
                    self.last_display_hash is not None):
                    time.sleep(0.1)
                    continue

                frame_char = Config.SPINNER_FRAMES[self.frame % len(Config.SPINNER_FRAMES)]
                completed = self.completed
                total = self.total
                active_tests = dict(self.active_tests)
                completed_results = list(self.completed_results)

            # Generate display content
            display_content = self._generate_display_content(
                frame_char, completed, total, active_tests, completed_results
            )

            # Check if content actually changed (avoid unnecessary updates)
            content_hash = hash(display_content)
            if content_hash == self.last_display_hash:
                time.sleep(0.1)
                continue

            # Update display efficiently
            self._update_display(display_content)

            self.last_display_hash = content_hash
            self.last_update_time = current_time
            self.frame += 1

            # Adaptive sleep based on activity
            sleep_time = 0.3 if len(active_tests) > 0 else 0.8
            time.sleep(sleep_time)

    def _get_terminal_size(self) -> tuple[int, int]:
        """Get terminal size with fallback defaults."""
        try:
            width, height = shutil.get_terminal_size()
            return min(width, 120), height  # Cap width to prevent line wrapping
        except:
            return 80, 24  # Fallback defaults

    def _generate_display_content(self, frame_char: str, completed: int, total: int, 
                                 active_tests: Dict[str, Dict[str, Any]], 
                                 completed_results: List[Dict[str, Any]]) -> str:
        """Generate the complete display content as a string."""
        lines = []

        # Header with overall progress
        progress_pct = (completed / total * 100) if total > 0 else 0
        progress_bar = self._create_progress_bar(completed, total, min(30, self.terminal_width // 4))
        lines.append(f"📊 {frame_char} {progress_bar} {completed}/{total} ({progress_pct:.1f}%)")

        # Recent completed tests (with detailed counts)
        if completed_results:
            recent_count = min(self.max_display_lines, len(completed_results))
            lines.append(f"📋 Recent ({recent_count}):")

            # Show only the most recent tests with detailed count formatting
            start_idx = max(0, len(completed_results) - recent_count)
            for i in range(start_idx, len(completed_results)):
                result = completed_results[i]
                status = result['status']
                path = result['path']
                duration = result['duration']
                counts = result['counts']
                test_number = i + 1

                icon = Config.STATUS_ICONS.get(status, '?')
                color = Config.STATUS_COLORS.get(status, Config.RESET)
                display_path = self._shorten_path(path, min(35, self.terminal_width - 45))

                # Build detailed count string
                count_parts = []
                for status_name in ['passed', 'failed', 'error', 'skipped']:
                    count = counts.get(status_name, 0)
                    if count > 0:
                        count_parts.append(f"{count} {status_name}")

                count_str = f"({', '.join(count_parts)})" if count_parts else "(0 tests)"

                lines.append(f"  [{test_number:3d}] {color}{icon} {display_path} {count_str} {duration:.1f}s{Config.RESET}")

        # Active workers (condensed)
        if active_tests:
            lines.append(f"🔄 Active ({len(active_tests)}/{self.max_workers}):")
            current_time = time.time()
            worker_list = list(active_tests.items())
            worker_list.sort(key=lambda x: x[1]['start_time'])

            for worker_id, test_info in worker_list[:self.max_workers]:
                test_path = test_info['test_path']
                duration = current_time - test_info['start_time']

                display_path = self._shorten_path(test_path, min(40, self.terminal_width - 20))

                if duration > 20:
                    status_icon = "🐌"
                elif duration > 8:
                    status_icon = "⏱️"
                else:
                    status_icon = "⚡"

                lines.append(f"  {status_icon} {display_path} ({duration:.0f}s)")

        return "\n".join(lines)

    def _update_display(self, content: str) -> None:
        """Update display efficiently with minimal cursor movement."""
        lines = content.split('\n')
        new_line_count = len(lines)

        # Clear previous content if needed
        if self.current_display_lines > 0:
            # Move cursor up to start of our content
            print(f"\033[{self.current_display_lines}A", end="")
            # Clear each line
            for _ in range(self.current_display_lines):
                print(f"\033[2K\n", end="")  # Clear line and move to next
            # Move cursor back to start
            print(f"\033[{self.current_display_lines}A", end="")

        # Print new content
        for line in lines:
            # Truncate line if it's too long for terminal
            if len(line) > self.terminal_width:
                line = line[:self.terminal_width-3] + "..."
            print(line)

        self.current_display_lines = new_line_count

    def _create_progress_bar(self, completed: int, total: int, width: int = 30) -> str:
        """Create a visual progress bar."""
        if total == 0:
            return "█" * width

        filled = int((completed / total) * width)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}]"

    def get_status_summary(self, results: List[Dict[str, Any]]) -> str:
        """Get a compact status summary."""
        status_counts = {'passed': 0, 'failed': 0, 'error': 0, 'skipped': 0}
        for result in results:
            status = result['status']
            status_counts[status] = status_counts.get(status, 0) + 1

        summary_parts = []
        for status in ['passed', 'failed', 'error', 'skipped']:
            count = status_counts.get(status, 0)
            if count > 0:
                color = Config.STATUS_COLORS.get(status, Config.RESET)
                icon = Config.STATUS_ICONS.get(status, '?')
                summary_parts.append(f"{color}{icon}{count}{Config.RESET}")

        return ' '.join(summary_parts) if summary_parts else 'None'


    def _shorten_path(self, path: str, max_length: int) -> str:
        """Intelligently shorten a file path for display."""
        if len(path) <= max_length:
            return path

        # Try to keep the filename and relevant parent directories
        parts = path.split('/')
        if len(parts) > 1:
            filename = parts[-1]

            # If just the filename is too long, truncate it
            if len(filename) >= max_length - 3:
                return "..." + filename[-(max_length-3):]

            # Try to keep meaningful directory structure
            for i in range(len(parts) - 2, -1, -1):
                candidate_path = '/'.join(parts[i:])
                if len(candidate_path) <= max_length:
                    return candidate_path
                # Keep tests/ and other important prefixes
                if parts[i] in ['tests', 'goesvfi', 'src'] and i > 0:
                    candidate_with_ellipsis = f".../{'/'.join(parts[i:])}"
                    if len(candidate_with_ellipsis) <= max_length:
                        return candidate_with_ellipsis

            return "..." + filename

        return "..." + path[-(max_length-3):]


def run_test_with_json(test_path: str, debug_mode: bool = False, progress_tracker: Optional[FancyProgressTracker] = None) -> Dict[str, Any]:
    """Run a single test file with pytest JSON reporting.

    Args:
        test_path: Path to the test file
        debug_mode: Whether to run with extra debug options
        progress_tracker: Optional progress tracker for UI updates

    Returns:
        Dict with test results
    """
    script_dir = Path(__file__).parent
    venv_python = script_dir / ".venv" / "bin" / "python"

    # Create temporary file for JSON report
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as json_file:
        json_report_path = json_file.name

    # Build pytest command with JSON reporting
    cmd = [
        str(venv_python), "-m", "pytest", 
        test_path, 
        "--json-report", 
        f"--json-report-file={json_report_path}",
        "-v", 
        "-p", "no:cov"  # Disable coverage to avoid import issues
    ]

    # Add debug options if requested
    if debug_mode:
        cmd.extend([
            "--log-cli-level=DEBUG",
            "-s",  # Don't capture stdout/stderr
            "--showlocals",
        ])

        # Set debug environment variables
        env = os.environ.copy()
        env["FILE_COPY_DEBUG"] = "1"
        env["PYTHONVERBOSE"] = "1"
    else:
        env = None

    start_time = time.time()
    worker_id = str(threading.get_ident())

    # Update progress tracker
    if progress_tracker:
        progress_tracker.update_active_test(worker_id, test_path)

    try:
        # Run pytest with JSON reporting
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            env=env
        )

        duration = time.time() - start_time
        stdout = result.stdout
        stderr = result.stderr

        # Parse JSON report
        try:
            with open(json_report_path, 'r') as f:
                json_data = json.load(f)

            # Extract test results from JSON
            summary = json_data.get('summary', {})
            tests = json_data.get('tests', [])

            # Count results
            counts = {
                'passed': summary.get('passed', 0),
                'failed': summary.get('failed', 0),
                'error': summary.get('error', 0),
                'skipped': summary.get('skipped', 0),
            }

            # Determine overall status
            if counts['failed'] > 0:
                status = 'failed'
            elif counts['error'] > 0:
                status = 'error'
            elif counts['passed'] > 0:
                status = 'passed'
            elif counts['skipped'] > 0:
                status = 'skipped'
            else:
                status = 'error'  # Fallback

            # Extract failed test details
            failed_details = []
            for test in tests:
                if test.get('outcome') in ['failed', 'error']:
                    test_name = test.get('nodeid', '').split('::')[-1]
                    failed_details.append(f"{test.get('outcome', 'unknown').upper()} {test_name}")

            test_result = {
                'path': test_path,
                'status': status,
                'duration': duration,
                'counts': counts,
                'failed_details': failed_details,
                'json_data': json_data,  # Keep full JSON for detailed reporting
                'stdout': stdout,
                'stderr': stderr
            }

        except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
            # Fallback to basic parsing if JSON fails
            test_result = {
                'path': test_path,
                'status': 'error',
                'duration': duration,
                'counts': {'error': 1, 'passed': 0, 'failed': 0, 'skipped': 0},
                'failed_details': [f'JSON parsing error: {str(e)}'],
                'stdout': stdout,
                'stderr': stderr
            }

        # Clean up temporary JSON file
        try:
            os.unlink(json_report_path)
        except OSError:
            pass

        # Update progress tracker with completed result
        if progress_tracker:
            progress_tracker.complete_test(worker_id, test_result)

        return test_result

    except Exception as e:
        duration = time.time() - start_time
        test_result = {
            'path': test_path,
            'status': 'error',
            'duration': duration,
            'counts': {'error': 1, 'passed': 0, 'failed': 0, 'skipped': 0},
            'failed_details': [f'Execution error: {str(e)}'],
            'stdout': '',
            'stderr': str(e)
        }

        # Update progress tracker with error result
        if progress_tracker:
            progress_tracker.complete_test(worker_id, test_result)

        return test_result


def find_test_files(directory: str = "tests") -> List[str]:
    """Find all test files in the given directory."""
    result = []

    # Find all test files recursively in the main tests directory
    pattern = os.path.join(directory, "**", "test_*.py")
    result.extend(glob.glob(pattern, recursive=True))

    # Also look for any remaining test files in the root directory
    root_pattern = "test_*.py"
    result.extend(glob.glob(root_pattern))

    # Remove duplicates while preserving order
    unique_result = []
    seen = set()
    for item in result:
        if item not in seen:
            seen.add(item)
            unique_result.append(item)

    return sorted(unique_result)


def print_smart_summary(all_results: List[Dict[str, Any]], terminal_width: int = 80) -> None:
    """Print an intelligent summary that adapts to terminal and human needs."""
    if not all_results:
        return

    # Calculate statistics
    failed_results = [r for r in all_results if r['status'] in ['failed', 'error']]
    total_duration = sum(r['duration'] for r in all_results)

    # Count files by status
    file_counts = {'passed': 0, 'failed': 0, 'error': 0, 'skipped': 0}
    test_counts = {'passed': 0, 'failed': 0, 'error': 0, 'skipped': 0}

    for result in all_results:
        status = result['status']
        file_counts[status] = file_counts.get(status, 0) + 1
        counts = result['counts']
        for key in test_counts:
            test_counts[key] += counts.get(key, 0)

    # Header
    sep_line = "═" * min(terminal_width, 80)
    print(f"\n{sep_line}")
    print(f"🏁 TEST SESSION COMPLETE ({total_duration:.1f}s)")
    print(f"{sep_line}")

    # Quick status overview
    total_files = len(all_results)
    success_files = file_counts['passed']
    total_tests = sum(test_counts.values())
    success_tests = test_counts['passed']

    # File-level summary
    file_success_rate = (success_files / total_files * 100) if total_files > 0 else 0
    test_success_rate = (success_tests / total_tests * 100) if total_tests > 0 else 0

    if file_success_rate == 100.0:
        status_emoji = "🎉"
        status_color = Config.STATUS_COLORS['passed']
    elif file_success_rate >= 80.0:
        status_emoji = "⚠️"
        status_color = Config.STATUS_COLORS['crashed']
    else:
        status_emoji = "❌"
        status_color = Config.STATUS_COLORS['failed']

    print(f"{status_emoji} {status_color}Files: {success_files}/{total_files} passed ({file_success_rate:.1f}%){Config.RESET}")
    print(f"📊 Tests: {success_tests}/{total_tests} passed ({test_success_rate:.1f}%)")

    # Show problem files if any
    if failed_results:
        print(f"\n🚨 {Config.STATUS_COLORS['failed']}FAILED FILES ({len(failed_results)}):{Config.RESET}")
        for i, result in enumerate(failed_results[:10], 1):  # Limit to 10 worst
            path = result['path']
            status = result['status']
            duration = result['duration']
            counts = result['counts']

            # Show compact failure info
            icon = Config.STATUS_ICONS.get(status, '?')
            color = Config.STATUS_COLORS.get(status, Config.RESET)

            # Build failure summary
            failure_parts = []
            if counts.get('failed', 0) > 0:
                failure_parts.append(f"{counts['failed']} failed")
            if counts.get('error', 0) > 0:
                failure_parts.append(f"{counts['error']} errors")

            failure_summary = f" ({', '.join(failure_parts)})" if failure_parts else ""

            # Shorten path for display
            max_path_len = min(50, terminal_width - 30)
            display_path = _shorten_path_simple(path, max_path_len)

            print(f"  {i:2d}. {color}{icon} {display_path}{failure_summary} {duration:.1f}s{Config.RESET}")

        if len(failed_results) > 10:
            print(f"  ... and {len(failed_results) - 10} more failed files")

    print(f"{sep_line}")

def _shorten_path_simple(path: str, max_length: int) -> str:
    """Simple path shortening for summary display."""
    if len(path) <= max_length:
        return path

    parts = path.split('/')
    if len(parts) > 1:
        filename = parts[-1]
        if len(filename) < max_length - 3:
            # Try to keep important directories
            for i in range(len(parts) - 2, -1, -1):
                if parts[i] in ['tests', 'goesvfi'] or i == 0:
                    candidate = '/'.join(parts[i:])
                    if len(candidate) <= max_length:
                        return candidate
                    return f".../{'/'.join(parts[i:])}"
        return "..." + filename

    return "..." + path[-(max_length-3):]


def is_ci_environment():
    """Detect if we're running in a CI environment."""
    ci_indicators = [
        'CI', 'CONTINUOUS_INTEGRATION', 'GITHUB_ACTIONS', 'TRAVIS', 'CIRCLECI',
        'JENKINS_URL', 'BUILDKITE', 'TF_BUILD', 'GITLAB_CI'
    ]
    return any(os.getenv(indicator) for indicator in ci_indicators)


def should_use_json_output(args):
    """Determine if we should use JSON output."""
    return args.json_output or is_ci_environment()


def main():
    """Run all tests with fancy progress visualization."""
    import argparse

    parser = argparse.ArgumentParser(description="Run all tests with enhanced progress tracking")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print verbose output")
    parser.add_argument("--parallel", "-p", type=int, default=4, help="Number of parallel workers")
    parser.add_argument("--file", action="append", help="Run specific test file")
    parser.add_argument("--directory", default="tests", help="Directory containing tests")
    parser.add_argument("--tolerant", action="store_true", help="Always return success (0) even if tests fail")
    parser.add_argument("--skip-problematic", action="store_true", help="Skip known problematic tests")
    parser.add_argument("--debug-mode", action="store_true", help="Run tests with extra debug options")
    parser.add_argument("--json-output", action="store_true", help="Output JSON lines for automation")

    args = parser.parse_args()

    # Find test files
    if args.file:
        test_files = args.file
    else:
        test_files = find_test_files(args.directory)

    # Filter out problematic tests if requested
    if args.skip_problematic:
        orig_count = len(test_files)
        test_files = [t for t in test_files if t not in Config.PROBLEMATIC_TESTS]
        skipped_count = orig_count - len(test_files)
        if skipped_count > 0:
            print(f"Skipping {skipped_count} known problematic tests")

    # Determine output mode
    use_json_output = should_use_json_output(args)

    if use_json_output:
        print(json.dumps({
            "type": "test_session_start",
            "total_tests": len(test_files),
            "workers": args.parallel,
            "mode": "json_output"
        }))
    else:
        print(f"🎯 Found {len(test_files)} test files")

    # Track results
    all_results = []
    start_time = time.time()

    # If debug mode is enabled, limit parallelism to 1
    if args.debug_mode:
        args.parallel = 1
        if not use_json_output:
            print(f"{Config.STATUS_COLORS['crashed']}🔧 Debug mode enabled - running tests sequentially{Config.RESET}")

    if not use_json_output:
        terminal_width = 80
        try:
            terminal_width, _ = shutil.get_terminal_size()
            terminal_width = min(terminal_width, 120)
        except:
            pass

        sep_line = "═" * min(terminal_width, 80)
        print(f"{sep_line}")
        print(f"🚀 RUNNING {len(test_files)} TESTS WITH {args.parallel} WORKERS")
        print(f"{sep_line}")
        print()  # Extra space before progress display starts

    # Start progress tracker (only for interactive mode)
    progress_tracker = None
    if not use_json_output:
        progress_tracker = FancyProgressTracker(args.parallel)
        progress_tracker.start(len(test_files))

    # Run tests in parallel with graceful cancellation
    cancelled = False
    running_futures = set()

    try:
        with ThreadPoolExecutor(max_workers=args.parallel) as executor:
            # Submit all tests
            future_to_path = {executor.submit(run_test_with_json, path, args.debug_mode, progress_tracker): path for path in test_files}
            running_futures = set(future_to_path.keys())
            completed_count = 0

            for future in as_completed(future_to_path):
                path = future_to_path[future]
                completed_count += 1
                running_futures.discard(future)

                try:
                    result = future.result()
                    all_results.append(result)

                    if use_json_output:
                        # Output JSON line for automation
                        json_result = {
                            "type": "test_complete",
                            "number": completed_count,
                            "path": result["path"],
                            "status": result["status"],
                            "duration": result["duration"],
                            "counts": result["counts"],
                            "progress": f"{completed_count}/{len(test_files)}"
                        }
                        if result.get("failed_details"):
                            json_result["failed_details"] = result["failed_details"]
                        print(json.dumps(json_result))

                except Exception as e:
                    error_result = {
                        "path": path,
                        "status": "error",
                        "duration": 0,
                        "counts": {"error": 1, "passed": 0, "failed": 0, "skipped": 0},
                        "failed_details": [f"Execution error: {str(e)}"],
                        "stdout": "",
                        "stderr": str(e)
                    }
                    all_results.append(error_result)

                    if use_json_output:
                        json_result = {
                            "type": "test_complete",
                            "number": completed_count,
                            "path": error_result["path"],
                            "status": error_result["status"],
                            "duration": error_result["duration"],
                            "counts": error_result["counts"],
                            "progress": f"{completed_count}/{len(test_files)}"
                        }
                        print(json.dumps(json_result))

    except KeyboardInterrupt:
        cancelled = True
        if progress_tracker:
            progress_tracker.stop()

        if use_json_output:
            print(json.dumps({
                "type": "test_session_cancelled",
                "completed": len(all_results),
                "total": len(test_files)
            }))
        else:
            print(f"\n{Config.STATUS_COLORS['crashed']}🛑 Testing cancelled by user (Ctrl+C){Config.RESET}")
            print(f"Completed {len(all_results)}/{len(test_files)} tests before cancellation")

        # Cancel remaining futures
        remaining_count = len(running_futures)
        if remaining_count > 0 and not use_json_output:
            print(f"Cancelling {remaining_count} running tests...")
            for future in running_futures:
                future.cancel()

        return 130  # Standard exit code for Ctrl+C

    # Stop the progress tracker
    if progress_tracker:
        progress_tracker.stop()

    # Extract failed tests from results
    failed_results = [
        result for result in all_results 
        if result["status"] in ["failed", "error"] or 
           result.get("counts", {}).get("failed", 0) > 0 or 
           result.get("counts", {}).get("error", 0) > 0
    ]

    # If cancelled, skip the normal summary
    if cancelled:
        return 130

    # Calculate summary
    total_duration = time.time() - start_time

    # Count files by status
    file_counts = {'passed': 0, 'failed': 0, 'error': 0, 'skipped': 0}
    for result in all_results:
        status = result['status']
        file_counts[status] = file_counts.get(status, 0) + 1

    # Count individual tests
    test_counts = {'passed': 0, 'failed': 0, 'error': 0, 'skipped': 0}
    for result in all_results:
        counts = result['counts']
        for key in test_counts:
            test_counts[key] += counts.get(key, 0)

    # Use smart summary instead of verbose output
    terminal_width = 80
    try:
        terminal_width, _ = shutil.get_terminal_size()
        terminal_width = min(terminal_width, 120)
    except:
        pass

    print_smart_summary(all_results, terminal_width)

    # Return non-zero exit code if there were failures or errors
    if args.tolerant:
        return 0
    else:
        return 0 if file_counts['failed'] + file_counts['error'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())