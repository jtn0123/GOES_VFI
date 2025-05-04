# goesvfi/gui_tabs/ffmpeg_settings_tab.py
from __future__ import annotations
import logging
import math # For isnan check
from typing import TYPE_CHECKING, Optional, Any, Dict, List, TypedDict, cast

from PyQt6.QtCore import pyqtSignal, Qt, QTimer # Added QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QComboBox, QLineEdit, QSpinBox,
    QDoubleSpinBox, QCheckBox, QGridLayout, QLabel, QHBoxLayout, QSizePolicy
)
from PyQt6.QtGui import QIntValidator, QDoubleValidator # Import validators

# Runtime import for constants defined in gui.py
from goesvfi.utils.config import FFMPEG_PROFILES, DEFAULT_FFMPEG_PROFILE, FfmpegProfile # Import from config
# Avoid circular import if MainWindow is type hinted
if TYPE_CHECKING:
    from goesvfi.gui import MainWindow # Assuming MainWindow is in gui.py

# Setup logger
from goesvfi.utils import log
LOGGER = log.get_logger(__name__) # Use __name__ for specific logger

# Import TYPE_CHECKING definitions needed within the class
if TYPE_CHECKING:
    # Import from config for type checking as well
    from goesvfi.utils.config import FfmpegProfile, FFMPEG_PROFILES, DEFAULT_FFMPEG_PROFILE


