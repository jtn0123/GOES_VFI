"""Widget pooling system for reusable GUI components.

This module provides efficient widget reuse to reduce memory allocation overhead
and improve performance for frequently created/destroyed widgets.
"""

from collections.abc import Callable
from typing import TypeVar, Generic

from PyQt6.QtWidgets import QWidget

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)

T = TypeVar("T", bound=QWidget)


class WidgetPool(Generic[T]):
    """Manages a pool of reusable widgets to reduce allocation overhead."""

    def __init__(
        self,
        widget_type: type[T],
        factory: Callable[[], T],
        max_size: int = 10,
        cleanup_func: Callable[[T], None] | None = None,
    ) -> None:
        """Initialize widget pool.

        Args:
            widget_type: Type of widget to pool
            factory: Function to create new widget instances
            max_size: Maximum number of widgets to keep in pool
            cleanup_func: Optional function to reset widget state
        """
        self.widget_type = widget_type
        self.factory = factory
        self.max_size = max_size
        self.cleanup_func = cleanup_func
        self.pool: list[T] = []
        self.allocated: dict[int, T] = {}  # Track allocated widgets by id

    def acquire(self) -> T:
        """Get a widget from the pool or create a new one.

        Returns:
            Widget instance ready for use
        """
        if self.pool:
            widget = self.pool.pop()
            LOGGER.debug(f"Acquired {self.widget_type.__name__} from pool (remaining: {len(self.pool)})")
        else:
            widget = self.factory()
            LOGGER.debug(f"Created new {self.widget_type.__name__} (pool empty)")

        # Track allocated widget
        self.allocated[id(widget)] = widget
        return widget

    def release(self, widget: T) -> None:
        """Return a widget to the pool for reuse.

        Args:
            widget: Widget to return to pool
        """
        widget_id = id(widget)
        if widget_id not in self.allocated:
            LOGGER.warning(f"Attempted to release untracked {self.widget_type.__name__}")
            return

        # Remove from allocated tracking
        del self.allocated[widget_id]

        # Clean up widget state if cleanup function provided
        if self.cleanup_func:
            try:
                self.cleanup_func(widget)
            except Exception:
                LOGGER.exception(f"Error cleaning up {self.widget_type.__name__}")
                # Don't return problematic widget to pool
                widget.deleteLater()
                return

        # Return to pool if there's space
        if len(self.pool) < self.max_size:
            self.pool.append(widget)
            LOGGER.debug(f"Returned {self.widget_type.__name__} to pool (size: {len(self.pool)})")
        else:
            # Pool is full, delete the widget
            widget.deleteLater()
            LOGGER.debug(f"Pool full, deleted {self.widget_type.__name__}")

    def clear(self) -> None:
        """Clear all widgets from the pool."""
        for widget in self.pool:
            widget.deleteLater()
        self.pool.clear()

        # Clean up any remaining allocated widgets
        for widget in self.allocated.values():
            widget.deleteLater()
        self.allocated.clear()

        LOGGER.info(f"Cleared {self.widget_type.__name__} pool")

    def stats(self) -> dict[str, int]:
        """Get pool statistics.

        Returns:
            Dictionary with pool statistics
        """
        return {
            "pool_size": len(self.pool),
            "allocated_count": len(self.allocated),
            "max_size": self.max_size,
        }


