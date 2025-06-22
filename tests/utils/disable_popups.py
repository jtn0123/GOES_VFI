"""
Test utility to disable all GUI popups and user interactions.
Import this at the start of any test that uses GUI components.
"""

import os
from unittest.mock import MagicMock, patch

# Set Qt to use offscreen platform
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class NoPopupQDateTimeEdit:
    """QDateTimeEdit that never opens calendar popups."""

    def __init__(self, *args, **kwargs):
        from PyQt6.QtCore import QDateTime
        from PyQt6.QtWidgets import QDateTimeEdit

        self._real_widget = QDateTimeEdit(*args, **kwargs)
        # Disable calendar popup
        self._real_widget.setCalendarPopup(False)

    def __getattr__(self, name):
        # Delegate all other attributes to the real widget
        return getattr(self._real_widget, name)

    def setCalendarPopup(self, enabled):
        # Always keep calendar popup disabled
        self._real_widget.setCalendarPopup(False)


class NoPopupQFileDialog:
    """QFileDialog that returns mock values instead of opening dialogs."""

    @staticmethod
    def getExistingDirectory(*args, **kwargs):
        return "/test/mock/directory"

    @staticmethod
    def getSaveFileName(*args, **kwargs):
        return ("/test/mock/file.txt", "All Files (*)")

    @staticmethod
    def getOpenFileName(*args, **kwargs):
        return ("/test/mock/file.txt", "All Files (*)")


class NoPopupQMessageBox:
    """QMessageBox that returns mock values instead of showing dialogs."""

    class StandardButton:
        Yes = 1
        No = 2
        Ok = 3
        Cancel = 4

    @staticmethod
    def information(*args, **kwargs):
        return NoPopupQMessageBox.StandardButton.Ok

    @staticmethod
    def warning(*args, **kwargs):
        return NoPopupQMessageBox.StandardButton.Ok

    @staticmethod
    def critical(*args, **kwargs):
        return NoPopupQMessageBox.StandardButton.Ok

    @staticmethod
    def question(*args, **kwargs):
        return NoPopupQMessageBox.StandardButton.Yes


def apply_gui_patches():
    """Apply patches to prevent GUI popups."""
    patches = []

    # Patch QFileDialog
    patches.extend(
        [
            patch("PyQt6.QtWidgets.QFileDialog", NoPopupQFileDialog),
            patch("goesvfi.gui.QFileDialog", NoPopupQFileDialog),
            patch("goesvfi.gui_tabs.main_tab.QFileDialog", NoPopupQFileDialog),
            patch("goesvfi.integrity_check.gui_tab.QFileDialog", NoPopupQFileDialog),
            patch("goesvfi.file_sorter.gui_tab.QFileDialog", NoPopupQFileDialog),
            patch("goesvfi.date_sorter.gui_tab.QFileDialog", NoPopupQFileDialog),
        ]
    )

    # Patch QMessageBox
    patches.extend(
        [
            patch("PyQt6.QtWidgets.QMessageBox", NoPopupQMessageBox),
            patch(
                "goesvfi.integrity_check.enhanced_gui_tab.QMessageBox",
                NoPopupQMessageBox,
            ),
            patch("goesvfi.integrity_check.gui_tab.QMessageBox", NoPopupQMessageBox),
            patch("goesvfi.gui.QMessageBox", NoPopupQMessageBox),
        ]
    )

    # Patch QDateTimeEdit to disable calendar popups
    patches.extend(
        [
            patch("PyQt6.QtWidgets.QDateTimeEdit", NoPopupQDateTimeEdit),
        ]
    )

    # Start all patches
    for p in patches:
        p.start()

    return patches


# Global list to track active patches
_active_patches = []


def disable_all_gui_popups():
    """Main function to disable all GUI popups."""
    global _active_patches
    if not _active_patches:  # Only apply once
        _active_patches = apply_gui_patches()


def restore_gui_popups():
    """Restore normal GUI behavior."""
    global _active_patches
    for patch in _active_patches:
        try:
            patch.stop()
        except:
            pass
    _active_patches = []


# Auto-apply when imported
disable_all_gui_popups()
