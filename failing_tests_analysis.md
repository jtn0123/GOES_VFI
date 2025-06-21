# Failing Tests Analysis

## Overall Summary
- **Total Tests Run**: 541 (excluding GUI/tab/dialog tests)
- **Passed**: 464
- **Failed**: 77
- **Skipped**: 8
- **Errors**: 2
- **Success Rate**: ~85.8%

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