class FFmpegSettingsTab(QWidget):
    """QWidget containing the settings for FFmpeg interpolation and encoding."""

    # Signal emitted when any setting affecting previews changes
    # (This signal is no longer passed in, but defined here if needed for internal use
    # or if MainWindow needs to connect to it later)
    # preview_settings_changed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the FFmpegSettingsTab."""
        super().__init__(parent)

        # --- Create Widgets ---
        self._create_widgets()

        # --- Setup Layout ---
        self._setup_layout()

        # --- Connect Signals ---
        self._connect_signals()

        # --- Initialize Control States ---
        self._update_all_control_states()

    def _create_widgets(self) -> None:
        """Create all the widgets for the FFmpeg settings tab."""
        # --- Profile Selection ---
        self.ffmpeg_profile_combo = QComboBox()
        self.ffmpeg_profile_combo.addItems(list(FFMPEG_PROFILES.keys()) + ["Custom"])
        self.ffmpeg_profile_combo.setToolTip("Select a predefined FFmpeg settings profile or 'Custom'")

        # --- Interpolation Settings Group ---
        self.ffmpeg_settings_group = QGroupBox("Interpolation (minterpolate filter)")
        self.ffmpeg_settings_group.setCheckable(True) # Corresponds to use_ffmpeg_interp
        self.ffmpeg_settings_group.setToolTip("Enable and configure FFmpeg's motion interpolation filter")

        self.ffmpeg_mi_mode_combo = QComboBox()
        self.ffmpeg_mi_mode_combo.addItems(["dup", "blend", "mci"])
        self.ffmpeg_mi_mode_combo.setToolTip("Motion interpolation mode")

        self.ffmpeg_mc_mode_combo = QComboBox()
        self.ffmpeg_mc_mode_combo.addItems(["obmc", "aobmc"])
        self.ffmpeg_mc_mode_combo.setToolTip("Motion compensation mode")

        self.ffmpeg_me_mode_combo = QComboBox()
        self.ffmpeg_me_mode_combo.addItems(["bidir", "bilat"])
        self.ffmpeg_me_mode_combo.setToolTip("Motion estimation mode")

        self.ffmpeg_vsbmc_checkbox = QCheckBox("VSBMC")
        self.ffmpeg_vsbmc_checkbox.setToolTip("Variable size block motion compensation")

        self.ffmpeg_scd_combo = QComboBox()
        self.ffmpeg_scd_combo.addItems(["none", "fdiff"])
        self.ffmpeg_scd_combo.setToolTip("Scene change detection mode")

        self.ffmpeg_me_algo_combo = QComboBox() # Changed from QLineEdit
        self.ffmpeg_me_algo_combo.addItems(["(default)", "esa", "tss", "tdls", "ntss", "fss", "ds", "hexbs", "epzs", "umh"])
        self.ffmpeg_me_algo_combo.setToolTip("Motion estimation algorithm (leave as default unless you know why)")

        self.ffmpeg_search_param_spinbox = QSpinBox()
        self.ffmpeg_search_param_spinbox.setRange(4, 2048) # Example range, adjust if needed
        self.ffmpeg_search_param_spinbox.setToolTip("Motion estimation search parameter")

        self.ffmpeg_scd_threshold_spinbox = QDoubleSpinBox()
        self.ffmpeg_scd_threshold_spinbox.setRange(0.0, 100.0)
        self.ffmpeg_scd_threshold_spinbox.setDecimals(1)
        self.ffmpeg_scd_threshold_spinbox.setSingleStep(0.1)
        self.ffmpeg_scd_threshold_spinbox.setToolTip("Scene change detection threshold (0-100)")

        self.ffmpeg_mb_size_combo = QComboBox() # Changed from QLineEdit
        self.ffmpeg_mb_size_combo.addItems(["(default)", "8", "16", "32", "64"]) # Common block sizes
        self.ffmpeg_mb_size_combo.setToolTip("Macroblock size for motion estimation")

        # --- Unsharp Mask Group ---
        self.ffmpeg_unsharp_group = QGroupBox("Sharpening (unsharp filter)")
        self.ffmpeg_unsharp_group.setCheckable(True) # Corresponds to apply_unsharp
        self.ffmpeg_unsharp_group.setToolTip("Apply unsharp mask for sharpening")

        self.ffmpeg_unsharp_lx_spinbox = QSpinBox()
        self.ffmpeg_unsharp_lx_spinbox.setRange(3, 63)
        self.ffmpeg_unsharp_lx_spinbox.setSingleStep(2)
        self.ffmpeg_unsharp_lx_spinbox.setToolTip("Luma matrix horizontal size (odd, 3-63)")

        self.ffmpeg_unsharp_ly_spinbox = QSpinBox()
        self.ffmpeg_unsharp_ly_spinbox.setRange(3, 63)
        self.ffmpeg_unsharp_ly_spinbox.setSingleStep(2)
        self.ffmpeg_unsharp_ly_spinbox.setToolTip("Luma matrix vertical size (odd, 3-63)")

        self.ffmpeg_unsharp_la_spinbox = QDoubleSpinBox()
        self.ffmpeg_unsharp_la_spinbox.setRange(-10.0, 10.0) # Wider range
        self.ffmpeg_unsharp_la_spinbox.setDecimals(2)
        self.ffmpeg_unsharp_la_spinbox.setSingleStep(0.1)
        self.ffmpeg_unsharp_la_spinbox.setToolTip("Luma amount (-10 to 10)")

        self.ffmpeg_unsharp_cx_spinbox = QSpinBox()
        self.ffmpeg_unsharp_cx_spinbox.setRange(3, 63)
        self.ffmpeg_unsharp_cx_spinbox.setSingleStep(2)
        self.ffmpeg_unsharp_cx_spinbox.setToolTip("Chroma matrix horizontal size (odd, 3-63)")

        self.ffmpeg_unsharp_cy_spinbox = QSpinBox()
        self.ffmpeg_unsharp_cy_spinbox.setRange(3, 63)
        self.ffmpeg_unsharp_cy_spinbox.setSingleStep(2)
        self.ffmpeg_unsharp_cy_spinbox.setToolTip("Chroma matrix vertical size (odd, 3-63)")

        self.ffmpeg_unsharp_ca_spinbox = QDoubleSpinBox()
        self.ffmpeg_unsharp_ca_spinbox.setRange(-10.0, 10.0) # Wider range
        self.ffmpeg_unsharp_ca_spinbox.setDecimals(2)
        self.ffmpeg_unsharp_ca_spinbox.setSingleStep(0.1)
        self.ffmpeg_unsharp_ca_spinbox.setToolTip("Chroma amount (-10 to 10)")

        # --- Quality Settings Group ---
        self.ffmpeg_quality_group = QGroupBox("Encoding Quality (libx264)")
        self.ffmpeg_quality_group.setToolTip("Settings for the final video encoding")

        self.ffmpeg_quality_combo = QComboBox()
        # Define presets similar to gui_backup.py
        self.quality_presets = {
            "Very High (CRF 16)": {"crf": 16, "bitrate": 15000, "bufsize": 22500, "pix_fmt": "yuv444p"},
            "High (CRF 18)": {"crf": 18, "bitrate": 12000, "bufsize": 18000, "pix_fmt": "yuv444p"},
            "Medium (CRF 20)": {"crf": 20, "bitrate": 10000, "bufsize": 15000, "pix_fmt": "yuv420p"},
            "Low (CRF 23)": {"crf": 23, "bitrate": 8000, "bufsize": 12000, "pix_fmt": "yuv420p"},
            "Very Low (CRF 26)": {"crf": 26, "bitrate": 5000, "bufsize": 7500, "pix_fmt": "yuv420p"},
            "Custom": {} # Placeholder for custom settings
        }
        self.ffmpeg_quality_combo.addItems(list(self.quality_presets.keys()))
        self.ffmpeg_quality_combo.setToolTip("Select a quality preset (adjusts CRF, Bitrate, Bufsize, Pixel Format)")

        self.ffmpeg_crf_spinbox = QSpinBox()
        self.ffmpeg_crf_spinbox.setRange(0, 51) # x264 CRF range
        self.ffmpeg_crf_spinbox.setToolTip("Constant Rate Factor (0=lossless, 51=worst)")

        self.ffmpeg_bitrate_spinbox = QSpinBox()
        self.ffmpeg_bitrate_spinbox.setRange(100, 100000) # In kbps
        self.ffmpeg_bitrate_spinbox.setSuffix(" kbps")
        self.ffmpeg_bitrate_spinbox.setToolTip("Target video bitrate (used if CRF is not the primary mode, often informational)")
        self.ffmpeg_bitrate_spinbox.setDisabled(True) # Typically controlled by preset/CRF

        self.ffmpeg_bufsize_spinbox = QSpinBox()
        self.ffmpeg_bufsize_spinbox.setRange(100, 200000) # In kb
        self.ffmpeg_bufsize_spinbox.setSuffix(" kB")
        self.ffmpeg_bufsize_spinbox.setToolTip("Decoder buffer size (often 1.5x-2x bitrate)")
        self.ffmpeg_bufsize_spinbox.setDisabled(True) # Typically controlled by preset/CRF

        self.ffmpeg_pix_fmt_combo = QComboBox()
        self.ffmpeg_pix_fmt_combo.addItems(["yuv444p", "yuv420p", "yuv422p", "rgb24"]) # Common formats
        self.ffmpeg_pix_fmt_combo.setToolTip("Pixel format for encoding (yuv444p recommended for quality)")

        self.ffmpeg_filter_preset_combo = QComboBox()
        self.ffmpeg_filter_preset_combo.addItems(["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"])
        self.ffmpeg_filter_preset_combo.setToolTip("x264 encoding speed preset (slower = better compression/quality)")

    def _setup_layout(self) -> None:
        """Setup the layout and add widgets."""
        main_layout = QVBoxLayout(self)

        # Profile Selection Layout
        profile_layout = QHBoxLayout()
        profile_layout.addWidget(QLabel("FFmpeg Profile:"))
        profile_layout.addWidget(self.ffmpeg_profile_combo)
        profile_layout.addStretch()
        main_layout.addLayout(profile_layout)

        # Interpolation Settings Layout
        interp_layout = QGridLayout(self.ffmpeg_settings_group)
        interp_layout.addWidget(QLabel("MI Mode:"), 0, 0)
        interp_layout.addWidget(self.ffmpeg_mi_mode_combo, 0, 1)
        interp_layout.addWidget(QLabel("MC Mode:"), 0, 2)
        interp_layout.addWidget(self.ffmpeg_mc_mode_combo, 0, 3)
        interp_layout.addWidget(QLabel("ME Mode:"), 1, 0)
        interp_layout.addWidget(self.ffmpeg_me_mode_combo, 1, 1)
        interp_layout.addWidget(self.ffmpeg_vsbmc_checkbox, 1, 2, 1, 2) # Span 2 columns
        interp_layout.addWidget(QLabel("SCD Mode:"), 2, 0)
        interp_layout.addWidget(self.ffmpeg_scd_combo, 2, 1)
        interp_layout.addWidget(QLabel("SCD Thresh:"), 2, 2)
        interp_layout.addWidget(self.ffmpeg_scd_threshold_spinbox, 2, 3)
        interp_layout.addWidget(QLabel("ME Algo:"), 3, 0)
        interp_layout.addWidget(self.ffmpeg_me_algo_combo, 3, 1)
        interp_layout.addWidget(QLabel("Search Param:"), 3, 2)
        interp_layout.addWidget(self.ffmpeg_search_param_spinbox, 3, 3)
        interp_layout.addWidget(QLabel("MB Size:"), 4, 0)
        interp_layout.addWidget(self.ffmpeg_mb_size_combo, 4, 1)
        interp_layout.setColumnStretch(1, 1) # Allow combos/spinners to expand
        interp_layout.setColumnStretch(3, 1)
        main_layout.addWidget(self.ffmpeg_settings_group)

        # Unsharp Mask Layout
        unsharp_layout = QGridLayout(self.ffmpeg_unsharp_group)
        unsharp_layout.addWidget(QLabel("Luma X:"), 0, 0)
        unsharp_layout.addWidget(self.ffmpeg_unsharp_lx_spinbox, 0, 1)
        unsharp_layout.addWidget(QLabel("Luma Y:"), 0, 2)
        unsharp_layout.addWidget(self.ffmpeg_unsharp_ly_spinbox, 0, 3)
        unsharp_layout.addWidget(QLabel("Luma Amt:"), 0, 4)
        unsharp_layout.addWidget(self.ffmpeg_unsharp_la_spinbox, 0, 5)
        unsharp_layout.addWidget(QLabel("Chroma X:"), 1, 0)
        unsharp_layout.addWidget(self.ffmpeg_unsharp_cx_spinbox, 1, 1)
        unsharp_layout.addWidget(QLabel("Chroma Y:"), 1, 2)
        unsharp_layout.addWidget(self.ffmpeg_unsharp_cy_spinbox, 1, 3)
        unsharp_layout.addWidget(QLabel("Chroma Amt:"), 1, 4)
        unsharp_layout.addWidget(self.ffmpeg_unsharp_ca_spinbox, 1, 5)
        for i in [1, 3, 5]: # Allow spinboxes to expand
            unsharp_layout.setColumnStretch(i, 1)
        main_layout.addWidget(self.ffmpeg_unsharp_group)

        # Quality Settings Layout
        quality_layout = QGridLayout(self.ffmpeg_quality_group)
        quality_layout.addWidget(QLabel("Quality Preset:"), 0, 0)
        quality_layout.addWidget(self.ffmpeg_quality_combo, 0, 1)
        quality_layout.addWidget(QLabel("CRF:"), 0, 2)
        quality_layout.addWidget(self.ffmpeg_crf_spinbox, 0, 3)
        quality_layout.addWidget(QLabel("Bitrate:"), 1, 0)
        quality_layout.addWidget(self.ffmpeg_bitrate_spinbox, 1, 1)
        quality_layout.addWidget(QLabel("Bufsize:"), 1, 2)
        quality_layout.addWidget(self.ffmpeg_bufsize_spinbox, 1, 3)
        quality_layout.addWidget(QLabel("Pixel Format:"), 2, 0)
        quality_layout.addWidget(self.ffmpeg_pix_fmt_combo, 2, 1)
        quality_layout.addWidget(QLabel("Encoder Preset:"), 2, 2)
        quality_layout.addWidget(self.ffmpeg_filter_preset_combo, 2, 3)
        quality_layout.setColumnStretch(1, 1) # Allow combos/spinners to expand
        quality_layout.setColumnStretch(3, 1)
        main_layout.addWidget(self.ffmpeg_quality_group)

        main_layout.addStretch() # Push everything to the top
        self.setLayout(main_layout)

    def _connect_signals(self) -> None:
        """Connect signals for enabling/disabling controls and profile handling."""
        # Profile selection
        self.ffmpeg_profile_combo.currentTextChanged.connect(self._on_profile_selected)

        # Controls that affect dependent control states
        self.ffmpeg_settings_group.toggled.connect(self._update_interpolation_controls_state)
        self.ffmpeg_scd_combo.currentTextChanged.connect(self._update_scd_thresh_state)
        self.ffmpeg_unsharp_group.toggled.connect(self._update_unsharp_controls_state)
        self.ffmpeg_quality_combo.currentTextChanged.connect(self._update_quality_controls_state)

        # All controls that should trigger the "Custom" profile state when changed
        controls_to_monitor = [
            self.ffmpeg_settings_group, # Checkable groupbox itself
            self.ffmpeg_mi_mode_combo,
            self.ffmpeg_mc_mode_combo,
            self.ffmpeg_me_mode_combo,
            self.ffmpeg_vsbmc_checkbox,
            self.ffmpeg_scd_combo,
            self.ffmpeg_me_algo_combo,
            self.ffmpeg_search_param_spinbox,
            self.ffmpeg_scd_threshold_spinbox,
            self.ffmpeg_mb_size_combo,
            self.ffmpeg_unsharp_group, # Checkable groupbox itself
            self.ffmpeg_unsharp_lx_spinbox,
            self.ffmpeg_unsharp_ly_spinbox,
            self.ffmpeg_unsharp_la_spinbox,
            self.ffmpeg_unsharp_cx_spinbox,
            self.ffmpeg_unsharp_cy_spinbox,
            self.ffmpeg_unsharp_ca_spinbox,
            self.ffmpeg_quality_combo, # Changing quality preset affects others
            self.ffmpeg_crf_spinbox,
            # Bitrate/Bufsize are usually disabled, but connect anyway
            self.ffmpeg_bitrate_spinbox,
            self.ffmpeg_bufsize_spinbox,
            self.ffmpeg_pix_fmt_combo,
            self.ffmpeg_filter_preset_combo,
        ]

        for control in controls_to_monitor:
            if isinstance(control, (QComboBox)):
                control.currentTextChanged.connect(self._on_ffmpeg_setting_changed)
            elif isinstance(control, (QSpinBox, QDoubleSpinBox)):
                control.valueChanged.connect(self._on_ffmpeg_setting_changed)
            elif isinstance(control, QCheckBox):
                 control.stateChanged.connect(self._on_ffmpeg_setting_changed)
            elif isinstance(control, QGroupBox) and control.isCheckable():
                 control.toggled.connect(self._on_ffmpeg_setting_changed)

    # --- Control State Update Methods (from gui_backup.py, adapted) ---

    def _update_all_control_states(self) -> None:
        """Update the enabled state of all dependent controls based on current selections."""
        self._update_interpolation_controls_state(self.ffmpeg_settings_group.isChecked())
        self._update_scd_thresh_state(self.ffmpeg_scd_combo.currentText())
        self._update_unsharp_controls_state(self.ffmpeg_unsharp_group.isChecked())
        self._update_quality_controls_state(self.ffmpeg_quality_combo.currentText())

    def _update_interpolation_controls_state(self, enable: bool) -> None:
        """Enable/disable interpolation controls based on the group checkbox."""
        widgets = [
            self.ffmpeg_mi_mode_combo, self.ffmpeg_mc_mode_combo,
            self.ffmpeg_me_mode_combo, self.ffmpeg_vsbmc_checkbox,
            self.ffmpeg_scd_combo, self.ffmpeg_me_algo_combo,
            self.ffmpeg_search_param_spinbox, self.ffmpeg_scd_threshold_spinbox,
            self.ffmpeg_mb_size_combo
        ]
        for widget in widgets:
            widget.setEnabled(enable)
        # Special handling for SCD threshold based on SCD mode
        if enable:
            self._update_scd_thresh_state(self.ffmpeg_scd_combo.currentText())
        else:
            self.ffmpeg_scd_threshold_spinbox.setEnabled(False)

    def _update_scd_thresh_state(self, scd_mode: str) -> None:
        """Enable/disable SCD threshold based on SCD mode selection."""
        # Only enable threshold if main group is checked AND scd mode is not 'none'
        enabled = self.ffmpeg_settings_group.isChecked() and scd_mode != "none"
        self.ffmpeg_scd_threshold_spinbox.setEnabled(enabled)

    def _update_unsharp_controls_state(self, enable: bool) -> None:
        """Enable/disable unsharp controls based on the group checkbox."""
        widgets = [
            self.ffmpeg_unsharp_lx_spinbox, self.ffmpeg_unsharp_ly_spinbox,
            self.ffmpeg_unsharp_la_spinbox, self.ffmpeg_unsharp_cx_spinbox,
            self.ffmpeg_unsharp_cy_spinbox, self.ffmpeg_unsharp_ca_spinbox
        ]
        for widget in widgets:
            widget.setEnabled(enable)

    def _update_quality_controls_state(self, preset_text: Optional[str] = None) -> None:
        """Update quality controls based on the selected preset."""
        if preset_text is None:
            preset_text = self.ffmpeg_quality_combo.currentText()

        preset_settings = self.quality_presets.get(preset_text)

        if preset_settings is None: # Should not happen if "Custom" is handled
             LOGGER.warning(f"Unknown quality preset '{preset_text}' encountered.")
             # Keep controls enabled if preset is unknown or "Custom"
             self.ffmpeg_crf_spinbox.setEnabled(True)
             self.ffmpeg_bitrate_spinbox.setEnabled(True) # Enable custom bitrate/bufsize
             self.ffmpeg_bufsize_spinbox.setEnabled(True)
             self.ffmpeg_pix_fmt_combo.setEnabled(True)
             return

        if preset_text == "Custom":
            # Enable all controls for custom configuration
            self.ffmpeg_crf_spinbox.setEnabled(True)
            self.ffmpeg_bitrate_spinbox.setEnabled(True)
            self.ffmpeg_bufsize_spinbox.setEnabled(True)
            self.ffmpeg_pix_fmt_combo.setEnabled(True)
        else:
            # Preset selected: disable direct editing of dependent fields
            # and set their values from the preset
            self.ffmpeg_crf_spinbox.setEnabled(False)
            self.ffmpeg_bitrate_spinbox.setEnabled(False)
            self.ffmpeg_bufsize_spinbox.setEnabled(False)
            self.ffmpeg_pix_fmt_combo.setEnabled(False)

            # Block signals temporarily while setting preset values
            widgets_to_block = [
                self.ffmpeg_crf_spinbox, self.ffmpeg_bitrate_spinbox,
                self.ffmpeg_bufsize_spinbox, self.ffmpeg_pix_fmt_combo
            ]
            for w in widgets_to_block: w.blockSignals(True)
            try:
                if "crf" in preset_settings: self.ffmpeg_crf_spinbox.setValue(preset_settings["crf"])
                if "bitrate" in preset_settings: self.ffmpeg_bitrate_spinbox.setValue(preset_settings["bitrate"])
                if "bufsize" in preset_settings: self.ffmpeg_bufsize_spinbox.setValue(preset_settings["bufsize"])
                if "pix_fmt" in preset_settings: self.ffmpeg_pix_fmt_combo.setCurrentText(preset_settings["pix_fmt"])
            finally:
                for w in widgets_to_block: w.blockSignals(False)

    # --- Profile Handling Methods (from gui_backup.py, adapted) ---

    def _on_profile_selected(self, profile_name: str) -> None:
        LOGGER.debug(f"FFmpeg profile selected: {profile_name}")
        """Load settings from the selected FFmpeg profile."""
        if profile_name == "Custom":
            # When user explicitly selects "Custom", enable quality controls
            self._update_quality_controls_state("Custom")
            return # Don't load any settings

        profile_dict = FFMPEG_PROFILES.get(profile_name)
        if not profile_dict:
            LOGGER.warning(f"Unknown FFmpeg profile selected: {profile_name}")
            return

        # Block signals on the profile combo itself to prevent recursion
        self.ffmpeg_profile_combo.blockSignals(True)
        # Block signals on all other controls to prevent _on_ffmpeg_setting_changed firing prematurely
        all_controls = self._get_all_setting_controls()
        for widget in all_controls:
            if widget != self.ffmpeg_profile_combo: # Don't double-block
                widget.blockSignals(True)

        try:
            # --- Apply settings from profile_dict ---
            # Interpolation
            self.ffmpeg_settings_group.setChecked(profile_dict["use_ffmpeg_interp"])
            self.ffmpeg_mi_mode_combo.setCurrentText(profile_dict["mi_mode"])
            self.ffmpeg_mc_mode_combo.setCurrentText(profile_dict["mc_mode"])
            self.ffmpeg_me_mode_combo.setCurrentText(profile_dict["me_mode"])
            self.ffmpeg_vsbmc_checkbox.setChecked(profile_dict["vsbmc"])
            self.ffmpeg_scd_combo.setCurrentText(profile_dict["scd"])
            self.ffmpeg_me_algo_combo.setCurrentText(profile_dict["me_algo"]) # Use combo now
            self.ffmpeg_search_param_spinbox.setValue(profile_dict["search_param"])
            self.ffmpeg_scd_threshold_spinbox.setValue(profile_dict["scd_threshold"])
            self.ffmpeg_mb_size_combo.setCurrentText(profile_dict["mb_size"]) # Use combo now

            # Unsharp
            self.ffmpeg_unsharp_group.setChecked(profile_dict["apply_unsharp"])
            self.ffmpeg_unsharp_lx_spinbox.setValue(profile_dict["unsharp_lx"])
            self.ffmpeg_unsharp_ly_spinbox.setValue(profile_dict["unsharp_ly"])
            self.ffmpeg_unsharp_la_spinbox.setValue(profile_dict["unsharp_la"])
            self.ffmpeg_unsharp_cx_spinbox.setValue(profile_dict["unsharp_cx"])
            self.ffmpeg_unsharp_cy_spinbox.setValue(profile_dict["unsharp_cy"])
            self.ffmpeg_unsharp_ca_spinbox.setValue(profile_dict["unsharp_ca"])

            # Quality - Set the quality preset combo, which triggers _update_quality_controls_state
            self.ffmpeg_quality_combo.setCurrentText(profile_dict["preset_text"])

            # Filter Preset
            self.ffmpeg_filter_preset_combo.setCurrentText(profile_dict["filter_preset"])

            # --- Update control states after applying profile ---
            self._update_all_control_states()

        except KeyError as e:
            LOGGER.error(f"Profile '{profile_name}' is missing key: {e}")
        except Exception as e:
            LOGGER.error(f"Error applying profile '{profile_name}': {e}", exc_info=True)
        finally:
            # Unblock signals
            for widget in all_controls:
                widget.blockSignals(False)
            self.ffmpeg_profile_combo.blockSignals(False) # Unblock profile combo last

        # Verify if settings still match after applying (should match unless error occurred)
        # This prevents the combo immediately switching back to "Custom" if _update_quality_controls_state
        # had a side effect that didn't perfectly match the original profile dict (e.g., float precision)
        QTimer.singleShot(0, self._verify_profile_match) # Check slightly later


    def _verify_profile_match(self) -> None:
        """Checks if current settings match the selected profile and updates combo if not."""
        current_profile_name = self.ffmpeg_profile_combo.currentText()
        if current_profile_name == "Custom":
            return # Already custom

        profile_dict = FFMPEG_PROFILES.get(current_profile_name)
        if not profile_dict:
            return # Unknown profile selected

        if not self._check_settings_match_profile(profile_dict):
            LOGGER.warning(f"Settings drifted after applying profile '{current_profile_name}'. Setting to 'Custom'.")
            self.ffmpeg_profile_combo.blockSignals(True)
            self.ffmpeg_profile_combo.setCurrentText("Custom")
            self.ffmpeg_profile_combo.blockSignals(False)
            # Ensure quality controls are enabled when switching to Custom this way
            self._update_quality_controls_state("Custom")


    def _on_ffmpeg_setting_changed(self, *args: Any) -> None:
        # LOGGER.debug("FFmpeg setting changed, checking profile match...")
        """Handle changes to FFmpeg settings to set the profile combo to 'Custom' if needed."""
        # If the current profile is already "Custom", do nothing more
        if self.ffmpeg_profile_combo.currentText() == "Custom":
            # If the quality preset was changed *to* "Custom", ensure controls are enabled
            if self.sender() == self.ffmpeg_quality_combo and self.ffmpeg_quality_combo.currentText() == "Custom":
                 self._update_quality_controls_state("Custom")
            return

        # Check if the current settings match any known profile *other than* "Custom"
        matching_profile_name = None
        for name, profile_dict in FFMPEG_PROFILES.items():
            if self._check_settings_match_profile(profile_dict):
                matching_profile_name = name
                break

        # If settings no longer match the currently selected profile, switch to "Custom"
        if not matching_profile_name:
            # Check if the combo isn't already "Custom" to prevent loops
            if self.ffmpeg_profile_combo.currentText() != "Custom":
                LOGGER.debug("Settings no longer match any profile, setting profile combo to 'Custom'.")
                self.ffmpeg_profile_combo.blockSignals(True)
                self.ffmpeg_profile_combo.setCurrentText("Custom")
                self.ffmpeg_profile_combo.blockSignals(False)
                # Ensure quality controls are enabled when switching to Custom
                self._update_quality_controls_state("Custom")
        # This case should ideally not happen if _on_profile_selected works correctly,
        # but handles the case where settings change *back* to matching a profile.
        elif matching_profile_name != self.ffmpeg_profile_combo.currentText():
             LOGGER.debug(f"Settings now match profile '{matching_profile_name}', updating combo.")
             self.ffmpeg_profile_combo.blockSignals(True)
             self.ffmpeg_profile_combo.setCurrentText(matching_profile_name)
             self.ffmpeg_profile_combo.blockSignals(False)
             # Update quality controls based on the matched profile's preset text
             matched_profile = FFMPEG_PROFILES.get(matching_profile_name)
             if matched_profile:
                 self._update_quality_controls_state(matched_profile["preset_text"])


    def _check_settings_match_profile(self, profile_dict: FfmpegProfile) -> bool:
        """Checks if current FFmpeg settings match a given profile dictionary."""
        try:
            current_settings = self.get_current_settings() # Use getter method
        except Exception as e:
             LOGGER.error(f"Error getting current settings in _check_settings_match_profile: {e}", exc_info=True)
             return False # Cannot compare if widgets are missing or getters fail

        # Compare current settings with the profile dictionary
        # Explicitly list keys from FfmpegProfile *excluding* 'preset_text'
        # as preset_text is derived/used to set other values, not a direct setting itself.
        ffmpeg_profile_keys_to_compare: List[str] = [
            "use_ffmpeg_interp", "mi_mode", "mc_mode", "me_mode", "vsbmc", "scd",
            "me_algo", "search_param", "scd_threshold", "mb_size", "apply_unsharp",
            "unsharp_lx", "unsharp_ly", "unsharp_la", "unsharp_cx", "unsharp_cy",
            "unsharp_ca", "crf", "bitrate", "bufsize", "pix_fmt",
            "filter_preset"
        ]

        for key in ffmpeg_profile_keys_to_compare:
            # Ensure key exists in current_settings before accessing
            if key not in current_settings:
                 LOGGER.warning(f"Key '{key}' in profile but not returned by get_current_settings().")
                 return False

            current_value = current_settings[key]
            # Use cast to satisfy type checker for TypedDict access
            profile_value = cast(Any, profile_dict[key]) # type: ignore[literal-required]

            # Special handling for float comparison (SCD Threshold, Unsharp Amounts)
            if key in ["scd_threshold", "unsharp_la", "unsharp_ca"]:
                # For scd_threshold, only compare if scd is not "none" in *both* current and profile
                if key == "scd_threshold":
                    current_scd_mode = current_settings.get("scd")
                    profile_scd_mode = profile_dict.get("scd")
                    if current_scd_mode == "none" and profile_scd_mode == "none":
                        continue # Threshold doesn't matter if both are none, skip comparison
                    if current_scd_mode == "none" or profile_scd_mode == "none":
                         # If one is none and the other isn't, they don't match profile-wise
                         # regarding threshold relevance, but the threshold *value* might still match
                         # the profile's default if the user just toggled scd mode.
                         # Let the main scd key comparison handle the mode mismatch.
                         # We only care about the *value* comparison here if *both* are active.
                         pass # Don't compare value if modes differ like this

                # Proceed with float comparison if relevant
                # Handle potential None values before comparison
                if current_value is None or profile_value is None or (isinstance(current_value, float) and math.isnan(current_value)) or (isinstance(profile_value, float) and math.isnan(profile_value)):
                     if current_value != profile_value: # Treat None/NaN mismatch as difference
                          # LOGGER.debug(f"Mismatch on float key '{key}' (None/NaN): Current='{current_value}', Profile='{profile_value}'")
                          return False
                     else:
                          continue # Both are None or NaN, treat as matching

                if not isinstance(current_value, (float, int)) or not isinstance(profile_value, (float, int)):
                    LOGGER.warning(f"Non-numeric value for float key '{key}'. Current: {current_value}, Profile: {profile_value}")
                    # Allow comparison if one is int and other is float (e.g., 1 vs 1.0)
                    try:
                        if abs(float(current_value) - float(profile_value)) > 1e-6:
                            # LOGGER.debug(f"Mismatch on float key '{key}': Current='{current_value}', Profile='{profile_value}'")
                            return False
                    except (ValueError, TypeError):
                         # LOGGER.debug(f"Type mismatch on float key '{key}': Current='{current_value}', Profile='{profile_value}'")
                         return False # Cannot convert, definitely mismatch
                elif abs(float(current_value) - float(profile_value)) > 1e-6: # Use tolerance
                    # LOGGER.debug(f"Mismatch on float key '{key}': Current='{current_value}', Profile='{profile_value}'")
                    return False

            # Special handling for text fields that might be "(default)" or empty (ME Algo, MB Size)
            elif key in ["me_algo", "mb_size"]:
                # Treat empty string and "(default)" as equivalent for comparison
                current_text = current_value if current_value and current_value != "(default)" else "(default)"
                profile_text = profile_value if profile_value and profile_value != "(default)" else "(default)"
                if current_text != profile_text:
                    # LOGGER.debug(f"Mismatch on text key '{key}': Current='{current_value}', Profile='{profile_value}'")
                    return False
            # General comparison for other types (bool, int, str)
            elif current_value != profile_value:
                # LOGGER.debug(f"Mismatch on key '{key}': Current='{current_value}', Profile='{profile_value}'")
                return False

        # LOGGER.debug(f"Settings match profile dict: {profile_dict}")
        return True

    # --- Helper Methods ---

    def _get_all_setting_controls(self) -> List[QWidget]:
        """Returns a list of all widgets that define FFmpeg settings."""
        return [
            self.ffmpeg_profile_combo,
            self.ffmpeg_settings_group,
            self.ffmpeg_mi_mode_combo,
            self.ffmpeg_mc_mode_combo,
            self.ffmpeg_me_mode_combo,
            self.ffmpeg_vsbmc_checkbox,
            self.ffmpeg_scd_combo,
            self.ffmpeg_me_algo_combo,
            self.ffmpeg_search_param_spinbox,
            self.ffmpeg_scd_threshold_spinbox,
            self.ffmpeg_mb_size_combo,
            self.ffmpeg_unsharp_group,
            self.ffmpeg_unsharp_lx_spinbox,
            self.ffmpeg_unsharp_ly_spinbox,
            self.ffmpeg_unsharp_la_spinbox,
            self.ffmpeg_unsharp_cx_spinbox,
            self.ffmpeg_unsharp_cy_spinbox,
            self.ffmpeg_unsharp_ca_spinbox,
            self.ffmpeg_quality_combo,
            self.ffmpeg_crf_spinbox,
            self.ffmpeg_bitrate_spinbox,
            self.ffmpeg_bufsize_spinbox,
            self.ffmpeg_pix_fmt_combo,
            self.ffmpeg_filter_preset_combo,
        ]

    # --- Public Methods for MainWindow Interaction ---

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the entire tab content."""
        # Disable the main group boxes first
        self.ffmpeg_settings_group.setEnabled(enabled)
        self.ffmpeg_unsharp_group.setEnabled(enabled)
        self.ffmpeg_quality_group.setEnabled(enabled)
        self.ffmpeg_profile_combo.setEnabled(enabled) # Also disable profile selection

        # If enabling, restore the individual control states based on selections
        if enabled:
            self._update_all_control_states()
        else:
            # If disabling, ensure all child controls are also disabled
            # (though disabling the group boxes should handle most)
             for control in self._get_all_setting_controls():
                 if control != self.ffmpeg_profile_combo: # Already handled
                    control.setEnabled(False)


    def get_current_settings(self) -> Dict[str, Any]:
        """Returns a dictionary of the current FFmpeg settings from the UI."""
        # Handle "(default)" text for combo boxes that allow it
        me_algo = self.ffmpeg_me_algo_combo.currentText()
        mb_size = self.ffmpeg_mb_size_combo.currentText()

        settings = {
            # Interpolation Group
            "use_ffmpeg_interp": self.ffmpeg_settings_group.isChecked(),
            "mi_mode": self.ffmpeg_mi_mode_combo.currentText(),
            "mc_mode": self.ffmpeg_mc_mode_combo.currentText(),
            "me_mode": self.ffmpeg_me_mode_combo.currentText(),
            "vsbmc": self.ffmpeg_vsbmc_checkbox.isChecked(),
            "scd": self.ffmpeg_scd_combo.currentText(),
            "me_algo": me_algo if me_algo != "(default)" else "", # Store empty string if default
            "search_param": self.ffmpeg_search_param_spinbox.value(),
            "scd_threshold": self.ffmpeg_scd_threshold_spinbox.value(),
            "mb_size": mb_size if mb_size != "(default)" else "", # Store empty string if default
            # Unsharp Group
            "apply_unsharp": self.ffmpeg_unsharp_group.isChecked(),
            "unsharp_lx": self.ffmpeg_unsharp_lx_spinbox.value(),
            "unsharp_ly": self.ffmpeg_unsharp_ly_spinbox.value(),
            "unsharp_la": self.ffmpeg_unsharp_la_spinbox.value(),
            "unsharp_cx": self.ffmpeg_unsharp_cx_spinbox.value(),
            "unsharp_cy": self.ffmpeg_unsharp_cy_spinbox.value(),
            "unsharp_ca": self.ffmpeg_unsharp_ca_spinbox.value(),
             # Quality Group
            "preset_text": self.ffmpeg_quality_combo.currentText(), # Include the preset text itself
            "crf": self.ffmpeg_crf_spinbox.value(),
            "bitrate": self.ffmpeg_bitrate_spinbox.value(),
            "bufsize": self.ffmpeg_bufsize_spinbox.value(),
            "pix_fmt": self.ffmpeg_pix_fmt_combo.currentText(),
            "filter_preset": self.ffmpeg_filter_preset_combo.currentText(),
        }
        return settings

    def get_selected_profile_name(self) -> str:
        """Returns the name of the currently selected profile."""
        return self.ffmpeg_profile_combo.currentText()

    def load_settings(self, settings: Dict[str, Any]) -> None:
        """Loads settings into the UI elements, typically from QSettings."""
        LOGGER.debug("Loading FFmpeg settings into tab UI...")

        # Block signals during loading
        all_controls = self._get_all_setting_controls()
        for widget in all_controls:
            widget.blockSignals(True)

        try:
            # Load Profile Selection First
            profile_name = settings.get("ffmpeg_profile", "Default") # Default to "Default"
            # Ensure the profile name exists in the combo box items
            items = [self.ffmpeg_profile_combo.itemText(i) for i in range(self.ffmpeg_profile_combo.count())]
            if profile_name not in items:
                LOGGER.warning(f"Saved profile '{profile_name}' not found in combo box, defaulting to 'Custom'.")
                profile_name = "Custom"
            self.ffmpeg_profile_combo.setCurrentText(profile_name)

            # If the loaded profile is "Custom", load individual settings
            if profile_name == "Custom":
                LOGGER.debug("Loading individual custom FFmpeg settings...")
                # Interpolation
                self.ffmpeg_settings_group.setChecked(settings.get("ffmpeg_use_interp", DEFAULT_FFMPEG_PROFILE["use_ffmpeg_interp"]))
                self.ffmpeg_mi_mode_combo.setCurrentText(settings.get("ffmpeg_mi_mode", DEFAULT_FFMPEG_PROFILE["mi_mode"]))
                self.ffmpeg_mc_mode_combo.setCurrentText(settings.get("ffmpeg_mc_mode", DEFAULT_FFMPEG_PROFILE["mc_mode"]))
                self.ffmpeg_me_mode_combo.setCurrentText(settings.get("ffmpeg_me_mode", DEFAULT_FFMPEG_PROFILE["me_mode"]))
                self.ffmpeg_vsbmc_checkbox.setChecked(settings.get("ffmpeg_vsbmc", DEFAULT_FFMPEG_PROFILE["vsbmc"]))
                self.ffmpeg_scd_combo.setCurrentText(settings.get("ffmpeg_scd", DEFAULT_FFMPEG_PROFILE["scd"]))
                # Handle "(default)" vs empty string for loading
                me_algo_saved = settings.get("ffmpeg_me_algo", DEFAULT_FFMPEG_PROFILE["me_algo"])
                self.ffmpeg_me_algo_combo.setCurrentText(me_algo_saved if me_algo_saved else "(default)")
                self.ffmpeg_search_param_spinbox.setValue(settings.get("ffmpeg_search_param", DEFAULT_FFMPEG_PROFILE["search_param"]))
                self.ffmpeg_scd_threshold_spinbox.setValue(settings.get("ffmpeg_scd_threshold", DEFAULT_FFMPEG_PROFILE["scd_threshold"]))
                mb_size_saved = settings.get("ffmpeg_mb_size", DEFAULT_FFMPEG_PROFILE["mb_size"])
                self.ffmpeg_mb_size_combo.setCurrentText(mb_size_saved if mb_size_saved else "(default)")

                # Unsharp
                self.ffmpeg_unsharp_group.setChecked(settings.get("ffmpeg_apply_unsharp", DEFAULT_FFMPEG_PROFILE["apply_unsharp"]))
                self.ffmpeg_unsharp_lx_spinbox.setValue(settings.get("ffmpeg_unsharp_lx", DEFAULT_FFMPEG_PROFILE["unsharp_lx"]))
                self.ffmpeg_unsharp_ly_spinbox.setValue(settings.get("ffmpeg_unsharp_ly", DEFAULT_FFMPEG_PROFILE["unsharp_ly"]))
                self.ffmpeg_unsharp_la_spinbox.setValue(settings.get("ffmpeg_unsharp_la", DEFAULT_FFMPEG_PROFILE["unsharp_la"]))
                self.ffmpeg_unsharp_cx_spinbox.setValue(settings.get("ffmpeg_unsharp_cx", DEFAULT_FFMPEG_PROFILE["unsharp_cx"]))
                self.ffmpeg_unsharp_cy_spinbox.setValue(settings.get("ffmpeg_unsharp_cy", DEFAULT_FFMPEG_PROFILE["unsharp_cy"]))
                self.ffmpeg_unsharp_ca_spinbox.setValue(settings.get("ffmpeg_unsharp_ca", DEFAULT_FFMPEG_PROFILE["unsharp_ca"]))

                # Quality - Load the preset text first, then individual values if preset is "Custom"
                quality_preset_text = settings.get("ffmpeg_quality_preset_text", DEFAULT_FFMPEG_PROFILE["preset_text"])
                # Ensure preset text exists
                quality_items = [self.ffmpeg_quality_combo.itemText(i) for i in range(self.ffmpeg_quality_combo.count())]
                if quality_preset_text not in quality_items:
                     LOGGER.warning(f"Saved quality preset '{quality_preset_text}' not found, defaulting.")
                     quality_preset_text = DEFAULT_FFMPEG_PROFILE["preset_text"] # Or maybe "Custom"?

                self.ffmpeg_quality_combo.setCurrentText(quality_preset_text)

                # If the loaded quality preset is "Custom", load the specific values
                if quality_preset_text == "Custom":
                    self.ffmpeg_crf_spinbox.setValue(settings.get("ffmpeg_crf", DEFAULT_FFMPEG_PROFILE["crf"]))
                    self.ffmpeg_bitrate_spinbox.setValue(settings.get("ffmpeg_bitrate", DEFAULT_FFMPEG_PROFILE["bitrate"]))
                    self.ffmpeg_bufsize_spinbox.setValue(settings.get("ffmpeg_bufsize", DEFAULT_FFMPEG_PROFILE["bufsize"]))
                    self.ffmpeg_pix_fmt_combo.setCurrentText(settings.get("ffmpeg_pix_fmt", DEFAULT_FFMPEG_PROFILE["pix_fmt"]))
                # Else: _update_quality_controls_state (called later) will set values from preset

                # Filter Preset
                self.ffmpeg_filter_preset_combo.setCurrentText(settings.get("ffmpeg_filter_preset", DEFAULT_FFMPEG_PROFILE["filter_preset"]))

            # If a specific profile was loaded, apply it (this handles non-"Custom" cases)
            else:
                LOGGER.debug(f"Applying loaded profile: {profile_name}")
                self._on_profile_selected(profile_name) # Apply the loaded profile

            # --- Update control states after loading all settings ---
            self._update_all_control_states()

        except Exception as e:
            LOGGER.error(f"Error loading FFmpeg settings into UI: {e}", exc_info=True)
        finally:
            # Unblock signals
            for widget in all_controls:
                widget.blockSignals(False)

            # Re-check profile match after loading everything, in case loading custom settings
            # happened to match a predefined profile.
            QTimer.singleShot(0, self._verify_profile_match_after_load)

    def _verify_profile_match_after_load(self) -> None:
        """Checks if loaded settings match a profile and updates combo if needed."""
        current_profile_name = self.ffmpeg_profile_combo.currentText()
        if current_profile_name != "Custom":
            # If a profile was explicitly loaded, trust it unless it drifted during load somehow
            profile_dict = FFMPEG_PROFILES.get(current_profile_name)
            if profile_dict and not self._check_settings_match_profile(profile_dict):
                 LOGGER.warning(f"Settings drifted from loaded profile '{current_profile_name}' during load. Setting to 'Custom'.")
                 self.ffmpeg_profile_combo.blockSignals(True)
                 self.ffmpeg_profile_combo.setCurrentText("Custom")
                 self.ffmpeg_profile_combo.blockSignals(False)
                 self._update_quality_controls_state("Custom") # Ensure custom quality enabled
            return # Already handled or matched

        # If "Custom" was loaded, check if the loaded values actually match a profile
        matching_profile_name = None
        for name, profile_dict in FFMPEG_PROFILES.items():
            if self._check_settings_match_profile(profile_dict):
                matching_profile_name = name
                break

        if matching_profile_name:
            LOGGER.info(f"Loaded custom settings match profile '{matching_profile_name}'. Updating profile combo.")
            self.ffmpeg_profile_combo.blockSignals(True)
            self.ffmpeg_profile_combo.setCurrentText(matching_profile_name)
            self.ffmpeg_profile_combo.blockSignals(False)
            # Update quality controls based on the matched profile's preset text
            self._update_quality_controls_state(FFMPEG_PROFILES[matching_profile_name]["preset_text"])