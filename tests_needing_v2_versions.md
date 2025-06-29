# Tests Needing V2 Versions

## Priority 1: Integration Tests (10 files)
These tests validate end-to-end workflows and component interactions:

1. **test_end_to_end_satellite_download.py** - Tests complete satellite data download workflow
2. **test_goes_imagery_tab.py** - Tests GOES imagery tab functionality
3. **test_headless_workflow.py** - Tests non-GUI workflow execution
4. **test_integrity_check_tab.py** - Tests integrity check tab functionality
5. **test_integrity_tab_integration.py** - Tests integrity tab integration with other components
6. **test_pipeline.py** - Tests overall processing pipeline
7. **test_preview_functionality.py** - Tests preview feature functionality
8. **test_preview_integration.py** - Tests preview integration with other components
9. **test_vfi_worker.py** - Tests VFI worker functionality
10. **test_video_processing_pipeline.py** - Tests video processing pipeline

## Priority 2: Unit Tests (11 files)
These tests validate individual components and utilities:

1. **test_date_utils.py** - Tests date/time utility functions
2. **test_interpolator.py** - Tests interpolation functionality
3. **test_processing_view_model_ffmpeg.py** - Tests FFmpeg processing view model
4. **test_real_s3_store.py** - Tests S3 store implementation
5. **test_rife_analyzer.py** - Tests RIFE analysis functionality
6. **test_s3_connection_pool.py** - Tests S3 connection pooling
7. **test_s3_retry_strategy.py** - Tests S3 retry mechanisms
8. **test_s3_unsigned_access.py** - Tests unsigned S3 access
9. **test_vfi_crop_handler.py** - Tests VFI crop handling
10. **test_vfi_ffmpeg_builder.py** - Tests VFI FFmpeg builder
11. **test_vfi_image_processor.py** - Tests VFI image processing

## Files That Don't Need V2 Versions (6 files)
These are special case files that should be excluded:

- **download_band13_manual.py** - Manual test script, not automated
- **sanchez_manual_test.py** - Manual test script, not automated
- **test_file_sorter_refactored.py** - Already refactored version
- **test_real_s3_store_fixed.py** - Fixed version of test_real_s3_store.py
- **test_s3_retry_strategy_fixed.py** - Fixed version of test_s3_retry_strategy.py
- **test_time_index_refactored.py** - Already refactored version

## Summary
- **Total files needing v2 versions**: 21
- **Integration tests**: 10
- **Unit tests**: 11
- **GUI tests**: 0 (all have v2 versions)

## Recommended Approach
1. Start with integration tests as they test critical workflows
2. Focus on S3-related unit tests next (important for data access)
3. Complete remaining unit tests
4. Skip the 6 special case files listed above
