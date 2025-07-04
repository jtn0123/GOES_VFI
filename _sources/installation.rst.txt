Installation Guide
==================

This guide covers the installation of GOES_VFI on different operating systems.

System Requirements
-------------------

Before installing GOES_VFI, ensure your system meets the following requirements:

**Minimum Requirements:**

- Python 3.13 or higher
- 4GB RAM (8GB+ recommended for large datasets)
- 1GB free disk space
- Internet connection for downloading satellite data

**Recommended System:**

- Python 3.13+
- 16GB RAM or more
- SSD storage with 10GB+ free space
- Multi-core CPU (4+ cores recommended)
- Dedicated GPU (optional, for accelerated processing)

Supported Operating Systems
---------------------------

GOES_VFI is tested and supported on:

- **Windows**: Windows 10/11 (64-bit)
- **macOS**: macOS 10.15+ (Catalina and later)
- **Linux**: Ubuntu 20.04+, CentOS 8+, and other modern distributions

Installation Methods
--------------------

Method 1: Standard Installation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The recommended way to install GOES_VFI:

.. code-block:: bash

   # Clone the repository
   git clone https://github.com/username/GOES_VFI.git
   cd GOES_VFI

   # Create a virtual environment (recommended)
   python -m venv .venv

   # Activate the virtual environment
   # On Windows:
   .venv\Scripts\activate
   # On macOS/Linux:
   source .venv/bin/activate

   # Install dependencies
   pip install -e .

Method 2: Development Installation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For contributors and developers:

.. code-block:: bash

   # Clone the repository
   git clone https://github.com/username/GOES_VFI.git
   cd GOES_VFI

   # Create and activate virtual environment
   python -m venv .venv
   source .venv/bin/activate  # or .venv\Scripts\activate on Windows

   # Install the package in editable mode with development tools
   pip install -e .[test,dev,typing,docs]

Dependency Installation
-----------------------

Core Dependencies
~~~~~~~~~~~~~~~~~

GOES_VFI requires several Python packages:

.. code-block:: bash

   # GUI and system
   pip install PyQt6 psutil

   # Image and video processing
   pip install numpy Pillow opencv-python-headless ffmpeg-python

   # Satellite data processing
   pip install aiohttp aioboto3 xarray netCDF4 matplotlib aiofiles

   # Utilities
   pip install colorlog requests tqdm imageio python-dateutil

System Dependencies
~~~~~~~~~~~~~~~~~~~

Some dependencies require system-level packages:

**Ubuntu/Debian:**

.. code-block:: bash

   sudo apt update
   sudo apt install -y \
       python3-dev \
       libgl1-mesa-glx \
       libglib2.0-0 \
       libsm6 \
       libxext6 \
       libxrender-dev \
       libfontconfig1 \
       ffmpeg

**CentOS/RHEL:**

.. code-block:: bash

   sudo yum install -y \
       python3-devel \
       mesa-libGL \
       glib2 \
       libSM \
       libXext \
       libXrender \
       fontconfig \
       ffmpeg

**macOS:**

.. code-block:: bash

   # Install Homebrew if not already installed
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

   # Install FFmpeg
   brew install ffmpeg

**Windows:**

1. Download and install FFmpeg from https://ffmpeg.org/download.html
2. Add FFmpeg to your system PATH
3. Install Microsoft Visual C++ Redistributable if needed

External Tools
--------------

GOES_VFI can use several external tools for enhanced functionality:

RIFE (Real-Time Intermediate Flow Estimation)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For AI-powered frame interpolation:

1. Download RIFE from: https://github.com/megvii-research/ECCV2022-RIFE
2. Place the executable in ``goesvfi/bin/`` or add to system PATH
3. Download model files to ``goesvfi/models/``

Sanchez
~~~~~~~

For false-color satellite image processing:

1. Download Sanchez from: https://github.com/nullpainter/sanchez
2. Place the executable in ``goesvfi/sanchez/bin/`` or add to system PATH

Verification
------------

