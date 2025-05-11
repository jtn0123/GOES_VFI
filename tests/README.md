# GOES VFI Test Organization

This directory contains the organized test structure for the GOES VFI project. The test directory is organized as follows:

## Test Categories

- **[unit/](unit/)**: Unit tests for individual components
  - Tests for specific classes, methods, and functions in isolation
  - Typically mock external dependencies
  - Fast-running, reliable tests

- **[integration/](integration/)**: Integration tests for component interactions
  - Tests for how components work together
  - May include simple end-to-end test scenarios
  - More complex than unit tests but still controlled

- **[gui/](gui/)**: Tests for the PyQt6 user interface
  - **[imagery/](gui/imagery/)**: Tests for imagery-related GUI components
  - **[tabs/](gui/tabs/)**: Tests for tab components in the UI
  - These tests have specific patterns to avoid segmentation faults
  - See [CLAUDE.md](../CLAUDE.md) for GUI testing best practices

- **[utils/](utils/)**: Test utilities and helpers
  - Shared fixtures, mocks, and testing utilities

## Test Runners

The project includes multiple test runner scripts for different testing scenarios:

- **run_working_tests.py**: Only runs reliable, non-GUI tests
- **run_fixed_gui_tests.py**: Runs GUI tests with extra safeguards to prevent segfaults
- **run_all_tests.py**: Complete test suite (use with caution due to GUI test instability)

## Running Tests

### Running All Tests
```bash
# Run all tests (including potentially problematic ones)
./run_all_tests.py

# Run in parallel with 4 workers
./run_all_tests.py --parallel 4

# Run with debugging options
./run_all_tests.py --debug-mode

# Skip known problematic tests
./run_all_tests.py --skip-problematic
```

### Running Specific Tests
```bash
# Run a single test file
python -m pytest tests/unit/test_config.py

# Run a specific test function
python -m pytest tests/unit/test_main_tab.py::test_initial_state

# Run with verbose output
python -m pytest tests/unit/test_config.py -v
```

### Running Only Fixed GUI Tests
```bash
# Run only GUI tests that have been fixed and don't cause segmentation faults
./run_fixed_gui_tests.py
```

## GUI Testing Issues

Some GUI tests may cause segmentation faults, especially when interacting with FFmpeg controls. See [CLAUDE.md](../CLAUDE.md) for known issues and workarounds.

## Test Naming Convention

Tests follow the naming convention:
- Test files: `test_{component}_{functionality}.py`
- Test functions: `test_{what_is_being_tested}_{condition}`

## Test Independence

Each test is designed to run independently of others. Tests should not rely on state changes from previous tests.
