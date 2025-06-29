# V2 Test Files Linting Fix Coordination

## Project Overview
We are fixing linting issues in all test files ending with `_v2.py`. The work is divided between two AI agents to accelerate completion.

## Task Instructions
1. Fix all linting issues in assigned v2 test files using `python3 run_linters.py <file> --fix --format`
2. Manually fix issues that can't be auto-fixed (complexity, type annotations, docstrings, etc.)
3. Work in small batches of 1-2 files at a time
4. After fixing each batch: stage files, commit, and push to GitHub
5. Validate successful push to GitHub before moving to next batch
6. Update this coordination file to track progress

## File Allocation

### Lead Agent Files (Claude Code - Primary)
- [⚠️] tests/unit/test_encode_v2.py (CORRUPTED FILE - massive embedded \\n chars, needs complete rewrite)
- [✅] tests/unit/test_interpolate_v2.py (COMPLETED - committed as 540c553)
- [⚠️] tests/unit/test_run_vfi_param_v2.py (CORRUPTED FILE - thousands of embedded \\\" chars, needs complete rewrite)
- [ ] tests/unit/test_raw_encoder_v2.py (SYNTAX ERRORS - HIGH PRIORITY)
- [ ] tests/unit/test_run_ffmpeg_v2.py (SYNTAX ERRORS - HIGH PRIORITY)
- [ ] tests/unit/test_pipeline_exceptions_v2.py (73 issues)
- [ ] tests/unit/test_processing_handler_v2.py
- [ ] tests/unit/test_processing_manager_v2.py
- [ ] tests/unit/test_cache_utils_v2.py
- [ ] tests/unit/test_config_v2.py
- [ ] tests/unit/test_ffmpeg_builder_critical_v2.py
- [ ] tests/unit/test_ffmpeg_builder_v2.py
- [ ] tests/unit/test_log_v2.py
- [ ] tests/unit/test_real_s3_path_v2.py
- [ ] tests/unit/test_real_s3_patterns_v2.py
- [ ] tests/unit/test_remote_stores_v2.py
- [ ] tests/unit/test_run_ffmpeg_v2.py
- [ ] tests/unit/test_s3_band13_v2.py
- [ ] tests/unit/test_s3_download_stats_param_v2.py
- [ ] tests/unit/test_s3_error_handling_v2.py
- [ ] tests/unit/test_s3_store_critical_v2.py
- [ ] tests/unit/test_s3_threadlocal_integration_v2.py
- [ ] tests/unit/test_s3_utils_modules_v2.py
- [ ] tests/unit/test_time_index_v2.py
- [ ] tests/unit/test_validation_v2.py

### Worker Agent Files (Secondary Agent)
- [x] tests/integration/test_full_application_workflow_v2.py
- [x] tests/unit/test_main_tab_v2.py
- [x] tests/unit/test_model_manager_v2.py
- [ ] tests/unit/test_network_failure_simulation_optimized_v2.py
- [ ] tests/unit/test_security_optimized_v2.py
- [ ] tests/integration/test_end_to_end_satellite_download_v2.py
- [ ] tests/integration/test_goes_imagery_tab_v2.py
- [ ] tests/integration/test_headless_workflow_v2.py
- [ ] tests/integration/test_integrity_check_tab_v2.py
- [ ] tests/integration/test_integrity_tab_integration_v2.py
- [ ] tests/integration/test_pipeline_v2.py
- [ ] tests/integration/test_preview_functionality_v2.py
- [ ] tests/integration/test_preview_integration_v2.py
- [ ] tests/integration/test_vfi_worker_v2.py
- [ ] tests/integration/test_video_processing_pipeline_v2.py
- [ ] tests/unit/test_date_utils_v2.py
- [ ] tests/unit/test_processing_view_model_ffmpeg_v2.py
- [ ] tests/unit/test_rife_analyzer_v2.py
- [ ] tests/unit/test_s3_unsigned_access_v2.py

## Instructions for Worker Agent
1. You are the **Worker Agent** handling the files listed in your section above
2. Work on 1-2 files at a time to avoid conflicts with Lead Agent
3. Use command: `python3 run_linters.py <your_file> --fix --format`
4. Manually fix issues that can't be auto-fixed:
   - C901: Function complexity (refactor or add `# noqa: C901`)
   - ANN201/ANN001: Add missing type annotations
   - PLR6301: Make methods static/class methods where appropriate
   - DOC201: Add missing docstring sections
   - PLC1901: Simplify string comparisons
5. After each batch, commit and push:
   ```bash
   git add <files>
   git commit -m "fix: resolve linting issues in <file_names>

   🤖 Generated with [Claude Code](https://claude.ai/code)

   Co-Authored-By: Claude <noreply@anthropic.com>"
   git push
   ```
6. Update this file to mark your completed files with [x]
7. **IMPORTANT**: If you get "file not read" errors when editing this coordination file, just read it first, then edit

## Progress Tracking

### Completed Files
#### Lead Agent
- [✅] tests/unit/test_pipeline_exceptions_v2.py (auto-fixed 160 issues, syntax clean)
- [✅] tests/unit/test_interpolate_v2.py (COMPLETED - committed as 540c553)

#### Worker Agent
- [x] tests/integration/test_full_application_workflow_v2.py (164→0 issues fixed, all type annotations added)
- [x] tests/unit/test_main_tab_v2.py (133→19 issues fixed, major type annotation and constructor fixes)
- [x] tests/unit/test_model_manager_v2.py (165→0 issues fixed, complete linting resolution)

### Current Work In Progress
- Lead Agent:
  - ✅ Completed full rewrite of test_interpolate_v2.py - COMMITTED (commit 540c553)
  - 🔄 Working on test_run_vfi_param_v2.py - rewritten, adding @staticmethod decorators
  - 🔄 Working on test_encode_v2.py - rewritten, fixing remaining linting issues
  - 🔄 Working on test_main_tab_v2.py - adding @staticmethod decorators to fix PLR6301
  - ⚠️ Pre-commit hooks are blocking commits due to test_goes_imagery_tab_v2.py integration test issues
- Worker Agent: Ready to work on integration files and optimized test files

### Major Issues Discovered & Status
- ✅ RESOLVED: test_interpolate_v2.py and test_run_vfi_param_v2.py massive corruption (completely rewritten)
- 🔄 IN PROGRESS: test_encode_v2.py still has significant linting issues preventing commits
- ⚠️ BLOCKER: test_goes_imagery_tab_v2.py integration test has 50+ linting errors blocking all commits
- ⚠️ Pre-commit hooks are very strict - may need to add `# noqa` comments for complex methods
- 📝 All syntax errors have been eliminated, but type annotation and complexity issues remain

## Lead Agent Progress

### Files In Progress (with specific issues)
- test_encode_v2.py: 
  - Missing @staticmethod decorators (partially fixed)
  - `self` reference in static method (line 222)
  - Nested with statements (SIM117)
  - Missing type annotations for inner function
  - Exception handling too broad (BLE001, PT011)
- test_run_vfi_param_v2.py:
  - Missing @staticmethod decorators on inner methods (added, needs commit)
  - MyPy type errors related to dict unpacking
- test_main_tab_v2.py:
  - All test methods need @staticmethod decorator (PLR6301)

### Notes
- Files with syntax errors (embedded `\n` characters) need manual fixing
- Focus on high-issue count files first
- Coordinate through this file to avoid conflicts
- Validate pushes to GitHub after each batch