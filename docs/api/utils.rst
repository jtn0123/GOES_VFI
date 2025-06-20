Utilities API
=============

The utils module provides shared utilities and helper functions used throughout GOES_VFI.

.. currentmodule:: goesvfi.utils

Overview
--------

The utilities module contains essential functionality for:

- **Configuration Management**: Application settings and preferences
- **Logging**: Structured logging with multiple outputs
- **Resource Management**: System resource monitoring and limits
- **Security**: Input validation and sanitization
- **Memory Management**: Memory optimization and monitoring
- **GUI Helpers**: Common UI components and utilities

Configuration
-------------

.. automodule:: goesvfi.utils.config
   :members:
   :undoc-members:
   :show-inheritance:

The configuration module manages application settings and provides access to configuration files.

**Key Functions:**

.. autofunction:: goesvfi.utils.config.get_output_dir
.. autofunction:: goesvfi.utils.config.get_cache_dir
.. autofunction:: goesvfi.utils.config.get_available_rife_models
.. autofunction:: goesvfi.utils.config.find_rife_executable

**Configuration Example:**

.. code-block:: python

   from goesvfi.utils import config

   # Get configuration paths
   output_dir = config.get_output_dir()
   cache_dir = config.get_cache_dir()

   # Find available models
   models = config.get_available_rife_models()
   print(f"Available RIFE models: {models}")

   # Locate executables
   rife_path = config.find_rife_executable("rife-v4.6")

   # Get FFmpeg profiles
   profiles = config.FFMPEG_PROFILES
   optimal_profile = profiles["Optimal"]

**Configuration File Format:**

GOES_VFI uses TOML configuration files stored in ``~/.config/goesvfi/config.toml``:

.. code-block:: toml

   [paths]
   output_dir = "~/Documents/goesvfi"
   cache_dir = "~/Documents/goesvfi/cache"

   [pipeline]
   default_tile_size = 2048
   supported_extensions = [".png", ".jpg", ".jpeg"]

   [sanchez]
   bin_dir = "./sanchez/bin"

   [logging]
   level = "INFO"

Logging
-------

.. automodule:: log
   :members:
   :undoc-members:
   :show-inheritance:

Provides structured logging with color output and multiple handlers.

**Basic Usage:**

.. code-block:: python

   from goesvfi.utils import log

   # Get logger for your module
   LOGGER = log.get_logger(__name__)

   # Log at different levels
   LOGGER.debug("Debug information for developers")
   LOGGER.info("General information")
   LOGGER.warning("Something might be wrong")
   LOGGER.error("An error occurred")
   LOGGER.exception("Exception with full traceback")

**Advanced Configuration:**

.. code-block:: python

   import logging
   from goesvfi.utils import log

   # Set global log level
   log.set_global_log_level(logging.DEBUG)

   # Get logger with specific configuration
   logger = log.get_logger("my_module", level=logging.INFO)

   # Log with structured data
   logger.info("Processing started", extra={
       'input_count': 100,
       'output_format': 'mp4',
       'encoder': 'RIFE'
   })

Resource Management
-------------------

.. automodule:: resource_manager
   :members:
   :undoc-members:
   :show-inheritance:

Provides system resource monitoring and limiting capabilities.

**Core Classes:**

ResourceLimits
~~~~~~~~~~~~~~

.. autoclass:: resource_manager.ResourceLimits
   :members:
   :show-inheritance:

Configuration for resource limits:

.. code-block:: python

   from goesvfi.utils.resource_manager import ResourceLimits

   # Basic limits
   limits = ResourceLimits(
       max_memory_mb=2048,
       max_processing_time_sec=1800,
       max_cpu_percent=80.0
   )

   # Conservative limits for low-end systems
   conservative_limits = ResourceLimits(
       max_memory_mb=512,
       max_processing_time_sec=600,
       max_cpu_percent=50.0,
       max_open_files=100
   )

ResourceMonitor
~~~~~~~~~~~~~~~

.. autoclass:: resource_manager.ResourceMonitor
   :members:
   :show-inheritance:

Real-time resource monitoring:

