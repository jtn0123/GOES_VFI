# V2 Test Files - Detailed File-by-File Comparison

## Summary
- **Total v2 files analyzed**: 153
- **Files with original counterparts**: 131
- **Overall coverage change**: 1,427 → 2,041 test functions (+614, **+43.0%**)

## Files with Syntax Errors (Cannot be analyzed)
These files have syntax errors and need to be fixed:
1. `test_encode_v2.py` - line 259
2. `test_interpolate_v2.py` - line 84
3. `test_raw_encoder_v2.py` - line 65
4. `test_run_ffmpeg_v2.py` - line 118
5. `test_run_vfi_param_v2.py` - line 136

## Files with Major Coverage Improvements (≥200%)

| V2 File | Original | V2 | Change | Coverage |
|---------|----------|----|---------|-----------|
| test_netcdf_channel_extraction_v2.py | 1 | 27 | +26 | **2700%** |
| test_download_real_v2.py | 1 | 16 | +15 | **1600%** |
| test_batch_processing_tab_v2.py | 1 | 13 | +12 | **1300%** |
| test_image_cropper_v2.py | 2 | 22 | +20 | **1100%** |
| test_operation_history_tab_v2.py | 2 | 19 | +17 | **950%** |
| test_operation_history_tab_v2.py | 1 | 9 | +8 | **900%** |
| test_file_sorter_view_model_v2.py | 2 | 16 | +14 | **800%** |
| test_vfi_worker_run_v2.py | 1 | 8 | +7 | **800%** |
| test_mock_popen_v2.py | 2 | 15 | +13 | **750%** |
| test_main_window_view_model_v2.py | 3 | 18 | +15 | **600%** |
| test_processing_view_model_ffmpeg_v2.py | 2 | 11 | +9 | **550%** |
| test_real_s3_path_v2.py | 2 | 11 | +9 | **550%** |
| test_run_ffmpeg_interpolation_v2.py | 2 | 10 | +8 | **500%** |
| test_vfi_worker_v2.py | 1 | 5 | +4 | **500%** |

## Files with Significant Coverage Loss (≤50%)

| V2 File | Original | V2 | Change | Coverage |
|---------|----------|----|---------|-----------|
| test_pipeline_v2.py | 17 | 4 | -13 | **23.5%** ⚠️ |
| test_ffmpeg_builder_v2.py | 15 | 4 | -11 | **26.7%** ⚠️ |
| test_resource_manager_v2.py | 33 | 10 | -23 | **30.3%** ⚠️ |
| test_video_processing_pipeline_v2.py | 12 | 4 | -8 | **33.3%** ⚠️ |
| test_preview_integration_v2.py | 15 | 5 | -10 | **33.3%** ⚠️ |
| test_security_v2.py | 37 | 14 | -23 | **37.8%** ⚠️ |
| test_pipeline_exceptions_v2.py | 34 | 13 | -21 | **38.2%** ⚠️ |
| test_goes_imagery_tab_v2.py | 9 | 4 | -5 | **44.4%** ⚠️ |
| test_model_manager_v2.py | 13 | 6 | -7 | **46.2%** ⚠️ |
| test_errors_reporter_v2.py | 17 | 8 | -9 | **47.1%** ⚠️ |
| test_s3_utils_modules_v2.py | 23 | 11 | -12 | **47.8%** ⚠️ |
| test_main_tab_v2.py | 10 | 5 | -5 | **50.0%** ⚠️ |

## Files Without Original Counterparts

These v2 files don't have matching original files (may be renamed or new):

### Optimized Variants (recovered from git)
- test_full_application_workflow_optimized_v2.py (14 test functions) - **duplicate entry**
- test_main_tab_optimized_v2.py (14 test functions) - **duplicate entry**
- test_model_manager_optimized_v2.py (9 test functions) - **duplicate entry**
- test_network_failure_simulation_optimized_v2.py (11 test functions) - **duplicate entry**
- test_security_optimized_v2.py (26 test functions) - **duplicate entry**

### New Test Files
- test_async_io_v2.py (31 test functions)
- test_configuration_v2.py (30 test functions)
- test_error_decorators_v2.py (22 test functions)
- test_global_process_pool_v2.py (15 test functions)
- test_modern_resources_v2.py (25 test functions)
- test_simple_example_v2.py (3 test functions)
- test_timeline_tab_v2.py (6 test functions)

## Files Still Missing (from tracking document)
1. test_error_classifier_fast_v2.py
2. test_optimized_results_tab_v2.py
3. test_optimized_timeline_tab_v2.py

## Complete File-by-File Breakdown

### Files with Increased Coverage (85 files)
| File | Original | V2 | Change | Coverage % |
|------|----------|----|---------|-----------|
| test_netcdf_channel_extraction_v2.py | 1 | 27 | +26 | 2700.0% |
| test_download_real_v2.py | 1 | 16 | +15 | 1600.0% |
| test_batch_processing_tab_v2.py | 1 | 13 | +12 | 1300.0% |
| test_image_cropper_v2.py | 2 | 22 | +20 | 1100.0% |
| test_operation_history_tab_v2.py | 2 | 19 | +17 | 950.0% |
| test_operation_history_tab_v2.py | 1 | 9 | +8 | 900.0% |
| test_file_sorter_view_model_v2.py | 2 | 16 | +14 | 800.0% |
| test_vfi_worker_run_v2.py | 1 | 8 | +7 | 800.0% |
| test_mock_popen_v2.py | 2 | 15 | +13 | 750.0% |
| test_main_window_view_model_v2.py | 3 | 18 | +15 | 600.0% |
| ... (75 more files with improvements)

