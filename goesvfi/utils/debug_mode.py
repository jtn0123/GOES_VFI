"""Debug mode handler with enhanced verbose output and diagnostics."""

from __future__ import annotations

import os
import sys
import time
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from goesvfi.utils import config

get_correlation_id,
get_enhanced_logger,
setup_json_logging,
)
from goesvfi.utils.operation_history import get_operation_store, track_operation

LOGGER = get_enhanced_logger(__name__)

class DebugModeManager:
    """Manages debug mode settings and enhanced diagnostics."""

    def __init__(self):
        self._debug_mode = False
        self._json_logging = False
        self._verbose_components: set[str] = set()
        self._performance_tracking = False
        self._operation_tracking = False
        self._debug_file: Optional[Path] = None
        self._callbacks: List[Callable[[bool], None]] = []

        # Check environment variable
        if os.environ.get("GOESVFI_DEBUG", "").lower() in ("1", "true", "yes"):
            pass
            self.enable()

    def enable(self,
    components: Optional[List[str]] = None,
    json_logging: bool = False,
    performance_tracking: bool = True,
    operation_tracking: bool = True,
    debug_file: Optional[Path] = None,
    ) -> None:
        """Enable debug mode with specified options.

        Args:
            pass
            components: List of components to enable verbose logging for
            json_logging: Enable structured JSON logging
            performance_tracking: Enable performance metrics
            operation_tracking: Enable operation history tracking
            debug_file: Path to write debug logs to file
        """
        self._debug_mode = True  # pylint: disable=attribute-defined-outside-init
        self._json_logging = json_logging  # pylint: disable=attribute-defined-outside-init
        self._performance_tracking = performance_tracking  # pylint: disable=attribute-defined-outside-init
        self._operation_tracking = operation_tracking  # pylint: disable=attribute-defined-outside-init
        self._debug_file = debug_file  # pylint: disable=attribute-defined-outside-init

        if components:
            pass
            self._verbose_components.update(components)

        # Set up JSON logging if requested
        if json_logging:
            pass
            setup_json_logging()

        # Create debug file handler if specified
        if debug_file:
            pass
            self._setup_debug_file(debug_file)

        # Log the configuration
        with ()
        track_operation("debug_mode_enable")
        if operation_tracking
        else nullcontext()
        ):
            pass
            LOGGER.info()
            "Debug mode enabled",
            extra={
            "debug_config": {
            "components": list(self._verbose_components),
            "json_logging": json_logging,
            "performance_tracking": performance_tracking,
            "operation_tracking": operation_tracking,
            "debug_file": str(debug_file) if debug_file else None,
            }
            },
            )

        # Notify callbacks
        for callback in self._callbacks:
            pass
            try:
                callback(True)
            except Exception as e:
                pass
                LOGGER.exception("Error in debug mode callback: %s", e)

    def disable(self) -> None:
        """Disable debug mode."""
        self._debug_mode = False  # pylint: disable=attribute-defined-outside-init
        self._verbose_components.clear()

        LOGGER.info("Debug mode disabled")

        # Notify callbacks
        for callback in self._callbacks:
            pass
            try:
                callback(False)
            except Exception as e:
                pass
                LOGGER.exception("Error in debug mode callback: %s", e)

    def _setup_debug_file(self, debug_file: Path) -> None:
        """Set up file handler for debug logs."""
        import logging
        from logging.handlers import RotatingFileHandler

        # Create directory if needed
        debug_file.parent.mkdir(parents=True, exist_ok=True)

        # Create rotating file handler
        file_handler = RotatingFileHandler()
        str(debug_file), maxBytes=10 * 1024 * 1024, backupCount=5  # 10MB
        )

        # Set formatter based on JSON setting
        if self._json_logging:
            pass
            from goesvfi.utils.enhanced_log import StructuredJSONFormatter

            file_handler.setFormatter(StructuredJSONFormatter())
        else:
            file_handler.setFormatter()
            logging.Formatter()
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            )

        # Add to root logger
        logging.getLogger().addHandler(file_handler)

    def is_enabled(self) -> bool:
        """Check if debug mode is enabled."""
        return self._debug_mode

    def is_component_verbose(self, component: str) -> bool:
        """Check if verbose logging is enabled for a component."""
        return self._debug_mode and ()
        not self._verbose_components or component in self._verbose_components
        )

    def add_callback(self, callback: Callable[[bool], None]) -> None:
        """Add a callback to be notified when debug mode changes."""
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[bool], None]) -> None:
        """Remove a debug mode callback."""
        if callback in self._callbacks:
            pass
            self._callbacks.remove(callback)

    def log_verbose(self, component: str, message: str, **extra: Any) -> None:
        """Log a verbose debug message for a component."""
        if self.is_component_verbose(component):
            pass
            LOGGER.debug("[%s] %s", component, message, extra={"component": component, **extra})
            )

    def log_performance(self, operation: str, elapsed: float, **extra: Any) -> None:
        """Log performance metric."""
        if self._performance_tracking:
            pass
            LOGGER.info("Performance: %s", operation,)
            extra={
            "performance": {
            "operation": operation,
            "elapsed_seconds": elapsed,
            "elapsed_ms": elapsed * 1000,
            **extra,
            }
            },
            )

    def get_debug_info(self) -> Dict[str, Any]:
        """Get current debug configuration and statistics."""
        info = {
        "enabled": self._debug_mode,
        "json_logging": self._json_logging,
        "performance_tracking": self._performance_tracking,
        "operation_tracking": self._operation_tracking,
        "verbose_components": list(self._verbose_components),
        "debug_file": str(self._debug_file) if self._debug_file else None,
        "current_correlation_id": get_correlation_id(),
        }

        # Add operation statistics if tracking
        if self._operation_tracking:
            pass
            try:
                store = get_operation_store()
                metrics = store.get_operation_metrics()
                info["operation_metrics"] = {
                m["operation_name"]: {
                "total": m["total_count"],
                "success": m["success_count"],
                "failure": m["failure_count"],
                "avg_duration": m["avg_duration"],
                }
                for m in metrics[:10]  # Top 10 operations
                }
            except Exception as e:
                pass
                info["operation_metrics_error"] = str(e)

        return info

    def create_debug_report(self, output_path: Optional[Path] = None) -> Path:
        """Create a comprehensive debug report."""
        if output_path is None:
            pass
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            output_path = Path(config.get_cache_dir()) / f"debug_report_{timestamp}.txt"

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            f.write("GOES VFI Debug Report\n")
            f.write("=" * 50 + "\n\n")

            # System info
            f.write("System Information:\n")
            f.write(f"  Python version: {sys.version}\n")
            f.write(f"  Platform: {sys.platform}\n")
            f.write(f"  Current time: {datetime.now(UTC).isoformat()}\n\n")

            # Debug configuration
            f.write("Debug Configuration:\n")
            debug_info = self.get_debug_info()
            for key, value in debug_info.items():
                if key != "operation_metrics":
                    pass
                    f.write(f"  {key}: {value}\n")
            f.write("\n")

            # Operation metrics
            if "operation_metrics" in debug_info:
                pass
                f.write("Top Operation Metrics:\n")
                for op_name, metrics in debug_info["operation_metrics"].items():
                    f.write(f"  {op_name}:\n")
                    for metric, value in metrics.items():
                        f.write(f"    {metric}: {value}\n")
                f.write("\n")

            # Recent operations
            if self._operation_tracking:
                pass
                f.write("Recent Operations:\n")
                try:
                    store = get_operation_store()
                    recent_ops = store.get_recent_operations(limit=20)
                    for op in recent_ops:
                        f.write(f"  - {op['name']} ({op['status']}): ")
                        f.write(f"{op.get('duration', 'N/A')}s\n")
                except Exception as e:
                    pass
                    f.write(f"  Error loading operations: {e}\n")
                f.write("\n")

            # Configuration
            f.write("Application Configuration:\n")
            f.write(f"  Cache directory: {config.get_cache_dir()}\n")
            f.write(f"  Logging level: {config.get_logging_level()}\n")
            f.write(f"  Worker count: {config.get_worker_count()}\n")
            f.write("\n")

        LOGGER.info("Debug report created: %s", output_path)
        return output_path

