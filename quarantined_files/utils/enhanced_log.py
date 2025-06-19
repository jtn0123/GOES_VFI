"""Enhanced logging utilities with structured JSON logging, correlation IDs, and performance metrics."""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from threading import Lock, local
from typing import Any, Dict, Iterator, List, Optional

from goesvfi.utils import config, log

# Thread-local storage for correlation IDs
_thread_local = local()
_correlation_lock = Lock()

class StructuredJSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON."""
        # Build the basic log structure
        log_data = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": record.levelname,
        "logger": record.name,
        "message": record.getMessage(),
        "module": record.module,
        "function": record.funcName,
        "line": record.lineno,
        "thread": record.thread,
        "thread_name": record.threadName,
        "process": record.process,
        }

        # Add correlation ID if available
        correlation_id = getattr(_thread_local, "correlation_id", None)
        if correlation_id:
            pass
            log_data["correlation_id"] = correlation_id

        # Add exception info if present
        if record.exc_info:
            pass
    pass
    log_data["exception"] = self.formatException(record.exc_info)

    # Add any extra fields from the record
    extra_fields = {
    k: v
    for k, v in record.__dict__.items()
    if k not in logging.LogRecord.__dict__ and not k.startswith("_")
    }
    if extra_fields:
            pass
            log_data["extra"] = extra_fields

    return json.dumps(log_data, default=str)

class PerformanceLogger:
    """Tracks and logs performance metrics."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.metrics: Dict[str, List[float]] = {}
        self._lock = Lock()

    @contextmanager
    def measure(self, operation: str, **extra: Any) -> Iterator[None]:
        """Context manager to measure operation timing."""
        start_time = time.perf_counter()

        try:
            yield
        finally:
            elapsed = time.perf_counter() - start_time

            # Store metric
            with self._lock:
                if operation not in self.metrics:
                    pass
                    self.metrics[operation] = []
                self.metrics[operation].append(elapsed)

            # Log the timing
            self.logger.info(
                "Performance metric: %s",
                operation,
                extra={
                    "performance": {
                        "operation": operation,
                        "elapsed_seconds": elapsed,
                        "elapsed_ms": elapsed * 1000,
                        **extra,
                    }
                },
            )

    def get_stats(self, operation: str) -> Dict[str, float]:
        """Get statistics for a specific operation."""
        with self._lock:
            pass
            timings = self.metrics.get(operation, [])
            if not timings:
                pass
                return {}

            return {
            "count": len(timings),
            "total": sum(timings),
            "min": min(timings),
            "max": max(timings),
            "avg": sum(timings) / len(timings),
            }

    def log_summary(self) -> None:
        """Log a summary of all performance metrics."""
        with self._lock:
            for operation, _timings in self.metrics.items():
                stats = self.get_stats(operation)
                self.logger.info("Performance summary: %s", operation,)
                extra={"performance_summary": {"operation": operation, **stats}},
                )

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self.metrics.clear()

class DebugLogger:
    """Enhanced logger with debug mode capabilities."""

    def __init__(self, name: Optional[str] = None):
        self.logger = log.get_logger(name)
        self.performance = PerformanceLogger(self.logger)
        self._debug_mode = False
        self._verbose_components: set[str] = set()

    def enable_debug_mode(self, components: Optional[List[str]] = None) -> None:
        """Enable debug mode with optional component filtering."""
        self._debug_mode = True
        if components:
            pass
            self._verbose_components.update(components)
        self.logger.info()
        "Debug mode enabled",
        extra={
        "debug_mode": True,
        "verbose_components": list(self._verbose_components),
        },
        )

    def disable_debug_mode(self) -> None:
        """Disable debug mode."""
        self._debug_mode = False  # pylint: disable=attribute-defined-outside-init
        self._verbose_components.clear()
        self.logger.info("Debug mode disabled")

    def debug_verbose(self, component: str, message: str, **extra: Any) -> None:
        """Log verbose debug message for specific component."""
        if self._debug_mode and ()
        not self._verbose_components or component in self._verbose_components
        ):
            pass
            self.logger.debug("[%s] %s", component, message, extra={"component": component, **extra})
            )

    def __getattr__(self, name: str) -> Any:
        """Forward other logging methods to the underlying logger."""
        return getattr(self.logger, name)

# Correlation ID management
def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """Set a correlation ID for the current thread."""
    if correlation_id is None:
        pass
        correlation_id = str(uuid.uuid4())

    with _correlation_lock:
        _thread_local.correlation_id = correlation_id

    return correlation_id

def get_correlation_id() -> Optional[str]:
    """Get the current thread's correlation ID."""
    return getattr(_thread_local, "correlation_id", None)

def clear_correlation_id() -> None:
    """Clear the current thread's correlation ID."""
    with _correlation_lock:
        if hasattr(_thread_local, "correlation_id"):
            pass
            delattr(_thread_local, "correlation_id")

@contextmanager
def correlation_context(correlation_id: Optional[str] = None) -> Iterator[str]:
    """Context manager for correlation IDs."""
    old_id = get_correlation_id()
    new_id = set_correlation_id(correlation_id)

    try:
        yield new_id
    finally:
        if old_id:
            pass
            set_correlation_id(old_id)
        else:
            clear_correlation_id()

# Enhanced logger factory
def get_enhanced_logger(name: Optional[str] = None, use_json: bool = False
) -> DebugLogger:
    """Get an enhanced logger instance with optional JSON formatting."""
    logger = DebugLogger(name)

    if use_json:
        pass
        # Configure JSON formatting for this logger
        json_handler = logging.StreamHandler(sys.stdout)
        json_handler.setFormatter(StructuredJSONFormatter())

        # Get the actual logger and add the JSON handler
        actual_logger = logger.logger
        actual_logger.handlers = []  # Clear existing handlers
        actual_logger.addHandler(json_handler)
        actual_logger.propagate = False  # Don't propagate to root logger

    return logger

# Operation tracking
class Operation:
    """Represents a tracked operation with timing and metadata."""

    def __init__(self, name: str, correlation_id: str, start_time: float):
        self.name = name
        self.correlation_id = correlation_id
        self.start_time = start_time
        self.end_time: Optional[float] = None
        self.status: str = "in_progress"
        self.error: Optional[str] = None
        self.metadata: Dict[str, Any] = {}

    def complete(self, status: str = "success", error: Optional[str] = None) -> None:
        """Mark the operation as complete."""
        self.end_time = time.perf_counter()
        self.status = status
        self.error = error

    @property
    def duration(self) -> Optional[float]:
        """Get the operation duration in seconds."""
        if self.end_time:
            pass
            return self.end_time - self.start_time
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
        "name": self.name,
        "correlation_id": self.correlation_id,
        "start_time": self.start_time,
        "end_time": self.end_time,
        "duration": self.duration,
        "status": self.status,
        "error": self.error,
        "metadata": self.metadata,
        }

# Export convenience functions
def setup_json_logging(root_logger: bool = True) -> None:
    """Set up JSON logging for the application."""
    if root_logger:
        pass
        # Configure the root logger with JSON formatting
        root = logging.getLogger()
        root.handlers = []

        json_handler = logging.StreamHandler(sys.stdout)
        json_handler.setFormatter(StructuredJSONFormatter())
        root.addHandler(json_handler)

        # Set level from config
        level_name = config.get_logging_level().upper()
        level = getattr(logging, level_name, logging.INFO)
        root.setLevel(level)
