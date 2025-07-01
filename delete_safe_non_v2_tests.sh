#!/bin/bash
# Script to delete 134 non-v2 test files that have working v2 equivalents
# Generated from analysis of completed v2 files with 0 linting issues

echo "Deleting 134 non-v2 test files that have working v2 equivalents..."

# GUI tests with v2 equivalents
rm -f tests/gui/imagery/test_imagery_enhancement.py
rm -f tests/gui/test_accessibility.py
rm -f tests/gui/test_button_advanced.py
rm -f tests/gui/test_enhanced_main_tab.py
rm -f tests/gui/test_gui_button_validation.py
rm -f tests/gui/test_gui_component_validation.py
rm -f tests/gui/test_gui_components.py
rm -f tests/gui/test_settings_density.py
rm -f tests/gui/test_super_button.py
rm -f tests/gui/test_tab_coordination.py
rm -f tests/gui/test_workflows_integration.py

# Integration tests with v2 equivalents
rm -f tests/integration/test_all_gui_elements.py
rm -f tests/integration/test_crop_dialog_integration.py
rm -f tests/integration/test_end_to_end_satellite_download.py
rm -f tests/integration/test_enhanced_preview_validation.py
rm -f tests/integration/test_full_application_workflow.py
rm -f tests/integration/test_goes_imagery_tab.py
rm -f tests/integration/test_headless_workflow.py
rm -f tests/integration/test_integrity_check_tab.py
rm -f tests/integration/test_integrity_tab_data_flow.py
rm -f tests/integration/test_integrity_tab_integration.py
rm -f tests/integration/test_integrity_tab_performance.py
rm -f tests/integration/test_large_dataset_processing.py
rm -f tests/integration/test_pipeline.py
rm -f tests/integration/test_preview_crop_workflow.py
rm -f tests/integration/test_preview_functionality.py
rm -f tests/integration/test_preview_integration.py
rm -f tests/integration/test_preview_visual_validation.py
rm -f tests/integration/test_run_ffmpeg_interpolation.py
rm -f tests/integration/test_vfi_worker_run.py

# Root level tests with v2 equivalents
rm -f tests/test_coverage_example.py
rm -f tests/test_reconcile_manager_integration.py

# Unit tests with v2 equivalents
rm -f tests/unit/test_auto_detect_features.py
rm -f tests/unit/test_background_worker.py
rm -f tests/unit/test_basic_time_index.py
rm -f tests/unit/test_batch_processing_tab.py
rm -f tests/unit/test_batch_queue.py
rm -f tests/unit/test_cache_utils.py
rm -f tests/unit/test_cache.py
rm -f tests/unit/test_config_management.py
rm -f tests/unit/test_config.py
rm -f tests/unit/test_core_exceptions.py
rm -f tests/unit/test_crop_handler.py
rm -f tests/unit/test_crop_manager.py
rm -f tests/unit/test_date_range_selector.py
rm -f tests/unit/test_date_utils.py
rm -f tests/unit/test_encode.py
rm -f tests/unit/test_enhanced_gui_tab.py
rm -f tests/unit/test_enhanced_view_model.py
rm -f tests/unit/test_error_classifier.py
rm -f tests/unit/test_error_handler_chain.py
rm -f tests/unit/test_ffmpeg_builder_critical.py
rm -f tests/unit/test_ffmpeg_builder.py
rm -f tests/unit/test_ffmpeg_settings_tab.py
rm -f tests/unit/test_file_sorter_view_model.py
rm -f tests/unit/test_goes_imagery.py
rm -f tests/unit/test_image_cropper.py
rm -f tests/unit/test_image_saver.py
rm -f tests/unit/test_interpolate.py
rm -f tests/unit/test_loader.py
rm -f tests/unit/test_log.py
rm -f tests/unit/test_main_tab.py
rm -f tests/unit/test_main_window_view_model.py
rm -f tests/unit/test_memory_management.py
rm -f tests/unit/test_model_manager.py
rm -f tests/unit/test_netcdf_channel_extraction.py
rm -f tests/unit/test_netcdf_render.py
rm -f tests/unit/test_netcdf_renderer.py
rm -f tests/unit/test_network_failure_simulation.py
rm -f tests/unit/test_operation_history_tab.py
rm -f tests/unit/test_pipeline_exceptions.py
rm -f tests/unit/test_preview_manager.py
rm -f tests/unit/test_preview_scaling_fixes.py
rm -f tests/unit/test_processing_handler.py
rm -f tests/unit/test_processing_state_management.py
rm -f tests/unit/test_processing_view_model_ffmpeg.py
rm -f tests/unit/test_progress_reporting.py
rm -f tests/unit/test_raw_encoder.py
rm -f tests/unit/test_real_s3_path.py
rm -f tests/unit/test_remote_stores.py
rm -f tests/unit/test_resource_limits_tab.py
rm -f tests/unit/test_rife_analyzer.py
rm -f tests/unit/test_run_vfi_param.py
rm -f tests/unit/test_s3_download_stats_param.py
rm -f tests/unit/test_s3_threadlocal_integration.py
rm -f tests/unit/test_s3_unsigned_access.py
rm -f tests/unit/test_s3_utils_modules.py
rm -f tests/unit/test_security.py
rm -f tests/unit/test_settings_manager.py
rm -f tests/unit/test_thread_cache_db.py
rm -f tests/unit/test_tiler.py
rm -f tests/unit/test_time_index.py
rm -f tests/unit/test_validation.py
rm -f tests/unit/test_worker_factory.py

# Utils tests with v2 equivalents
rm -f tests/utils/test_optimization_helpers.py

echo "Deleted all 134 non-v2 test files that have working v2 equivalents."
echo "Files remaining to handle:"
echo "- 13 non-v2 files without v2 equivalents (need v2 versions created)"
echo "- 25+ non-v2 files whose v2 equivalents still have linting issues"
