#!/usr/bin/env python3
"""
Run only the GUI tests that have been fixed and don't cause segmentation faults.
"""

import os
import subprocess
import sys

if __name__ == "__main__":
    # Get the path to Python in the current virtual environment
    python_executable = sys.executable

    # Only run tests that are known to work
    cmd = [
        python_executable,
        "-m",
        "pytest",
        # GUI tests through main window
        "tests/gui/test_main_window.py::test_initial_state",
        "tests/gui/test_main_window.py::test_successful_completion",
        "tests/gui/test_main_window.py::test_change_settings_main_tab",
        "tests/gui/test_main_window.py::test_change_ffmpeg_profile",
        # Isolated unit tests for specific components
        "tests/unit/test_ffmpeg_settings_tab.py",
        # All MainTab tests - now fixed
        "tests/unit/test_main_tab.py::test_initial_state",
        "tests/unit/test_main_tab.py::test_encoder_selection",
        "tests/unit/test_main_tab.py::test_rife_options_toggles",
        "tests/unit/test_main_tab.py::test_sanchez_options_toggles",
        # GUI imagery tests
        "tests/gui/imagery/test_fallback_preview.py",
        "tests/gui/imagery/test_imagery_enhancement.py",
        "tests/gui/imagery/test_imagery_simple.py",
        "tests/gui/imagery/test_imagery_simplified.py",
        # GUI tabs tests
        "tests/gui/tabs/test_enhanced_imagery_tab.py",
        # Other GUI tests
        "tests/gui/test_goes_ui.py",
        "tests/gui/test_imagery_error_handling.py",
        "tests/unit/test_main_tab.py::test_processing_state_updates_ui",
        "tests/unit/test_main_tab.py::test_browse_input_path",
        "tests/unit/test_main_tab.py::test_browse_output_path",
        "tests/unit/test_main_tab.py::test_start_processing",
        "tests/unit/test_main_tab.py::test_update_start_button_state",
        "tests/unit/test_main_tab.py::test_update_crop_buttons_state",
        # Fixed utility tests
        "tests/unit/test_log.py",
        "tests/unit/test_cache.py",
        # Fixed integration tests
        "tests/integration/test_pipeline.py::test_basic_interpolation",
        # Run with verbose output
        "-v",
    ]

    result = subprocess.run(cmd, check=False)
    sys.exit(result.returncode)
