# AGENTS.md

This repository provides a PyQt6 application named **GOES-VFI** for interpolating satellite imagery.
The following guidance applies when using Codex (and other automated tools) with this repository.

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

## Linting
- Run all linters via:
  ```bash
  python run_linters.py
  ```
- Individual linter options are available (e.g. `--flake8-only`, `--black-only`).
- Formatting tools use **Black** (line length 88) and **isort**.

## Testing
- Reliable tests with mocks: `./run_working_tests_with_mocks.py`
- Non‑GUI tests (avoid PyQt segmentation faults): `./run_non_gui_tests.py`
- Full test suite (may be unstable due to GUI tests): `./run_all_tests.py`
- Always activate your virtual environment and run `pip install -r requirements.txt`
  before executing these scripts to avoid ImportError issues (e.g. missing PyQt6).

## Repository Guidelines
- Follow the project structure described in `DIRECTORY_STRUCTURE.md` and the
  detailed usage instructions in `README.md`.
- Do **not** commit large data files. Use `cleanup.py --list-only` to see them
  or `cleanup.py --delete-data` to remove them before committing.
- Include type hints in new code and run `python -m run_mypy_checks`.
- Use the MVVM architecture and existing logging/config utilities.

