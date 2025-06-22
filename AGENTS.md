# AGENTS.md

This repository provides a PyQt6 application named **GOES-VFI** for interpolating satellite imagery.
The following guidance applies when using AI assistants (Claude, Codex, and other automated tools) with this repository.

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

## Important Notes
- **Never skip tests** - if a test is skipped, it provides no value
- **Never skip pre-commit hooks** - they maintain code quality
- **Test incrementally** - run tests in batches when debugging issues
- **Mock external dependencies** - especially network services like S3/CDN