.. code-block:: python

   from goesvfi.utils.resource_manager import ResourceMonitor, ResourceLimits

   # Create monitor
   limits = ResourceLimits(max_memory_mb=1024)
   monitor = ResourceMonitor(limits, check_interval=1.0)

   # Add callbacks
   def on_usage_update(usage):
       print(f"Memory: {usage.memory_mb:.1f}MB, CPU: {usage.cpu_percent:.1f}%")

   def on_limit_exceeded(usage):
       print(f"Resource limit exceeded!")

   monitor.add_callback('usage_update', on_usage_update)
   monitor.add_callback('limit_exceeded', on_limit_exceeded)

   # Start monitoring
   monitor.start_monitoring()

   try:
       # Your processing code here
       time.sleep(10)
   finally:
       monitor.stop_monitoring()

ResourceLimitedContext
~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: resource_manager.ResourceLimitedContext
   :members:
   :show-inheritance:

Context manager for applying resource limits:

.. code-block:: python

   from goesvfi.utils.resource_manager import ResourceLimitedContext, ResourceLimits

   limits = ResourceLimits(max_memory_mb=1024, max_processing_time_sec=300)

   with ResourceLimitedContext(limits, monitor=True) as context:
       monitor = context.get_monitor()
       if monitor:
           print("Resource monitoring active")

       # Your processing code runs with resource limits applied
       process_large_dataset()

**Utility Functions:**

.. autofunction:: resource_manager.get_system_resource_info
.. autofunction:: resource_manager.set_system_resource_limits

Security
--------

.. automodule:: security
   :members:
   :undoc-members:
   :show-inheritance:

Provides input validation and security utilities to prevent common vulnerabilities.

**Core Classes:**

InputValidator
~~~~~~~~~~~~~~

.. autoclass:: security.InputValidator
   :members:
   :show-inheritance:

Comprehensive input validation:

.. code-block:: python

   from goesvfi.utils.security import InputValidator, SecurityError

   try:
       # Validate file paths
       InputValidator.validate_file_path(
           "/path/to/file.mp4",
           allowed_extensions=['.mp4', '.avi'],
           must_exist=False
       )

       # Validate numeric ranges
       InputValidator.validate_numeric_range(
           value=30,
           min_val=1,
           max_val=120,
           name="fps"
       )

       # Validate FFmpeg encoder
       InputValidator.validate_ffmpeg_encoder("Software x265")

       # Validate Sanchez arguments
       InputValidator.validate_sanchez_argument("res_km", "4")

       print("All validations passed")

   except SecurityError as e:
       print(f"Security validation failed: {e}")

SecureFileHandler
~~~~~~~~~~~~~~~~~

.. autoclass:: security.SecureFileHandler
   :members:
   :show-inheritance:

Secure file operations:

.. code-block:: python

   from goesvfi.utils.security import SecureFileHandler

   # Create secure temporary file
   temp_file = SecureFileHandler.create_secure_temp_file(
       suffix='.tmp',
       prefix='goesvfi_'
   )

   # Create secure config directory
   config_dir = Path.home() / '.config' / 'goesvfi'
   SecureFileHandler.create_secure_config_dir(config_dir)

**Security Functions:**

.. autofunction:: security.secure_subprocess_call

Secure subprocess execution:

.. code-block:: python

   from goesvfi.utils.security import secure_subprocess_call, SecurityError

   try:
       result = secure_subprocess_call([
           'ffmpeg',
           '-i', 'input.mp4',
           '-c:v', 'libx264',
           'output.mp4'
       ], timeout=300)

       print(f"Command output: {result.stdout}")

   except SecurityError as e:
       print(f"Security validation failed: {e}")

Memory Management
-----------------

.. automodule:: memory_manager
   :members:
   :undoc-members:
   :show-inheritance:

Provides memory optimization and monitoring utilities.

**Core Classes:**

MemoryOptimizer
~~~~~~~~~~~~~~~

.. autoclass:: memory_manager.MemoryOptimizer
   :members:
   :show-inheritance:

Automatic memory optimization:

.. code-block:: python

   from goesvfi.utils.memory_manager import MemoryOptimizer

   # Create optimizer with target memory usage
   optimizer = MemoryOptimizer(target_memory_mb=1024)

   # Process data with automatic optimization
   for data_chunk in large_dataset:
       # Memory usage is automatically monitored and optimized
       processed = optimizer.process_with_optimization(data_chunk)
       yield processed

