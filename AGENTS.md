# AGENTS.md - AI Assistant Guidelines for GOES-VFI

This document provides comprehensive guidance for AI assistants (Claude, Codex, GitHub Copilot, and other automated tools) working with the GOES-VFI repository.

## Understanding GOES-VFI

### What is GOES-VFI?
GOES-VFI is a desktop application that creates smooth timelapse videos from satellite imagery. Think of it as turning a flipbook of satellite photos into a smooth movie.

### Core Components Explained

1. **GOES Satellite Data**
   - GOES = Geostationary Operational Environmental Satellites
   - These satellites take pictures of Earth every 10-15 minutes
   - Band 13 = Infrared channel (10.3 μm) that shows cloud temperatures
   - Data comes as NetCDF files (.nc) from NOAA's AWS S3 buckets
   - We convert these to PNG images for processing

2. **RIFE v4.6 (AI Frame Interpolation)**
   - RIFE = Real-Time Intermediate Flow Estimation
   - It's an AI model that creates smooth frames between existing images
   - Like creating in-between frames in animation
   - Uses neural networks to understand motion and generate new frames

3. **Sanchez (False Color Processing)**
   - Converts grayscale infrared data to colorful images
   - Makes cloud temperatures visible as different colors
   - Blue = cold (high clouds), Red = warm (low clouds/ground)

4. **FFmpeg (Video Encoding)**
   - Professional video processing tool
   - Combines frames into MP4 videos
   - Handles compression, quality settings, and additional smoothing

5. **PyQt6 (User Interface)**
   - Python framework for creating desktop applications
   - Provides buttons, menus, and visual elements users interact with

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

Each test runner serves a specific purpose:

- **`./run_all_tests.py`** - Complete test suite
  - Runs all 827+ tests across 87+ files
  - Options: `--debug-mode` (verbose), `--parallel 4` (faster)
  - Use after fixing all issues to verify everything works

- **`./run_working_tests_with_mocks.py`** - Stable subset
  - Runs tests that reliably pass with mocked dependencies
  - Good for quick verification during development

- **`./run_non_gui_tests.py`** - Non-GUI tests only
  - Dynamically discovers and runs all non-GUI tests
  - Avoids Qt-related segmentation faults
  - Options: `--quiet`, `--verbose`, `--parallel N`
  - Safe to run in CI/CD environments

- **`./run_coverage.py`** - Code coverage analysis
  - Measures test coverage and generates reports
  - Note: May have issues with Python 3.13 due to coverage library
  - Outputs: HTML report (htmlcov/), XML, JSON formats

### Utility Scripts

- **`fix_pylint_docstrings.py`** - Auto-add docstrings
  - Usage: `python fix_pylint_docstrings.py <file_or_directory>`
  - Adds placeholder "TODO" docstrings to satisfy pylint
  - Skips private methods and test functions
  - Generated docstrings need manual editing to be meaningful

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

#### Project Structure Understanding
```
goesvfi/                    # Main application package
├── gui.py                  # Main window and application entry point
├── gui_tabs/               # Different tabs in the interface
│   ├── main_tab.py        # Primary processing controls
│   ├── ffmpeg_settings_tab.py  # Video encoding settings
│   └── ...
├── integrity_check/        # Satellite data management
│   ├── remote/            # S3 and CDN data fetching
│   ├── time_index.py      # Timestamp handling for satellite data
│   └── view_model.py      # Business logic for data checking
├── pipeline/              # Core processing pipeline
│   ├── run_vfi.py        # Main processing orchestrator
│   ├── interpolate.py    # RIFE integration
│   ├── encode.py         # FFmpeg video creation
│   └── sanchez_processor.py  # False color processing
├── utils/                 # Shared utilities
│   ├── log.py            # Centralized logging
│   ├── config.py         # Configuration management
│   └── memory_manager.py # Memory usage monitoring
└── view_models/          # MVVM pattern implementations
```

#### Key File Locations
- **Entry point**: `goesvfi/gui.py` - Start here to understand the application
- **Main processing**: `goesvfi/pipeline/run_vfi.py` - Core video creation logic
- **Satellite data**: `goesvfi/integrity_check/` - All GOES data handling
- **Tests**: `tests/unit/`, `tests/integration/`, `tests/gui/`
- **Examples**: `examples/` - Self-contained demonstration scripts

#### Common Code Patterns

1. **Logging Pattern**:
   ```python
   from goesvfi.utils import log
   LOGGER = log.get_logger(__name__)

   LOGGER.info("Processing started")
   LOGGER.error("Failed to process: %s", error_msg)
   ```

