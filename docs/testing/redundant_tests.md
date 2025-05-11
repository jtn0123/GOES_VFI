# Redundant and Unnecessary Test Files

This document lists test files that appear to be redundant, unnecessary, or would be better categorized as examples rather than tests.

## Files to Remove (Redundant)

These files are redundant with newer, more comprehensive tests in the proper test directories:

1. `/Users/justin/Documents/Github/GOES_VFI/test_s3_unsigned_access.py` - Redundant with `tests/unit/test_s3_unsigned_access.py`
2. `/Users/justin/Documents/Github/GOES_VFI/test_real_s3_paths.py` - Redundant with `tests/unit/test_real_s3_patterns.py`
3. `/Users/justin/Documents/Github/GOES_VFI/test_real_s3_path.py` - Redundant with `tests/unit/test_real_s3_patterns.py`
4. `/Users/justin/Documents/Github/GOES_VFI/test_imagery_simplified.py` - Redundant with other imagery tests

## Files to Move to Examples Directory

These files appear to be demonstration or prototype scripts rather than proper tests:

1. `/Users/justin/Documents/Github/GOES_VFI/test_netcdf_channel_extraction.py` - Example of NetCDF channel extraction
2. `/Users/justin/Documents/Github/GOES_VFI/test_download_band13.py` - Example of downloading Band 13 data
3. `/Users/justin/Documents/Github/GOES_VFI/test_download_mesoscale.py` - Example of downloading mesoscale data
4. `/Users/justin/Documents/Github/GOES_VFI/test_download_all_products.py` - Example of downloading all products
5. `/Users/justin/Documents/Github/GOES_VFI/test_download_full_disk.py` - Example of downloading full disk imagery
6. `/Users/justin/Documents/Github/GOES_VFI/test_satpy_rendering.py` - Example of Satpy rendering
7. `/Users/justin/Documents/Github/GOES_VFI/test_goes_product_detection.py` - Example of GOES product detection
8. `/Users/justin/Documents/Github/GOES_VFI/test_download_real.py` - Example of downloading real data
9. `/Users/justin/Documents/Github/GOES_VFI/test_run_goes_imagery.py` - Example of running GOES imagery processing
10. `/Users/justin/Documents/Github/GOES_VFI/test_goes_ui.py` - Example of GOES UI components
11. `/Users/justin/Documents/Github/GOES_VFI/test_sanchez.py` - Example of Sanchez processing
12. `/Users/justin/Documents/Github/GOES_VFI/test_s3_list.py` - Example of S3 listing
13. `/Users/justin/Documents/Github/GOES_VFI/test_s3_band13.py` - Example of S3 Band 13 access

## Tests to Modernize and Properly Integrate

These files contain valuable test logic but should be moved to the proper test directories and updated to follow test conventions:

1. `/Users/justin/Documents/Github/GOES_VFI/test_vfi_worker.py` - Should be integrated into proper integration tests
2. `/Users/justin/Documents/Github/GOES_VFI/test_imagery_enhancement.py` - Should be integrated into UI tests
3. `/Users/justin/Documents/Github/GOES_VFI/test_imagery_gui.py` - Should be integrated into GUI tests
4. `/Users/justin/Documents/Github/GOES_VFI/test_imagery_gui_fixed.py` - Should be integrated into GUI tests
5. `/Users/justin/Documents/Github/GOES_VFI/test_imagery_gui_zoom.py` - Should be integrated into GUI tests
6. `/Users/justin/Documents/Github/GOES_VFI/test_imagery_simple.py` - Should be integrated into GUI tests
7. `/Users/justin/Documents/Github/GOES_VFI/test_fallback_preview.py` - Should be integrated into UI tests
8. `/Users/justin/Documents/Github/GOES_VFI/test_enhanced_imagery_tab.py` - Should be integrated into proper tab tests
9. `/Users/justin/Documents/Github/GOES_VFI/test_combined_tab.py` - Should be integrated into proper tab tests
10. `/Users/justin/Documents/Github/GOES_VFI/test_signal.py` - Should be moved to unit tests
11. `/Users/justin/Documents/Github/GOES_VFI/test_timestamp.py` - Should be moved to unit tests
12. `/Users/justin/Documents/Github/GOES_VFI/test_imagery_error_handling.py` - Should be integrated into error handling tests
13. `/Users/justin/Documents/Github/GOES_VFI/test_unified_interface.py` - Should be integrated into interface tests

## Proposed Directory Structure

```
tests/
├── unit/                 # Unit tests
│   ├── test_config.py
│   ├── test_timestamp.py  # Moved from root
│   ├── test_signal.py     # Moved from root
│   └── ... (existing unit tests)
├── integration/          # Integration tests
│   ├── test_pipeline.py
│   ├── test_vfi_worker.py  # Moved from root
│   └── ... (existing integration tests)
├── gui/                  # GUI tests
│   ├── test_main_window.py
│   ├── imagery/            # Subdirectory for imagery-specific GUI tests
│   │   ├── test_imagery_enhancement.py  # Moved from root
│   │   ├── test_imagery_gui.py          # Moved from root
│   │   ├── test_imagery_zoom.py         # Moved from root
│   │   └── test_fallback_preview.py     # Moved from root
│   ├── tabs/              # Subdirectory for tab-specific GUI tests
│   │   ├── test_enhanced_imagery_tab.py  # Moved from root
│   │   ├── test_combined_tab.py          # Moved from root
│   │   └── ... (other tab tests)
│   └── ... (other GUI tests)
├── conftest.py
└── __init__.py

examples/                 # New directory for example scripts
├── download/             # Download examples
│   ├── download_band13.py          # Renamed from test_download_band13.py
│   ├── download_mesoscale.py       # Renamed from test_download_mesoscale.py
│   ├── download_all_products.py    # Renamed from test_download_all_products.py
│   ├── download_full_disk.py       # Renamed from test_download_full_disk.py
│   └── download_real.py            # Renamed from test_download_real.py
├── s3_access/            # S3 access examples
│   ├── s3_list.py                  # Renamed from test_s3_list.py
│   ├── s3_band13.py                # Renamed from test_s3_band13.py
│   └── ... (other S3 examples)
├── imagery/              # Imagery processing examples
│   ├── netcdf_channel_extraction.py # Renamed from test_netcdf_channel_extraction.py
│   ├── satpy_rendering.py          # Renamed from test_satpy_rendering.py
│   ├── goes_product_detection.py   # Renamed from test_goes_product_detection.py
│   └── run_goes_imagery.py         # Renamed from test_run_goes_imagery.py
└── processing/           # Processing examples
    └── sanchez_processing.py       # Renamed from test_sanchez.py
```
