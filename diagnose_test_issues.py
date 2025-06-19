#!/usr/bin/env python
"""Diagnose why tests are failing to import."""

import importlib
import sys
import traceback
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))


def test_import(module_path):
    """Test importing a module and report any errors."""
    try:
        importlib.import_module(module_path)
        return True, None
    except Exception as e:
        return False, traceback.format_exc()


def main():
    """Test importing key modules."""
    test_modules = [
        # Core modules
        "goesvfi.utils.log",
        "goesvfi.utils.config",
        "goesvfi.pipeline.batch_queue",
        "goesvfi.integrity_check.enhanced_gui_tab",
        "goesvfi.integrity_check.gui_tab",
        "goesvfi.integrity_check.view_model",
        "goesvfi.gui_tabs.batch_processing_tab",
        "goesvfi.gui_tabs.main_tab",
        "goesvfi.gui",
    ]

    print("Testing module imports...")
    print("=" * 80)

    failed_count = 0
    for module in test_modules:
        success, error = test_import(module)
        if success:
            print(f"✓ {module}")
        else:
            print(f"✗ {module}")
            print(f"  Error: {error.splitlines()[-1]}")
            failed_count += 1

    print("=" * 80)
    print(
        f"Summary: {failed_count} modules failed to import out of {len(test_modules)}"
    )

    # Now test some test files directly
    print("\nTesting test file imports...")
    print("=" * 80)

    test_files = [
        "tests.unit.test_batch_queue",
        "tests.unit.test_config",
        "tests.unit.test_auto_detect_features",
    ]

    for test_file in test_files:
        success, error = test_import(test_file)
        if success:
            print(f"✓ {test_file}")
        else:
            print(f"✗ {test_file}")
            if error:
                # Extract the actual error message
                lines = error.splitlines()
                for line in lines:
                    if "Error:" in line or "Exception:" in line:
                        print(f"  {line.strip()}")


if __name__ == "__main__":
    main()
