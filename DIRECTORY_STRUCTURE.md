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

## Important Files

- **[pyproject.toml](pyproject.toml)**: Project configuration and dependencies
- **[README.md](README.md)**: Main project documentation
- **[CLAUDE.md](CLAUDE.md)**: Instructions for Claude Code AI
- **[run_all_tests.py](run_all_tests.py)**: Script to run all tests
- **[run_fixed_gui_tests.py](run_fixed_gui_tests.py)**: Script to run only fixed GUI tests
- **[run_working_tests.py](run_working_tests.py)**: Script to run only working tests

## Data Directories

- **[satpy_images/](satpy_images/)**: Images processed with satpy
- **[temp_netcdf_downloads/](temp_netcdf_downloads/)**: Temporary NetCDF files downloaded for processing

## Test Data

- **[test_input/](test_input/)**: Input files for tests
- **[test_output/](test_output/)**: Output files from tests