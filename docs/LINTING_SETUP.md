# Linting Setup Guide

This guide explains how to set up and use the linting tools in the GOES-VFI project.

## Pre-commit Hooks

We use [pre-commit](https://pre-commit.com/) to run linting checks automatically before each commit.

### Installation

1. Install pre-commit:
   ```bash
   pip install pre-commit
   ```

2. Install the git hooks:
   ```bash
   pre-commit install
   ```

### Manual Execution

To run pre-commit manually on all files:
```bash
pre-commit run --all-files
```

To run a specific hook:
```bash
pre-commit run flake8 --all-files
```

## Linting Tools

The following linting tools are configured:

1. **flake8**: Checks for style issues, bugs, and complexity
2. **black**: Code formatter ensuring consistent style
3. **isort**: Sorts imports automatically
4. **mypy**: Type checking
5. **pre-commit-hooks**: Various small checks (trailing whitespace, YAML validation, etc.)

## Bulk Fixing

For bulk fixing of linting issues, we provide two tools:

1. **bulk_lint_fix.py**: Python script with options for fixing multiple files
   ```bash
   python bulk_lint_fix.py --directory goesvfi --backup
   ```

2. **fix_common_lints.sh**: Shell script for quick fixes
   ```bash
   ./fix_common_lints.sh
   ```

Both tools create backups before making changes.

## GitHub Actions

The repository includes GitHub Actions workflows that run linting checks automatically:

- **Linting**: Runs on every push and pull request to main branch
- Checks flake8, black, isort, and mypy

## Common Issues and Solutions

### Trailing Whitespace

```bash
# Fix with bulk_lint_fix.py
python bulk_lint_fix.py

# Or fix manually
find goesvfi -name "*.py" -type f -exec sed -i 's/[[:space:]]*$//' {} \;
```

### Import Sorting

```bash
# Fix with isort
isort --profile black goesvfi
```

### Formatting

```bash
# Fix with black
black --line-length=88 goesvfi
```

### Type Errors

Check type errors with:
```bash
python -m run_mypy_checks
```

## Ignoring Linting Issues

### In Flake8

Add a comment to the line:
```python
example = lambda: 'example'  # noqa: E731
```

### In Black

Add a comment:
```python
# fmt: off
example = lambda: 'example'
# fmt: on
```

### In Mypy

Add a comment:
```python
reveal_type(example)  # type: ignore
```
