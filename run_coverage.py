#!/usr/bin/env python3
"""Code Coverage Runner for GOES_VFI.

This script runs tests with coverage measurement and generates reports.
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


class CoverageRunner:
    """Manages code coverage execution and reporting."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.coverage_file = repo_root / ".coverage"
        self.htmlcov_dir = repo_root / "htmlcov"
        self.coverage_xml = repo_root / "coverage.xml"
        self.coverage_json = repo_root / "coverage.json"

    def clean_coverage_data(self) -> None:
        """Clean existing coverage data."""
        # Remove coverage data file
        if self.coverage_file.exists():
            self.coverage_file.unlink()

        # Remove HTML coverage directory
        if self.htmlcov_dir.exists():
            shutil.rmtree(self.htmlcov_dir)

        # Remove XML report
        if self.coverage_xml.exists():
            self.coverage_xml.unlink()

        # Remove JSON report
        if self.coverage_json.exists():
            self.coverage_json.unlink()

    def install_coverage_tools(self) -> bool:
        """Install coverage tools if not present."""
        try:
            import coverage  # noqa: F401
            import pytest_cov  # noqa: F401

            return True
        except ImportError:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "coverage[toml]",
                    "pytest-cov",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            return result.returncode == 0

    def run_coverage(
        self,
        test_paths: list[str] | None = None,
        markers: str | None = None,
        parallel: bool = False,
    ) -> bool:
        """Run tests with coverage measurement."""
        # Build pytest command
        cmd = [sys.executable, "-m", "pytest", "-c", "pytest-coverage.ini"]

        # Add test paths if specified
        if test_paths:
            cmd.extend(test_paths)

        # Add markers if specified
        if markers:
            cmd.extend(["-m", markers])

        # Add parallel execution if requested
        if parallel:
            cmd.extend(["-n", "auto"])

        # Set environment variables
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.repo_root)
        env["COVERAGE_CORE"] = "sysmon"  # Use sysmon for better branch coverage

        # Run pytest with coverage
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)

        # Print output
        if result.stderr:
            pass

        # Check if tests actually failed or just coverage threshold
        # pytest-cov returns 1 if coverage is below threshold even if tests pass
        tests_failed = "FAILED" in result.stdout or "ERRORS" in result.stdout

        return not tests_failed  # Return True if tests didn't fail

    def generate_reports(self) -> dict[str, Any]:
        """Generate coverage reports in various formats."""
        reports = {}

        # Generate terminal report
        subprocess.run([sys.executable, "-m", "coverage", "report", "--rcfile=.coveragerc"], check=False)

        # Generate HTML report
        subprocess.run(
            [sys.executable, "-m", "coverage", "html", "--rcfile=.coveragerc"],
            capture_output=True,
            text=True,
            check=False,
        )

        if self.htmlcov_dir.exists() and (self.htmlcov_dir / "index.html").exists():
            reports["html"] = str(self.htmlcov_dir / "index.html")

        # Generate XML report (for CI/CD integration)
        subprocess.run(
            [sys.executable, "-m", "coverage", "xml", "--rcfile=.coveragerc"],
            capture_output=True,
            text=True,
            check=False,
        )

        if self.coverage_xml.exists():
            reports["xml"] = str(self.coverage_xml)

        # Generate JSON report
        subprocess.run(
            [sys.executable, "-m", "coverage", "json", "--rcfile=.coveragerc"],
            capture_output=True,
            text=True,
            check=False,
        )

        if self.coverage_json.exists():
            reports["json"] = str(self.coverage_json)

            # Parse and display summary
            self._display_json_summary()

        return reports

    def _display_json_summary(self) -> None:
        """Display coverage summary from JSON report."""
        try:
            with open(self.coverage_json, encoding="utf-8") as f:
                data = json.load(f)

            summary = data.get("totals", {})

            if "num_branches" in summary:
                (
                    (summary.get("num_branches", 0) - summary.get("num_partial_branches", 0))
                    / summary.get("num_branches", 1)
                    * 100
                )

        except Exception:
            pass

    def check_coverage_threshold(self, threshold: float = 80.0) -> bool:
        """Check if coverage meets the threshold."""
        try:
            with open(self.coverage_json, encoding="utf-8") as f:
                data = json.load(f)

            coverage_percent = data.get("totals", {}).get("percent_covered", 0)

            return coverage_percent >= threshold

        except Exception:
            return False

    def open_html_report(self) -> None:
        """Open HTML coverage report in browser."""
        import webbrowser

        html_index = self.htmlcov_dir / "index.html"
        if html_index.exists():
            webbrowser.open(f"file://{html_index.absolute()}")


def main() -> int:
    """Main function."""
    parser = argparse.ArgumentParser(description="Run tests with code coverage")
    parser.add_argument("test_paths", nargs="*", help="Specific test files or directories to run")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean existing coverage data before running",
    )
    parser.add_argument("--markers", "-m", help="Run tests matching given mark expression")
    parser.add_argument("--parallel", "-n", action="store_true", help="Run tests in parallel")
    parser.add_argument("--html", action="store_true", help="Generate HTML coverage report")
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open HTML report in browser after generation",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=80.0,
        help="Coverage threshold percentage (default: 80.0)",
    )
    parser.add_argument(
        "--no-fail",
        action="store_true",
        help="Don't fail if coverage is below threshold",
    )

    args = parser.parse_args()

    repo_root = Path(__file__).parent
    runner = CoverageRunner(repo_root)

    # Clean if requested
    if args.clean:
        runner.clean_coverage_data()

    # Install coverage tools if needed
    if not runner.install_coverage_tools():
        return 1

    # Run coverage
    success = runner.run_coverage(test_paths=args.test_paths, markers=args.markers, parallel=args.parallel)

    if not success:
        return 1

    # Generate reports
    reports = runner.generate_reports()

    # Check threshold
    if not args.no_fail and not runner.check_coverage_threshold(args.threshold):
        return 1

    # Open HTML report if requested
    if args.open and "html" in reports:
        runner.open_html_report()

    return 0


if __name__ == "__main__":
    sys.exit(main())