# Global debug mode manager
_debug_manager = DebugModeManager()

# Context manager helper

# Public API
def enable_debug_mode(**kwargs) -> None:
    """Enable debug mode with specified options."""
    _debug_manager.enable(**kwargs)

def disable_debug_mode() -> None:
    pass
    """Disable debug mode."""
    _debug_manager.disable()

def is_debug_mode() -> bool:
    """Check if debug mode is enabled."""
    return _debug_manager.is_enabled()

def debug_log(component: str, message: str, **extra: Any) -> None:
    """Log a verbose debug message for a component."""
    _debug_manager.log_verbose(component, message, **extra)

def get_debug_manager() -> DebugModeManager:
    """Get the global debug mode manager."""
    return _debug_manager

# Decorator for debug-only functions
def debug_only(func: Callable) -> Callable:
    """Decorator to run function only in debug mode."""

    def wrapper(*args, **kwargs):
        if is_debug_mode():
            pass
            return func(*args, **kwargs)
        return None

    return wrapper

# Decorator for performance tracking
def track_performance(operation_name: Optional[str] = None):
    """Decorator to track function performance."""

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            name = operation_name or f"{func.__module__}.{func.__name__}"

            if _debug_manager._performance_tracking:
                pass
                start_time = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    elapsed = time.perf_counter() - start_time
                    _debug_manager.log_performance(name, elapsed)
                    return result
                except Exception as e:
                    pass
                    elapsed = time.perf_counter() - start_time
                    _debug_manager.log_performance(name, elapsed, error=str(e))
                    raise
            else:
                return func(*args, **kwargs)

        return wrapper

    return decorator
