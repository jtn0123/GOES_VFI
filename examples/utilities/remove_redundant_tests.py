#!/usr/bin/env python3
"""
Script to remove redundant test files from the root directory
that have already been moved to the proper test directories.
"""
import os
import sys

def main():
    """Main function to remove redundant test files."""
    # List of test files to remove from root directory
    files_to_remove = [
        "test_combined_tab.py",
        "test_download_all_products.py",
        "test_download_band13.py",
        "test_download_full_disk.py",
        "test_download_mesoscale.py",
        "test_download_real.py",
        "test_enhanced_imagery_tab.py",
        "test_fallback_preview.py",
        "test_goes_product_detection.py",
        "test_goes_ui.py",
        "test_imagery_enhancement.py",
        "test_imagery_error_handling.py",
        "test_imagery_gui_fixed.py",
        "test_imagery_gui_zoom.py",
        "test_imagery_gui.py",
        "test_imagery_simple.py",
        "test_imagery_simplified.py",
        "test_netcdf_channel_extraction.py",
        "test_real_s3_path.py",
        "test_real_s3_paths.py",
        "test_run_goes_imagery.py",
        "test_s3_band13.py",
        "test_s3_list.py",
        "test_s3_unsigned_access.py",
        "test_sanchez.py",
        "test_satpy_rendering.py",
        "test_signal.py",
        "test_timestamp.py",
        "test_unified_interface.py",
        "test_vfi_worker.py",
    ]
    
    # Count of removed files
    removed_count = 0
    
    # Remove each file if it exists
    for filename in files_to_remove:
        if os.path.exists(filename):
            try:
                os.remove(filename)
                print(f"Removed: {filename}")
                removed_count += 1
            except Exception as e:
                print(f"Error removing {filename}: {e}")
                
    print(f"\nRemoved {removed_count} redundant test files from root directory.")

if __name__ == "__main__":
    main()