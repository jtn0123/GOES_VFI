# Linting Fix Plan for GOES-VFI

## Issue Summary

The codebase currently has the following linting issues:

1. **Total linting issues**: 888
2. **Line length issues (B950)**: 116
3. **Unused imports (F401)**: 425 
4. **f-string formatting issues (B907)**: 94
5. **Complex functions (C901)**: 65
6. **Other issues**: 188

## Phase 1: Simple Automated Fixes

These issues can be fixed with automated scripts with minimal risk:

- **Fix unused imports**: These account for nearly half of all linting issues and can be safely removed with automated tools
- **Fix f-string formatting**: Replace manual quotes with `!r` conversion flags
- **Fix line length issues**: Add line breaks or `# noqa: B950` comments for long lines

## Phase 2: Module-by-Module Cleanup

Clean up code module by module, prioritizing by importance:

1. **Core modules**:
   - `goesvfi/integrity_check/` - Core functionality for satellite data integrity 
   - `goesvfi/pipeline/` - Processing pipeline for images
   - `goesvfi/utils/` - Shared utility functions

2. **GUI modules**:
   - `goesvfi/gui.py` - Main application window
   - `goesvfi/gui_tabs/` - Tab components
   - `goesvfi/date_sorter/` and `goesvfi/file_sorter/` - File management GUI components

## Phase 3: Address Complex Function Issues

Functions identified as too complex (C901) should be refactored:

1. Use Extract Method to break large functions into smaller ones
2. Consider using the Strategy pattern for functions with many conditional branches
3. Create helper classes to handle specific functionality
4. Add unit tests before refactoring to ensure behavior is preserved

## Implementation Plan

### Week 1: Automated Fixes (Low Risk)

1. **Fix Unused Imports**:
   - Use `fix_imports.py` script to clean up imports in all files
   - Verify changes with unit tests

2. **Fix f-string formatting**:
   - Update all f-strings to use proper `!r` conversion flags
   - Create unit tests for string formatting functions

3. **Fix Line Length Issues**:
   - Add line breaks for long function calls and assignments
   - Use `# noqa: B950` for documentation strings and comments

### Week 2: Core Module Cleanup

1. **Integrity Check Module**:
   - Clean up imports
   - Fix remaining formatting issues
   - Add typing annotations where missing

2. **Pipeline Module**:
   - Clean up imports
   - Fix string formatting
   - Fix line length issues 

3. **Utils Module**:
   - Standardize logging practices
   - Fix GUI helper issues
   - Clean up string formatting

### Week 3: GUI Module Cleanup

1. **Main GUI File**:
   - Clean up remaining imports
   - Fix complexity issues in key functions
   - Add proper type annotations

2. **Tab Modules**:
   - Fix imports in tab modules
   - Standardize tab interface implementations 
   - Clean up long lines in UI construction code

### Week 4: Complex Function Refactoring

Identify and refactor the most complex functions:

1. `scan_for_missing_intervals` in `date_sorter/sorter.py` (complexity: 15)
2. `SanchezProcessor.process` in `pipeline/sanchez_processor.py` (complexity: 26)
3. `AsyncDownloadTask._run_downloads` in `integrity_check/enhanced_view_model.py` (complexity: 18)
4. `MainWindow._update_previews` and other complex UI functions in `gui.py`

## Tooling and Scripts

The following tools will be used:

1. **Fix Imports**: `python fix_imports.py [FILE_PATH]`
2. **Fix f-strings**: `python fix_fstrings.py [FILE_PATH]` 
3. **Fix Line Lengths**: `python fix_line_length.py [FILE_PATH]`

## Metrics and Monitoring

Progress will be tracked by:

1. Running `flake8 goesvfi/ --count` to get updated issue counts
2. Maintaining a linting score by module in LINTING_PROGRESS.md
3. Tracking issue count by type:
   ```
   flake8 goesvfi/ --select=F401 --count  # Unused imports
   flake8 goesvfi/ --select=B950 --count  # Line length issues
   flake8 goesvfi/ --select=B907 --count  # f-string formatting
   flake8 goesvfi/ --select=C901 --count  # Complex functions
   ```

## Legacy Test Handling

To ensure changes don't break existing functionality:

1. Run unit tests after each phase: `./run_working_tests.py`
2. Run non-GUI tests: `./run_non_gui_tests.py`
3. Run fixed GUI tests with special care: `./run_fixed_gui_tests.py`

## Completion Criteria

The linting fix project will be considered complete when:

1. Line count for `flake8 goesvfi/ --count` is below 100
2. No unused imports remain
3. All f-string formatting issues are fixed
4. Line length issues are either fixed with line breaks or have appropriate `# noqa` comments
5. Complex functions are refactored or have documented justification