# GOES_VFI Linting Guide

This document describes how to use the linting tools set up for the GOES_VFI project to maintain code quality and consistency.

## Available Linters

The project uses the following linters:

1. **Flake8**: For general Python code style and quality checks
2. **Flake8-Qt-TR**: For PyQt translation string checks
3. **Flake8-Bugbear**: For additional bug finding
4. **Flake8-Comprehensions**: For optimizing comprehensions
5. **Pylint**: For more comprehensive code analysis

## Installing Linting Tools

All the linting tools are included in the `requirements.txt` file and can be installed with:

```bash
pip install -r requirements.txt
```

### Flake8-Qt-TR

The `flake8-qt-tr` package provides checks specifically for PyQt translation strings. It helps ensure that all user-facing strings are properly marked for translation with `tr()` calls.

This linter is particularly important for internationalization (i18n) of the application. It flags instances where string literals are used directly in UI components without translation markers.

## Running the Linters

The project includes a `run_linters.py` script that can run all the linters with appropriate settings. Here's how to use it:

```bash
# Run all linters on the entire codebase
python run_linters.py

# Run only Flake8
python run_linters.py --flake8-only

# Run only Pylint
python run_linters.py --pylint-only

# Run Flake8-Qt for PyQt files
python run_linters.py --flake8-qt-only

# Run linters on specific paths
python run_linters.py goesvfi/integrity_check

# Run in parallel with multiple jobs
python run_linters.py -j 4
```

## Configuration Files

The linting tools are configured with the following files:

- `.flake8`: Configuration for Flake8
- `.pylintrc`: Configuration for Pylint

These configuration files are tailored for PyQt development and include settings to:

1. Ignore common PyQt-specific naming conventions
2. Allow longer lines in UI code
3. Handle Qt-specific imports
4. Customize error checking for desktop applications

## Lint Error Fixing

To automatically fix some issues:

1. **Flake8 issues**: Install the `autopep8` tool:
   ```bash
   pip install autopep8
   autopep8 --in-place --aggressive --aggressive file.py
   ```

2. **Formatting issues**: Install the `black` formatter:
   ```bash
   pip install black
   black file.py
   ```

3. **Import sorting**: Install `isort`:
   ```bash
   pip install isort
   isort file.py
   ```

## Best Practices for PyQt Code

When writing PyQt code, follow these best practices to avoid common linting issues:

1. Use descriptive variable names for widgets, even if they're longer than normal Python conventions
2. Put UI setup code in separate methods like `_setup_ui()` or `initUI()`
3. Connect signals in a dedicated method like `_connect_signals()`
4. Use type annotations for all parameters and return values
5. Document signal parameters carefully
6. Avoid inline lambdas in signal connections when possible
7. Use constants for magic values like sizes, colors, and margins

## CI/CD Integration

The linting scripts can be integrated into continuous integration systems. For example, add this to your CI configuration:

```bash
python run_linters.py
```

The script will exit with a non-zero code if any linter finds issues, causing the CI build to fail.

## Ignoring Specific Errors

Sometimes you need to ignore specific errors. Here's how:

### Flake8

```python
# flake8: noqa
# or for specific codes:
# flake8: noqa: E501,F403
```

### Pylint

```python
# pylint: disable=invalid-name,unused-argument
```

Use these sparingly and with good reason!