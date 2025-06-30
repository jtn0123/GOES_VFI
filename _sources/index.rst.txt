GOES_VFI Documentation
======================

Welcome to the GOES_VFI (GOES Video Frame Interpolation) documentation. This project provides tools for processing GOES satellite data and creating smooth video interpolations using advanced frame interpolation techniques.

.. image:: https://img.shields.io/badge/python-3.13+-blue.svg
   :target: https://www.python.org/downloads/
   :alt: Python Version

.. image:: https://img.shields.io/badge/license-MIT-green.svg
   :target: https://opensource.org/licenses/MIT
   :alt: License

Overview
--------

GOES_VFI is a comprehensive tool suite for:

- **GOES Satellite Data Processing**: Download and process GOES-16/17/18 satellite imagery
- **Video Frame Interpolation**: Create smooth animations using RIFE, FFmpeg, and Sanchez processors
- **Data Integrity Checking**: Validate satellite data completeness and quality
- **Resource Management**: Monitor and control system resource usage
- **Security**: Input validation and secure processing pipelines

Key Features
------------

🛰️ **Satellite Data Processing**
   - Download GOES ABI (Advanced Baseline Imager) data from AWS S3
   - Support for all 16 ABI bands and multiple scanning modes
   - NetCDF file processing and visualization
   - False color and natural color composites

🎬 **Video Frame Interpolation**
   - RIFE (Real-Time Intermediate Flow Estimation) integration
   - FFmpeg-based interpolation with advanced motion estimation
   - Sanchez false-color processing for enhanced imagery
   - Customizable output formats and quality settings

🔍 **Data Integrity & Quality**
   - Comprehensive data validation and integrity checking
   - Missing data detection and reporting
   - Timeline visualization for data availability
   - Automated quality assessment tools

🛡️ **Security & Resource Management**
   - Input validation and sanitization
   - Resource usage monitoring and limits
   - Secure subprocess execution
   - Memory and CPU usage controls

🖥️ **User Interface**
   - Modern PyQt6-based GUI
   - Real-time preview and monitoring
   - Intuitive workflow management
   - Comprehensive settings and configuration

Getting Started
---------------

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   installation
   quickstart

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/index

.. toctree::
   :maxdepth: 1
   :caption: Additional Information

   changelog
   license
   support

Quick Example
-------------

Here's a simple example of processing GOES satellite data:

.. code-block:: python

   from goesvfi.pipeline import VfiWorker
   from goesvfi.utils.resource_manager import ResourceLimits
   from pathlib import Path

   # Set up resource limits
   limits = ResourceLimits(
       max_memory_mb=2048,
       max_processing_time_sec=1800
   )

   # Create a processing worker
   worker = VfiWorker(
       in_dir=Path("satellite_images/"),
       out_file_path=Path("output/animation.mp4"),
       fps=30,
       encoder="RIFE",
       resource_limits=limits
   )

   # Start processing
   worker.start()

Installation
------------

Install GOES_VFI using pip:

.. code-block:: bash

   pip install -e .

Or for development:

.. code-block:: bash

   git clone https://github.com/username/GOES_VFI.git
   cd GOES_VFI
   pip install -e .[test,dev,typing,docs]

System Requirements
-------------------

- **Python**: 3.13 or higher
- **Operating System**: Windows, macOS, or Linux
- **Memory**: Minimum 4GB RAM (8GB+ recommended)
- **Storage**: 1GB+ free space for temporary files
- **Network**: Internet connection for downloading satellite data

Dependencies
~~~~~~~~~~~~

Core dependencies:

- PyQt6 (GUI framework)
- NumPy (numerical computing)
- Pillow (image processing)
- OpenCV (computer vision)
- FFmpeg (video processing)
- psutil (system monitoring)

Satellite data dependencies:

- aiohttp (async HTTP requests)
- aioboto3 (AWS S3 access)
- xarray (NetCDF processing)
- matplotlib (visualization)

See :doc:`installation` for detailed setup instructions.

Architecture Overview
---------------------

GOES_VFI follows a modular architecture:

.. code-block:: text

   GOES_VFI/
   ├── goesvfi/
   │   ├── pipeline/          # Core processing pipeline
   │   ├── integrity_check/   # Data validation and quality
   │   ├── gui/              # User interface components
   │   ├── utils/            # Utilities and helpers
   │   └── sanchez/          # Sanchez processor integration
   ├── examples/             # Example scripts and demos
   ├── tests/               # Test suite
   └── docs/                # Documentation

Key components:

- **Pipeline**: Core processing engine for video frame interpolation
- **Integrity Check**: Data validation and quality assessment tools
- **GUI**: Modern PyQt6 user interface
- **Utils**: Shared utilities for logging, configuration, and resource management
- **Sanchez**: Integration with the Sanchez false-color processor

License
-------

This project is licensed under the MIT License. See the :doc:`license` file for details.

Support
-------

- **Documentation**: https://goes-vfi.readthedocs.io/
- **Issues**: https://github.com/username/GOES_VFI/issues
- **Discussions**: https://github.com/username/GOES_VFI/discussions

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
