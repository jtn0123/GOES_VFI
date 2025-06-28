#!/usr/bin/env python3
"""
Code Coverage Runner for GOES_VFI

This script runs tests with coverage measurement and generates reports.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


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
        print("🧹 Cleaning existing coverage data...")

        # Remove coverage data file
        if self.coverage_file.exists():
            self.coverage_file.unlink()
            print("  ✓ Removed .coverage")

        # Remove HTML coverage directory
        if self.htmlcov_dir.exists():
            shutil.rmtree(self.htmlcov_dir)
            print("  ✓ Removed htmlcov/")

        # Remove XML report
        if self.coverage_xml.exists():
            self.coverage_xml.unlink()
            print("  ✓ Removed coverage.xml")

        # Remove JSON report
        if self.coverage_json.exists():
            self.coverage_json.unlink()
            print("  ✓ Removed coverage.json")

    def install_coverage_tools(self) -> bool:
        """Install coverage tools if not present."""
        print("📦 Checking coverage tools...")

        try:
            import coverage  # noqa: F401
            import pytest_cov  # noqa: F401

            print("  ✓ Coverage tools already installed")
            return True
        except ImportError:
            print("  ⚠️  Installing coverage tools...")
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
            )

            if result.returncode == 0:
                print("  ✓ Coverage tools installed successfully")
                return True
            else:
                print(f"  ✗ Failed to install coverage tools: {result.stderr}")
                return False

    def run_coverage(
        self,
        test_paths: list[str] | None = None,
        markers: str | None = None,
        parallel: bool = False,
    ) -> bool:
        """Run tests with coverage measurement."""
        print("🧪 Running tests with coverage...")

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
        print(f"  Command: {' '.join(cmd)}")
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)

        # Print output
        print(result.stdout)
        if result.stderr:
            print(result.stderr)

        # Check if tests actually failed or just coverage threshold
        # pytest-cov returns 1 if coverage is below threshold even if tests pass
        tests_failed = "FAILED" in result.stdout or "ERRORS" in result.stdout

        return not tests_failed  # Return True if tests didn't fail

    def generate_reports(self) -> dict[str, Any]:
        """Generate coverage reports in various formats."""
        print("📊 Generating coverage reports...")

        reports = {}

        # Generate terminal report
        print("  📋 Terminal report:")
        subprocess.run(
            [sys.executable, "-m", "coverage", "report", "--rcfile=.coveragerc"]
        )

        # Generate HTML report
        print("  🌐 Generating HTML report...")
        result = subprocess.run(
            [sys.executable, "-m", "coverage", "html", "--rcfile=.coveragerc"],
            capture_output=True,
            text=True,
        )

        if self.htmlcov_dir.exists() and (self.htmlcov_dir / "index.html").exists():
            print(f"  ✓ HTML report generated at: {self.htmlcov_dir}/index.html")
            reports["html"] = str(self.htmlcov_dir / "index.html")
        else:
            print(f"  ✗ Failed to generate HTML report: {result.stderr}")

        # Generate XML report (for CI/CD integration)
        print("  📄 Generating XML report...")
        result = subprocess.run(
            [sys.executable, "-m", "coverage", "xml", "--rcfile=.coveragerc"],
            capture_output=True,
            text=True,
        )

        if self.coverage_xml.exists():
            print(f"  ✓ XML report generated at: {self.coverage_xml}")
            reports["xml"] = str(self.coverage_xml)
        else:
            print(f"  ✗ Failed to generate XML report: {result.stderr}")

        # Generate JSON report
        print("  📊 Generating JSON report...")
        result = subprocess.run(
            [sys.executable, "-m", "coverage", "json", "--rcfile=.coveragerc"],
            capture_output=True,
            text=True,
        )

        if self.coverage_json.exists():
            print(f"  ✓ JSON report generated at: {self.coverage_json}")
            reports["json"] = str(self.coverage_json)

            # Parse and display summary
            self._display_json_summary()
        else:
            print(f"  ✗ Failed to generate JSON report: {result.stderr}")

        return reports

    def _display_json_summary(self) -> None:
        """Display coverage summary from JSON report."""
        try:
            with open(self.coverage_json, "r") as f:
                data = json.load(f)

            summary = data.get("totals", {})

            print("\n📈 Coverage Summary:")
            print(f"  • Statement coverage: {summary.get('percent_covered', 0):.2f}%")
            print(f"  • Statements: {summary.get('num_statements', 0)}")
            print(f"  • Missing: {summary.get('missing_lines', 0)}")
            print(f"  • Excluded: {summary.get('excluded_lines', 0)}")

            if "num_branches" in summary:
                branch_coverage = (
                    (
                        summary.get("num_branches", 0)
                        - summary.get("num_partial_branches", 0)
                    )
                    / summary.get("num_branches", 1)
                    * 100
                )
                print(f"  • Branch coverage: {branch_coverage:.2f}%")
                print(f"  • Branches: {summary.get('num_branches', 0)}")
                print(f"  • Partial: {summary.get('num_partial_branches', 0)}")

        except Exception as e:
            print(f"  ⚠️  Could not parse JSON report: {e}")

    def check_coverage_threshold(self, threshold: float = 80.0) -> bool:
        """Check if coverage meets the threshold."""
        try:
            with open(self.coverage_json, "r") as f:
                data = json.load(f)

            coverage_percent = data.get("totals", {}).get("percent_covered", 0)

            if coverage_percent >= threshold:
                print(
                    f"\n✅ Coverage {coverage_percent:.2f}% meets threshold of {threshold}%"
                )
                return True
            else:
                print(
                    f"\n❌ Coverage {coverage_percent:.2f}% is below threshold of {threshold}%"
                )
                return False

        except Exception as e:
            print(f"\n⚠️  Could not check coverage threshold: {e}")
            return False

    def open_html_report(self) -> None:
        """Open HTML coverage report in browser."""
        import webbrowser

        html_index = self.htmlcov_dir / "index.html"
        if html_index.exists():
            print("\n🌐 Opening coverage report in browser...")
            webbrowser.open(f"file://{html_index.absolute()}")
        else:
            print("\n⚠️  HTML report not found. Generate it first with --html")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Run tests with code coverage")
    parser.add_argument(
        "test_paths", nargs="*", help="Specific test files or directories to run"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean existing coverage data before running",
    )
    parser.add_argument(
        "--markers", "-m", help="Run tests matching given mark expression"
    )
    parser.add_argument(
        "--parallel", "-n", action="store_true", help="Run tests in parallel"
    )
    parser.add_argument(
        "--html", action="store_true", help="Generate HTML coverage report"
    )
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

    print("🔧 GOES_VFI Code Coverage Runner")
    print("=" * 50)

    repo_root = Path(__file__).parent
    runner = CoverageRunner(repo_root)

    # Clean if requested
    if args.clean:
        runner.clean_coverage_data()

    # Install coverage tools if needed
    if not runner.install_coverage_tools():
        return 1

    # Run coverage
    success = runner.run_coverage(
        test_paths=args.test_paths, markers=args.markers, parallel=args.parallel
    )

    if not success:
        print("\n❌ Tests failed")
        return 1

    # Generate reports
    reports = runner.generate_reports()

    # Check threshold
    if not args.no_fail:
        if not runner.check_coverage_threshold(args.threshold):
            return 1

    # Open HTML report if requested
    if args.open and "html" in reports:
        runner.open_html_report()

    print("\n✅ Coverage analysis complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
