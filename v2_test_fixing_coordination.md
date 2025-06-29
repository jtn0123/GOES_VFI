# V2 Test Files Linting Fix Coordination

## Project Overview
We are fixing linting issues in all test files ending with `_v2.py`. Total: **141 v2 test files** discovered.
- Unit tests: 100 files
- Integration tests: 21 files
- GUI tests: 17 files
- Other: 3 files

## CRITICAL DISCOVERY: Auto-Fix Does NOT Work for Most Issues

**IMPORTANT**: The `--fix` flag only fixes trivial issues like trailing whitespace and import sorting. It does NOT fix:
- Missing type annotations (ANN201, ANN001)
- Methods that should be @staticmethod (PLR6301)
- Missing docstring Returns sections (DOC201)
- Function complexity (C901)
- Any other code structure issues

## Updated Task Instructions
1. Check current issues: `ruff check <file> --statistics`
2. Run auto-fix for trivial issues: `python3 run_linters.py <file> --fix --format`
3. **Manually fix all remaining issues** by editing the code:
   - Add type annotations to ALL functions and parameters
   - Add @staticmethod decorator to methods not using self
   - Add Returns sections to docstrings for functions that return values
   - Add # noqa comments for acceptable violations
4. Verify all issues resolved: `python3 run_linters.py <file> --check`
5. Test that the file still works: `python -m pytest <file>`
6. Commit and push: Follow standard git workflow
7. Update this coordination file to track progress

## Manual Fix Examples

### Adding Type Annotations
```python
# Before
def exception_test_components(self):

# After
@staticmethod
def exception_test_components() -> dict[str, Any]:
```

### Adding Returns Documentation
```python
def get_value() -> int:
    """Get a test value.

    Returns:
        int: The test value.
    """
    return 42
```

### Handling Complexity
```python
def complex_function() -> None:  # noqa: C901
    """Complex test function."""
```

## Current Status Summary

### Lead Agent - Completed Files (6)
1. ✅ tests/unit/test_interpolate_v2.py (commit 540c553) - CLEAN
2. ✅ tests/unit/test_encode_v2.py (commit bd031ed) - CLEAN
3. ✅ tests/unit/test_run_vfi_param_v2.py (commit 4804c05) - CLEAN
4. ✅ tests/unit/test_main_tab_v2.py (commit 531f67f) - CLEAN
5. ✅ tests/unit/test_raw_encoder_v2.py (commit 62a171d) - CLEAN
6. ✅ tests/unit/test_run_ffmpeg_v2.py (commit e648b07) - CLEAN

### Worker Agent - Actually Completed Files (5)
1. ✅ tests/integration/test_goes_imagery_tab_v2.py (commit bea0bf5) - VERIFIED CLEAN
2. ✅ tests/integration/test_integrity_check_tab_v2.py (commit a3eda6c) - VERIFIED CLEAN
3. ✅ tests/integration/test_integrity_tab_integration_v2.py (commit 9ca9244) - VERIFIED CLEAN
4. ✅ tests/unit/test_model_manager_v2.py - VERIFIED CLEAN
5. ✅ tests/unit/test_network_failure_simulation_v2.py - VERIFIED CLEAN

### Files Needing Work

**High Priority - Files with Remaining Issues:**
- ❌ tests/integration/test_end_to_end_satellite_download_v2.py (44 issues - ARG, BLE, RUF, TRY, S324)
- ❌ tests/integration/test_headless_workflow_v2.py (27 issues - ARG, PLR, PLC, PT, B, F, S, W, C, DOC)

