# Failing Tests Analysis

## Overall Summary
- **Total Tests Run**: 541 (excluding GUI/tab/dialog tests)
- **Passed**: 464
- **Failed**: 77
- **Skipped**: 8
- **Errors**: 2
- **Success Rate**: ~85.8%

## Update: Additional Failing Tests from GitHub Actions

### New Test Failures Identified:

1. **test_stats_updated_on_download_failure** (test_s3_download_stats.py:324)
   - **Error**: `AssertionError: 0 != 1`
   - **Issue**: The test expects download stats to be updated when a download fails, but the statistics show 0 failed attempts instead of 1
   - **Root Cause**: In the current implementation, when a `ResourceNotFoundError` occurs during wildcard search (line 1825-1827 in s3_store.py), the error is re-raised without updating download statistics
   - **Fix**: Update download stats before re-raising ResourceNotFoundError

2. **test_download_wildcard_not_found** (test_s3_error_handling.py:119)
   - **Error**: `AssertionError: 'Unexpected error searching' not found in 'No files found for GOES_18 at 2023-06-15T12:00:00'`
   - **Issue**: The test expects the error message to contain "Unexpected error searching", but it's getting "No files found for..."
   - **Root Cause**: When no matching objects are found during wildcard search, a `ResourceNotFoundError` is raised with the message "No files found for..." (line 1517), not "Unexpected error searching"
   - **Fix**: Update test expectation to match actual error message

3. **test_download_with_unsigned_access** (test_s3_unsigned_access.py:172)
   - **Error**: `AssertionError: Expected 'download_file_file' to have been called once. Called 0 times.`
   - **Issue**: The test is checking for `download_file_file` but should be checking for `download_file`
   - **Root Cause**: Typo in the test - the mock is set up as `self.s3_client_mock.download_file_file` (line 181) but the actual method is `download_file`
   - **Fix**: Correct the typo in the mock method name

4. **test_run_goes_imagery** (unittest.loader._FailedTest)
5. **test_s3_list** (unittest.loader._FailedTest)
6. **test_timestamp** (unittest.loader._FailedTest)
   - **Issue**: These test files don't exist but are referenced in reorganize_tests.py
   - **Root Cause**: The files `/tests/unit/test_run_goes_imagery.py`, `/tests/unit/test_s3_list.py`, and `/tests/unit/test_timestamp.py` were likely removed or renamed but are still referenced in the test discovery
   - **Fix**: Remove references to non-existent test files from reorganize_tests.py

## Detailed Analysis of Failing Tests

### 1. test_goes_imagery.py (6 failures)

#### Missing Attributes/Methods on ChannelType:
- **Test**: `test_channel_type_enum`
- **Error**: `AttributeError: 'ChannelType' object has no attribute 'is_infrared'`
- **Expected**: Properties `is_infrared`, `is_near_ir`, `is_water_vapor`
- **Current**: Only has `is_visible`, `is_ir`, `is_composite`
- **Fix**: Add missing properties to ChannelType class

#### Missing Classes:
- **Test**: `test_download_precolorized_image`, `test_get_imagery_product_mode`
- **Error**: `AttributeError: module 'goesvfi.integrity_check.goes_imagery' has no attribute 'GOESImageryDownloader'`
- **Expected**: `GOESImageryDownloader` class
- **Current**: Only has `GOESImageryManager` (stub implementation)
- **Fix**: Implement GOESImageryDownloader class

- **Test**: `test_extract_timestamp_from_filename`, `test_get_imagery_raw_mode`
- **Error**: `NameError: name 'GOESImageProcessor' is not defined`
- **Expected**: `GOESImageProcessor` class
- **Current**: Missing entirely
- **Fix**: Implement GOESImageProcessor class

#### Missing Module Import:
- **Test**: `test_download_precolorized_image`
- **Error**: `AttributeError: module 'goesvfi.integrity_check.goes_imagery' has no attribute 'requests'`
- **Expected**: `requests` module to be imported
- **Fix**: Add `import requests` to goes_imagery.py

#### Missing Methods on ProductType:
- **Test**: `test_product_type_mapping`
- **Error**: `AttributeError: type object 'ProductType' has no attribute 'to_s3_prefix'`
- **Expected**: Class methods `to_s3_prefix()` and `to_web_path()`
- **Current**: ProductType is a simple Enum
- **Fix**: Add static methods to ProductType enum

### 2. test_encode.py (4 failures)

