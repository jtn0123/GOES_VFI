"""Patch to integrate UI enhancements into the existing MainWindow.

This can be applied to the MainWindow class to add all the UI/UX improvements.
"""

from typing import Any, Type

from PyQt6.QtWidgets import QWidget

from goesvfi.gui_enhancements_integration import enhance_existing_gui
from goesvfi.utils.log import get_logger

LOGGER = get_logger(__name__)


def patch_main_window(MainWindow_class: Type[Any]) -> None:
    """Monkey patch the MainWindow class to add UI enhancements.

    This function modifies the MainWindow class to integrate all UI/UX improvements.

    Args:
        MainWindow_class: The MainWindow class to patch
    """
    # Store original __init__
    original_init = MainWindow_class.__init__

    def enhanced_init(self: Any, *args: Any, **kwargs: Any) -> None:
        """Enhanced initialization with UI improvements."""
        # Call original init
        original_init(self, *args, **kwargs)

        # Add UI enhancements after initialization
        try:
            self._ui_enhancer = enhance_existing_gui(
                self
            )  # pylint: disable=attribute-defined-outside-init
            LOGGER.info("UI enhancements successfully integrated")

            # Connect to processing signals if available
            if hasattr(self, "main_tab"):
                # Connect processing started signal
                if hasattr(self.main_tab, "processing_started"):
                    self.main_tab.processing_started.connect(
                        lambda: self._ui_enhancer.start_operation("processing")
                    )

                # Connect processing finished signal
                if hasattr(self.main_tab, "processing_finished"):
                    self.main_tab.processing_finished.connect(
                        lambda success, msg: self._ui_enhancer.stop_operation(
                            "processing"
                        )
                    )

        except Exception as e:
            LOGGER.error("Failed to integrate UI enhancements: %s", e)
            # Continue without enhancements

    # Replace the __init__ method
    MainWindow_class.__init__ = enhanced_init

    def update_progress(
        self: Any, current: int, total: int, bytes_transferred: int = 0
    ) -> None:
        """Update progress information."""
        if hasattr(self, "_ui_enhancer"):
            # Update progress through enhancer
            pass

    # Add method to class
    MainWindow_class.update_progress = update_progress
