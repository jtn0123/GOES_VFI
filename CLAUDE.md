# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Python Environment
This project uses Python 3.13. A virtual environment should be used:

```bash
# Create virtual environment with Python 3.13
python3 -m venv venv-py313

# Activate the environment
source venv-py313/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Build, Lint & Test Commands
- Run working tests only: `./run_working_tests.py`
- Run fixed GUI tests only: `./run_fixed_gui_tests.py`
- Run all tests: `./run_all_tests.py`
- Run a single test: `python -m pytest tests/path/to/test_file.py`
- Run a specific test function: `python -m pytest tests/path/to/test_file.py::test_function_name`
- Run with debug options: `./run_all_tests.py --debug-mode`
- Run in parallel: `./run_all_tests.py --parallel 4`
- Launch application: `source venv-py313/bin/activate && python -m goesvfi.gui`
- Debug mode: `source venv-py313/bin/activate && python -m goesvfi.gui --debug`

Note: Some tests may fail due to recent refactoring. When testing new changes:
- Use `run_working_tests.py` for non-GUI tests
- Use `run_fixed_gui_tests.py` for GUI tests (avoids segmentation faults)
- PyQt GUI tests are prone to segmentation faults - be careful when running all GUI tests at once

## Test Organization and Strategy

The repository has a well-organized structure for tests and examples:

### Examples Directory
- `/examples/`: Contains example scripts demonstrating various features
  - `/examples/download/`: Examples for downloading GOES satellite data
  - `/examples/s3_access/`: Examples for interacting with NOAA S3 buckets
  - `/examples/imagery/`: Examples of processing and rendering satellite imagery
  - `/examples/processing/`: Examples of various processing techniques
  - `/examples/visualization/`: Examples of data visualization techniques
  - `/examples/debugging/`: Examples for debugging specific functionality
  - `/examples/utilities/`: Utility scripts for code maintenance

**IMPORTANT**: When developing a new feature, first create it as an example script in the appropriate examples directory before integrating it into the main codebase. This allows for isolated testing and easier iteration.

### Test Directories
- `/tests/unit/`: Unit tests for individual components
- `/tests/integration/`: Integration tests for component interactions
- `/tests/gui/`: Tests for the PyQt6 user interface
  - `/tests/gui/imagery/`: Tests for imagery-related GUI components
  - `/tests/gui/tabs/`: Tests for various tab components
- `/tests/utils/`: Test utilities and helpers

### Legacy Tests
- `/legacy_tests/`: Contains potentially redundant or outdated tests for evaluation

### Testing Best Practices
These practices should be followed for all new tests:
1. **Test Independence**: Each test should run independently of others.
2. **Avoid Network Dependencies**: Mock external services and AWS S3 access.
3. **Use Fixtures**: Utilize pytest fixtures for common setup and teardown.
4. **Type Safety**: All test code should follow type hint best practices.
5. **Error Isolation**: Each test should clearly identify what feature is being tested.
6. **Test Naming**: Follow `test_{component}_{functionality}_{condition}` naming convention.

### Python Import Path Handling
All example scripts follow a standardized pattern for import path handling:
```python
# Add the repository root to the Python path
repo_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, repo_root)
```

This ensures examples can be run from any directory while properly accessing the project modules.

### Test Runner Scripts
Multiple test runners are provided for different testing scenarios:
- `run_working_tests.py`: Only runs reliable non-GUI tests
- `run_fixed_gui_tests.py`: Runs GUI tests with extra safeguards to prevent segfaults
- `run_all_tests.py`: Complete test suite (use with caution due to GUI test instability)

## Known Test Issues
- Some GUI tests may cause segmentation faults when testing FFmpeg controls directly
- Currently fixed and reliable tests include:
  - `test_initial_state`: Verifies initial UI state
  - `test_successful_completion`: Verifies UI updates after successful process completion
  - `test_change_settings_main_tab`: Tests settings in the main tab safely
  - `test_change_ffmpeg_profile`: Tests FFmpeg profile selection with extra safeguards

### GUI Testing Best Practices
1. Use `QApplication.processEvents()` frequently to ensure UI updates
2. Mock problematic signals to prevent cascading failures
3. Split tests into smaller, focused tests to isolate issues
4. Manually call update methods rather than relying on signal propagation
5. Add explicit `blockSignals(True/False)` around critical widget state changes
6. Restore original widget states at the end of each test
7. Add robust error handling in test teardown

## Code Style Guidelines
- Follow PEP 8 strictly; formatting done with Black (line length: 88)
- Use type hints for all functions/methods with Python's `typing` module
- Imports: Prefer absolute imports (e.g., `from goesvfi.utils import log`)
- Naming: `snake_case` for functions/variables, `CamelCase` for classes, `UPPER_SNAKE_CASE` for constants
- Logging: Use `LOGGER = log.get_logger(__name__)` for module-level logging
- Error handling: Use try/except with specific exceptions, log with `LOGGER.exception()`
- UI components: Follow MVVM pattern with view models for state management
- Testing: Use pytest fixtures for common setup/teardown operations

## Type Safety and Mypy

The codebase now has comprehensive type annotations and passes mypy checks in both standard and strict modes for core files. When adding or modifying code:

- Always include type annotations for function parameters and return values
- Use `Optional[Type]` when a value might be None
- Use `Union[Type1, Type2]` for variables that could have multiple types
- Properly annotate class attributes in `__init__` methods
- For numpy arrays, use `numpy.typing.NDArray[np.float64]` with specific dtype
- For collections, specify contained type: `List[str]`, `Dict[str, int]`, etc.
- Use type narrowing with `isinstance()` checks where needed
- Use `TypeVar` and generic types for polymorphic functions

### Mypy Checks

Run mypy checks with:
```bash
# Standard mode
python -m run_mypy_checks

