# AGENTS.md

This repository provides a PyQt6 application named **GOES-VFI** for interpolating satellite imagery.
The following guidance applies when using AI assistants (Claude, Codex, and other automated tools) with this repository.

## Quick Context
GOES-VFI processes GOES satellite imagery (Band 13, 10.3 μm infrared) to create smooth timelapse videos using:
- **RIFE v4.6**: AI-based video frame interpolation
- **Sanchez**: False color processing for grayscale satellite images
- **FFmpeg**: Video encoding and additional interpolation
- **PyQt6**: Cross-platform GUI interface

## Environment Setup
- Requires **Python 3.13**.
- Always create and activate a virtual environment before running commands:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  ```

## Running the Application
- Launch the GUI with:
  ```bash
  python -m goesvfi.gui [--debug]
  ```
- Ensure you have placed the `rife-cli` executable in `goesvfi/bin/` and the
  required model files in `goesvfi/models/` as described in the README.

## Linting and Code Quality

### Running Linters
- Run all linters via:
  ```bash
  python run_linters.py
  ```
- Individual linter options:
  - `python run_linters.py --flake8-only` - Style and static analysis
  - `python run_linters.py --black-only` - Code formatting check
  - `python run_linters.py --isort-only` - Import ordering check
  - `python run_linters.py --mypy-only` - Type checking
  - `python run_linters.py --pylint-only` - Advanced static analysis
- Apply formatting automatically:
  ```bash
  python run_linters.py --format  # Applies Black and isort formatting
  ```
- Formatting tools use **Black** (line length 88) and **isort**.

### Pre-commit Hooks
- **NEVER skip pre-commit hooks** with `--no-verify`
- If pre-commit hooks fail, fix the issues before committing
- Pre-commit hooks run the same linters automatically

## Testing

### Recommended Testing Approach
When verifying all tests pass, use this systematic approach:

1. **First, ensure virtual environment is activated:**
   ```bash
   source .venv/bin/activate
   ```

2. **Run tests in batches to identify issues:**
   ```bash
   # Run integration tests first (usually most stable)
   python -m pytest tests/integration/ -v

   # Run unit tests in smaller batches to isolate hanging tests
   python -m pytest tests/unit/test_*.py -v --tb=short

   # Run GUI tests separately (prone to segmentation faults)
   python -m pytest tests/gui/ -v
   ```

3. **If tests hang, use timeout and verbose output:**
   ```bash
   python -m pytest tests/unit/test_enhanced_integrity_check_tab.py -v -s --timeout=30
   ```

### Test Runner Scripts
- **All tests (recommended after fixes):** `./run_all_tests.py`
  - Runs complete test suite (827+ tests across 87+ files)
  - Use `--debug-mode` for verbose output
  - Use `--parallel 4` for faster execution
- **Reliable tests with mocks:** `./run_working_tests_with_mocks.py`
- **Non-GUI tests only:** `./run_non_gui_tests.py`

### Common Test Issues and Solutions
1. **Hanging tests:** Usually due to network initialization in S3Store/CDNStore
   - Solution: Mock these classes at module level before imports

2. **PyQt segmentation faults:** Common in GUI tests
   - Solution: Run GUI tests separately or use `run_non_gui_tests.py`

3. **Import errors:** Always activate virtual environment first
   - Solution: `source .venv/bin/activate && pip install -r requirements.txt`

## Repository Guidelines
- Follow the project structure described in `DIRECTORY_STRUCTURE.md` and the
  detailed usage instructions in `README.md`.
- Do **not** commit large data files (.nc files, large .png files):
  ```bash
  python cleanup.py --list-only    # List large files
  python cleanup.py --delete-data  # Remove them before committing
  ```
- Include type hints in new code and verify with:
  ```bash
  python -m run_mypy_checks         # Standard mode
  python -m run_mypy_checks --strict # Strict mode
  ```
- Use the MVVM architecture and existing logging/config utilities.
- Follow the guidelines in `CLAUDE.md` for AI-assisted development.

## AI Agent Behavioral Guidelines

### Response Style
1. **Be concise** - Provide direct answers without unnecessary preamble
2. **Show don't tell** - When asked to do something, do it rather than explaining how you would do it
3. **Respect user preferences** - If user says "don't use X" or gives specific instructions, follow them exactly
4. **One task at a time** - Focus on the immediate request before suggesting next steps

### Code Modification Best Practices
1. **Always read before editing** - Use the Read tool before Edit/Write tools
2. **Prefer Edit over Write** - Edit existing files rather than creating new ones
3. **Check for existing patterns** - Look at neighboring files for conventions
4. **Verify imports** - Never assume a library is available; check requirements.txt or imports
5. **Follow existing style** - Match the code style, naming conventions, and patterns
6. **Minimize file creation** - Don't create documentation files unless explicitly requested

### Working with the Codebase
1. **GOES Satellite Data:**
   - GOES-16 (East) and GOES-18 (West) satellites
   - Band 13 (10.3 μm) is the primary infrared channel used
   - Data is stored in NetCDF (.nc) format from AWS S3
   - Processed to PNG format for interpolation

2. **Key Components:**
   - **GUI**: PyQt6-based interface with tabs for different functions
   - **Pipeline**: Video frame interpolation using RIFE
   - **Integrity Check**: Verifies and downloads missing satellite imagery
   - **Sanchez**: Colors grayscale satellite images

3. **Common Tasks:**
   - When fixing tests: Run in batches, mock network dependencies
   - When adding features: Create example scripts first in `/examples`
   - When debugging: Use `--debug` flag and check logs
   - When committing: Let pre-commit hooks run and fix issues

### Error Handling Patterns
1. **Network Operations:**
   ```python
   from goesvfi.integrity_check.remote.base import RemoteStoreError
   # Always handle RemoteStoreError for S3/CDN operations
   ```

2. **GUI Operations:**
   ```python
   from PyQt6.QtCore import QCoreApplication
   # Use QCoreApplication.processEvents() to prevent UI freezing
   ```

3. **File Operations:**
   ```python
   from pathlib import Path
   # Always use Path objects, not string paths
   ```

### Testing Philosophy
- **Test everything** - No skipped tests, all must pass or fail
- **Mock external services** - S3, CDN, network calls
- **Test in isolation** - Each test should be independent
- **Use fixtures** - For common setup/teardown operations

## Important Notes
- **Never skip tests** - if a test is skipped, it provides no value
- **Never skip pre-commit hooks** - they maintain code quality
- **Test incrementally** - run tests in batches when debugging issues
- **Mock external dependencies** - especially network services like S3/CDN
- **Respect user feedback** - If user says "don't use X", follow their guidance
- **Be concise** - Keep responses focused on the task at hand
