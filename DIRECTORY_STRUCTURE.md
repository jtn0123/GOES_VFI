# GOES VFI Directory Structure

This document provides an overview of the directory structure for the GOES VFI project.

## Main Directories

### Core Package

- **[goesvfi/](goesvfi/)**: Main package code
  - **[bin/](goesvfi/bin/)**: Binary and executable files
  - **[date_sorter/](goesvfi/date_sorter/)**: Date sorting functionality
  - **[file_sorter/](goesvfi/file_sorter/)**: File sorting functionality
  - **[gui_tabs/](goesvfi/gui_tabs/)**: GUI tab implementations
  - **[integrity_check/](goesvfi/integrity_check/)**: Integrity checking for satellite data
    - **[remote/](goesvfi/integrity_check/remote/)**: Remote data stores (S3, CDN)
    - **[render/](goesvfi/integrity_check/render/)**: Rendering tools for data visualization
  - **[models/](goesvfi/models/)**: Machine learning models
  - **[pipeline/](goesvfi/pipeline/)**: Data processing pipeline
  - **[sanchez/](goesvfi/sanchez/)**: Sanchez algorithm implementation
  - **[utils/](goesvfi/utils/)**: Utility functions
  - **[view_models/](goesvfi/view_models/)**: MVVM view models

### Testing

- **[tests/](tests/)**: All tests for the project
  - **[unit/](tests/unit/)**: Unit tests for individual components
  - **[integration/](tests/integration/)**: Integration tests for component interactions
  - **[gui/](tests/gui/)**: Tests for the PyQt6 user interface
    - **[imagery/](tests/gui/imagery/)**: Tests for imagery-related GUI components
    - **[tabs/](tests/gui/tabs/)**: Tests for tab components in the UI
  - **[utils/](tests/utils/)**: Test utilities and helpers
  - **[data/](tests/data/)**: Test data files
    - **[test_input/](tests/data/test_input/)**: Input files for tests
    - **[test_output/](tests/data/test_output/)**: Output files from tests

### Examples

- **[examples/](examples/)**: Example scripts demonstrating functionality
  - **[download/](examples/download/)**: Examples for downloading GOES satellite data
  - **[imagery/](examples/imagery/)**: Examples for image processing and rendering
  - **[processing/](examples/processing/)**: Examples for data processing
  - **[s3_access/](examples/s3_access/)**: Examples for AWS S3 access
  - **[visualization/](examples/visualization/)**: Examples for data visualization
  - **[debugging/](examples/debugging/)**: Examples for debugging the application
  - **[utilities/](examples/utilities/)**: Utility scripts

### Documentation

- **[docs/](docs/)**: Documentation files
  - **[assets/](docs/assets/)**: Images and other assets for documentation
  - **[testing/](docs/testing/)**: Testing documentation
  - **[reports/](docs/reports/)**: Project reports and documentation
    - Performance reports
    - Improvement plans
    - Status reports
    - Feature guides

### Data & Logs

- **[data/](data/)**: Data files and cached downloads
  - **[satpy_images/](data/satpy_images/)**: Images processed with satpy
  - **[temp_netcdf_downloads/](data/temp_netcdf_downloads/)**: Temporary NetCDF files

- **[logs/](logs/)**: Log files from application runs
  - Application logs
  - Debug logs
  - Error logs
  - AWS and S3 logs

### Scripts

- **[scripts/](scripts/)**: Utility and helper scripts
  - Tools for analysis
  - Date conversion examples
  - Repository management

## Important Files

- **[pyproject.toml](pyproject.toml)**: Project configuration and dependencies
- **[README.md](README.md)**: Main project documentation
- **[CLAUDE.md](CLAUDE.md)**: Instructions for Claude Code AI
- **[DIRECTORY_STRUCTURE.md](DIRECTORY_STRUCTURE.md)**: This directory structure guide
- **[CHANGELOG.md](CHANGELOG.md)**: Project changelog and version history
- **[pyproject.toml](pyproject.toml)**: Project configuration and dependencies
- **[mypy.ini](mypy.ini)**: Type checking configuration

## Test Runner Scripts

- **[run_all_tests.py](run_all_tests.py)**: Script to run all tests (for local development with display)
- **[run_non_gui_tests_ci.py](run_non_gui_tests_ci.py)**: Script to run non-GUI tests (for CI/headless environments)
- **[run_mypy_checks.py](run_mypy_checks.py)**: Script to run mypy type checking
