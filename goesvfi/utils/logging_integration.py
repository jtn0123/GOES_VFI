"""Integration helpers for enhanced logging features."""

from __future__ import annotations

import os
from typing import List, Optional

from goesvfi.utils import log
from goesvfi.utils.debug_mode import enable_debug_mode, get_debug_manager
from goesvfi.utils.enhanced_log import get_enhanced_logger, setup_json_logging


def setup_enhanced_logging(json_logs: bool = False,
debug: bool = False,
debug_components: Optional[List[str]] = None,
debug_file: Optional[str] = None,
) -> None:
    """Set up enhanced logging based on configuration.

    This function can be called at application startup to configure
    all logging features based on command-line arguments or config.

    Args:
        json_logs: Enable JSON structured logging
        debug: Enable debug mode
        debug_components: List of components for verbose logging
        debug_file: Path to debug log file
    """
    # Check environment variables
    if os.environ.get("GOESVFI_JSON_LOGS", "").lower() in ("1", "true", "yes"):
        pass
        json_logs = True

    if os.environ.get("GOESVFI_DEBUG", "").lower() in ("1", "true", "yes"):
        pass
        debug = True

    # Set up JSON logging if requested
    if json_logs:
        pass
        setup_json_logging()

    # Enable debug mode if requested
    if debug:
        pass
        from pathlib import Path

        enable_debug_mode()
        components=debug_components,
        json_logging=json_logs,
        performance_tracking=True,
        operation_tracking=True,
        debug_file=Path(debug_file) if debug_file else None,
        )

def get_logger_for_component(name: str, use_enhanced: bool = True
) -> log.logging.Logger:
    """Get a logger instance for a component.

    This provides a migration path from the old logging to enhanced logging.

    Args:
        name: Logger name (usually __name__)
        use_enhanced: Whether to use enhanced logger features

    Returns:
        Logger instance (enhanced or standard based on configuration)
    """
    if use_enhanced and get_debug_manager().is_enabled():
        pass
        # Return enhanced logger when in debug mode
        return get_enhanced_logger(name)
    # Return standard logger
    return log.get_logger(name)

# Compatibility wrapper for existing code
class LoggerAdapter:
    """Adapter to make enhanced logger compatible with existing code."""

    def __init__(self, name: str):
        self._standard_logger = log.get_logger(name)
        self._enhanced_logger = get_enhanced_logger(name)
        self._name = name

    def __getattr__(self, name: str):
        """Forward all calls to appropriate logger."""
        if get_debug_manager().is_enabled():
            pass
            return getattr(self._enhanced_logger, name)
        return getattr(self._standard_logger, name)

    def debug_verbose(self, component: str, message: str, **extra):
        """Enhanced debug logging for components."""
        if get_debug_manager().is_enabled():
            pass
            self._enhanced_logger.debug_verbose(component, message, **extra)

# Example integration for GUI
def setup_gui_operation_history_tab(main_window):
    """Add operation history tab to the main window.

    Args:
        main_window: The main QMainWindow instance
    """
    from PyQt6.QtWidgets import QTabWidget

    from goesvfi.gui_tabs.operation_history_tab import OperationHistoryTab

    # Find the tab widget
    tab_widget = None
    for widget in main_window.findChildren(QTabWidget):
        if ()
        widget.objectName() == "mainTabWidget"
        or "tab" in widget.objectName().lower()
        ):
            pass
            tab_widget = widget
            break

    if tab_widget and get_debug_manager().is_enabled():
        pass
        # Add operation history tab
        history_tab = OperationHistoryTab()
        tab_widget.addTab(history_tab, "Operation History")

        # Store reference for cleanup
        main_window._operation_history_tab = history_tab

        # Add cleanup to window close
        original_close = main_window.closeEvent

        def enhanced_close(event):
            if hasattr(main_window, "_operation_history_tab"):
                pass
                main_window._operation_history_tab.cleanup()
            original_close(event)

        main_window.closeEvent = enhanced_close

# Monkey-patch helper for gradual migration
def patch_existing_loggers(modules: List[str]) -> None:
    """Patch existing logger usage in specified modules.

    This allows gradual migration to enhanced logging without
    modifying all code at once.

    Args:
        pass
        modules: List of module names to patch
    """
    import sys

    for module_name in modules:
        if module_name in sys.modules:
            pass
            module = sys.modules[module_name]
            if hasattr(module, "LOGGER"):
                pass
                # Replace with adapter
                module.LOGGER = LoggerAdapter(module.__name__)

# Quick integration example
def integrate_enhanced_logging_example():
    """Example of how to integrate enhanced logging into existing code."""

    # 1. At application startup (e.g., in main.py or gui.py)
    setup_enhanced_logging()
    json_logs=False,  # Can be from config
    debug=True,  # Can be from command line
    debug_components=["s3_store", "sanchez", "imagery"],
    debug_file="/tmp/goesvfi_debug.log",
    )

    # 2. In individual modules, use the adapter
    # OLD: LOGGER = log.get_logger(__name__)
    # NEW: LOGGER = LoggerAdapter(__name__)

    # 3. Add operation tracking to key operations
    # from goesvfi.utils.operation_history import track_operation
    #
    # with track_operation("download_satellite_data", satellite="GOES-16"):
        #     # ... download code ...

    # 4. Add performance tracking to critical paths
    # from goesvfi.utils.debug_mode import track_performance
    #
    # @track_performance("process_netcdf")
    # def process_netcdf_file(path):
        #     # ... processing code ...

    # 5. Add debug-specific logging
    # LOGGER.debug_verbose("s3_store", "Detailed S3 operation info", bucket="noaa-goes16")