# Strict mode
python -m run_mypy_checks --strict
```

Common mypy issues to watch for:
- Missing return type annotations (no-untyped-def)
- Untyped attribute access in class instances
- Improper use of `Optional` without checking for None
- Missing generic type parameters (e.g., `List` vs `List[str]`)
- Incompatible return types in functions

### Type-Related Improvements

Recent type safety improvements include:
- Full type annotation for async methods
- Proper error handling types
- Complete numpy array typing with appropriate dtypes
- Generic type parameters for exception handling
- Type safe logging and configuration utilities

## S3 Access and Network Resilience

The project includes robust patterns for accessing NOAA's S3 buckets. When working with S3 access code:

### Best Practices
1. **Error Handling**: Always use the custom `RemoteStoreError` hierarchy for S3 errors
2. **Retry Logic**: Include configurable retry strategies for transient network issues
3. **Timeouts**: Set appropriate timeouts for all S3 operations (connection and read)
4. **Diagnostics**: Include network diagnostics in error messages (DNS resolution, connectivity)
5. **Anonymous Access**: Use `boto3.UNSIGNED` for public bucket access
6. **Progress Reporting**: Implement progress callbacks for large downloads
7. **Statistics Collection**: Gather download statistics for monitoring
8. **Thread Safety**: Ensure S3 client instances are thread-safe with proper initialization
9. **Cancellation**: Support async cancellation in long-running operations

### S3 Store Implementation
The `S3Store` class in `goesvfi.integrity_check.remote.s3_store` provides a robust implementation with:
- Comprehensive error handling
- Connection diagnostics
- Download statistics
- Async context manager support
- Type-safe interfaces

### Testing S3 Code
When writing tests for S3 code:
- Use the mocking utilities in `tests/utils/mocks.py`
- Create realistic error scenarios
- Test both success and failure paths
- Verify proper handling of network timeouts
- Simulate different AWS error responses

## GOES Satellite Data Processing

The project includes components for handling GOES satellite data, particularly from the Advanced Baseline Imager (ABI) instrument. Understanding these patterns is essential when working with this code:

### GOES Data Access Patterns
- **ABI Bands**: Represented by the `ChannelType` class with band numbers, wavelengths, and descriptions
- **Products**: Various product types (RadF, RadC, RadM) for full disk, CONUS, and mesoscale regions
- **File Patterns**: Standard naming conventions in `time_index.py` for S3 objects
- **Timestamp Handling**: Date/time manipulation with year, day-of-year, and hour components
- **Scan Patterns**: Different scan schedules for full disk (15 min), CONUS (5 min), and mesoscale (1 min)

### NetCDF Processing
When working with NetCDF data files:
- Use the utilities in `goesvfi.integrity_check.render.netcdf` for extraction and processing
- Handle multi-band data appropriately
- Apply proper scaling, normalization, and calibration to raw satellite values
- Consider different visualization approaches for each band (false color, etc.)

### Satellite Imagery Visualization
For visualization components:
- Use the `VisualizationManager` for consistent rendering and comparisons
- Follow consistent colormap usage for specific bands
- Apply proper contrast enhancement and normalization
- Support multi-band composites for true color and false color

### Example Processing Workflows
The `examples/` directory includes several workflows demonstrating:
- Downloading satellite data for specific bands and products
- Processing NetCDF files to extract imagery
- Creating RGB composites from multiple bands
- Visualizing and comparing different products