**Lead Agent - Unit Tests Needing Manual Fixes (19 files, ~3,600 issues):**
1. test_pipeline_exceptions_v2.py (152 issues)
2. test_processing_handler_v2.py (211 issues)
3. test_processing_manager_v2.py (222 issues)
4. test_cache_utils_v2.py (121 issues)
5. test_config_v2.py (143 issues)
6. test_ffmpeg_builder_critical_v2.py (212 issues)
7. test_ffmpeg_builder_v2.py (252 issues)
8. test_log_v2.py (105 issues)
9. test_real_s3_path_v2.py (222 issues)
10. test_real_s3_patterns_v2.py (203 issues)
11. test_remote_stores_v2.py (263 issues)
12. test_s3_band13_v2.py (223 issues)
13. test_s3_download_stats_param_v2.py (158 issues)
14. test_s3_error_handling_v2.py (260 issues)
15. test_s3_store_critical_v2.py (274 issues)
16. test_s3_threadlocal_integration_v2.py (517 issues)
17. test_s3_utils_modules_v2.py (148 issues)
18. test_time_index_v2.py (215 issues)
19. test_validation_v2.py (80 issues)

**Worker Agent - Remaining Files to Check/Fix:**

Integration Tests (need verification):
- [ ] tests/integration/test_full_application_workflow_v2.py
- [ ] tests/integration/test_preview_functionality_v2.py
- [ ] tests/integration/test_pipeline_v2.py
- [ ] tests/integration/test_preview_integration_v2.py
- [ ] tests/integration/test_vfi_worker_v2.py
- [ ] tests/integration/test_video_processing_pipeline_v2.py
- [ ] tests/integration/test_all_gui_elements_v2.py
- [ ] tests/integration/test_crop_dialog_integration_v2.py
- [ ] tests/integration/test_enhanced_preview_validation_v2.py

GUI Tests (all 17 untouched):
- [ ] tests/gui/test_main_window_v2.py
- [ ] tests/gui/test_gui_components_v2.py
- [ ] tests/gui/test_enhanced_main_tab_v2.py
- [ ] tests/gui/test_settings_advanced_v2.py
- [ ] tests/gui/test_accessibility_v2.py
- [ ] tests/gui/test_error_handling_ui_v2.py
- [ ] tests/gui/test_performance_ui_v2.py
- [ ] tests/gui/test_workflows_integration_v2.py
- [ ] tests/gui/imagery/test_band_selector_v2.py
- [ ] tests/gui/imagery/test_imagery_dialog_v2.py
- [ ] tests/gui/imagery/test_imagery_loader_v2.py
- [ ] tests/gui/imagery/test_imagery_manager_v2.py
- [ ] tests/gui/tabs/test_about_tab_v2.py
- [ ] tests/gui/tabs/test_main_tab_v2.py
- [ ] tests/gui/tabs/test_preview_tab_v2.py
- [ ] tests/gui/tabs/test_render_tab_v2.py
- [ ] tests/gui/tabs/test_settings_tab_v2.py

Remaining Unit Tests (need verification):
- [ ] tests/unit/test_date_utils_v2.py
- [ ] tests/unit/test_processing_view_model_ffmpeg_v2.py
- [ ] tests/unit/test_rife_analyzer_v2.py
- [ ] tests/unit/test_s3_unsigned_access_v2.py
- [ ] tests/unit/test_security_v2.py
- [ ] tests/unit/test_main_tab_optimized_v2.py
- [ ] tests/unit/test_model_manager_optimized_v2.py
- [ ] tests/unit/test_network_failure_simulation_optimized_v2.py
- [ ] tests/unit/test_security_optimized_v2.py

## Summary Statistics
- **Total v2 files**: 141
- **Completed and clean**: 11 files (8%)
- **Need rework**: 2 files
- **Remaining**: 128 files (91%)

## Recommended Next Steps

### For Lead Agent:
1. Start with test_validation_v2.py (smallest file, 80 issues)
2. Work through unit test files from smallest to largest
3. Focus on systematic fixes:
   - First pass: Add all type annotations
   - Second pass: Add @staticmethod decorators
   - Third pass: Fix docstrings
   - Fourth pass: Add noqa comments

### For Worker Agent:
1. Fix the 2 files that need rework (test_end_to_end_satellite_download_v2.py and test_headless_workflow_v2.py)
2. Verify status of claimed complete files
3. Continue with remaining integration tests
4. Move to GUI tests after integration tests

## Important Notes
- DO NOT claim files are fixed without verification using `ruff check`
- Test files after fixing to ensure they still work
- Update this file with accurate status only
- The auto-fix tool is nearly useless for v2 files - expect manual work
