API Reference
=============

This section provides detailed API documentation for all GOES_VFI modules and classes.

.. toctree::
   :maxdepth: 2
   :caption: Core API

   pipeline
   integrity_check
   gui
   utils
   sanchez

Overview
--------

The GOES_VFI API is organized into several key modules:

- :doc:`pipeline` - Core processing pipeline for video frame interpolation
- :doc:`integrity_check` - Data validation and quality assessment
- :doc:`gui` - User interface components and widgets
- :doc:`utils` - Shared utilities and helper functions
- :doc:`sanchez` - Sanchez processor integration

Quick Reference
---------------

**Core Classes:**

.. autosummary::
   :toctree: _autosummary

   goesvfi.pipeline.run_vfi.VfiWorker
   goesvfi.integrity_check.enhanced_view_model.EnhancedIntegrityCheckViewModel
   goesvfi.gui.MainWindow
   goesvfi.utils.resource_manager.ResourceMonitor
   goesvfi.utils.security.InputValidator

**Processing Pipeline:**

.. autosummary::
   :toctree: _autosummary

   goesvfi.pipeline.image_loader.ImageLoader
   goesvfi.pipeline.image_cropper.ImageCropper
   goesvfi.pipeline.sanchez_processor.SanchezProcessor
   goesvfi.pipeline.encode.FFmpegBuilder

**Data Management:**

.. autosummary::
   :toctree: _autosummary

   goesvfi.integrity_check.time_index.TimeIndex
   goesvfi.integrity_check.remote.s3_store.S3Store
   goesvfi.integrity_check.cache_db.CacheDB

**GUI Components:**

.. autosummary::
   :toctree: _autosummary

   goesvfi.gui_tabs.main_tab.MainTab
   goesvfi.gui_tabs.ffmpeg_settings_tab.FFmpegSettingsTab
   goesvfi.gui_tabs.resource_limits_tab.ResourceLimitsTab

**Utilities:**

.. autosummary::
   :toctree: _autosummary

   goesvfi.utils.config
   goesvfi.utils.log
   goesvfi.utils.memory_manager.MemoryOptimizer
   goesvfi.utils.gui_helpers

Common Usage Patterns
---------------------

**Basic Processing Workflow:**

.. code-block:: python

   from goesvfi.pipeline.run_vfi import VfiWorker
   from goesvfi.utils.resource_manager import ResourceLimits
   from pathlib import Path

   # Configure resource limits
   limits = ResourceLimits(max_memory_mb=2048)

   # Create worker
   worker = VfiWorker(
       in_dir=Path("input/"),
       out_file_path=Path("output.mp4"),
       fps=30,
       encoder="RIFE",
       resource_limits=limits
   )

   # Connect signals
   worker.progress.connect(lambda c, t, e: print(f"Progress: {c}/{t}"))
   worker.finished.connect(lambda p: print(f"Finished: {p}"))
   worker.error.connect(lambda e: print(f"Error: {e}"))

   # Start processing
   worker.start()

**Data Integrity Checking:**

.. code-block:: python

   from goesvfi.integrity_check.enhanced_view_model import EnhancedIntegrityCheckViewModel
   from goesvfi.integrity_check.remote.s3_store import S3Store
   from datetime import datetime

   # Create S3 store
   s3_store = S3Store()

   # Create view model
   vm = EnhancedIntegrityCheckViewModel(s3_store=s3_store)

   # Check data for specific date range
   start_date = datetime(2024, 1, 1)
   end_date = datetime(2024, 1, 2)

   # Perform integrity check
   results = vm.scan_date_range(start_date, end_date)

**Resource Monitoring:**

.. code-block:: python

   from goesvfi.utils.resource_manager import ResourceMonitor, ResourceLimits

   # Create monitor with limits
   limits = ResourceLimits(
       max_memory_mb=1024,
       max_cpu_percent=80.0,
       max_processing_time_sec=300
   )

   monitor = ResourceMonitor(limits)

   # Add callbacks
   monitor.add_callback('usage_update', lambda u: print(f"Memory: {u.memory_mb}MB"))
   monitor.add_callback('limit_exceeded', lambda u: print("Limit exceeded!"))

   # Start monitoring
   monitor.start_monitoring()

