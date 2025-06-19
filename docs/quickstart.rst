Quick Start Guide
=================

This guide will help you get up and running with GOES_VFI quickly.

Prerequisites
-------------

Before starting, ensure you have:

- Python 3.13 or higher installed
- At least 4GB of available RAM
- 1GB of free disk space
- Internet connection for downloading satellite data

Installation
------------

1. **Clone the repository:**

   .. code-block:: bash

      git clone https://github.com/username/GOES_VFI.git
      cd GOES_VFI

2. **Create a virtual environment:**

   .. code-block:: bash

      python -m venv .venv
      source .venv/bin/activate  # On Windows: .venv\Scripts\activate

3. **Install dependencies:**

   .. code-block:: bash

      pip install -r requirements.txt

4. **Verify installation:**

   .. code-block:: bash

      python -c "import goesvfi; print('GOES_VFI installed successfully!')"

First Run
---------

**Launch the GUI:**

.. code-block:: bash

   python -m goesvfi.gui

This will open the GOES_VFI main window with several tabs:

- **Main**: Core processing controls
- **FFmpeg Settings**: Video encoding configuration
- **Resource Limits**: System resource management
- **Model Library**: RIFE model management
- **Satellite Integrity**: Data validation tools

Basic Workflow
--------------

1. **Select Input Directory**

   Click "Browse" next to "Input Directory" and select a folder containing your image sequence.

2. **Choose Output File**

   Click "Browse" next to "Output File" and specify where to save the resulting video.

3. **Configure Settings**

   - **FPS**: Set the output video frame rate (typically 30)
   - **Multiplier**: Number of intermediate frames to generate (2-4 recommended)
   - **Encoder**: Choose processing method:
     - **RIFE**: AI-powered interpolation (best quality)
     - **FFmpeg**: Traditional motion interpolation
     - **Sanchez**: False-color satellite processing

4. **Set Resource Limits** (Optional)

   Switch to the "Resource Limits" tab to configure:
   - Memory usage limits
   - Processing time limits
   - CPU usage constraints

5. **Start Processing**

   Click "Start" in the Main tab. Progress will be shown in the status bar.

Example: Processing Satellite Data
----------------------------------

Here's a complete example of processing GOES satellite imagery:

**Step 1: Download Sample Data**

.. code-block:: python

   from goesvfi.integrity_check.remote.s3_store import S3Store
   from datetime import datetime
   import asyncio

   async def download_sample_data():
       store = S3Store()

       # Download a few recent images
       date = datetime(2024, 1, 1, 12, 0)  # Noon UTC

       for hour in range(3):  # 3 hours of data
           key = f"ABI-L1b-RadF/2024/001/{hour:02d}/OR_ABI-L1b-RadF-M6C13_G16_s20240011{hour:02d}00000_e20240011{hour:02d}59999_c20240011{hour:02d}59999.nc"

           try:
               data = await store.fetch_data(key)
               with open(f"sample_{hour:02d}.nc", "wb") as f:
                   f.write(data)
               print(f"Downloaded {key}")
           except Exception as e:
               print(f"Failed to download {key}: {e}")

   # Run the download
   asyncio.run(download_sample_data())

**Step 2: Convert to Images**

.. code-block:: python

   from goesvfi.integrity_check.render.netcdf import NetCDFRenderer
   import xarray as xr
   from pathlib import Path

   # Convert NetCDF files to PNG images
   output_dir = Path("satellite_images")
   output_dir.mkdir(exist_ok=True)

   renderer = NetCDFRenderer()

   for i, nc_file in enumerate(Path(".").glob("sample_*.nc")):
       try:
           # Load NetCDF data
           dataset = xr.open_dataset(nc_file)

           # Render to image
           image_path = output_dir / f"frame_{i:03d}.png"
           renderer.render_to_file(dataset, image_path)

           print(f"Converted {nc_file} -> {image_path}")
           dataset.close()

       except Exception as e:
           print(f"Error converting {nc_file}: {e}")

**Step 3: Process with GOES_VFI**