Test Installation
~~~~~~~~~~~~~~~~~

Verify your installation by running the test suite:

.. code-block:: bash

   # Basic functionality test
   python -c "import goesvfi; print('GOES_VFI imported successfully')"

   # Run unit tests
   python -m pytest tests/unit/ -v

   # Test resource management
   python examples/utilities/test_resource_management.py

   # Launch GUI (if display is available)
   python -m goesvfi.gui --debug

Quick Test Script
~~~~~~~~~~~~~~~~~

Create a simple test script to verify core functionality:

.. code-block:: python

   #!/usr/bin/env python3
   """Quick installation test for GOES_VFI."""

   def test_imports():
       """Test that all core modules can be imported."""
       try:
           import goesvfi.utils.log
           import goesvfi.utils.config
           import goesvfi.utils.resource_manager
           import goesvfi.pipeline.image_loader
           print("✅ Core modules imported successfully")
       except ImportError as e:
           print(f"❌ Import error: {e}")
           return False
       return True

   def test_dependencies():
       """Test that key dependencies are available."""
       deps = ['PyQt6', 'numpy', 'PIL', 'cv2', 'psutil']
       for dep in deps:
           try:
               __import__(dep)
               print(f"✅ {dep} available")
           except ImportError:
               print(f"❌ {dep} not found")
               return False
       return True

   if __name__ == "__main__":
       print("Testing GOES_VFI installation...")
       if test_imports() and test_dependencies():
           print("🎉 Installation test passed!")
       else:
           print("💥 Installation test failed!")

Save this as ``test_installation.py`` and run it:

.. code-block:: bash

   python test_installation.py

Troubleshooting
---------------

Common Issues
~~~~~~~~~~~~~

**ImportError: No module named 'PyQt6'**

.. code-block:: bash

   pip install PyQt6

**FFmpeg not found**

Ensure FFmpeg is installed and in your system PATH:

.. code-block:: bash

   # Test FFmpeg installation
   ffmpeg -version

**Permission errors on Linux/macOS**

Ensure proper permissions for the installation directory:

.. code-block:: bash

   chmod +x goesvfi/bin/*
   chmod +x examples/utilities/*.py

**Memory errors during processing**

Reduce resource limits in the GUI or use command-line options:

.. code-block:: python

   from goesvfi.utils.resource_manager import ResourceLimits

   limits = ResourceLimits(max_memory_mb=1024)  # Limit to 1GB

Performance Optimization
~~~~~~~~~~~~~~~~~~~~~~~~

For optimal performance:

1. **Use SSD storage** for temporary files
2. **Increase memory limits** based on available RAM
3. **Use multiple CPU cores** for parallel processing
4. **Close other applications** during intensive processing

Development Setup
-----------------

Additional setup for development:

.. code-block:: bash

   # Install pre-commit hooks
   pip install pre-commit
   pre-commit install

   # Install linting tools
   pip install flake8 pylint mypy black isort

   # Run linters
   python run_linters.py

   # Generate documentation
   cd docs
   make html

Docker Installation (Optional)
------------------------------

For containerized deployment:

.. code-block:: dockerfile

   FROM python:3.13-slim

   RUN apt-get update && apt-get install -y \
       ffmpeg \
       libgl1-mesa-glx \
       libglib2.0-0 \
       && rm -rf /var/lib/apt/lists/*

   WORKDIR /app
   COPY pyproject.toml .
   RUN pip install .

   COPY . .
   CMD ["python", "-m", "goesvfi.gui"]

Build and run:

.. code-block:: bash

   docker build -t goes-vfi .
   docker run -it --rm -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix goes-vfi

Next Steps
----------

Once installation is complete:

1. Read the :doc:`quickstart` guide
2. Explore the :doc:`tutorials/index`
3. Check out the :doc:`user_guide/index`
4. Join our community discussions on GitHub

For any installation issues, please check our `GitHub Issues <https://github.com/username/GOES_VFI/issues>`_ or start a new discussion.
