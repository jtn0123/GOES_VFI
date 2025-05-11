# Test Organization Implementation Plan

This document outlines the specific steps to organize the test files in the GOES-VFI repository.

## Step 1: Create New Directories

```bash
# Create examples directory structure
mkdir -p examples/download
mkdir -p examples/s3_access
mkdir -p examples/imagery
mkdir -p examples/processing

# Create proper test directory structure
mkdir -p tests/gui/imagery
mkdir -p tests/gui/tabs
```

## Step 2: Move Files to Examples Directory

These files are prototype/example scripts that would be better as examples than tests:

```bash
# Download examples
git mv test_download_band13.py examples/download/download_band13.py
git mv test_download_mesoscale.py examples/download/download_mesoscale.py
git mv test_download_all_products.py examples/download/download_all_products.py
git mv test_download_full_disk.py examples/download/download_full_disk.py
git mv test_download_real.py examples/download/download_real.py

# S3 access examples
git mv test_s3_list.py examples/s3_access/s3_list.py
git mv test_s3_band13.py examples/s3_access/s3_band13.py

# Imagery examples
git mv test_netcdf_channel_extraction.py examples/imagery/netcdf_channel_extraction.py
git mv test_satpy_rendering.py examples/imagery/satpy_rendering.py
git mv test_goes_product_detection.py examples/imagery/goes_product_detection.py
git mv test_run_goes_imagery.py examples/imagery/run_goes_imagery.py

# Processing examples
git mv test_sanchez.py examples/processing/sanchez_processing.py
```

## Step 3: Move Tests to Proper Test Directories

These files contain actual test code that should be moved to the proper test directories:

```bash
# Move unit tests to unit directory
git mv test_signal.py tests/unit/test_signal.py
git mv test_timestamp.py tests/unit/test_timestamp.py

# Move integration tests to integration directory
git mv test_vfi_worker.py tests/integration/test_vfi_worker.py
git mv test_unified_interface.py tests/integration/test_unified_interface.py
git mv test_combined_tab.py tests/integration/test_combined_tab.py

# Move GUI tests to GUI directories
git mv test_imagery_enhancement.py tests/gui/imagery/test_imagery_enhancement.py
git mv test_imagery_gui.py tests/gui/imagery/test_imagery_gui.py
git mv test_imagery_gui_fixed.py tests/gui/imagery/test_imagery_gui_fixed.py
git mv test_imagery_gui_zoom.py tests/gui/imagery/test_imagery_zoom.py
git mv test_imagery_simple.py tests/gui/imagery/test_imagery_simple.py
git mv test_fallback_preview.py tests/gui/imagery/test_fallback_preview.py
git mv test_enhanced_imagery_tab.py tests/gui/tabs/test_enhanced_imagery_tab.py
git mv test_goes_ui.py tests/gui/test_goes_ui.py
git mv test_imagery_error_handling.py tests/gui/test_imagery_error_handling.py
```

## Step 4: Remove Redundant Test Files

These files are redundant with newer tests and can be safely removed:

```bash
# Remove redundant tests
git rm test_s3_unsigned_access.py  # Covered by tests/unit/test_s3_unsigned_access.py
git rm test_real_s3_paths.py  # Covered by tests/unit/test_real_s3_patterns.py
git rm test_real_s3_path.py  # Covered by tests/unit/test_real_s3_patterns.py
git rm test_imagery_simplified.py  # Redundant with test_imagery_simple.py
```

## Step 5: Update Test Runners

Update the test runner scripts to reflect the new organization:

1. Update `run_working_tests.py` to include the newly moved tests
2. Update `run_fixed_gui_tests.py` to reference the correct paths
3. Update `run_fixed_integration_tests.py` to include any moved integration tests
4. Update `run_all_tests.py` to correctly find all tests in the new structure

## Step 6: Create README files

Create README files in each directory to explain the purpose of the tests/examples:

```bash
# Create README files for examples directories
cat > examples/README.md << EOL
# Examples

This directory contains example scripts demonstrating various GOES-VFI functionality.
These are not formal tests but rather demonstrations of how to use different features.
EOL

cat > examples/download/README.md << EOL
# Download Examples

Example scripts demonstrating how to download GOES satellite data from various sources.
EOL

cat > examples/s3_access/README.md << EOL
# S3 Access Examples

Example scripts demonstrating how to access GOES data from AWS S3 buckets.
EOL

cat > examples/imagery/README.md << EOL
# Imagery Examples

Example scripts demonstrating how to work with GOES satellite imagery.
EOL

cat > examples/processing/README.md << EOL
# Processing Examples

Example scripts demonstrating how to process GOES satellite data.
EOL

# Create README for new test directories
cat > tests/gui/imagery/README.md << EOL
# Imagery GUI Tests

Tests for the imagery-related GUI components of the GOES-VFI application.
EOL

cat > tests/gui/tabs/README.md << EOL
# Tab GUI Tests

Tests for the various tabs in the GOES-VFI application GUI.
EOL
```

## Step 7: Update Tests to Ensure Compatibility

Some test files might need updates after moving to maintain imports and path compatibility:

1. Check imports in moved files to ensure they use the correct relative imports
2. Update any hardcoded paths in tests to use proper relative paths
3. Make sure fixtures are correctly used and accessible from the new locations

## Step 8: Verify Tests Still Run

Run the test runners to verify that the reorganized tests still run properly:

```bash
./run_working_tests.py
./run_fixed_gui_tests.py
./run_fixed_integration_tests.py
./run_all_tests.py
```

## Step 9: Update Documentation

Update relevant documentation to reflect the new organization:

1. Update CLAUDE.md to mention the examples directory
2. Update README.md with information about the examples
3. Document any changes to test running procedures