**Monitoring Functions:**

.. autofunction:: memory_manager.get_memory_monitor
.. autofunction:: memory_manager.log_memory_usage

Example usage:

.. code-block:: python

   from goesvfi.utils.memory_manager import get_memory_monitor, log_memory_usage

   # Get memory monitor
   monitor = get_memory_monitor()
   monitor.start_monitoring()

   # Log current memory usage
   log_memory_usage("Before processing")

   # Your processing code
   process_data()

   log_memory_usage("After processing")
   monitor.stop_monitoring()

GUI Helpers
-----------

.. automodule:: gui_helpers
   :members:
   :undoc-members:
   :show-inheritance:

Common GUI components and utilities.

**Key Classes:**

ClickableLabel
~~~~~~~~~~~~~~

.. autoclass:: gui_helpers.ClickableLabel
   :members:
   :show-inheritance:

Enhanced QLabel with click handling:

.. code-block:: python

   from goesvfi.utils.gui_helpers import ClickableLabel
   from PyQt6.QtWidgets import QVBoxLayout, QWidget

   class MyWidget(QWidget):
       def __init__(self):
           super().__init__()
           layout = QVBoxLayout(self)

           # Create clickable label
           label = ClickableLabel("Click me!")
           label.clicked.connect(self.on_label_clicked)
           layout.addWidget(label)

       def on_label_clicked(self):
           print("Label was clicked!")

CropSelectionDialog
~~~~~~~~~~~~~~~~~~~

.. autoclass:: gui_helpers.CropSelectionDialog
   :members:
   :show-inheritance:

Dialog for selecting crop rectangles:

.. code-block:: python

   from goesvfi.utils.gui_helpers import CropSelectionDialog
   from PyQt6.QtCore import QRect

   # Show crop selection dialog
   dialog = CropSelectionDialog(parent=self)
   dialog.set_image(image_pixmap)

   if dialog.exec() == QDialog.DialogCode.Accepted:
       crop_rect = dialog.get_crop_rect()
       print(f"Selected crop: {crop_rect}")

ImageViewerDialog
~~~~~~~~~~~~~~~~~

.. autoclass:: gui_helpers.ImageViewerDialog
   :members:
   :show-inheritance:

Full-screen image viewer:

.. code-block:: python

   from goesvfi.utils.gui_helpers import ImageViewerDialog

   # Show image in viewer
   viewer = ImageViewerDialog(parent=self)
   viewer.set_image(image_pixmap)
   viewer.show()

Date and Time Utilities
-----------------------

.. automodule:: date_utils
   :members:
   :undoc-members:
   :show-inheritance:

Utilities for handling dates and times in satellite data.

**Key Functions:**

.. autofunction:: date_utils.parse_goes_timestamp
.. autofunction:: date_utils.format_timestamp
.. autofunction:: date_utils.get_date_range

Example usage:

.. code-block:: python

   from goesvfi.utils.date_utils import parse_goes_timestamp, get_date_range
   from datetime import datetime

   # Parse GOES timestamp
   timestamp = parse_goes_timestamp("OR_ABI-L1b-RadF-M6C01_G16_s20230661200000")
   print(f"Image timestamp: {timestamp}")

   # Get date range for scanning
   start_date = datetime(2024, 1, 1)
   end_date = datetime(2024, 1, 2)
   date_range = get_date_range(start_date, end_date, hours=True)

RIFE Analyzer
-------------

.. automodule:: rife_analyzer
   :members:
   :undoc-members:
   :show-inheritance:

Utilities for analyzing and configuring RIFE models.

**Key Classes:**

RifeCapabilityDetector
~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: rife_analyzer.RifeCapabilityDetector
   :members:
   :show-inheritance:

Detect RIFE capabilities:

.. code-block:: python

   from goesvfi.utils.rife_analyzer import RifeCapabilityDetector

   detector = RifeCapabilityDetector()

   # Analyze RIFE executable
   capabilities = detector.analyze_executable("/path/to/rife")

   print(f"Supports UHD: {capabilities.supports_uhd}")
   print(f"Supports TTA: {capabilities.supports_tta}")
   print(f"Available models: {capabilities.available_models}")

**Analysis Functions:**

.. autofunction:: rife_analyzer.analyze_rife_executable

UI Security Indicators
----------------------

