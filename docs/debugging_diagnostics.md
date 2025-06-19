# Debugging and Diagnostics Guide

This guide covers the enhanced debugging and diagnostics features added to GOES_VFI.

## Overview

The debugging enhancements provide:
- **Structured JSON Logging**: Machine-readable logs with consistent schema
- **Correlation IDs**: Track related operations across components
- **Performance Metrics**: Automatic timing and statistics
- **Debug Mode**: Component-specific verbose logging
- **Operation History**: Persistent tracking with GUI viewer

## Quick Start

### Enable Debug Mode

```python
from goesvfi.utils.debug_mode import enable_debug_mode

# Enable with specific components
enable_debug_mode(
    components=["s3_store", "sanchez", "imagery"],
    json_logging=True,
    performance_tracking=True,
    operation_tracking=True,
    debug_file="/tmp/goesvfi_debug.log"
)
```

Or use environment variables:
```bash
export GOESVFI_DEBUG=1
export GOESVFI_JSON_LOGS=1
python -m goesvfi.gui
```

### Track Operations

```python
from goesvfi.utils.operation_history import track_operation

# Automatic tracking with context manager
with track_operation("download_satellite_data", satellite="GOES-16") as op:
    # Your code here
    result = download_data()
    op.metadata["file_count"] = len(result)
    # Automatically tracks success/failure and duration
```

### Performance Tracking

```python
from goesvfi.utils.debug_mode import track_performance

@track_performance("process_netcdf")
def process_file(path):
    # Automatically logs execution time
    return process_netcdf(path)

# Or use context manager
from goesvfi.utils.enhanced_log import get_enhanced_logger
logger = get_enhanced_logger(__name__)

with logger.performance.measure("database_query", table="files"):
    results = query_database()
```

### Correlation IDs

```python
from goesvfi.utils.enhanced_log import correlation_context

# Automatic correlation across operations
with correlation_context() as correlation_id:
    logger.info(f"Starting batch job {correlation_id}")

    # All logs within this context share the correlation ID
    await download_files()
    process_files()
    upload_results()
```

## Integration Guide

### Minimal Integration

Replace existing logger initialization:

```python
# Old
from goesvfi.utils import log
LOGGER = log.get_logger(__name__)

# New (backward compatible)
from goesvfi.utils.logging_integration import LoggerAdapter
LOGGER = LoggerAdapter(__name__)
```

### Full Integration

```python
# At application startup
from goesvfi.utils.logging_integration import setup_enhanced_logging

setup_enhanced_logging(
    json_logs=args.json_logs,
    debug=args.debug,
    debug_components=["s3_store", "imagery"],
    debug_file=args.debug_file
)

# In modules
from goesvfi.utils.enhanced_log import get_enhanced_logger
from goesvfi.utils.operation_history import track_operation
from goesvfi.utils.debug_mode import track_performance

LOGGER = get_enhanced_logger(__name__)

@track_performance()
async def process_data():
    with track_operation("data_processing"):
        LOGGER.debug_verbose("processing", "Starting processing")
        # ... your code ...
```

### GUI Integration

The operation history viewer can be added to the main window:

```python
from goesvfi.utils.logging_integration import setup_gui_operation_history_tab

# In your main window initialization
if debug_mode:
    setup_gui_operation_history_tab(main_window)
```

## Features

### JSON Logging

When enabled, logs are output as structured JSON:

```json
{
  "timestamp": "2024-12-06T10:30:45.123Z",
  "level": "INFO",
  "logger": "goesvfi.integrity_check.s3_store",
  "message": "Download complete",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "extra": {
    "performance": {
      "operation": "s3_download",
      "elapsed_seconds": 1.234,
      "elapsed_ms": 1234
    }
  }
}
```

### Operation History Database

Operations are stored in SQLite with:
- Automatic metric aggregation
- Search and filtering
- Retention management
- Export capabilities

### Debug Reports

Generate comprehensive debug reports:

```python
from goesvfi.utils.debug_mode import get_debug_manager

report_path = get_debug_manager().create_debug_report()
```

## Examples

See the following examples:
- `/examples/debugging/test_enhanced_logging.py` - Comprehensive feature demo
- `/examples/debugging/test_s3_enhanced_logging.py` - S3Store integration example

## Performance Impact

The debugging features are designed to have minimal impact:
- Correlation IDs use thread-local storage
- Operation history uses efficient SQLite storage
- Performance tracking adds ~0.1ms overhead
- All features can be completely disabled in production

## Troubleshooting

### Debug mode not working
- Check environment variable: `echo $GOESVFI_DEBUG`
- Verify debug mode is enabled: `get_debug_manager().is_enabled()`
- Check component list if using filtered verbose logging

### Missing correlation IDs
- Correlation IDs are thread-local
- Use `correlation_context()` for automatic management
- For async code, IDs are preserved within the context

### Performance metrics missing
- Ensure `performance_tracking=True` in debug mode
- Check that decorators/context managers are properly applied
- Verify operations complete (metrics recorded on completion)
