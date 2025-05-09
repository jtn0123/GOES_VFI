# GOES-VFI Test Organization

## Overview

This document organizes all the test files in the GOES-VFI repository into logical categories to help understand what each test does and identify any redundant or unnecessary tests.

## Test Categories

### 1. Core Backend Unit Tests
These test the core functionality of the application's backend components.

| File Path | Purpose | Status |
|-----------|---------|--------|
| tests/unit/test_config.py | Tests configuration loading and saving | Working |
| tests/unit/test_loader.py | Tests image loading functionality | Working |
| tests/unit/test_encode.py | Tests video encoding functionality | Working |
| tests/unit/test_interpolate.py | Tests frame interpolation | Working |
| tests/unit/test_ffmpeg_builder.py | Tests FFmpeg command line builder | Working |
| tests/unit/test_tiler.py | Tests image tiling functionality | Working |
| tests/unit/test_raw_encoder.py | Tests raw video encoding | Working |
| tests/unit/test_log.py | Tests logging functionality | Working |
| tests/unit/test_run_vfi.py | Tests VFI core execution | Working |
| tests/unit/test_date_sorter.py | Tests date-based file sorting | Working |
| tests/unit/test_file_sorter.py | Tests general file sorting | Working |
| tests/unit/test_cache.py | Tests caching functionality | Working |
| tests/test_rife_analyzer.py | Tests RIFE model analysis | Working |

### 2. GUI Unit Tests
These test individual GUI components in isolation.

| File Path | Purpose | Status |
|-----------|---------|--------|
| tests/unit/test_ffmpeg_settings_tab.py | Tests FFmpeg settings UI | Working |
| tests/unit/test_main_tab.py | Tests main tab UI components | Working/Partial |
| tests/unit/test_enhanced_gui_tab.py | Tests enhanced UI tab | Working |
| tests/unit/test_enhanced_status_messages.py | Tests UI status messages | Working |
| tests/unit/test_enhanced_view_model.py | Tests view model for enhanced UI | Working |
| tests/unit/test_progress_reporting.py | Tests progress reporting UI | Working |
| tests/gui/test_main_window.py | Tests main application window | Partial (Some tests cause segfaults) |

### 3. Integrity Check Tests
These test the integrity checking functionality for satellite data.

| File Path | Purpose | Status |
|-----------|---------|--------|
| tests/unit/test_basic_time_index.py | Tests time indexing functionality | Working |
| tests/unit/test_time_index.py | Tests extended time indexing | Working |
| tests/unit/test_thread_cache_db.py | Tests thread-safe cache DB | Working |
| tests/unit/test_reconcile_manager.py | Tests reconciliation manager | Working |
| tests/test_reconcile_manager_integration.py | Integration tests for reconciliation | Working |
| tests/unit/test_remote_stores.py | Tests remote data store interfaces | Working |
| tests/unit/test_netcdf_renderer.py | Tests NetCDF rendering | Working |

### 4. S3 and Remote Data Access Tests
These test AWS S3 and other remote data access functionality.

| File Path | Purpose | Status |
|-----------|---------|--------|
| tests/unit/test_s3_unsigned_access.py | Tests unsigned S3 access | Working |
| tests/unit/test_s3_error_handling.py | Tests S3 error handling | Working |
| tests/unit/test_s3_retry_strategy.py | Tests S3 retry logic | Working |
| tests/unit/test_s3_download_stats.py | Tests S3 download statistics | Working |
| tests/unit/test_s3_retry_strategy_fixed.py | Tests fixed S3 retry logic | Working |
| tests/unit/test_s3_download_stats_fixed.py | Tests fixed S3 download stats | Working |
| tests/unit/test_s3_threadlocal_integration.py | Tests thread-local S3 clients | Working |
| tests/unit/test_real_s3_patterns.py | Tests real S3 path patterns | Working |
| tests/unit/test_real_s3_store.py | Tests real S3 storage | Working |
| test_s3_unsigned_access.py | Tests S3 unsigned access (root) | Redundant with unit test |
| test_s3_list.py | Tests S3 listing functionality | Prototype/Example |
| test_s3_band13.py | Tests accessing band 13 data from S3 | Prototype/Example |
| test_real_s3_path.py | Tests real S3 path handling | Prototype/Example |
| test_real_s3_paths.py | Tests real S3 path patterns | Redundant |

### 5. GOES Satellite Imagery Tests
These test the handling and processing of GOES satellite imagery.

