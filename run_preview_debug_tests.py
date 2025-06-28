#!/usr/bin/env python3
"""Script to run preview tests with enhanced logging for debugging display issues."""

import argparse
import logging
import os
from pathlib import Path
import sys

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


# Configure logging for debugging
def setup_debug_logging():
    """Set up enhanced logging for preview debugging."""
    # Create logs directory if it doesn't exist
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True)

    # Set up file handler for detailed logs
    log_file = logs_dir / "preview_debug.log"
    file_handler = logging.FileHandler(log_file, mode="w")
    file_handler.setLevel(logging.DEBUG)

    # Set up console handler for important messages
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Create formatters
    detailed_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    )
    simple_formatter = logging.Formatter("%(levelname)s - %(name)s - %(message)s")

    file_handler.setFormatter(detailed_formatter)
    console_handler.setFormatter(simple_formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Set specific loggers to be more verbose
    preview_loggers = [
        "goesvfi.gui_components.preview_manager",
        "goesvfi.gui",
        "tests.integration.test_enhanced_preview_validation",
        "goesvfi.pipeline.image_loader",
        "goesvfi.pipeline.image_cropper",
        "goesvfi.pipeline.sanchez_processor",
    ]

    for logger_name in preview_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)

    return log_file


def run_preview_tests(test_filter=None, verbose=False):
    """Run preview-related tests with enhanced logging."""
    import subprocess

    # Set up debug logging
    setup_debug_logging()

    # Set environment variables for Qt
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"  # Use offscreen platform for testing
    env["PYTHONPATH"] = str(project_root)

    # Build pytest command
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-v" if verbose else "-s",
        "--tb=short",
        "--capture=no",  # Allow print statements to show
    ]

    # Add test filters
    if test_filter:
        if "preview" not in test_filter.lower():
            # If filter doesn't contain 'preview', add preview-related test patterns
            test_patterns = [
                "tests/integration/test_enhanced_preview_validation.py",
                "tests/integration/test_preview_functionality.py",
                "tests/unit/test_preview_manager.py",
                "tests/gui/test_preview_advanced.py",
            ]
            cmd.extend(pattern for pattern in test_patterns if Path(pattern).exists())
        else:
            cmd.append(f"-k {test_filter}")
    else:
        # Run all preview-related tests
        test_patterns = [
            "tests/integration/test_enhanced_preview_validation.py",
            "tests/integration/test_preview_functionality.py",
            "tests/unit/test_preview_manager.py",
        ]
        cmd.extend(pattern for pattern in test_patterns if Path(pattern).exists())

    # Run the tests
    try:
        result = subprocess.run(cmd, env=env, cwd=project_root, check=False)
        return result.returncode
    except KeyboardInterrupt:
        return 1
    except Exception:
        return 1
    finally:
        pass


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run preview tests with enhanced debugging",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all preview tests with debug logging
  python run_preview_debug_tests.py

  # Run specific test with verbose output
  python run_preview_debug_tests.py --filter "test_preview_images_display_validation" --verbose

  # Run enhanced validation test only
  python run_preview_debug_tests.py --filter "enhanced_preview_validation"
        """,
    )

    parser.add_argument("--filter", "-f", help="Filter tests by name or pattern")

    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose test output")

    args = parser.parse_args()

    exit_code = run_preview_tests(args.filter, args.verbose)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