.. automodule:: ui_security_indicators
   :members:
   :undoc-members:
   :show-inheritance:

UI components for showing security validation status.

**Key Classes:**

SecurityStatusIndicator
~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: ui_security_indicators.SecurityStatusIndicator
   :members:
   :show-inheritance:

Visual security status indicator:

.. code-block:: python

   from goesvfi.utils.ui_security_indicators import SecurityStatusIndicator

   # Create status indicator
   indicator = SecurityStatusIndicator(parent=self)

   # Set different statuses
   indicator.set_status("safe", "Input validated successfully")
   indicator.set_status("warning", "Input has minor issues")
   indicator.set_status("error", "Input failed validation")

SecureInputWidget
~~~~~~~~~~~~~~~~~

.. autoclass:: ui_security_indicators.SecureInputWidget
   :members:
   :show-inheritance:

Input widget with integrated security status:

.. code-block:: python

   from goesvfi.utils.ui_security_indicators import create_security_enhanced_input
   from PyQt6.QtWidgets import QLineEdit, QHBoxLayout

   # Create secure input widget
   line_edit = QLineEdit()
   secure_widget = create_security_enhanced_input(line_edit)

   # Add to layout
   layout = QHBoxLayout()
   layout.addWidget(secure_widget.get_input_widget())
   layout.addWidget(secure_widget.get_security_indicator())

**Utility Functions:**

.. autofunction:: ui_security_indicators.validate_and_show_status

Error Handling
--------------

All utility modules use consistent error handling:

.. code-block:: python

   from goesvfi.utils.security import SecurityError
   from goesvfi.utils.resource_manager import ResourceLimitExceeded
   from goesvfi.exceptions import ConfigurationError

   try:
       # Utility operations
       result = some_utility_function()
   except SecurityError as e:
       print(f"Security validation failed: {e}")
   except ResourceLimitExceeded as e:
       print(f"Resource limit exceeded: {e.resource_type}")
   except ConfigurationError as e:
       print(f"Configuration issue: {e}")
   except Exception as e:
       print(f"Unexpected error: {e}")

Performance Considerations
-------------------------

The utilities are designed for performance:

- **Lazy Loading**: Modules are loaded only when needed
- **Caching**: Configuration and resource information is cached
- **Efficient Monitoring**: Resource monitoring uses minimal overhead
- **Async Operations**: I/O operations use async when possible

**Best Practices:**

- Reuse utility instances where possible
- Cache expensive operations (file system access, network calls)
- Use appropriate logging levels to avoid performance impact
- Monitor resource usage in production environments

Thread Safety
-------------

All utility modules are designed to be thread-safe:

- **Configuration**: Read-only after initialization
- **Logging**: Thread-safe loggers with proper synchronization
- **Resource Monitoring**: Uses thread-safe data structures
- **Security Validation**: Stateless functions safe for concurrent use

**Thread-Safe Usage:**

.. code-block:: python

   import threading
   from goesvfi.utils import log, config
   from goesvfi.utils.security import InputValidator

   def worker_function(worker_id):
       # Each thread gets its own logger instance
       logger = log.get_logger(f"worker_{worker_id}")

       # Configuration access is thread-safe
       output_dir = config.get_output_dir()

       # Security validation is stateless and thread-safe
       try:
           InputValidator.validate_file_path(some_path)
       except SecurityError:
           logger.error("Validation failed")

   # Start multiple worker threads
   threads = []
   for i in range(4):
       thread = threading.Thread(target=worker_function, args=(i,))
       threads.append(thread)
       thread.start()

   # Wait for completion
   for thread in threads:
       thread.join()

Testing Utilities
-----------------

The utils module includes testing helpers:

.. code-block:: python

   from goesvfi.utils.testing import (
       create_test_config,
       mock_resource_monitor,
       create_test_images
   )

   # Create test configuration
   test_config = create_test_config(
       output_dir="/tmp/test_output",
       cache_dir="/tmp/test_cache"
   )

   # Mock resource monitor for testing
   with mock_resource_monitor() as monitor:
       # Test code that uses resource monitoring
       pass

   # Create test images
   test_images = create_test_images(
       count=10,
       size=(640, 480),
       format='png'
   )

See the individual module documentation for more detailed information on specific utilities.
