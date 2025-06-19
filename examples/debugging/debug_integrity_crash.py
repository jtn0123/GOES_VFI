#!/usr/bin/env python3
"""
Debug script to diagnose crashes in the integrity check tab.

This script adds extra instrumentation and exception handlers to diagnose
issues with the integrity check tab in the GOES_VFI application.

Usage:
    pass
python debug_integrity_crash.py
"""

import logging
import os
import signal
import sys
import traceback
from datetime import datetime
from pathlib import Path

# Configure comprehensive logging
log_directory = Path(os.path.expanduser("~/.goes_vfi / logs"))
log_directory.mkdir(parents=True, exist_ok=True)

log_timestamp = datetime.now().strftime("%Y % m % d_ % H % M % S")
log_file = log_directory / f"integrity_debug_{log_timestamp}.log"

# Configure root logger
logging.basicConfig(
level=logging.DEBUG,
format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("integrity_debug")
logger.info(f"Starting debug session, logs will be written to {log_file}")


# Add exception hook to catch and log unhandled exceptions
def exception_handler(exc_type, exc_value, exc_traceback):
    pass
"""Handle uncaught exceptions and log them."""
if issubclass(exc_type, KeyboardInterrupt):
     pass
pass
# Let the default handler handle keyboard interrupts
sys.__excepthook__(exc_type, exc_value, exc_traceback)
return

logger.critical(
"Uncaught exception:", exc_info=(exc_type, exc_value, exc_traceback)
)
logger.critical(f"Exception type: {exc_type.__name__}")
logger.critical(f"Exception value: {exc_value}")

# Get the traceback as a string
tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
tb_text = "".join(tb_lines)
logger.critical(f"Traceback:\n{tb_text}")

# Log system info
import platform

logger.info(f"Python version: {sys.version}")
logger.info(f"Platform: {platform.platform()}")

# Print to stderr as well
print(f"CRITICAL ERROR: {exc_value}", file=sys.stderr)
print(f"See logs at {log_file}", file=sys.stderr)


# Install exception hook
sys.excepthook = exception_handler


# Handle SIGTERM gracefully
def handle_sigterm(signum, frame):
    pass
"""Handle SIGTERM signal."""
logger.info("Received SIGTERM signal, exiting gracefully")
sys.exit(0)


# Register signal handler
signal.signal(signal.SIGTERM, handle_sigterm)

# Patch PyQt to log all exceptions in slots
try:
    pass
from PyQt6.QtCore import QMetaObject

# Store the original QMetaObject.invokeMethod
original_invoke_method = QMetaObject.invokeMethod

# Define a wrapper that logs exceptions
def logging_invoke_method(obj, member, *args, **kwargs):
     pass
try:
     return original_invoke_method(obj, member, *args, **kwargs)
except Exception as e:
     pass
logger.error(f"Exception in Qt slot {member}: {e}")
logger.error(traceback.format_exc())
raise

# Patch QMetaObject.invokeMethod
QMetaObject.invokeMethod = logging_invoke_method

logger.info("PyQt6 slot exception logging enabled")
except ImportError:
    pass
logger.warning("PyQt6 not available, slot exception logging not enabled")


# Add detailed logging for S3Store and other critical classes
def patch_s3_store():
    pass
"""Patch S3Store with additional logging."""
try:
     from goesvfi.integrity_check.remote.s3_store import S3Store

# Store original methods we want to wrap
original_get_s3_client = S3Store._get_s3_client
original_exists = S3Store.exists
original_download = S3Store.download

# Wrap _get_s3_client with logging
async def logged_get_s3_client(self):
     """Wrapped version of _get_s3_client with extra logging."""
logger.debug(
f"S3Store._get_s3_client called, client exists: {self._s3_client is not None}"
)
try:
     # Show actual parameters being used
logger.debug(
f"AWS profile: {self.aws_profile}, region: {self.aws_region}"
)
logger.debug(f"Session kwargs: {self.session_kwargs}")

result = await original_get_s3_client(self)

logger.debug(
f"S3Store._get_s3_client succeeded, returning client: {result}"
)
if result is None:
     pass
logger.warning("S3 client is None after successful creation!")
return result
except Exception as e:
     pass
logger.error(f"Error in S3Store._get_s3_client: {e}")
logger.error(traceback.format_exc())
raise

# Wrap exists with logging
async def logged_exists(self, ts, satellite):
     """Wrapped version of exists with extra logging."""
logger.debug(
f"S3Store.exists called for {satellite.name} at {ts.isoformat()}"
)
try:
     bucket, key = self._get_bucket_and_key(ts, satellite, exact_match=True)
logger.debug(f"Checking existence of s3://{bucket}/{key}")

result = await original_exists(self, ts, satellite)

logger.debug(
f"S3Store.exists result for {satellite.name} at {ts.isoformat()}: {result}"
)
return result
except Exception as e:
     pass
logger.error(
f"Error in S3Store.exists for {satellite.name} at {ts.isoformat()}: {e}"
)
logger.error(traceback.format_exc())
raise

# Wrap download with logging
async def logged_download(self, ts, satellite, dest_path):
     """Wrapped version of download with extra logging."""
logger.debug(
f"S3Store.download called for {satellite.name} at {ts.isoformat()} to {dest_path}"
)
try:
     bucket, key = self._get_bucket_and_key(ts, satellite, exact_match=True)
logger.debug(f"Attempting to download s3://{bucket}/{key}")

result = await original_download(self, ts, satellite, dest_path)

logger.debug(
f"S3Store.download succeeded for {satellite.name} at {ts.isoformat()}"
)
return result
except Exception as e:
     pass
logger.error(
f"Error in S3Store.download for {satellite.name} at {ts.isoformat()}: {e}"
)
logger.error(traceback.format_exc())
raise

# Apply the patches
S3Store._get_s3_client = logged_get_s3_client
S3Store.exists = logged_exists
S3Store.download = logged_download

logger.info("S3Store methods successfully patched with logging")
except ImportError as e:
     pass
logger.error(f"Could not patch S3Store: {e}")


def patch_integrity_tab():
    """Patch integrity tab with additional logging."""
try:
     from goesvfi.integrity_check.enhanced_gui_tab import EnhancedIntegrityCheckTab

# Store original methods to wrap
original_browse_directory = EnhancedIntegrityCheckTab._browse_directory
original_start_scan = EnhancedIntegrityCheckTab._start_enhanced_scan

# Wrap _browse_directory with logging
def logged_browse_directory(self):
     """Wrapped version of _browse_directory with extra logging."""
logger.debug("EnhancedIntegrityCheckTab._browse_directory called")
try:
     current_dir = getattr(self.view_model, "base_directory", Path.home())
logger.debug(
f"Current directory: {current_dir}, exists: {current_dir.exists()}"
)

result = original_browse_directory(self)

new_dir = getattr(self.view_model, "base_directory", None)
logger.debug(f"Directory browsing completed, new directory: {new_dir}")
return result
except Exception as e:
     pass
logger.error(
f"Error in EnhancedIntegrityCheckTab._browse_directory: {e}"
)
logger.error(traceback.format_exc())
raise

# Wrap _start_enhanced_scan with logging
def logged_start_scan(self):
     """Wrapped version of _start_enhanced_scan with extra logging."""
logger.debug("EnhancedIntegrityCheckTab._start_enhanced_scan called")
try:
     params = {
"start_date": self.start_date_edit.dateTime().toPython(),
"end_date": self.end_date_edit.dateTime().toPython(),
"interval": self.interval_spinbox.value(),
"force_rescan": self.force_rescan_checkbox.isChecked(),
"auto_download": self.auto_download_checkbox.isChecked(),
}
logger.debug(f"Scan parameters: {params}")

# Check if view model is properly initialized
vm = self.view_model
logger.debug(f"ViewModel type: {type(vm).__name__}")

# Check for the required methods
has_start_scan = hasattr(vm, "start_enhanced_scan")
logger.debug(f"ViewModel has start_enhanced_scan: {has_start_scan}")

result = original_start_scan(self)

logger.debug("Enhanced scan started successfully")
return result
except Exception as e:
     pass
logger.error(
f"Error in EnhancedIntegrityCheckTab._start_enhanced_scan: {e}"
)
logger.error(traceback.format_exc())
raise

# Apply the patches
EnhancedIntegrityCheckTab._browse_directory = logged_browse_directory
EnhancedIntegrityCheckTab._start_enhanced_scan = logged_start_scan

logger.info(
"EnhancedIntegrityCheckTab methods successfully patched with logging"
)
except ImportError as e:
     pass
logger.error(f"Could not patch EnhancedIntegrityCheckTab: {e}")


def main():
    """Main function to run the application with extra instrumentation."""
logger.info("Starting GOES_VFI with enhanced debugging")

# Apply patches
patch_s3_store()
patch_integrity_tab()

# Add debug info about boto3 and aioboto3
try:
     import boto3
import botocore

logger.info(f"boto3 version: {boto3.__version__}")
logger.info(f"botocore version: {botocore.__version__}")

try:
     import aioboto3

logger.info(f"aioboto3 version: {aioboto3.__version__}")
except ImportError:
     pass
logger.warning("aioboto3 not available")

# Check AWS configuration
session = boto3.Session()
profiles = session.available_profiles
logger.info(f"Available AWS profiles: {profiles}")

# Import the main GOES_VFI module
import goesvfi

logger.info(f"goesvfi version: {getattr(goesvfi, '__version__', 'unknown')}")
except ImportError as e:
     pass
logger.warning(f"Could not import boto3 or goesvfi: {e}")

try:
     # Start the application with debug flag
from goesvfi.gui import main

logger.info("Starting GOES_VFI GUI...")
sys.argv = [sys.argv[0], "--debug"] # Add debug flag
main()
except Exception as e:
     pass
logger.critical(f"Failed to start GOES_VFI: {e}")
logger.critical(traceback.format_exc())
sys.exit(1)


if __name__ == "__main__":
    pass
main()
