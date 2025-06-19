Pipeline API
============

The pipeline module contains the core processing components for video frame interpolation and image processing.

.. currentmodule:: goesvfi.pipeline

Overview
--------

The pipeline architecture follows a modular design where each component has a specific responsibility:

- **Image Loading**: Load and validate input images
- **Image Processing**: Apply various transformations and effects
- **Frame Interpolation**: Generate intermediate frames using AI or traditional methods
- **Video Encoding**: Combine frames into output videos
- **Resource Management**: Monitor and control resource usage

Core Components
---------------

VfiWorker
~~~~~~~~~

.. autoclass:: run_vfi.VfiWorker
   :members:
   :inherited-members:
   :show-inheritance:

The main worker thread that orchestrates the entire video frame interpolation process.

**Key Features:**

- Asynchronous processing with progress reporting
- Resource limit enforcement
- Multiple encoder support (RIFE, FFmpeg, Sanchez)
- Error handling and recovery

**Example Usage:**

.. code-block:: python

   from goesvfi.pipeline.run_vfi import VfiWorker
   from goesvfi.utils.resource_manager import ResourceLimits
   from pathlib import Path

   # Configure processing
   worker = VfiWorker(
       in_dir=Path("input_frames/"),
       out_file_path=Path("output.mp4"),
       fps=30,
       mid_count=2,  # Generate 2 intermediate frames
       encoder="RIFE",
       resource_limits=ResourceLimits(max_memory_mb=2048)
   )

   # Connect signals
   worker.progress.connect(lambda current, total, eta:
       print(f"Progress: {current}/{total} (ETA: {eta:.1f}s)"))
   worker.finished.connect(lambda path: print(f"Complete: {path}"))
   worker.error.connect(lambda msg: print(f"Error: {msg}"))

   # Start processing
   worker.start()

Image Processing Components
---------------------------

ImageLoader
~~~~~~~~~~~

.. autoclass:: image_loader.ImageLoader
   :members:
   :show-inheritance:

Handles loading and initial validation of input images.

**Supported Formats:**

- PNG, JPEG, BMP, TIFF
- NetCDF files (for satellite data)
- RAW formats (with appropriate libraries)

ImageCropper
~~~~~~~~~~~~

.. autoclass:: image_cropper.ImageCropper
   :members:
   :show-inheritance:

Provides image cropping functionality with various modes.

**Cropping Modes:**

- Manual rectangle selection
- Automatic content-aware cropping
- Aspect ratio preservation
- Batch cropping with consistent parameters

SanchezProcessor
~~~~~~~~~~~~~~~~

.. autoclass:: sanchez_processor.SanchezProcessor
   :members:
   :show-inheritance:

Integrates with the Sanchez tool for false-color satellite image processing.

**Features:**

- False-color enhancement
- Geographic projection
- Resolution scaling
- Batch processing support

Image Processing Interfaces
---------------------------

.. automodule:: image_processing_interfaces
   :members:
   :show-inheritance:

These interfaces define the contract for all image processing components:

**ImageProcessor Protocol:**

.. code-block:: python

   from typing import Protocol
   from .image_processing_interfaces import ImageData

   class ImageProcessor(Protocol):
       def process(self, image_data: ImageData, **kwargs) -> ImageData:
           """Process image data and return result."""
           ...

**ImageData Class:**

.. code-block:: python

   @dataclass
   class ImageData:
       image_data: np.ndarray
       metadata: Dict[str, Any]

       def copy(self) -> 'ImageData':
           """Create a deep copy of the image data."""
           return ImageData(
               image_data=self.image_data.copy(),
               metadata=self.metadata.copy()
           )

Video Encoding
--------------

FFmpegBuilder
~~~~~~~~~~~~~

.. automodule:: encode
   :members:
   :show-inheritance:

Handles video encoding using FFmpeg with comprehensive options.

**Encoding Profiles:**

- **High Quality**: CRF 16, slow preset, yuv444p
- **Balanced**: CRF 20, medium preset, yuv420p
- **Fast**: CRF 24, fast preset, yuv420p
- **Custom**: User-defined parameters

**Advanced Features:**

- Motion interpolation with configurable algorithms
- Unsharp mask filtering
- Scene change detection
- Variable bitrate encoding

Utility Functions
-----------------

.. autofunction:: run_vfi.run_vfi

The main processing function that coordinates all pipeline components.

**Parameters:**

- **folder**: Input directory containing image sequence
- **output_mp4_path**: Output video file path
- **rife_exe_path**: Path to RIFE executable (if using RIFE)
- **fps**: Output video frame rate
- **encoder_type**: Processing method ("RIFE", "FFmpeg", or "Sanchez")
- **ffmpeg_settings**: FFmpeg configuration dictionary
- **resource_limits**: Resource usage constraints

**Returns:**

