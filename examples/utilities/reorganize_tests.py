#!/usr/bin/env python3
"""
Script to reorganize test files from the root directory to appropriate test subdirectories.
"""
import os
import shutil
from pathlib import Path
import sys

def ensure_directory(directory):
    """Ensure the directory exists."""
    os.makedirs(directory, exist_ok=True)

def move_file(source, destination):
    """Move a file from source to destination."""
    # Create parent directory if it doesn't exist
    ensure_directory(os.path.dirname(destination))
    
    # Check if the file exists at the destination
    if os.path.exists(destination):
        print(f"Warning: {destination} already exists. Skipping...")
        return False
    
    # Check if the source file exists
    if not os.path.exists(source):
        print(f"Error: Source file {source} does not exist. Skipping...")
        return False
    
    # Move the file
    try:
        shutil.copy2(source, destination)
        print(f"Moved: {source} -> {destination}")
        return True
    except Exception as e:
        print(f"Error moving {source} to {destination}: {e}")
        return False

def main():
    """Main function to reorganize test files."""
    # Define the mapping of test files to their destinations
    test_mapping = {
        # Unit tests
        "test_download_all_products.py": "tests/unit/test_download_all_products.py",
        "test_download_band13.py": "tests/unit/test_download_band13.py",
        "test_download_full_disk.py": "tests/unit/test_download_full_disk.py",
        "test_download_mesoscale.py": "tests/unit/test_download_mesoscale.py",
        "test_download_real.py": "tests/unit/test_download_real.py",
        "test_goes_product_detection.py": "tests/unit/test_goes_product_detection.py",
        "test_netcdf_channel_extraction.py": "tests/unit/test_netcdf_channel_extraction.py",
        "test_real_s3_path.py": "tests/unit/test_real_s3_path.py",
        "test_real_s3_paths.py": "tests/unit/test_real_s3_paths.py",
        "test_run_goes_imagery.py": "tests/unit/test_run_goes_imagery.py",
        "test_s3_band13.py": "tests/unit/test_s3_band13.py",
        "test_s3_list.py": "tests/unit/test_s3_list.py",
        "test_s3_unsigned_access.py": "tests/unit/test_s3_unsigned_access.py",
        "test_sanchez.py": "tests/unit/test_sanchez.py",
        "test_satpy_rendering.py": "tests/unit/test_satpy_rendering.py",
        "test_signal.py": "tests/unit/test_signal.py",
        "test_timestamp.py": "tests/unit/test_timestamp.py",
        
        # Integration tests
        "test_combined_tab.py": "tests/integration/test_combined_tab.py",
        "test_unified_interface.py": "tests/integration/test_unified_interface.py",
        "test_vfi_worker.py": "tests/integration/test_vfi_worker.py",
        
        # GUI tests - imagery
        "test_fallback_preview.py": "tests/gui/imagery/test_fallback_preview.py",
        "test_imagery_enhancement.py": "tests/gui/imagery/test_imagery_enhancement.py",
        "test_imagery_gui.py": "tests/gui/imagery/test_imagery_gui.py",
        "test_imagery_gui_fixed.py": "tests/gui/imagery/test_imagery_gui_fixed.py",
        "test_imagery_gui_zoom.py": "tests/gui/imagery/test_imagery_zoom.py",
        "test_imagery_simple.py": "tests/gui/imagery/test_imagery_simple.py",
        "test_imagery_simplified.py": "tests/gui/imagery/test_imagery_simplified.py",
        
        # GUI tests - tabs
        "test_enhanced_imagery_tab.py": "tests/gui/tabs/test_enhanced_imagery_tab.py",
        
        # GUI tests - other
        "test_goes_ui.py": "tests/gui/test_goes_ui.py",
        "test_imagery_error_handling.py": "tests/gui/test_imagery_error_handling.py",
    }
    
    # Move the files
    for source, destination in test_mapping.items():
        move_file(source, destination)
    
    print("Test reorganization complete.")

if __name__ == "__main__":
    main()