2. **Path Handling**:
   ```python
   from pathlib import Path

   # Always use Path objects, not strings
   input_dir = Path("/path/to/images")
   output_file = input_dir / "output.mp4"
   ```

3. **Error Handling for Network Operations**:
   ```python
   from goesvfi.integrity_check.remote.base import RemoteStoreError

   try:
       result = await s3_store.download(...)
   except RemoteStoreError as e:
       LOGGER.error("Download failed: %s", e)
   ```

4. **GUI Update Pattern**:
   ```python
   from PyQt6.QtCore import QCoreApplication

   # Update UI and prevent freezing
   self.progress_bar.setValue(50)
   QCoreApplication.processEvents()
   ```

#### Common Tasks and How to Approach Them

1. **Adding a New Feature**:
   - First create an example in `examples/` to prototype
   - Add unit tests in `tests/unit/`
   - Integrate into main codebase
   - Update GUI if needed
   - Add integration tests

2. **Fixing a Bug**:
   - Reproduce with a minimal test case
   - Check logs for error details
   - Fix the issue
   - Add regression test
   - Verify all tests still pass

3. **Working with Satellite Data**:
   - Use `TimeIndex` class for timestamp handling
   - Mock S3/CDN stores in tests to avoid network calls
   - Handle missing data gracefully
   - Consider both GOES-16 and GOES-18 satellites

4. **Modifying the GUI**:
   - Follow MVVM pattern (View → ViewModel → Model)
   - Keep business logic in ViewModels
   - Use signals/slots for communication
   - Test with mock ViewModels

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

## Important Behavioral Notes

### Do's and Don'ts for AI Agents

**DO:**
- ✅ Read files before editing them
- ✅ Use existing patterns and conventions
- ✅ Run tests after making changes
- ✅ Mock external services in tests
- ✅ Use Path objects for file paths
- ✅ Handle errors gracefully
- ✅ Follow MVVM pattern for GUI code
- ✅ Create examples before implementing features
- ✅ Be concise and direct in responses

**DON'T:**
- ❌ Skip tests or mark them as skipped
- ❌ Use `--no-verify` to bypass pre-commit hooks
- ❌ Create new files when you can edit existing ones
- ❌ Assume libraries are available without checking
- ❌ Make network calls in tests without mocking
- ❌ Use string paths instead of Path objects
- ❌ Put business logic in GUI view code
- ❌ Create documentation unless explicitly asked
- ❌ Give long explanations when action is requested

### Common Pitfalls to Avoid

1. **Test Hanging Issues**
   - Problem: Tests hang due to S3Store/CDNStore initialization
   - Solution: Mock at module level before imports
   ```python
   # At the top of test file, before imports
   import unittest.mock
   unittest.mock.patch('goesvfi.integrity_check.remote.s3_store.S3Store', MockS3Store).start()
   ```

2. **GUI Test Segfaults**
   - Problem: PyQt tests crash with segmentation fault
   - Solution: Run GUI tests separately, use proper cleanup
   ```python
   def tearDown(self):
       QApplication.processEvents()  # Process pending events
       self.widget.close()
       self.widget.deleteLater()
   ```

3. **Import Errors**
   - Problem: Module not found errors
   - Solution: Always activate virtual environment first
   ```bash
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Large File Commits**
   - Problem: Accidentally committing .nc or large .png files
   - Solution: Check before committing
   ```bash
   python cleanup.py --list-only
   git status --porcelain | grep -E '\.(nc|png)$'
   ```

### Understanding User Intent

When a user asks you to:
- **"Fix the tests"** → Run tests, identify failures, fix them, verify all pass
- **"Add a feature"** → Create example first, add tests, then implement
- **"Debug this"** → Check logs, add debug prints, identify root cause
- **"Make it work"** → Focus on functionality first, optimize later
- **"Clean this up"** → Run linters, fix issues, improve readability

### Performance Considerations

1. **Memory Usage**
   - Large satellite images can use significant memory
   - Use tiling for images over 4K resolution
   - Monitor with `MemoryManager` class

2. **Processing Speed**
   - RIFE interpolation is GPU-intensive
   - FFmpeg encoding can be CPU-intensive
   - Use hardware encoding when available

3. **Network Operations**
   - S3 downloads can be slow
   - Use CDN for recent data (faster)
   - Implement retry logic for failures

### Security Best Practices

1. **Never commit secrets**
   - AWS credentials
   - API keys
   - Personal information

2. **Validate user input**
   - File paths
   - Numeric parameters
   - Command-line arguments

3. **Use safe file operations**
   - Check paths are within expected directories
   - Don't overwrite without confirmation
   - Handle permissions errors gracefully
