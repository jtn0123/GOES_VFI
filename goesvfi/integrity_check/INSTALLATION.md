# Installation Guide for GOES Integrity Check Module

This document provides step-by-step instructions for installing and setting up the GOES Integrity Check module.

## Prerequisites

The GOES Integrity Check module requires Python 3.13 or later, and several additional dependencies:

- **PyQt6**: For the GUI components
- **aiohttp**: For asynchronous HTTP requests to the CDN
- **aioboto3**: For asynchronous AWS S3 access
- **xarray** and **netCDF4**: For processing NetCDF files
- **matplotlib**: For rendering NetCDF files to PNG images
- **aiofiles**: For asynchronous file operations

## Installation

### Step 1: Create a Virtual Environment

```bash
# Create a Python 3.13 virtual environment
python3.13 -m venv venv-py313

# Activate the environment
# On Windows:
# venv-py313\Scripts\activate
# On macOS/Linux:
source venv-py313/bin/activate
```

### Step 2: Install Dependencies

```bash
# Install all dependencies from pyproject.toml
pip install -e .

# Install development and test dependencies (optional)
pip install -e .[test,dev,typing]
```

Alternatively, you can install the package with all dependencies:

```bash
# Install the package with all dependencies
pip install -e .

# Install test dependencies
pip install -e ".[test]"
```

### Step 3: AWS Configuration (Optional)

If you plan to use S3 access for historical data, you'll need to configure AWS credentials:

1. Create an AWS account if you don't have one
2. Create an IAM user with read access to the NOAA GOES bucket
3. Configure AWS credentials:

```bash
# Option 1: Use the AWS CLI
pip install awscli
aws configure

# Option 2: Create credentials file manually
mkdir -p ~/.aws
touch ~/.aws/credentials
```

Add your credentials to `~/.aws/credentials`:

```ini
[default]
aws_access_key_id = YOUR_ACCESS_KEY
aws_secret_access_key = YOUR_SECRET_KEY
```

## Running the Tests

After installation, you can run the tests to verify everything is working:

```bash
# Run a specific test file
python -m pytest tests/unit/test_basic_time_index.py -v

# Run all tests for the integrity check module
python -m pytest tests/unit/test_*_time_index.py tests/unit/test_remote_stores.py tests/unit/test_netcdf_renderer.py tests/unit/test_reconcile_manager.py tests/unit/test_enhanced_view_model.py -v
```

## Troubleshooting

### Missing Dependencies

If you encounter errors about missing dependencies, ensure you've installed all required packages:

```bash
pip install -e .
```

### AWS Access Issues

If you encounter AWS access issues:

1. Verify your credentials are correct in `~/.aws/credentials`
2. Make sure your IAM user has permission to access the NOAA GOES buckets
3. Check that you've configured the correct AWS region (us-east-1 for NOAA GOES buckets)

## Usage

After installation, you can use the Integrity Check tab in the main GOES-VFI application:

```bash
# Launch the application
python -m goesvfi.gui
```

For programmatic usage, see the examples in the README.md file.
