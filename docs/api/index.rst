API Reference
=============

This section provides detailed API documentation for all GOES_VFI modules and classes.

.. toctree::
   :maxdepth: 2
   :caption: Core Modules

   gui
   pipeline
   utils
   exceptions

.. toctree::
   :maxdepth: 2
   :caption: GUI Components

   gui_tabs_main_tab
   gui_tabs_ffmpeg_settings_tab
   gui_tabs_resource_limits_tab
   gui_tabs_model_library_tab
   gui_tabs_operation_history_tab

.. toctree::
   :maxdepth: 2
   :caption: Processing Pipeline

   pipeline_image_loader
   pipeline_image_cropper
   pipeline_sanchez_processor
   pipeline_encode
   pipeline_interpolate
   pipeline_run_vfi
   pipeline_ffmpeg_builder

.. toctree::
   :maxdepth: 2
   :caption: Integrity Check

   integrity_check_view_model
   integrity_check_goes_imagery
   integrity_check_time_index
   integrity_check_cache_db
   integrity_check_remote_store

.. toctree::
   :maxdepth: 2
   :caption: Utilities

   utils_config
   utils_log
   utils_date_utils
   utils_gui_helpers
   utils_memory_manager
   utils_security

Overview
--------

The GOES_VFI API is organized into several key modules:

- **GUI** - User interface components and main window
- **Pipeline** - Core processing pipeline for video frame interpolation
- **Integrity Check** - Data validation and quality assessment
- **Utils** - Shared utilities and helper functions
- **File/Date Sorter** - Tools for organizing and sorting files

Core Components
--------------

**Main Application:**

The main entry point is through the `goesvfi.gui` module which provides the MainWindow class.

**Processing Pipeline:**

The processing pipeline consists of several stages:

1. Image loading (`goesvfi.pipeline.image_loader`)
2. Optional cropping (`goesvfi.pipeline.image_cropper`)
3. Optional Sanchez processing (`goesvfi.pipeline.sanchez_processor`)
4. Frame interpolation (`goesvfi.pipeline.interpolate`)
5. Video encoding (`goesvfi.pipeline.encode`)

**Data Management:**

- Time indexing and organization (`goesvfi.integrity_check.time_index`)
- Remote data access via S3 (`goesvfi.integrity_check.remote.s3_store`)
- Local caching (`goesvfi.integrity_check.cache_db`)

**GUI Components:**

- Main processing tab (`goesvfi.gui_tabs.main_tab`)
- FFmpeg settings (`goesvfi.gui_tabs.ffmpeg_settings_tab`)
- Resource limits configuration (`goesvfi.gui_tabs.resource_limits_tab`)
- Model library management (`goesvfi.gui_tabs.model_library_tab`)

Common Usage Patterns
---------------------

**Basic Processing Workflow:**

.. code-block:: python

   from goesvfi.pipeline.run_vfi import VfiWorker
   from pathlib import Path

   # Create worker
   worker = VfiWorker(
       in_dir=Path("input/"),
       out_file_path=Path("output.mp4"),
       fps=30,
       encoder="RIFE"
   )

   # Connect signals
   worker.progress.connect(lambda c, t, e: print(f"Progress: {c}/{t}"))
   worker.finished.connect(lambda p: print(f"Finished: {p}"))
   worker.error.connect(lambda e: print(f"Error: {e}"))

   # Start processing
   worker.start()

**Configuration Access:**

.. code-block:: python

   from goesvfi.utils import config

   # Get configuration values
   output_dir = config.get_output_dir()
   cache_dir = config.get_cache_dir()

   # Get available models
   models = config.get_available_rife_models()

**Logging:**

.. code-block:: python

   from goesvfi.utils import log

   # Get logger for your module
   LOGGER = log.get_logger(__name__)

   # Log messages
   LOGGER.info("Processing started")
   LOGGER.error("An error occurred")

For detailed documentation of specific modules, see the individual API reference pages listed above.
