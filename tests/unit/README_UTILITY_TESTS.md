# Utility Function Tests

This directory contains comprehensive tests for utility functions across the GOES_VFI project.

## Test Files Created

### 1. `test_main_tab_utils.py`
Tests for utility functions in the MainTab GUI component:
- **TestValidateThreadSpec**: Tests the thread specification validation for RIFE
  - Empty thread spec allowed
  - Valid formats (N:N:N)
  - Invalid formats detection

- **TestGenerateTimestampedOutputPath**: Tests output path generation
  - Generation with base parameters
  - Generation from input directory
  - Fallback to current working directory
  - Timestamp format validation

- **TestCheckInputDirectoryContents**: Tests directory content analysis
  - Empty directory handling
  - Directory with valid images
  - Mixed file types
  - Corrupt image handling

- **TestGetProcessingArgs**: Tests processing argument collection
  - Missing input/output validation
  - RIFE encoder configuration
  - FFmpeg encoder configuration
  - Output directory creation

- **TestVerifyCropAgainstImages**: Tests crop validation
  - Valid crop rectangles
  - Crops exceeding image bounds
  - Empty directory handling

- **TestSetInputDirectory**: Tests input directory setting
  - String path handling
  - Path object handling

- **TestVerifyStartButtonState**: Tests start button state validation
  - Enabled state conditions
  - Disabled state conditions

### 2. `test_gui_helpers.py`
Tests for GUI helper utilities and widgets:
- **TestClickableLabel**: Tests custom clickable label widget
  - Signal emission on click
  - Mouse button differentiation

- **TestZoomDialog**: Tests zoom dialog functionality
  - Initialization and styling
  - Click-to-close behavior

- **TestCropDialog**: Tests crop selection dialog
  - Initialization with/without initial rectangle
  - Coordinate scaling
  - Mouse interaction for selection

- **TestRifeCapabilityManager**: Tests RIFE capability detection management
  - Successful capability detection
  - Detection failure handling
  - UI element updates based on capabilities
  - Capability summary generation

- **TestImageViewerDialog**: Tests advanced image viewer
  - Zoom functionality (wheel events)
  - Pan functionality (drag events)
  - Click-to-close without drag

- **TestCropLabel**: Tests crop selection label widget
  - Selection start/update/finish
  - Coordinate mapping
  - Signal emission

- **TestCropSelectionDialog**: Tests full crop selection dialog
  - Rectangle selection and scaling
  - Boundary clamping
  - Invalid selection handling

### 3. `test_rife_analyzer.py`
Tests for RIFE executable analysis utilities:
- **TestRifeCapabilityDetector**: Tests RIFE CLI capability detection
  - Successful capability detection
  - Executable not found handling
  - Help command failure handling
  - Version detection from various formats
  - Partial capability support
  - Command building with/without optional features

- **TestAnalyzeRifeExecutable**: Tests the analysis wrapper function
  - Successful analysis
  - File not found handling
  - Detection error handling

## Existing Test Coverage

### Already Tested
- **date_utils.py**: Comprehensive tests exist in `test_date_utils.py`
  - Date to day-of-year conversion
  - Day-of-year to date conversion
  - Satellite path parsing
  - Path formatting

- **config.py**: Tests exist in `test_config.py`
  - Configuration loading
  - Default values
  - RIFE executable finding

## Running the Tests

To run all utility function tests:
```bash
# Activate virtual environment
source .venv/bin/activate

# Run all utility tests
python -m pytest tests/unit/test_*utils*.py tests/unit/test_*helpers*.py tests/unit/test_*analyzer*.py -v

# Run specific test file
python -m pytest tests/unit/test_main_tab_utils.py -v
python -m pytest tests/unit/test_gui_helpers.py -v
python -m pytest tests/unit/test_rife_analyzer.py -v

# Run with coverage
python -m pytest tests/unit/test_*utils*.py --cov=goesvfi.utils --cov=goesvfi.gui_tabs
```

## Test Design Principles

1. **Isolation**: Each test is independent and uses mocks for external dependencies
2. **Coverage**: Tests cover both success and failure paths
3. **PyQt6 Compatibility**: GUI tests properly handle Qt application lifecycle
4. **Type Safety**: Tests verify type hints and return types
5. **Edge Cases**: Tests include boundary conditions and error scenarios

## Future Enhancements

- Add performance benchmarks for utility functions
- Test thread safety for concurrent operations
- Add integration tests for utility function combinations
- Test memory usage for image processing utilities
