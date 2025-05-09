# GOES-VFI Test Structure

## Overview

The GOES-VFI test suite has been reorganized to provide better structure, remove redundancies, and separate example code from actual test code. This document explains the new structure and how to run tests effectively.

## Test Directory Structure

```
tests/
├── unit/                 # Unit tests for individual components
│   ├── test_config.py    # Configuration tests
│   ├── test_log.py       # Logging functionality tests
│   ├── test_cache.py     # Cache functionality tests
│   └── ... (other unit tests)
├── integration/          # Tests that verify component integration
│   ├── test_pipeline.py             # End-to-end pipeline tests
│   ├── test_integrity_check_tab.py  # Integrity check tab integration
│   ├── test_goes_imagery_tab.py     # GOES imagery tab integration
│   └── ... (other integration tests)
├── gui/                  # GUI component tests
│   ├── test_main_window.py          # Main window tests
│   ├── imagery/                     # Imagery-specific GUI tests
│   │   ├── test_imagery_enhancement.py
│   │   ├── test_imagery_gui.py
│   │   └── ... (other imagery UI tests)
│   ├── tabs/                        # Tab-specific GUI tests
│   │   ├── test_enhanced_imagery_tab.py
│   │   ├── test_combined_tab.py
│   │   └── ... (other tab tests)
│   └── ... (other GUI tests)
└── conftest.py           # Shared pytest fixtures

examples/                 # Example scripts (not tests)
├── download/             # Data download examples
│   └── ... (download example scripts)
├── s3_access/            # S3 access examples
│   └── ... (S3 access example scripts)
├── imagery/              # Imagery processing examples
│   └── ... (imagery example scripts)
└── processing/           # Data processing examples
    └── ... (processing example scripts)
```

## Test Categories

### Unit Tests (`tests/unit/`)

Unit tests focus on testing individual components in isolation. These tests should:
- Be fast and reliable
- Not depend on external services
- Mock external dependencies
- Test a single piece of functionality

### Integration Tests (`tests/integration/`)

Integration tests verify that components work together correctly. These tests:
- May test multiple components together
- May access external services (with appropriate safeguards)
- Verify end-to-end functionality

### GUI Tests (`tests/gui/`)

GUI tests verify the user interface components work correctly. These tests:
- Test UI component behavior
- Verify signals and slots function correctly
- Ensure visual elements appear and behave as expected

## Running Tests

### Running All Tests

To run all tests that are known to pass:

```bash
./run_all_tests.py
```

### Running Specific Test Categories

To run only non-GUI tests (useful to avoid segfaults):

```bash
./run_non_gui_tests.py
```

To run only GUI tests that are known to work:

```bash
./run_fixed_gui_tests.py
```

To run only integration tests that are known to work:

```bash
./run_fixed_integration_tests.py
```

### Running Individual Tests

To run a specific test file:

```bash
python -m pytest tests/path/to/test_file.py
```

To run a specific test function:

```bash
python -m pytest tests/path/to/test_file.py::test_function_name
```

## Test Runner Options

The main test runner (`run_all_tests.py`) supports several options:

- `--verbose` or `-v`: Print verbose output
- `--parallel` or `-p`: Number of parallel workers (default: 4)
- `--file`: Run specific test file(s)
- `--directory`: Directory containing tests (default: tests)
- `--tolerant`: Always return success (0) even if tests fail or crash
- `--dump-logs`: Dump output logs for crashed and failed tests to files
- `--skip-problematic`: Skip known problematic tests
- `--debug-mode`: Run tests with extra debug options

## Examples vs. Tests

In the reorganization, we've separated example code from test code:

- **Tests** (in `tests/`): Formal test code that validates functionality through assertions
- **Examples** (in `examples/`): Demonstration scripts showing how to use features

Examples don't necessarily include assertions and are meant to demonstrate usage patterns rather than verify correctness.

## Known Issues

Some GUI tests are still known to cause segmentation faults, particularly when testing FFmpeg controls directly. When running GUI tests:

- Use `run_fixed_gui_tests.py` to avoid segmentation faults
- Be cautious when running all GUI tests at once

## Best Practices for Adding New Tests

When adding new tests to the repository:

1. **Place tests in the appropriate directory**:
   - Unit tests go in `tests/unit/`
   - Integration tests go in `tests/integration/`
   - GUI tests go in `tests/gui/` (with appropriate subdirectory)

2. **Use fixtures from conftest.py** where appropriate

3. **Follow the naming convention**:
   - Test files should be named `test_<what's being tested>.py`
   - Test functions should be named `test_<specific functionality>()`

4. **Document test purpose** with docstrings

5. **Example code** should go in the `examples/` directory, not with tests

6. **Update the test runners** if needed for new test categories