.. code-block:: python

   from goesvfi.pipeline.run_vfi import VfiWorker
   from goesvfi.utils.resource_manager import ResourceLimits
   from pathlib import Path

   # Configure processing
   input_dir = Path("satellite_images")
   output_file = Path("satellite_animation.mp4")

   # Set conservative resource limits
   limits = ResourceLimits(
       max_memory_mb=1024,
       max_processing_time_sec=600,
       max_cpu_percent=70.0
   )

   # Create worker
   worker = VfiWorker(
       in_dir=input_dir,
       out_file_path=output_file,
       fps=15,  # 15 FPS for smooth animation
       mid_count=3,  # Generate 3 intermediate frames
       encoder="RIFE",  # Use AI interpolation
       resource_limits=limits,

       # Additional parameters
       debug_mode=False,
       false_colour=True,  # Enable false color for satellite data
       res_km=4,  # 4km resolution
       crop_rect=None,  # No cropping
   )

   # Connect progress callback
   def on_progress(current, total, eta):
       percent = int((current / total) * 100)
       print(f"Progress: {percent}% ({current}/{total}) ETA: {eta:.1f}s")

   def on_finished(output_path):
       print(f"Processing complete! Output: {output_path}")

   def on_error(error_message):
       print(f"Error: {error_message}")

   worker.progress.connect(on_progress)
   worker.finished.connect(on_finished)
   worker.error.connect(on_error)

   # Start processing
   print("Starting video processing...")
   worker.start()

   # Wait for completion (in a real GUI app, this would be handled by signals)
   worker.wait()

Command Line Usage
------------------

GOES_VFI can also be used from the command line:

**Basic command:**

.. code-block:: bash

   python -m goesvfi.cli \
       --input ./satellite_images/ \
       --output ./animation.mp4 \
       --fps 30 \
       --encoder RIFE \
       --memory-limit 2048

**With advanced options:**

.. code-block:: bash

   python -m goesvfi.cli \
       --input ./images/ \
       --output ./output.mp4 \
       --fps 30 \
       --multiplier 4 \
       --encoder FFmpeg \
       --preset optimal \
       --memory-limit 4096 \
       --time-limit 1800 \
       --debug

**Batch processing:**

.. code-block:: bash

   # Process multiple directories
   for dir in satellite_data_*/; do
       python -m goesvfi.cli \
           --input "$dir" \
           --output "${dir%/}.mp4" \
           --fps 15 \
           --encoder Sanchez \
           --false-colour
   done

Configuration
-------------

**Create a configuration file** at ``~/.config/goesvfi/config.toml``:

.. code-block:: toml

   [paths]
   output_dir = "~/Videos/GOES_VFI"
   cache_dir = "~/Cache/GOES_VFI"

   [pipeline]
   default_tile_size = 2048
   supported_extensions = [".png", ".jpg", ".jpeg", ".nc"]

   [resource_limits]
   default_memory_mb = 2048
   default_time_limit_sec = 1800
   default_cpu_percent = 80.0

   [sanchez]
   bin_dir = "./sanchez/bin"
   default_res_km = 4

   [rife]
   models_dir = "./models"
   default_model = "rife-v4.6"

   [logging]
   level = "INFO"
   file_logging = true

**Load configuration in Python:**

.. code-block:: python

   from goesvfi.utils import config

   # Get configured paths
   output_dir = config.get_output_dir()
   cache_dir = config.get_cache_dir()

   # Get available models
   models = config.get_available_rife_models()

   # Get FFmpeg profiles
   profiles = config.FFMPEG_PROFILES
   optimal_settings = profiles["Optimal"]

Common Issues and Solutions
--------------------------

**"No module named 'PyQt6'" Error**

.. code-block:: bash

   pip install PyQt6

**"FFmpeg not found" Error**

Install FFmpeg:

- **Windows**: Download from https://ffmpeg.org/download.html
- **macOS**: ``brew install ffmpeg``
- **Ubuntu**: ``sudo apt install ffmpeg``

**Memory Errors**

Reduce memory usage:

.. code-block:: python

   # Use smaller tile sizes
   config.default_tile_size = 1024

   # Set memory limits
   limits = ResourceLimits(max_memory_mb=512)

**Slow Processing**

Optimize settings:

.. code-block:: python

   # Use more CPU cores
   worker = VfiWorker(
       max_workers=os.cpu_count(),
       # ... other settings
   )

   # Use hardware acceleration if available
   ffmpeg_settings = {
       'encoder': 'Hardware HEVC (VideoToolbox)',  # macOS
       # or 'encoder': 'Hardware H.264 (NVENC)',  # NVIDIA GPU
   }

**File Permission Errors**

Ensure proper permissions:

.. code-block:: bash

   chmod +x goesvfi/bin/*
   chmod 755 output_directory/

Next Steps
----------

Now that you have GOES_VFI running:

1. **Explore the GUI**: Try different encoders and settings
2. **Read the tutorials**: Check out :doc:`tutorials/index` for detailed workflows
3. **Join the community**: Visit our GitHub discussions for tips and support
4. **Customize settings**: Explore the :doc:`user_guide/index` for advanced configuration

For more detailed information, see:

- :doc:`user_guide/index` - Comprehensive user guide
- :doc:`tutorials/index` - Step-by-step tutorials
- :doc:`api/index` - API reference for developers
- :doc:`development/index` - Contributing and development guide

**Need help?** Check our `GitHub Issues <https://github.com/username/GOES_VFI/issues>`_ or start a discussion!