Generator yielding progress updates and final result.

Processing Pipeline Flow
------------------------

The typical processing flow follows these steps:

1. **Initialization**

   - Validate input parameters
   - Set up resource monitoring
   - Initialize processing components

2. **Input Processing**

   - Load and validate input images
   - Apply cropping if specified
   - Sort images by timestamp or filename

3. **Frame Interpolation**

   - Generate intermediate frames using selected method
   - Apply post-processing effects
   - Validate output quality

4. **Video Encoding**

   - Combine frames into video sequence
   - Apply compression and quality settings
   - Generate final output file

5. **Cleanup**

   - Remove temporary files
   - Release system resources
   - Report final statistics

Error Handling
--------------

The pipeline uses a comprehensive error handling system:

.. code-block:: python

   from goesvfi.exceptions import (
       ConfigurationError,
       ExternalToolError,
       ProcessingError
   )
   from goesvfi.utils.resource_manager import ResourceLimitExceeded

   try:
       worker = VfiWorker(...)
       worker.start()
   except ConfigurationError as e:
       print(f"Configuration issue: {e}")
   except ResourceLimitExceeded as e:
       print(f"Resource limit exceeded: {e.resource_type}")
   except ExternalToolError as e:
       print(f"External tool failed: {e.tool_name} - {e.message}")
   except ProcessingError as e:
       print(f"Processing failed: {e}")

**Common Error Scenarios:**

- Invalid input format or corrupted files
- Insufficient system resources
- Missing external tools (RIFE, FFmpeg, Sanchez)
- Network issues when downloading satellite data
- Permission errors when writing output files

Performance Optimization
------------------------

**Memory Management:**

.. code-block:: python

   from goesvfi.utils.resource_manager import ResourceLimits

   # Conservative settings for limited memory
   limits = ResourceLimits(
       max_memory_mb=1024,
       max_open_files=100
   )

   # High-performance settings
   limits = ResourceLimits(
       max_memory_mb=8192,
       max_cpu_percent=90.0,
       max_open_files=1000
   )

**Processing Optimization:**

- Use tiling for large images to reduce memory usage
- Enable parallel processing for multi-core systems
- Cache intermediate results to avoid recomputation
- Use appropriate compression settings for output quality vs. speed

**Monitoring Performance:**

.. code-block:: python

   from goesvfi.utils.memory_manager import get_memory_monitor

   # Monitor memory usage during processing
   monitor = get_memory_monitor()
   monitor.start_monitoring()

   # Check memory statistics
   stats = monitor.get_current_stats()
   print(f"Memory usage: {stats.memory_percent:.1f}%")

Configuration Options
---------------------

**RIFE Settings:**

.. code-block:: python

   rife_settings = {
       'model_key': 'rife-v4.6',
       'tile_enable': True,
       'tile_size': 512,
       'uhd_mode': False,
       'tta_spatial': False,
       'tta_temporal': False,
       'thread_spec': '1:1:1'
   }

**FFmpeg Settings:**

.. code-block:: python

   ffmpeg_settings = {
       'use_ffmpeg_interp': True,
       'mi_mode': 'mci',
       'mc_mode': 'aobmc',
       'me_mode': 'bidir',
       'filter_preset': 'slow',
       'crf': 16,
       'bitrate_kbps': 15000,
       'pix_fmt': 'yuv444p'
   }

**Sanchez Settings:**

.. code-block:: python

   sanchez_settings = {
       'false_colour': True,
       'res_km': 4,
       'crop': None,
       'brightness': 0.0,
       'contrast': 1.0,
       'saturation': 1.0
   }

Thread Safety
-------------

The pipeline components are designed to be thread-safe:

- **VfiWorker** runs in its own thread and communicates via Qt signals
- **ImageProcessor** implementations should be stateless or use thread-local storage
- **Resource monitoring** uses thread-safe data structures
- **Temporary file handling** uses unique naming to avoid conflicts

**Best Practices:**

- Create separate instances for concurrent processing
- Use signals/slots for inter-thread communication
- Avoid shared mutable state between threads
- Use appropriate locking for shared resources

Testing and Validation
-----------------------

The pipeline includes comprehensive testing utilities:

.. code-block:: python

   from goesvfi.pipeline.testing import (
       create_test_image_sequence,
       validate_output_video,
       benchmark_processing_speed
   )

   # Create test data
   test_images = create_test_image_sequence(
       count=10,
       size=(1920, 1080),
       format='png'
   )

   # Validate output
   is_valid = validate_output_video(
       video_path=Path("output.mp4"),
       expected_fps=30,
       expected_duration=5.0
   )

   # Benchmark performance
   stats = benchmark_processing_speed(
       input_dir=Path("test_images/"),
       encoder="RIFE"
   )

See the :doc:`../development/testing` section for more information on testing the pipeline components.
