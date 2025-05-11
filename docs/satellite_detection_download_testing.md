# Satellite Detection and Download Testing Guide

This document describes the testing approach and test cases for the enhanced satellite detection and download error handling in the GOES_VFI application.

## Test Coverage

The test suite includes tests for:

1. **Satellite Auto-Detection**
   - Auto-detection of GOES-16 and GOES-18 satellites
   - Error handling for invalid file formats and directories
   - Validation of logging behavior during auto-detection
   - Recovery from errors during satellite detection

2. **S3 Error Handling**
   - Testing various error scenarios during S3 file lookups and downloads
   - Validating error message formatting and content
   - Ensuring proper error classification (Authentication, Connection, Not Found, etc.)
   - Validating the recovery and retry behavior

3. **Enhanced Status Messages**
   - Verification of step-progress message formatting
   - Testing error message formatting with troubleshooting tips
   - Validation of context-specific error messages for different error types
   - Testing successful completion message formatting

## Running the Tests

```bash
cd /Users/justin/Documents/Github/GOES_VFI
source venv-py313/bin/activate
python -m pytest tests/unit/test_enhanced_status_messages.py -v
python -m pytest tests/unit/test_s3_error_handling.py -v
python -m pytest tests/unit/test_auto_detect_features.py -v
```

## Test Failures Note

Some of the tests may fail when run directly due to:

1. Asyncio event loop requirements in the S3 error handling tests
   - These tests need to be run in an environment with a properly configured asyncio event loop

2. Specific error message pattern matching in status message tests
   - The error message patterns need to match the exact HTML formatting in the status label

These tests can be used as a development guide, but full integration testing should be done manually to verify the complete user experience.

## Manual Testing Checklist

- [ ] Verify satellite auto-detection with valid GOES-16 files
- [ ] Verify satellite auto-detection with valid GOES-18 files
- [ ] Test auto-detection with mixed file types
- [ ] Test auto-detection with invalid file types
- [ ] Verify detailed error messages during satellite detection failures
- [ ] Test S3 download with valid timestamps
- [ ] Test S3 download with invalid timestamps
- [ ] Verify download error handling with network disconnection
- [ ] Test enhanced status messages for various operations
- [ ] Verify logs contain detailed diagnostic information

## Troubleshooting

When encountering test failures:

1. Check if the error is related to asyncio event loop configuration
2. Verify that the exact string patterns in the status message tests match the implementation
3. For integration tests, ensure the test environment has proper network connectivity
4. Examine application logs for detailed error information

## Future Test Improvements

Areas for future test enhancement:

1. Add complete end-to-end integration tests for the auto-detection and download workflow
2. Create mock S3 responses for more deterministic S3 error testing
3. Add more specific test cases for network-related errors
4. Enhance asyncio testing setup to properly handle event loops