**Security Validation:**

.. code-block:: python

   from goesvfi.utils.security import InputValidator, SecurityError

   try:
       # Validate file path
       InputValidator.validate_file_path(
           "/path/to/file.mp4",
           allowed_extensions=['.mp4', '.avi'],
           must_exist=False
       )

       # Validate numeric range
       InputValidator.validate_numeric_range(
           value=30,
           min_val=1,
           max_val=120,
           name="fps"
       )

       print("Validation passed")

   except SecurityError as e:
       print(f"Security validation failed: {e}")

Error Handling
--------------

GOES_VFI uses a hierarchical exception system:

.. code-block:: python

   from goesvfi.exceptions import (
       GOESVFIError,
       ConfigurationError,
       ExternalToolError
   )
   from goesvfi.utils.security import SecurityError
   from goesvfi.utils.resource_manager import ResourceLimitExceeded

   try:
       # Your processing code here
       pass
   except SecurityError as e:
       print(f"Security validation failed: {e}")
   except ResourceLimitExceeded as e:
       print(f"Resource limit exceeded: {e.resource_type}")
   except ConfigurationError as e:
       print(f"Configuration issue: {e}")
   except ExternalToolError as e:
       print(f"External tool error: {e}")
   except GOESVFIError as e:
       print(f"General GOES_VFI error: {e}")

Type Annotations
----------------

GOES_VFI is fully type-annotated. Import common types:

.. code-block:: python

   from typing import Optional, List, Dict, Any, Union
   from pathlib import Path
   from PyQt6.QtCore import QObject, pyqtSignal
   from numpy.typing import NDArray
   import numpy as np

   # Example function with full type annotations
   def process_images(
       input_paths: List[Path],
       output_dir: Path,
       quality: float = 0.8,
       resize: Optional[tuple[int, int]] = None
   ) -> Dict[str, Any]:
       """Process a list of images with specified quality and optional resizing.

       Args:
           input_paths: List of input image file paths
           output_dir: Directory to save processed images
           quality: Quality factor (0.0 to 1.0)
           resize: Optional (width, height) tuple for resizing

       Returns:
           Dictionary containing processing results and statistics
       """
       # Implementation here
       pass

Configuration
-------------

Access configuration through the config module:

.. code-block:: python

   from goesvfi.utils import config

   # Get configuration values
   output_dir = config.get_output_dir()
   cache_dir = config.get_cache_dir()
   tile_size = config.get_default_tile_size()

   # Get available models
   models = config.get_available_rife_models()

   # Find executables
   rife_path = config.find_rife_executable("rife-v4.6")

Logging
-------

GOES_VFI uses structured logging:

.. code-block:: python

   from goesvfi.utils import log

   # Get logger for your module
   LOGGER = log.get_logger(__name__)

   # Log messages at different levels
   LOGGER.debug("Debug information")
   LOGGER.info("General information")
   LOGGER.warning("Warning message")
   LOGGER.error("Error occurred")
   LOGGER.exception("Exception with traceback")

   # Set global log level
   log.set_global_log_level(logging.DEBUG)

Threading and Async
-------------------

GOES_VFI uses both threading (for GUI) and async (for I/O):

.. code-block:: python

   from PyQt6.QtCore import QThread, pyqtSignal
   import asyncio

   class ProcessingWorker(QThread):
       """Example worker thread for background processing."""

       progress = pyqtSignal(int)
       finished = pyqtSignal(str)

       def run(self):
           """Main worker method."""
           # Use asyncio for I/O operations
           asyncio.run(self._async_work())

       async def _async_work(self):
           """Async work method."""
           # Async I/O operations here
           pass

For detailed documentation of specific modules, see the individual API reference pages.