#### Encoder Name Mismatch:
- **Tests**: All `test_single_pass_encoders` variations
- **Error**: `ValueError: Unsupported encoder selected: libx265` (and libx264)
- **Issue**: The encode.py module sets encoder to "libx265"/"libx264" but FFmpegCommandBuilder expects "Software x265"/"Software x264"
- **Fix Options**:
  1. Update encode.py to use the full encoder names
  2. Update FFmpegCommandBuilder to accept short names
  3. Add mapping logic between short and full names

### 3. test_s3_store_critical.py (1 failure)

#### Exception Type Mismatch:
- **Test**: `test_download_not_found`
- **Error**: Test expects `ResourceNotFoundError` but gets `RemoteStoreError`
- **Issue**: When no files are found, the code wraps ResourceNotFoundError in RemoteStoreError
- **Current behavior**: The error is caught and re-raised as RemoteStoreError in line 1856
- **Fix Options**:
  1. Update test to expect RemoteStoreError
  2. Update S3Store to preserve the original ResourceNotFoundError
  3. Check if the wrapping is intentional for error handling consistency

### 4. test_memory_management.py (5 failures)

#### Return Value Mismatch:
- **Test**: `test_check_available_memory`
- **Error**: Expected "OK" but got "Memory available: 6544MB"
- **Issue**: The method returns a descriptive message instead of just "OK"
- **Fix**: Either update test expectations or change the return value

#### Missing Private Attribute:
- **Test**: `test_pool_max_size`
- **Error**: `AttributeError: 'ObjectPool' object has no attribute '_pool'`
- **Issue**: Test tries to access private attribute `_pool` but class has `pool`
- **Fix**: Update test to use correct attribute name

#### Missing Test Files:
- **Tests**: `test_memory_optimized_loading`, `test_image_size_limit`
- **Error**: `FileNotFoundError: Image file not found: test.png` / `huge.png`
- **Issue**: Tests expect image files that don't exist
- **Fix**: Mock the file operations or create test fixtures

#### Calculation Mismatch:
- **Test**: `test_estimate_memory_requirement`
- **Error**: Expected 2MB but got 3MB
- **Issue**: Memory calculation logic differs from test expectations
- **Fix**: Review calculation logic or update test expectations

### 5. test_auto_detect_features.py

- **Issue**: Test hangs/times out
- **Possible causes**: Infinite loop, blocking I/O, or GUI-related deadlock
- **Fix**: Investigate the test implementation for blocking operations

## Common Patterns

1. **Stub Implementations**: The goes_imagery.py module appears to have a stub implementation with missing functionality that tests expect
2. **Name Mismatches**: Encoder names don't match between different parts of the system
3. **Missing Methods/Properties**: Several expected methods and properties are not implemented
4. **Exception Hierarchy**: Error handling may need review for consistency
5. **Test Assumptions**: Some tests make assumptions about return values, file existence, or internal implementation details
6. **Attribute Access**: Tests accessing private attributes that may have been renamed

## Recommendations

1. **Priority 1**: Fix the goes_imagery.py module by implementing missing classes and methods
2. **Priority 2**: Resolve encoder name inconsistencies
3. **Priority 3**: Fix memory management test expectations and missing test fixtures
4. **Priority 4**: Review error handling patterns for consistency
5. **Priority 5**: Investigate hanging tests (may be GUI-related)

## Quick Fixes for GitHub Actions Failures

### 1. Fix test_stats_updated_on_download_failure
In `goesvfi/integrity_check/remote/s3_store.py` around line 1825-1827:
```python
except ResourceNotFoundError as e:
    # Update stats before re-raising
    update_download_stats(
        success=False,
        error_type="not_found",
        error_message=str(e)
    )
    raise
```

### 2. Fix test_download_wildcard_not_found
In `tests/unit/test_s3_error_handling.py` line 149:
```python
# Change from:
self.assertIn("Unexpected error searching", error_msg)
# To:
self.assertIn("No files found for", error_msg)
```

### 3. Fix test_download_with_unsigned_access
In `tests/unit/test_s3_unsigned_access.py`:
```python
# Line 181 - change from:
self.s3_client_mock.download_file_file = AsyncMock()
# To:
self.s3_client_mock.download_file = AsyncMock()

# Line 200 - change from:
self.s3_client_mock.download_file_file.assert_called_once()
# To:
self.s3_client_mock.download_file.assert_called_once()
```

### 4. Remove non-existent test references
Remove or update references to:
- `/tests/unit/test_run_goes_imagery.py`
- `/tests/unit/test_s3_list.py`
- `/tests/unit/test_timestamp.py`

These files should be removed from `examples/utilities/reorganize_tests.py` or any other test discovery mechanisms.