| File Path | Purpose | Status |
|-----------|---------|--------|
| tests/unit/test_goes_imagery.py | Tests GOES imagery processing | Working |
| tests/unit/test_auto_detect_features.py | Tests auto-detection of imagery features | Working |
| tests/integration/test_goes_imagery_tab.py | Tests GOES imagery tab integration | Working |
| test_goes_product_detection.py | Tests GOES product detection | Prototype/Example |
| test_download_band13.py | Tests downloading band 13 data | Prototype/Example |
| test_download_mesoscale.py | Tests downloading mesoscale data | Prototype/Example |
| test_download_all_products.py | Tests downloading all product types | Prototype/Example |
| test_download_full_disk.py | Tests downloading full disk imagery | Prototype/Example |
| test_netcdf_channel_extraction.py | Tests NetCDF channel extraction | Prototype/Example |
| test_run_goes_imagery.py | Tests running GOES imagery processing | Prototype/Example |
| test_satpy_rendering.py | Tests Satpy rendering | Prototype/Example |

### 6. Integration Tests
These test the integration between different components of the system.

| File Path | Purpose | Status |
|-----------|---------|--------|
| tests/integration/test_pipeline.py | Tests the complete processing pipeline | Working |
| tests/integration/test_integrity_check_tab.py | Tests integrity check tab integration | Working |
| test_vfi_worker.py | Tests the VFI worker integration | Prototype/Example |
| test_unified_interface.py | Tests unified interface integration | Prototype/Example |
| test_combined_tab.py | Tests combined tab functionality | Prototype/Example |

### 7. UI Enhancement and Preview Tests
These test various UI enhancements and preview functionality.

| File Path | Purpose | Status |
|-----------|---------|--------|
| test_imagery_enhancement.py | Tests imagery enhancement features | Prototype/Example |
| test_imagery_gui.py | Tests imagery GUI components | Prototype/Example |
| test_imagery_gui_fixed.py | Tests fixed imagery GUI | Prototype/Example |
| test_imagery_gui_zoom.py | Tests imagery zoom functionality | Prototype/Example |
| test_imagery_simple.py | Tests simplified imagery interface | Prototype/Example |
| test_imagery_simplified.py | Tests further simplified imagery | Redundant |
| test_fallback_preview.py | Tests fallback preview functionality | Prototype/Example |
| test_enhanced_imagery_tab.py | Tests enhanced imagery tab | Prototype/Example |
| test_goes_ui.py | Tests GOES UI components | Prototype/Example |

### 8. Miscellaneous Tests
These are tests that don't clearly fit into the other categories.

| File Path | Purpose | Status |
|-----------|---------|--------|
| tests/test_placeholder.py | Empty test file used as placeholder | Working |
| test_sanchez.py | Tests Sanchez processing | Prototype/Example |
| test_signal.py | Tests signal handling | Prototype/Example |
| test_timestamp.py | Tests timestamp handling | Prototype/Example |
| test_download_real.py | Tests downloading real data | Prototype/Example |
| test_imagery_error_handling.py | Tests error handling in imagery | Prototype/Example |

## Redundant Tests

The following tests appear to be redundant or superseded by newer, more comprehensive tests:

1. **S3 Access Tests**:
   - `test_s3_unsigned_access.py` (root) - Superseded by `tests/unit/test_s3_unsigned_access.py`
   - `test_real_s3_paths.py` - Superseded by `tests/unit/test_real_s3_patterns.py`
   - `test_real_s3_path.py` - Superseded by `tests/unit/test_real_s3_patterns.py`

2. **Imagery GUI Tests**:
   - `test_imagery_gui.py`, `test_imagery_gui_fixed.py`, `test_imagery_simplified.py` - Likely superseded by `test_enhanced_imagery_tab.py` and proper integration tests

3. **Download Tests**:
   - Many of the download test scripts in the root directory appear to be prototype scripts rather than proper tests

## Prototype vs. Production Tests

Many of the test files in the root directory appear to be prototype or example scripts rather than formal tests. These are characterized by:

1. Being in the root directory rather than the `tests/` directory
2. Not following the standard test patterns (no fixtures, few assertions)
3. Often containing main blocks that run demonstration code

These could be moved to an `examples/` directory if they're still useful, or removed if they've been superseded by proper tests.

## Recommendations

1. **Move to proper test directories**:
   - Move any useful test code from root-level files to the appropriate test directories (unit, integration, gui)

2. **Remove redundant tests**:
   - Remove or archive the redundant tests identified above

3. **Convert useful prototypes to examples**:
   - Move prototype scripts that demonstrate functionality to an `examples/` directory

4. **Standardize test organization**:
   - Ensure all tests follow the correct pattern for their test type
   - Add proper fixtures and assertions to any tests lacking them

5. **Update test runners**:
   - Update the test runner scripts to reflect the new organization
   - Consider adding test categories to make it easier to run specific types of tests

6. **Address segfault issues**:
   - Focus on fixing the GUI tests that cause segmentation faults