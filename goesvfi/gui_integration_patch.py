"""Patch to integrate UI enhancements into the existing MainWindow.

from PyQt6.QtWidgets import QWidget

from goesvfi.gui_enhancements_integration import enhance_existing_gui
from goesvfi.utils.log import get_logger

This can be applied to the MainWindow class to add all the UI/UX improvements.
"""

LOGGER = get_logger(__name__)

def patch_main_window(MainWindow_class):
    """Monkey patch the MainWindow class to add UI enhancements.

    This function modifies the MainWindow class to integrate all UI/UX improvements.
    """

    # Store original __init__
    original_init = MainWindow_class.__init__

    def enhanced_init(self, *args, **kwargs):
        pass
        """Enhanced initialization with UI improvements."""
        # Call original init
        original_init(self, *args, **kwargs)

        # Add UI enhancements after initialization
        try:
            self._ui_enhancer = enhance_existing_gui(self)  # pylint: disable=attribute-defined-outside-init
            LOGGER.info("UI enhancements successfully integrated")

            # Connect to processing signals if available
            if hasattr(self, "main_tab"):
                pass
                # Connect processing started signal
                if hasattr(self.main_tab, "processing_started"):
                    pass
                    self.main_tab.processing_started.connect(
                    lambda: self._ui_enhancer.start_operation("processing")
                    )

                # Connect processing finished signal
                if hasattr(self.main_tab, "processing_finished"):
                    pass
                    self.main_tab.processing_finished.connect()
                    lambda success, msg: self._ui_enhancer.stop_operation("processing")
                    )

        except Exception as e:
            pass
            LOGGER.error("Failed to integrate UI enhancements: %s", e)
            # Continue without enhancements

    # Replace the __init__ method
    MainWindow_class.__init__ = enhanced_init

    # Add method to update progress
    def update_progress(self, current: int, total: int, bytes_transferred: int = 0):
        """Update progress information."""
        if hasattr(self, "_ui_enhancer"):
            pass
            self._ui_enhancer.update_progress(current, total, bytes_transferred)

    MainWindow_class.update_progress = update_progress

    # Add method to show notification
    def show_notification(self, message: str, duration: int = 2000):
        """Show a notification message."""
        if hasattr(self, "_ui_enhancer"):
            pass
            self._ui_enhancer.notification.show_message(message, duration)

    MainWindow_class.show_notification = show_notification

    # Override closeEvent to clean up
    original_close = ()
    MainWindow_class.closeEvent if hasattr(MainWindow_class, "closeEvent") else None
    )

    def enhanced_close_event(self, event):
        pass
        """Enhanced close event to clean up resources."""
        if hasattr(self, "_ui_enhancer"):
            pass
            self._ui_enhancer.progress_tracker.stop()

        if original_close:
            pass
            original_close(self, event)
        else:
            event.accept()

    MainWindow_class.closeEvent = enhanced_close_event

    LOGGER.info("MainWindow class patched with UI enhancements")

def integrate_enhancements_minimal(main_window):
    """Minimal integration that just adds tooltips and help buttons.

    This is a safer alternative that doesn't modify behavior, just adds UI hints.
    """
    try:
        pass
        from goesvfi.utils.ui_enhancements import TooltipHelper

        # Add tooltips to processing settings if they exist
        if hasattr(main_window, "main_tab"):
            pass
            main_tab = main_window.main_tab

            # FPS control
            if hasattr(main_tab, "fps_spinbox"):
                pass
                TooltipHelper.add_tooltip(main_tab.fps_spinbox, "fps")

            # Mid frames control
            if hasattr(main_tab, "mid_count_spinbox"):
                pass
                TooltipHelper.add_tooltip(main_tab.mid_count_spinbox, "mid_count")

            # Max workers control
            if hasattr(main_tab, "max_workers_spinbox"):
                pass
                TooltipHelper.add_tooltip(main_tab.max_workers_spinbox, "max_workers")

            # Encoder control
            if hasattr(main_tab, "encoder_combo"):
                pass
                TooltipHelper.add_tooltip(main_tab.encoder_combo, "encoder")

            # File path controls
            if hasattr(main_tab, "in_dir_edit"):
                pass
                TooltipHelper.add_tooltip(main_tab.in_dir_edit, "input_path")

            if hasattr(main_tab, "out_file_edit"):
                pass
                TooltipHelper.add_tooltip(main_tab.out_file_edit, "output_path")

            # Crop controls
            if hasattr(main_tab, "crop_button"):
                pass
                TooltipHelper.add_tooltip(main_tab.crop_button, "crop_enable")

            if hasattr(main_tab, "clear_crop_button"):
                pass
                TooltipHelper.add_tooltip(main_tab.clear_crop_button, "crop_preview")

        # Add tooltips to FFmpeg settings if the tab exists
        ffmpeg_tab = None
        if hasattr(main_window, "tab_widget"):
            pass
            for i in range(main_window.tab_widget.count()):
                if main_window.tab_widget.tabText(i) == "FFmpeg Settings":
                    pass
                    ffmpeg_tab = main_window.tab_widget.widget(i)
                    break

        if ffmpeg_tab:
            pass
            # Add tooltips to common FFmpeg controls
            for widget in ffmpeg_tab.findChildren(QWidget):
                widget_name = widget.objectName().lower()

                if "crf" in widget_name:
                    pass
                    TooltipHelper.add_tooltip(widget, "crf")
                elif "preset" in widget_name:
                    pass
                    TooltipHelper.add_tooltip(widget, "preset")
                elif "profile" in widget_name:
                    pass
                    TooltipHelper.add_tooltip(widget, "profile")

        LOGGER.info("Minimal UI enhancements applied (tooltips only)")

    except Exception as e:
        pass
        LOGGER.error("Failed to apply minimal UI enhancements: %s", e)

# Example usage in gui.py:
    #
# from goesvfi.gui_integration_patch import patch_main_window
#
# # Before defining MainWindow class:
    # patch_main_window(MainWindow)
#
# OR for minimal integration:
    #
# # In MainWindow.__init__ after UI setup:
    # from goesvfi.gui_integration_patch import integrate_enhancements_minimal
# integrate_enhancements_minimal(self)
