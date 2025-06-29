"""Common widget pools for frequently used GUI components.

This module sets up widget pools for the most commonly created/destroyed widgets
in the GOES-VFI application to improve performance.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout

from goesvfi.utils import log

from .widget_pool import cleanup_button, cleanup_label, cleanup_progress_bar, get_pool_manager, register_widget_pool

LOGGER = log.get_logger(__name__)


def cleanup_group_box(group_box) -> None:
    """Clean up a QGroupBox for reuse."""
    if isinstance(group_box, QGroupBox):
        group_box.setTitle("")
        group_box.setToolTip("")
        group_box.setProperty("class", "")
        # Clear layout if it exists
        layout = group_box.layout()
        if layout:
            # Remove all items from layout
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)


def cleanup_layout(layout) -> None:
    """Clean up a layout for reuse."""
    if layout:
        # Remove all items from layout
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        # Reset layout properties
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)


def create_status_label() -> QLabel:
    """Factory function for status labels."""
    label = QLabel()
    label.setProperty("class", "StatusLabel")
    label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    return label


def create_info_label() -> QLabel:
    """Factory function for info labels."""
    label = QLabel()
    label.setProperty("class", "InfoLabel")
    label.setWordWrap(True)
    return label


def create_preview_label() -> QLabel:
    """Factory function for preview image labels."""
    label = QLabel()
    label.setProperty("class", "PreviewLabel")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setMinimumSize(200, 200)
    label.setScaledContents(False)
    return label


def create_action_button() -> QPushButton:
    """Factory function for action buttons."""
    button = QPushButton()
    button.setProperty("class", "ActionButton")
    return button


def create_secondary_button() -> QPushButton:
    """Factory function for secondary buttons."""
    button = QPushButton()
    button.setProperty("class", "SecondaryButton")
    return button


def create_progress_bar() -> QProgressBar:
    """Factory function for progress bars."""
    progress = QProgressBar()
    progress.setProperty("class", "StandardProgress")
    progress.setMinimum(0)
    progress.setMaximum(100)
    return progress


def create_group_box() -> QGroupBox:
    """Factory function for group boxes."""
    group = QGroupBox()
    group.setProperty("class", "StandardGroup")
    return group


def create_horizontal_layout() -> QHBoxLayout:
    """Factory function for horizontal layouts."""
    layout = QHBoxLayout()
    layout.setContentsMargins(5, 5, 5, 5)
    layout.setSpacing(5)
    return layout


def create_vertical_layout() -> QVBoxLayout:
    """Factory function for vertical layouts."""
    layout = QVBoxLayout()
    layout.setContentsMargins(5, 5, 5, 5)
    layout.setSpacing(5)
    return layout


def initialize_common_pools() -> None:
    """Initialize all common widget pools for the application."""
    # Label pools
    register_widget_pool("status_labels", QLabel, create_status_label, max_size=20, cleanup_func=cleanup_label)

    register_widget_pool("info_labels", QLabel, create_info_label, max_size=15, cleanup_func=cleanup_label)

    register_widget_pool("preview_labels", QLabel, create_preview_label, max_size=10, cleanup_func=cleanup_label)

    # Button pools
    register_widget_pool("action_buttons", QPushButton, create_action_button, max_size=15, cleanup_func=cleanup_button)

    register_widget_pool(
        "secondary_buttons", QPushButton, create_secondary_button, max_size=10, cleanup_func=cleanup_button
    )

    # Progress bar pool
    register_widget_pool(
        "progress_bars", QProgressBar, create_progress_bar, max_size=8, cleanup_func=cleanup_progress_bar
    )

    # Group box pool
    register_widget_pool("group_boxes", QGroupBox, create_group_box, max_size=12, cleanup_func=cleanup_group_box)

    # Layout pools (these are less commonly pooled but useful for complex dynamic UIs)
    register_widget_pool(
        "horizontal_layouts", QHBoxLayout, create_horizontal_layout, max_size=8, cleanup_func=cleanup_layout
    )

    register_widget_pool(
        "vertical_layouts", QVBoxLayout, create_vertical_layout, max_size=8, cleanup_func=cleanup_layout
    )

    LOGGER.info("Initialized common widget pools")


def get_widget_pool_stats() -> dict:
    """Get statistics for all widget pools.

    Returns:
        Dictionary with pool statistics and performance metrics
    """
    manager = get_pool_manager()
    stats = manager.get_stats()

    # Calculate some performance metrics
    total_pooled = sum(pool_stats["pool_size"] for pool_stats in stats.values())
    total_allocated = sum(pool_stats["allocated_count"] for pool_stats in stats.values())
    total_capacity = sum(pool_stats["max_size"] for pool_stats in stats.values())

    return {
        "pools": stats,
        "summary": {
            "total_pools": len(stats),
            "total_pooled_widgets": total_pooled,
            "total_allocated_widgets": total_allocated,
            "total_capacity": total_capacity,
            "pool_utilization": (total_pooled / total_capacity * 100) if total_capacity > 0 else 0,
        },
    }


# Convenience functions for common operations
def get_status_label() -> QLabel:
    """Get a status label from the pool."""
    from .widget_pool import acquire_widget

    return acquire_widget("status_labels")


def get_info_label() -> QLabel:
    """Get an info label from the pool."""
    from .widget_pool import acquire_widget

    return acquire_widget("info_labels")


def get_preview_label() -> QLabel:
    """Get a preview label from the pool."""
    from .widget_pool import acquire_widget

    return acquire_widget("preview_labels")


def get_action_button() -> QPushButton:
    """Get an action button from the pool."""
    from .widget_pool import acquire_widget

    return acquire_widget("action_buttons")


def get_secondary_button() -> QPushButton:
    """Get a secondary button from the pool."""
    from .widget_pool import acquire_widget

    return acquire_widget("secondary_buttons")


def get_progress_bar() -> QProgressBar:
    """Get a progress bar from the pool."""
    from .widget_pool import acquire_widget

    return acquire_widget("progress_bars")


def get_group_box() -> QGroupBox:
    """Get a group box from the pool."""
    from .widget_pool import acquire_widget

    return acquire_widget("group_boxes")


def return_status_label(label: QLabel) -> None:
    """Return a status label to the pool."""
    from .widget_pool import release_widget

    release_widget("status_labels", label)


def return_info_label(label: QLabel) -> None:
    """Return an info label to the pool."""
    from .widget_pool import release_widget

    release_widget("info_labels", label)


def return_preview_label(label: QLabel) -> None:
    """Return a preview label to the pool."""
    from .widget_pool import release_widget

    release_widget("preview_labels", label)


def return_action_button(button: QPushButton) -> None:
    """Return an action button to the pool."""
    from .widget_pool import release_widget

    release_widget("action_buttons", button)


def return_secondary_button(button: QPushButton) -> None:
    """Return a secondary button to the pool."""
    from .widget_pool import release_widget

    release_widget("secondary_buttons", button)


def return_progress_bar(progress: QProgressBar) -> None:
    """Return a progress bar to the pool."""
    from .widget_pool import release_widget

    release_widget("progress_bars", progress)


def return_group_box(group: QGroupBox) -> None:
    """Return a group box to the pool."""
    from .widget_pool import release_widget

    release_widget("group_boxes", group)
