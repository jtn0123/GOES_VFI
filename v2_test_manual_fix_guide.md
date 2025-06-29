# V2 Test Files Manual Fix Guide

## Overview
The v2 test files have linting issues that **cannot be auto-fixed**. Each file requires manual intervention to add type annotations, decorators, and documentation.

## Common Issues and Fixes

### 1. Missing Return Type Annotations (ANN201)
**Issue**: Functions/methods missing return type annotations
**Fix**: Add `-> ReturnType:` after function parameters
```python
# Before
def exception_test_components(self):

# After
def exception_test_components(self) -> dict[str, Any]:
```

### 2. Method Could Be Static (PLR6301)
**Issue**: Methods that don't use `self` should be static
**Fix**: Add `@staticmethod` decorator OR add `# noqa: PLR6301` if method needs to remain instance method
```python
# Option 1: Make static
@staticmethod
def _test_helper() -> None:

# Option 2: Keep as instance method
def _test_helper(self) -> None:  # noqa: PLR6301
```

### 3. Missing Argument Type Annotations (ANN001)
**Issue**: Function arguments missing type hints
**Fix**: Add type hints to all parameters
```python
# Before
def test_function(arg1, arg2):

# After
def test_function(arg1: str, arg2: int) -> None:
```

### 4. Missing Returns Documentation (DOC201)
**Issue**: Docstring missing Returns section when function returns a value
**Fix**: Add Returns section to docstring
```python
def get_value() -> int:
    """Get a test value.

    Returns:
        int: The test value.
    """
    return 42
```

### 5. Function Complexity Too High (C901)
**Issue**: Function exceeds complexity threshold
**Fix**: Add `# noqa: C901` comment (refactoring would break tests)
```python
def complex_function() -> None:  # noqa: C901
    """Complex test function."""
```

### 6. Private Member Access (SLF001)
**Issue**: Accessing private members (starting with _)
**Fix**: Add `# noqa: SLF001` for legitimate test access
```python
obj._private_method()  # noqa: SLF001
```

### 7. Compare to Empty String (PLC1901)
**Issue**: Using `== ""` instead of checking truthiness
**Fix**: Use `not string` or keep with `# noqa: PLC1901`
```python
# Before
if value == "":

# After (Option 1)
if not value:

# After (Option 2)
if value == "":  # noqa: PLC1901
```

## Files Requiring Manual Fixes

### Unit Tests (19 files, ~3,600 total issues)
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

## Recommended Approach

1. **Start with smaller files** (80-150 issues) to establish patterns
2. **Fix one type of issue at a time** across the file
3. **Run linter after each major change** to verify fixes
4. **Test the file** after fixing to ensure tests still pass
5. **Commit frequently** after fixing each file

## Example Fix Process

```bash
# 1. Check current issues
ruff check tests/unit/test_validation_v2.py --statistics

# 2. Open file and add type annotations to all methods
# 3. Add @staticmethod decorators where needed
# 4. Add Returns sections to docstrings
# 5. Add noqa comments for acceptable violations

# 6. Verify fixes
python3 run_linters.py tests/unit/test_validation_v2.py --check

# 7. Run tests to ensure they still pass
python -m pytest tests/unit/test_validation_v2.py

# 8. Commit
git add tests/unit/test_validation_v2.py
git commit -m "fix: add type annotations and resolve linting issues in test_validation_v2.py"
```
