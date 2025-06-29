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

## CLEAR TASK DIVISION

### Lead Agent - Responsible for Unit Tests (94 files total)
**Completed (11):**
1. ✅ tests/unit/test_interpolate_v2.py (commit 540c553)
2. ✅ tests/unit/test_encode_v2.py (commit bd031ed)
3. ✅ tests/unit/test_run_vfi_param_v2.py (commit 4804c05)
4. ✅ tests/unit/test_main_tab_v2.py (commit 531f67f)
5. ✅ tests/unit/test_raw_encoder_v2.py (commit 62a171d)
6. ✅ tests/unit/test_run_ffmpeg_v2.py (commit e648b07)
7. ✅ tests/unit/test_validation_v2.py (commit 5e33f33)
8. ✅ tests/unit/test_pipeline_exceptions_v2.py (commit 1cfa49c)
9. ✅ tests/unit/test_log_v2.py (commit 540c553)
10. ✅ tests/unit/test_cache_utils_v2.py (commit f205fad)
11. ✅ tests/unit/test_config_v2.py (commit 8393931)

**Remaining (83 files):** All other files in tests/unit/ ending with _v2.py, including but not limited to:
- test_processing_handler_v2.py (211 issues)
- test_processing_manager_v2.py (222 issues)
- test_ffmpeg_builder_critical_v2.py (212 issues)
- test_ffmpeg_builder_v2.py (252 issues)
- All S3-related test files
- All other unit test files

### Worker Agent - Responsible for Integration + GUI Tests (47 files total)
**Completed (5):**
1. ✅ tests/integration/test_goes_imagery_tab_v2.py (commit bea0bf5)
2. ✅ tests/integration/test_integrity_check_tab_v2.py (commit a3eda6c)
3. ✅ tests/integration/test_integrity_tab_integration_v2.py (commit 9ca9244)
4. ✅ tests/unit/test_model_manager_v2.py (EXCEPTION - was handled by Worker)
5. ✅ tests/unit/test_network_failure_simulation_v2.py (EXCEPTION - was handled by Worker)

**High Priority - Reworked and Improved:**
- ✅ tests/integration/test_end_to_end_satellite_download_v2.py (44→20 issues, 55% reduction, commit 4f30bf9)
- ✅ tests/integration/test_headless_workflow_v2.py (27→17 issues, 37% reduction, commit 3a0b811)

**Remaining Integration Tests (14 files):**
- tests/integration/test_full_application_workflow_v2.py
- tests/integration/test_preview_functionality_v2.py
- tests/integration/test_pipeline_v2.py
- tests/integration/test_preview_integration_v2.py
- tests/integration/test_vfi_worker_v2.py
- tests/integration/test_video_processing_pipeline_v2.py
- tests/integration/test_all_gui_elements_v2.py
- tests/integration/test_crop_dialog_integration_v2.py
- tests/integration/test_enhanced_preview_validation_v2.py
- All other integration test files

**All GUI Tests (17 files):**
- tests/gui/test_main_window_v2.py
- tests/gui/test_gui_components_v2.py
- tests/gui/test_enhanced_main_tab_v2.py
- tests/gui/test_settings_advanced_v2.py
- tests/gui/test_accessibility_v2.py
- tests/gui/test_error_handling_ui_v2.py
- tests/gui/test_performance_ui_v2.py
- tests/gui/test_workflows_integration_v2.py
- tests/gui/imagery/test_band_selector_v2.py
- tests/gui/imagery/test_imagery_dialog_v2.py
- tests/gui/imagery/test_imagery_loader_v2.py
- tests/gui/imagery/test_imagery_manager_v2.py
- tests/gui/tabs/test_about_tab_v2.py
- tests/gui/tabs/test_main_tab_v2.py
- tests/gui/tabs/test_preview_tab_v2.py
- tests/gui/tabs/test_render_tab_v2.py
- tests/gui/tabs/test_settings_tab_v2.py

**Other/Special Cases (9 files):**
- tests/unit/test_date_utils_v2.py
- tests/unit/test_processing_view_model_ffmpeg_v2.py
- tests/unit/test_rife_analyzer_v2.py
- tests/unit/test_s3_unsigned_access_v2.py
- tests/unit/test_security_v2.py
- tests/unit/test_main_tab_optimized_v2.py
- tests/unit/test_model_manager_optimized_v2.py
- tests/unit/test_network_failure_simulation_optimized_v2.py
- tests/unit/test_security_optimized_v2.py

## Summary Statistics
- **Total v2 files**: 141
- **Completed and clean**: 16 files (11%)
- **Lead Agent**: 11 completed, 83 remaining
- **Worker Agent**: 7 completed (2 reworked), 40 remaining
- **Progress Today**: 9 files improved (7 completed, 2 partially fixed)

## Next Actions

### For Lead Agent:
1. Continue with unit test files, starting with smaller files
2. Work systematically through all 83 remaining unit test files
3. Focus on core functionality tests first (pipeline, processing, etc.)
4. Next priorities: test_processing_* files, test_ffmpeg_builder_* files

### For Worker Agent:
1. **FIRST**: Fix the 2 files with remaining issues
2. Complete all remaining integration tests (14 files)
3. Move to GUI tests (17 files)
4. Handle the 9 special case files last

## Important Notes
- Each file requires extensive manual work
- Expect 70-90% reduction in issues with manual fixes
- Pre-commit hooks will catch additional mypy issues
- Some issues may require # noqa comments as acceptable
- Test files after fixing to ensure functionality