### Files with Same Coverage (6 files)
| File | Tests | Coverage % |
|------|-------|-----------|
| test_gui_button_validation_v2.py | 14 | 100.0% |
| test_performance_ui_v2.py | 8 | 100.0% |
| test_headless_workflow_v2.py | 4 | 100.0% |
| test_auto_detect_features_v2.py | 8 | 100.0% |
| test_processing_state_management_v2.py | 13 | 100.0% |
| test_real_s3_patterns_v2.py | 12 | 100.0% |

### Files with Decreased Coverage (40 files)
| File | Original | V2 | Change | Coverage % |
|------|----------|----|---------|-----------|
| test_accessibility_v2.py | 8 | 7 | -1 | 87.5% |
| test_super_button_v2.py | 25 | 24 | -1 | 96.0% |
| test_all_gui_elements_v2.py | 13 | 12 | -1 | 92.3% |
| test_integrity_tab_integration_v2.py | 4 | 3 | -1 | 75.0% |
| test_coverage_example_v2.py | 12 | 11 | -1 | 91.7% |
| test_memory_management_v2.py | 17 | 16 | -1 | 94.1% |
| test_error_handling_ui_v2.py | 8 | 6 | -2 | 75.0% |
| test_settings_advanced_v2.py | 8 | 6 | -2 | 75.0% |
| test_integrity_check_tab_v2.py | 6 | 4 | -2 | 66.7% |
| test_config_management_v2.py | 19 | 17 | -2 | 89.5% |
| test_ffmpeg_builder_critical_v2.py | 5 | 3 | -2 | 60.0% |
| test_processing_manager_v2.py | 16 | 14 | -2 | 87.5% |
| test_worker_factory_v2.py | 17 | 15 | -2 | 88.2% |
| test_gui_component_validation_v2.py | 15 | 12 | -3 | 80.0% |
| test_end_to_end_satellite_download_v2.py | 7 | 4 | -3 | 57.1% |
| test_preview_crop_workflow_v2.py | 10 | 7 | -3 | 70.0% |
| test_corrupt_file_handling_v2.py | 15 | 12 | -3 | 80.0% |
| test_processing_handler_v2.py | 17 | 14 | -3 | 82.4% |
| test_full_application_workflow_v2.py | 10 | 6 | -4 | 60.0% |
| test_config_v2.py | 14 | 10 | -4 | 71.4% |
| test_sanchez_health_v2.py | 23 | 19 | -4 | 82.6% |
| test_goes_imagery_tab_v2.py | 9 | 4 | -5 | 44.4% ⚠️ |
| test_main_tab_v2.py | 10 | 5 | -5 | 50.0% ⚠️ |
| test_network_failure_simulation_v2.py | 13 | 7 | -6 | 53.8% |
| test_zoom_manager_v2.py | 18 | 12 | -6 | 66.7% |
| test_model_manager_v2.py | 13 | 6 | -7 | 46.2% ⚠️ |
| test_resource_manager_fast_v2.py | 18 | 11 | -7 | 61.1% |
| test_gui_components_v2.py | 19 | 11 | -8 | 57.9% |
| test_video_processing_pipeline_v2.py | 12 | 4 | -8 | 33.3% ⚠️ |
| test_state_manager_v2.py | 21 | 13 | -8 | 61.9% |
| test_errors_reporter_v2.py | 17 | 8 | -9 | 47.1% ⚠️ |
| test_preview_integration_v2.py | 15 | 5 | -10 | 33.3% ⚠️ |
| test_main_tab_utils_v2.py | 30 | 20 | -10 | 66.7% |
| test_ffmpeg_builder_v2.py | 15 | 4 | -11 | 26.7% ⚠️ |
| test_core_exceptions_v2.py | 25 | 13 | -12 | 52.0% |
| test_s3_utils_modules_v2.py | 23 | 11 | -12 | 47.8% ⚠️ |
| test_pipeline_v2.py | 17 | 4 | -13 | 23.5% ⚠️ |
| test_pipeline_exceptions_v2.py | 34 | 13 | -21 | 38.2% ⚠️ |
| test_resource_manager_v2.py | 33 | 10 | -23 | 30.3% ⚠️ |
| test_security_v2.py | 37 | 14 | -23 | 37.8% ⚠️ |

## Recommendations

1. **Fix syntax errors** in 5 files immediately
2. **Review critical coverage losses** - 12 files have <50% of original tests
3. **Investigate duplicate entries** - The optimized_v2 files appear twice in the analysis
4. **Find missing files** - 3 files mentioned in tracking are still not found
5. **Consider renaming** - Some v2 files might need to be matched manually to their originals