class WidgetPoolManager:
    """Global manager for all widget pools."""

    def __init__(self) -> None:
        """Initialize the widget pool manager."""
        self.pools: dict[str, WidgetPool[QWidget]] = {}

    def register_pool(
        self,
        name: str,
        widget_type: type[T],
        factory: Callable[[], T],
        max_size: int = 10,
        cleanup_func: Callable[[T], None] | None = None,
    ) -> None:
        """Register a new widget pool.

        Args:
            name: Unique name for the pool
            widget_type: Type of widget to pool
            factory: Function to create new widgets
            max_size: Maximum pool size
            cleanup_func: Optional cleanup function
        """
        if name in self.pools:
            LOGGER.warning(f"Pool '{name}' already registered, replacing")

        # Type ignore due to complex generic constraints between T and QWidget
        pool: WidgetPool[QWidget] = WidgetPool(widget_type, factory, max_size, cleanup_func)  # type: ignore[arg-type]
        self.pools[name] = pool
        LOGGER.info(f"Registered widget pool '{name}' for {widget_type.__name__}")

    def acquire(self, pool_name: str) -> QWidget | None:
        """Acquire a widget from the specified pool.

        Args:
            pool_name: Name of the pool to acquire from

        Returns:
            Widget instance or None if pool doesn't exist
        """
        if pool_name not in self.pools:
            LOGGER.error(f"Pool '{pool_name}' not found")
            return None

        widget = self.pools[pool_name].acquire()
        return widget

    def release(self, pool_name: str, widget: QWidget) -> None:
        """Release a widget back to the specified pool.

        Args:
            pool_name: Name of the pool to release to
            widget: Widget to release
        """
        if pool_name not in self.pools:
            LOGGER.error(f"Pool '{pool_name}' not found")
            widget.deleteLater()
            return

        self.pools[pool_name].release(widget)

    def clear_all(self) -> None:
        """Clear all widget pools."""
        for pool in self.pools.values():
            pool.clear()
        self.pools.clear()
        LOGGER.info("Cleared all widget pools")

    def get_stats(self) -> dict[str, dict[str, int]]:
        """Get statistics for all pools.

        Returns:
            Dictionary mapping pool names to their statistics
        """
        return {name: pool.stats() for name, pool in self.pools.items()}


# Global widget pool manager instance
_pool_manager: WidgetPoolManager | None = None


def get_pool_manager() -> WidgetPoolManager:
    """Get the global widget pool manager instance."""
    global _pool_manager
    if _pool_manager is None:
        _pool_manager = WidgetPoolManager()
    return _pool_manager


def register_widget_pool(
    name: str,
    widget_type: type[T],
    factory: Callable[[], T],
    max_size: int = 10,
    cleanup_func: Callable[[T], None] | None = None,
) -> None:
    """Convenience function to register a widget pool.

    Args:
        name: Unique name for the pool
        widget_type: Type of widget to pool
        factory: Function to create new widgets
        max_size: Maximum pool size
        cleanup_func: Optional cleanup function
    """
    get_pool_manager().register_pool(name, widget_type, factory, max_size, cleanup_func)


def acquire_widget(pool_name: str) -> QWidget | None:
    """Convenience function to acquire a widget from a pool.

    Args:
        pool_name: Name of the pool to acquire from

    Returns:
        Widget instance or None if pool doesn't exist
    """
    return get_pool_manager().acquire(pool_name)


def release_widget(pool_name: str, widget: QWidget) -> None:
    """Convenience function to release a widget to a pool.

    Args:
        pool_name: Name of the pool to release to
        widget: Widget to release
    """
    get_pool_manager().release(pool_name, widget)


# Common widget cleanup functions
def cleanup_label(label) -> None:
    """Clean up a QLabel for reuse."""
    from PyQt6.QtWidgets import QLabel
    from PyQt6.QtGui import QPixmap

    if isinstance(label, QLabel):
        label.clear()
        label.setPixmap(QPixmap())  # Use empty QPixmap instead of None
        label.setText("")
        label.setToolTip("")
        label.setProperty("class", "")


def cleanup_button(button) -> None:
    """Clean up a QPushButton for reuse."""
    from PyQt6.QtWidgets import QPushButton
    from PyQt6.QtGui import QIcon

    if isinstance(button, QPushButton):
        button.setText("")
        button.setIcon(QIcon())  # Use empty QIcon instead of None
        button.setToolTip("")
        button.setEnabled(True)
        button.setProperty("class", "")
        # Disconnect all signals
        try:
            button.clicked.disconnect()
        except TypeError:
            pass  # No connections to disconnect


def cleanup_progress_bar(progress_bar) -> None:
    """Clean up a QProgressBar for reuse."""
    from PyQt6.QtWidgets import QProgressBar

    if isinstance(progress_bar, QProgressBar):
        progress_bar.setMinimum(0)
        progress_bar.setMaximum(100)
        progress_bar.setValue(0)
        progress_bar.setFormat("")
        progress_bar.setToolTip("")
        progress_bar.setProperty("class", "")
