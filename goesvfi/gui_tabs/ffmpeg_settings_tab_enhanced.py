# goesvfi/gui_tabs/ffmpeg_settings_tab_enhanced.py
"""Enhanced FFmpeg settings tab with UI/UX improvements."""

from typing import Optional

from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QSpinBox,
    QWidget,
)

from goesvfi.gui_tabs.ffmpeg_settings_tab import FFmpegSettingsTab
from goesvfi.utils.log import get_logger

try:
    from goesvfi.utils.ui_enhancements import (
        FadeInNotification,
        HelpButton,
        TooltipHelper,
    )
except ImportError:
    # Provide dummy implementations if module is missing
    FadeInNotification = None  # type: ignore
    HelpButton = None  # type: ignore
    TooltipHelper = None  # type: ignore

LOGGER = get_logger(__name__)


class EnhancedFFmpegSettingsTab(FFmpegSettingsTab):
    """Enhanced FFmpeg settings tab with improved UI/UX features."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        # Initialize notification widget
        self._notification = FadeInNotification(self)

        # Add UI enhancements after parent initialization
        self._enhance_ui()

    def _enhance_ui(self) -> None:
        """Add UI enhancements to existing widgets."""
        # Find all widgets and add tooltips/help buttons
        self._add_tooltips_to_profile_widgets()
        self._add_tooltips_to_quality_widgets()
        self._add_tooltips_to_advanced_widgets()

    def _add_tooltips_to_profile_widgets(self) -> None:
        """Add tooltips to profile selection widgets."""
        # Find profile combo box
        profile_widgets = self.findChildren(QComboBox)
        for widget in profile_widgets:
            if "profile" in widget.objectName().lower() or hasattr(self, "profile_combo"):
                TooltipHelper.add_tooltip(widget, "profile")
                self._add_help_button_next_to_widget(widget, "profile")

    def _add_tooltips_to_quality_widgets(self) -> None:
        """Add tooltips to quality control widgets."""
        # CRF controls
        crf_widgets = self.findChildren(QSpinBox)
        for widget in crf_widgets:
            widget_name = widget.objectName().lower()
            if "crf" in widget_name:
                TooltipHelper.add_tooltip(widget, "crf")
                self._add_help_button_next_to_widget(widget, "crf")

        # Preset controls
        preset_widgets = self.findChildren(QComboBox)
        for widget in preset_widgets:
            widget_name = widget.objectName().lower()
            if "preset" in widget_name:
                TooltipHelper.add_tooltip(widget, "preset")

        # Bitrate controls
        bitrate_widgets = self.findChildren(QDoubleSpinBox)
        for widget in bitrate_widgets:
            widget_name = widget.objectName().lower()
            if "audio" in widget_name and "bitrate" in widget_name:
                TooltipHelper.add_tooltip(widget, "audio_bitrate")
            elif "video" in widget_name and "bitrate" in widget_name:
                TooltipHelper.add_tooltip(widget, "video_bitrate")

    def _add_tooltips_to_advanced_widgets(self) -> None:
        """Add tooltips to advanced settings widgets."""
        # Find all checkboxes for advanced options
        checkboxes = self.findChildren(QCheckBox)

        advanced_tooltips = {
            "two_pass": "Enable two-pass encoding for better quality at target bitrate. Takes twice as long.",
            "hardware_accel": "Use GPU hardware acceleration when available. Much faster but may have compatibility issues.",
            "deinterlace": "Remove interlacing artifacts from source video. Only needed for interlaced content.",
            "denoise": "Apply noise reduction filter. Can help with grainy footage but may reduce detail.",
            "stabilize": "Apply video stabilization. Helps with shaky footage but adds processing time.",
        }

        for checkbox in checkboxes:
            widget_name = checkbox.objectName().lower()
            for key, tooltip in advanced_tooltips.items():
                if key in widget_name:
                    TooltipHelper.add_tooltip(checkbox, key, tooltip)
                    break

    def _add_help_button_next_to_widget(self, widget: QWidget, topic: str) -> None:
        """Add a help button next to a widget."""
        # Get parent layout
        parent = widget.parentWidget()
        if not parent:
            return

        layout = parent.layout()
        if not layout:
            return

        # Find widget in layout
        if isinstance(layout, QGridLayout):
            index = layout.indexOf(widget)
            if index >= 0:
                row, col, _, _ = layout.getItemPosition(index)

                # Check if there's already something in the next column
                item = layout.itemAtPosition(row, col + 2) if row is not None else None
                if not item:
                    # Create help button
                    help_btn = HelpButton(topic, parent)
                    help_btn.help_requested.connect(self._show_detailed_help)

                    # Add to layout
                    if row is not None:
                        layout.addWidget(help_btn, row, col + 2)

        elif isinstance(layout, QHBoxLayout):
            index = layout.indexOf(widget)
            if index >= 0:
                # Create help button
                help_btn = HelpButton(topic, parent)
                help_btn.help_requested.connect(self._show_detailed_help)

                # Insert after widget
                layout.insertWidget(index + 1, help_btn)

    @pyqtSlot(str)
    def _show_detailed_help(self, topic: str) -> None:
        """Show detailed help for a topic."""
        LOGGER.debug("FFmpeg help requested for: %s", topic)

        # Could open a help dialog or show in status bar
        help_messages = {
            "profile": "Profile determines the overall quality/speed tradeoff",
            "crf": "Lower CRF values mean higher quality but larger files",
            "preset": "Slower presets provide better compression",
        }

        message = help_messages.get(topic, f"Help for {topic}")
        self._notification.show_message(message, duration=3000)

    def on_profile_changed(self, profile_name: str) -> None:
        """Override to add notification."""
        # Call parent method if it exists
        if hasattr(super(), "on_profile_changed"):
            super().on_profile_changed(profile_name)  # type: ignore
        if self._notification and hasattr(self._notification, "show_message"):
            self._notification.show_message(f"Profile changed to: {profile_name}")

    def on_setting_changed(self) -> None:
        """Called when any setting changes."""
        # Could update a preview or estimated file size
        LOGGER.debug("FFmpeg setting changed")

        # Show brief notification
        self._notification.show_message("Settings updated", duration=1000)
