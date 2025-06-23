#!/usr/bin/env python3
"""
Debug script for troubleshooting Integrity Check tab crashes.

This script adds extensive logging and error tracking to help identify
the source of crashes in the Integrity Check tab.
"""

import asyncio
import logging
import signal
import sys
import traceback
from pathlib import Path

# Add the repository root to the Python path
repo_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, repo_root)

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("integrity_crash_debug.log"),
    ],
)

# Enable asyncio debug mode
asyncio.set_event_loop_policy(
    asyncio.WindowsSelectorEventLoopPolicy()
    if sys.platform == "win32"
    else asyncio.DefaultEventLoopPolicy()
)

# Get root logger
logger = logging.getLogger()

# Add special handling for Qt messages
try:
    from PyQt6.QtCore import QtMsgType, qInstallMessageHandler

    def qt_message_handler(msg_type, context, msg):
        """Handle Qt messages with proper logging."""
        if msg_type == QtMsgType.QtDebugMsg:
            logger.debug(f"Qt Debug: {msg}")
        elif msg_type == QtMsgType.QtInfoMsg:
            logger.info(f"Qt Info: {msg}")
        elif msg_type == QtMsgType.QtWarningMsg:
            logger.warning(f"Qt Warning: {msg}")
        elif msg_type == QtMsgType.QtCriticalMsg:
            logger.error(f"Qt Critical: {msg}")
        elif msg_type == QtMsgType.QtFatalMsg:
            logger.critical(f"Qt Fatal: {msg}")
            # For fatal messages, also print the stack trace
            logger.critical(traceback.format_exc())

    qInstallMessageHandler(qt_message_handler)
    logger.info("Qt message handler installed")
except ImportError:
    logger.warning("PyQt6 not available, Qt message handler not installed")


# Exception hook to catch unhandled exceptions
def exception_hook(exctype, value, tb):
    """Log unhandled exceptions before the default handler."""
    logger.critical("Unhandled exception:", exc_info=(exctype, value, tb))
    # Call the default handler
    sys.__excepthook__(exctype, value, tb)


sys.excepthook = exception_hook


# Add a custom signal handler for debugging
def handle_sigterm(signum, frame):
    """Handle SIGTERM signal gracefully."""
    logger.info("Received SIGTERM signal, exiting gracefully")
    sys.exit(0)


# Register signal handler
signal.signal(signal.SIGTERM, handle_sigterm)

# Patch PyQt to log all exceptions in slots
try:
    from PyQt6.QtCore import QMetaObject

    # Store the original QMetaObject.invokeMethod
    original_invoke_method = QMetaObject.invokeMethod

    # Define a wrapper that logs exceptions
    def logging_invoke_method(obj, member, *args, **kwargs):
        try:
            return original_invoke_method(obj, member, *args, **kwargs)
        except Exception as e:
            logger.error(f"Exception in Qt slot {member}: {e}")
            logger.error(traceback.format_exc())
            raise

    # Patch QMetaObject.invokeMethod
    QMetaObject.invokeMethod = logging_invoke_method

    logger.info("PyQt6 slot exception logging enabled")
except ImportError:
    logger.warning("PyQt6 not available, slot exception logging not enabled")


# Add detailed logging for S3Store and other critical classes
def patch_s3_store():
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
                    logger.warning("S3 client is None after successful creation!")
                return result
            except Exception as e:
                logger.error(f"Error in S3Store._get_s3_client: {e}")
                logger.error(traceback.format_exc())
                raise

        # Wrap exists with logging
        async def logged_exists(self, ts, satellite):
            """Wrapped version of exists with extra logging."""
            logger.debug(f"S3Store.exists called with ts={ts}, satellite={satellite}")
            try:
                result = await original_exists(self, ts, satellite)
                logger.debug(f"S3Store.exists returned {result}")
                return result
            except Exception as e:
                logger.error(f"Error in S3Store.exists: {e}")
                logger.error(traceback.format_exc())
                raise

        # Wrap download with logging
        async def logged_download(
            self, ts, satellite, dest_path, progress_callback=None
        ):
            """Wrapped version of download with extra logging."""
            logger.debug(
                f"S3Store.download called with ts={ts}, satellite={satellite}, dest={dest_path}"
            )
            try:
                result = await original_download(
                    self, ts, satellite, dest_path, progress_callback
                )
                logger.debug(f"S3Store.download succeeded, downloaded to {dest_path}")
                return result
            except Exception as e:
                logger.error(f"Error in S3Store.download: {e}")
                logger.error(traceback.format_exc())
                raise

        # Apply patches
        S3Store._get_s3_client = logged_get_s3_client
        S3Store.exists = logged_exists
        S3Store.download = logged_download

        logger.info("S3Store methods patched with extra logging")

    except ImportError:
        logger.warning("S3Store not available, patching skipped")


# Apply S3Store patches
patch_s3_store()


# Main entry point
def main():
    """Run the main application with debugging enabled."""
    logger.info("=" * 80)
    logger.info("Starting GOES-VFI with Integrity Check debugging")
    logger.info("=" * 80)

    try:
        # Import the main application
        from goesvfi.gui import main as gui_main

        # Add extra logging for the integrity tab
        from goesvfi.integrity_check.gui_tab import IntegrityCheckTab

        original_init = IntegrityCheckTab.__init__

        def logged_init(self, *args, **kwargs):
            """Wrapped IntegrityCheckTab.__init__ with logging."""
            logger.info("IntegrityCheckTab.__init__ called")
            logger.debug(f"Args: {args}")
            logger.debug(f"Kwargs: {kwargs}")
            try:
                result = original_init(self, *args, **kwargs)
                logger.info("IntegrityCheckTab.__init__ completed successfully")
                return result
            except Exception as e:
                logger.error(f"Error in IntegrityCheckTab.__init__: {e}")
                logger.error(traceback.format_exc())
                raise

        IntegrityCheckTab.__init__ = logged_init

        # Run the application
        logger.info("Launching GUI application...")
        gui_main()

    except Exception as e:
        logger.critical(f"Fatal error in main: {e}")
        logger.critical(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
