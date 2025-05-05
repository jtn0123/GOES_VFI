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