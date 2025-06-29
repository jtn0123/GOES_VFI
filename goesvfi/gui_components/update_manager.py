"""Centralized update manager with batching and debouncing.

This module provides a centralized way to manage UI updates, preventing
excessive refresh cycles and improving performance.
"""

from collections.abc import Callable
import time
from typing import Any

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)

# Default update batching delay (16ms ≈ 60fps)
DEFAULT_BATCH_DELAY_MS = 16


class UpdateManager(QObject):
    """Centralized update manager with batching and debouncing.

    This class manages UI updates to prevent excessive refresh cycles and
    improve performance. Updates are batched together and executed at
    regular intervals.
    """

    # Signal emitted when updates should be processed
    batch_update = pyqtSignal()

    def __init__(self, batch_delay_ms: int = DEFAULT_BATCH_DELAY_MS) -> None:
        """Initialize the update manager.

        Args:
            batch_delay_ms: Delay between batched updates in milliseconds
        """
        super().__init__()
        self.batch_delay_ms = batch_delay_ms
        self.pending_updates: set[str] = set()
        self.update_callbacks: dict[str, Callable[[], None]] = {}
        self.update_priorities: dict[str, int] = {}  # Higher number = higher priority
        self.last_update_times: dict[str, float] = {}

        # Single timer for batched updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._process_updates)
        self.update_timer.setSingleShot(True)

        # Statistics
        self.stats = {"total_requests": 0, "total_batches": 0, "total_updates_processed": 0, "avg_batch_size": 0.0}

        LOGGER.debug("UpdateManager initialized with %sms batch delay", batch_delay_ms)

    def register_update(self, update_id: str, callback: Callable[[], None], priority: int = 0) -> None:
        """Register an update callback.

        Args:
            update_id: Unique identifier for this update
            callback: Function to call when update is processed
            priority: Update priority (higher numbers processed first)
        """
        self.update_callbacks[update_id] = callback
        self.update_priorities[update_id] = priority
        LOGGER.debug("Registered update '%s' with priority %s", update_id, priority)

    def unregister_update(self, update_id: str) -> None:
        """Unregister an update callback.

        Args:
            update_id: Update ID to remove
        """
        self.update_callbacks.pop(update_id, None)
        self.update_priorities.pop(update_id, None)
        self.pending_updates.discard(update_id)
        self.last_update_times.pop(update_id, None)
        LOGGER.debug("Unregistered update '%s'", update_id)

    def request_update(self, update_id: str, force: bool = False) -> None:
        """Request an update to be processed in the next batch.

        Args:
            update_id: ID of the update to process
            force: If True, bypass debouncing and force update
        """
        if update_id not in self.update_callbacks:
            LOGGER.warning("Update ID '%s' not registered", update_id)
            return

        self.stats["total_requests"] += 1
        current_time = time.time()

        # Check if we should debounce this update
        if not force and update_id in self.last_update_times:
            time_since_last = current_time - self.last_update_times[update_id]
            min_interval = self.batch_delay_ms / 1000.0  # Convert to seconds

            if time_since_last < min_interval:
                # Too soon, add to pending but don't restart timer yet
                self.pending_updates.add(update_id)
                return

        self.pending_updates.add(update_id)

        # Start/restart the timer if not already active
        if not self.update_timer.isActive():
            self.update_timer.start(self.batch_delay_ms)

    def request_immediate_update(self, update_id: str) -> None:
        """Request an immediate update, bypassing batching.

        Args:
            update_id: ID of the update to process immediately
        """
        if update_id not in self.update_callbacks:
            LOGGER.warning("Update ID '%s' not registered", update_id)
            return

        try:
            self.update_callbacks[update_id]()
            self.last_update_times[update_id] = time.time()
            self.stats["total_updates_processed"] += 1
            LOGGER.debug("Immediate update processed: %s", update_id)
        except Exception as e:
            LOGGER.exception("Error processing immediate update '%s': %s", update_id, e)

    def _process_updates(self) -> None:
        """Process all pending updates in priority order."""
        if not self.pending_updates:
            return

        updates_to_process = list(self.pending_updates)
        self.pending_updates.clear()

        # Sort by priority (highest first)
        updates_to_process.sort(key=lambda uid: self.update_priorities.get(uid, 0), reverse=True)

        current_time = time.time()
        processed_count = 0

        for update_id in updates_to_process:
            if update_id in self.update_callbacks:
                try:
                    self.update_callbacks[update_id]()
                    self.last_update_times[update_id] = current_time
                    processed_count += 1
                except Exception as e:
                    LOGGER.exception("Error processing update '%s': %s", update_id, e)

        # Update statistics
        self.stats["total_batches"] += 1
        self.stats["total_updates_processed"] += processed_count
        if self.stats["total_batches"] > 0:
            self.stats["avg_batch_size"] = self.stats["total_updates_processed"] / self.stats["total_batches"]

        LOGGER.debug("Processed batch: %s updates, avg batch size: %.1f", processed_count, self.stats["avg_batch_size"])

        # Emit signal for any components that want to know about batch processing
        self.batch_update.emit()

    def clear_pending(self) -> None:
        """Clear all pending updates without processing them."""
        cleared_count = len(self.pending_updates)
        self.pending_updates.clear()
        self.update_timer.stop()
        LOGGER.debug("Cleared %s pending updates", cleared_count)

    def get_stats(self) -> dict[str, Any]:
        """Get update manager statistics.

        Returns:
            Dictionary with statistics about update processing
        """
        return self.stats.copy()

    def is_update_pending(self, update_id: str) -> bool:
        """Check if an update is currently pending.

        Args:
            update_id: Update ID to check

        Returns:
            True if the update is pending
        """
        return update_id in self.pending_updates


# Global singleton instance
_update_manager: UpdateManager | None = None


def get_update_manager() -> UpdateManager:
    """Get the global update manager instance.

    Returns:
        Global UpdateManager singleton
    """
    global _update_manager
    if _update_manager is None:
        _update_manager = UpdateManager()
        LOGGER.info("Created global UpdateManager instance")
    return _update_manager


def register_update(update_id: str, callback: Callable[[], None], priority: int = 0) -> None:
    """Convenience function to register an update with the global manager.

    Args:
        update_id: Unique identifier for this update
        callback: Function to call when update is processed
        priority: Update priority (higher numbers processed first)
    """
    get_update_manager().register_update(update_id, callback, priority)


def request_update(update_id: str, force: bool = False) -> None:
    """Convenience function to request an update with the global manager.

    Args:
        update_id: ID of the update to process
        force: If True, bypass debouncing and force update
    """
    get_update_manager().request_update(update_id, force)


def request_immediate_update(update_id: str) -> None:
    """Convenience function to request immediate update with the global manager.

    Args:
        update_id: ID of the update to process immediately
    """
    get_update_manager().request_immediate_update(update_id)
