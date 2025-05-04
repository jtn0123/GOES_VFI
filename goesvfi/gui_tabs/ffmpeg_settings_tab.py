
# goesvfi/gui_tabs/ffmpeg_settings_tab.py
from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Optional, Any, Dict, List, TypedDict, cast

from PyQt6.QtCore import pyqtSignal, pyqtBoundSignal, Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGroupBox,
    QComboBox,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
)

# Avoid circular import if MainWindow is type hinted
if TYPE_CHECKING:
    from goesvfi.gui import MainWindow # Assuming MainWindow is in gui.py

# Setup logger
# Note: Using the same logger name as in gui.py might merge logs,
# or consider a specific logger like get_logger(__name__)
from goesvfi.utils import log
LOGGER = log.get_logger("goesvfi.gui") # Or use __name__

# Define TypedDict for profile structure
class FfmpegProfile(TypedDict):
    use_ffmpeg_interp: bool # Added this key based on usage in _check_settings_match_profile
    mi_mode: str
    mc_mode: str
    me_mode: str
    vsbmc: bool
    scd: str
    me_algo: str
    search_param: int
    scd_threshold: float
    mb_size: str
    apply_unsharp: bool
    unsharp_lx: int
    unsharp_ly: int
    unsharp_la: float
    unsharp_cx: int
    unsharp_cy: int
    unsharp_ca: float
    preset_text: str # Used for setting quality combo, but not directly compared? Check _check_settings_match_profile
    crf: int
    bitrate: int
    bufsize: int
    pix_fmt: str
    filter_preset: str

# Define the profiles (copied from gui.py)
OPTIMAL_FFMPEG_PROFILE: FfmpegProfile = {
    "use_ffmpeg_interp": True, "mi_mode": "mci", "mc_mode": "aobmc", "me_mode": "bidir",
    "vsbmc": True, "scd": "none", "me_algo": "(default)", "search_param": 96,
    "scd_threshold": 10.0, "mb_size": "(default)", "apply_unsharp": False,
    "unsharp_lx": 7, "unsharp_ly": 7, "unsharp_la": 1.0, "unsharp_cx": 5,
    "unsharp_cy": 5, "unsharp_ca": 0.0, "preset_text": "Very High (CRF 16)",
    "crf": 16, "bitrate": 15000, "bufsize": 22500, "pix_fmt": "yuv444p",
    "filter_preset": "slow",
}
OPTIMAL_FFMPEG_PROFILE_2: FfmpegProfile = {
    "use_ffmpeg_interp": True, "mi_mode": "mci", "mc_mode": "aobmc", "me_mode": "bidir",
    "vsbmc": True, "scd": "none", "me_algo": "epzs", "search_param": 32,
    "scd_threshold": 10.0, "mb_size": "(default)", "apply_unsharp": False,
    "unsharp_lx": 7, "unsharp_ly": 7, "unsharp_la": 1.0, "unsharp_cx": 5,
    "unsharp_cy": 5, "unsharp_ca": 0.0, "preset_text": "Medium (CRF 20)",
    "crf": 20, "bitrate": 10000, "bufsize": 15000, "pix_fmt": "yuv444p",
    "filter_preset": "medium",
}
DEFAULT_FFMPEG_PROFILE: FfmpegProfile = {
    "use_ffmpeg_interp": True, "mi_mode": "mci", "mc_mode": "obmc", "me_mode": "bidir",
    "vsbmc": False, "scd": "fdiff", "me_algo": "(default)", "search_param": 96,
    "scd_threshold": 10.0, "mb_size": "(default)", "apply_unsharp": True,
    "unsharp_lx": 7, "unsharp_ly": 7, "unsharp_la": 1.0, "unsharp_cx": 5,
    "unsharp_cy": 5, "unsharp_ca": 0.0, "preset_text": "Very High (CRF 16)",
    "crf": 16, "bitrate": 15000, "bufsize": 22500, "pix_fmt": "yuv444p",
    "filter_preset": "slow",
}
FFMPEG_PROFILES: Dict[str, FfmpegProfile] = {
    "Default": DEFAULT_FFMPEG_PROFILE,
    "Optimal": OPTIMAL_FFMPEG_PROFILE,
    "Optimal 2": OPTIMAL_FFMPEG_PROFILE_2,
}


class FFmpegSettingsTab(QWidget):
    """QWidget containing the settings for FFmpeg interpolation and encoding."""

    request_previews_update: pyqtBoundSignal # Explicit type hint for the instance attribute

    def __init__(
        self,
        # Pass widgets and signals from MainWindow
        ffmpeg_settings_group: QGroupBox,
        ffmpeg_unsharp_group: QGroupBox,
        ffmpeg_quality_group: QGroupBox,
        ffmpeg_profile_combo: QComboBox,
        ffmpeg_mi_mode_combo: QComboBox,
        ffmpeg_mc_mode_combo: QComboBox,
        ffmpeg_me_mode_combo: QComboBox,
        ffmpeg_vsbmc_checkbox: QCheckBox,
        ffmpeg_scd_combo: QComboBox,
        ffmpeg_me_algo_edit: QLineEdit,
        ffmpeg_search_param_spinbox: QSpinBox,
        ffmpeg_scd_threshold_spinbox: QDoubleSpinBox,
        ffmpeg_mb_size_edit: QLineEdit,
        ffmpeg_unsharp_lx_spinbox: QSpinBox,
        ffmpeg_unsharp_ly_spinbox: QSpinBox,
        ffmpeg_unsharp_la_spinbox: QDoubleSpinBox,
        ffmpeg_unsharp_cx_spinbox: QSpinBox,
        ffmpeg_unsharp_cy_spinbox: QSpinBox,
        ffmpeg_unsharp_ca_spinbox: QDoubleSpinBox,
        ffmpeg_quality_combo: QComboBox,
        ffmpeg_crf_spinbox: QSpinBox,
        ffmpeg_bitrate_spinbox: QSpinBox,
        ffmpeg_bufsize_spinbox: QSpinBox,
        ffmpeg_pix_fmt_combo: QComboBox,
        ffmpeg_filter_preset_combo: QComboBox,
        in_dir_edit: QLineEdit,
        mid_count_spinbox: QSpinBox,
        encoder_combo: QComboBox,
        rife_model_combo: QComboBox,
        sanchez_false_colour_checkbox: QCheckBox,
        sanchez_res_combo: QComboBox, # Corrected based on gui.py
        request_previews_update: pyqtBoundSignal, # Pass the signal (bound signal)
        parent: Optional[QWidget] = None,
    ):
        """
        Initialize the FFmpegSettingsTab.

        Args:
            # List of widgets and signals passed from MainWindow
            ffmpeg_settings_group: The FFmpeg settings group box.
            ffmpeg_unsharp_group: The FFmpeg unsharp settings group box.
            ffmpeg_quality_group: The FFmpeg quality settings group box.
            ffmpeg_profile_combo: The FFmpeg profile combo box.
            ffmpeg_mi_mode_combo: The FFmpeg MI mode combo box.
            ffmpeg_mc_mode_combo: The FFmpeg MC mode combo box.
            ffmpeg_me_mode_combo: The FFmpeg ME mode combo box.
            ffmpeg_vsbmc_checkbox: The FFmpeg VSBMC checkbox.
            ffmpeg_scd_combo: The FFmpeg SCD mode combo box.
            ffmpeg_me_algo_edit: The FFmpeg ME algorithm line edit.
            ffmpeg_search_param_spinbox: The FFmpeg search parameter spin box.
            ffmpeg_scd_threshold_spinbox: The FFmpeg SCD threshold spin box.
            ffmpeg_mb_size_edit: The FFmpeg MB size line edit.
            ffmpeg_unsharp_lx_spinbox: The FFmpeg unsharp LX spin box.
            ffmpeg_unsharp_ly_spinbox: The FFmpeg unsharp LY spin box.
            ffmpeg_unsharp_la_spinbox: The FFmpeg unsharp LA spin box.
            ffmpeg_unsharp_cx_spinbox: The FFmpeg unsharp CX spin box.
            ffmpeg_unsharp_cy_spinbox: The FFmpeg unsharp CY spin box.
            ffmpeg_unsharp_ca_spinbox: The FFmpeg unsharp CA spin box.
            ffmpeg_quality_combo: The FFmpeg quality combo box.
            ffmpeg_crf_spinbox: The FFmpeg CRF spin box.
            ffmpeg_bitrate_spinbox: The FFmpeg bitrate spin box.
            ffmpeg_bufsize_spinbox: The FFmpeg bufsize spin box.
            ffmpeg_pix_fmt_combo: The FFmpeg pixel format combo box.
            ffmpeg_filter_preset_combo: The FFmpeg filter preset combo box.
            in_dir_edit: The input directory line edit from MainTab.
            mid_count_spinbox: The mid frames spin box from MainTab.
            encoder_combo: The encoder combo box from MainTab.
            rife_model_combo: The RIFE model combo box from MainTab.
            sanchez_false_colour_checkbox: The Sanchez false colour checkbox from MainTab.
            sanchez_res_combo: The Sanchez resolution combo box from MainTab.
            request_previews_update: The signal to request preview updates from MainWindow.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        # Store references to widgets and signals passed from MainWindow
        self.ffmpeg_settings_group = ffmpeg_settings_group
        self.ffmpeg_unsharp_group = ffmpeg_unsharp_group
        self.ffmpeg_quality_group = ffmpeg_quality_group
        self.ffmpeg_profile_combo = ffmpeg_profile_combo
        self.ffmpeg_mi_mode_combo = ffmpeg_mi_mode_combo
        self.ffmpeg_mc_mode_combo = ffmpeg_mc_mode_combo
        self.ffmpeg_me_mode_combo = ffmpeg_me_mode_combo
        self.ffmpeg_vsbmc_checkbox = ffmpeg_vsbmc_checkbox
        self.ffmpeg_scd_combo = ffmpeg_scd_combo
        self.ffmpeg_me_algo_edit = ffmpeg_me_algo_edit
        self.ffmpeg_search_param_spinbox = ffmpeg_search_param_spinbox
        self.ffmpeg_scd_threshold_spinbox = ffmpeg_scd_threshold_spinbox
        self.ffmpeg_mb_size_edit = ffmpeg_mb_size_edit
        self.ffmpeg_unsharp_lx_spinbox = ffmpeg_unsharp_lx_spinbox
        self.ffmpeg_unsharp_ly_spinbox = ffmpeg_unsharp_ly_spinbox
        self.ffmpeg_unsharp_la_spinbox = ffmpeg_unsharp_la_spinbox
        self.ffmpeg_unsharp_cx_spinbox = ffmpeg_unsharp_cx_spinbox
        self.ffmpeg_unsharp_cy_spinbox = ffmpeg_unsharp_cy_spinbox
        self.ffmpeg_ca_spinbox = ffmpeg_unsharp_ca_spinbox
        self.ffmpeg_quality_combo = ffmpeg_quality_combo
        self.ffmpeg_crf_spinbox = ffmpeg_crf_spinbox
        self.ffmpeg_bitrate_spinbox = ffmpeg_bitrate_spinbox
        self.ffmpeg_bufsize_spinbox = ffmpeg_bufsize_spinbox
        self.ffmpeg_pix_fmt_combo = ffmpeg_pix_fmt_combo
        self.ffmpeg_filter_preset_combo = ffmpeg_filter_preset_combo
        self.in_dir_edit = in_dir_edit
        self.mid_count_spinbox = mid_count_spinbox
        self.encoder_combo = encoder_combo
        self.rife_model_combo = rife_model_combo
        self.sanchez_false_colour_checkbox = sanchez_false_colour_checkbox
        self.sanchez_res_combo = sanchez_res_combo # Use the passed combo box
        self.request_previews_update = request_previews_update # Assign the passed signal

        # Setup layout using the passed group boxes
        layout = QVBoxLayout(self)
        layout.addWidget(self.ffmpeg_settings_group)
        layout.addWidget(self.ffmpeg_unsharp_group)
        layout.addWidget(self.ffmpeg_quality_group)
        layout.addStretch() # Add stretch to push groups to the top
        self.setLayout(layout)

        # Connect signals for this tab
        self._connect_signals()
        # Connect the profile combo box signal separately
        self.ffmpeg_profile_combo.currentTextChanged.connect(self._on_profile_selected)


    def _connect_signals(self) -> None:
        """Connect signals for enabling/disabling controls and profile handling."""
        # Connect signals for FFmpeg settings controls to update profile combo to "Custom"
        # Access widgets via self references
        controls_to_monitor = [
            self.ffmpeg_mi_mode_combo,
            self.ffmpeg_mc_mode_combo,
            self.ffmpeg_me_mode_combo,
            self.ffmpeg_vsbmc_checkbox,
            self.ffmpeg_scd_combo,
            self.ffmpeg_me_algo_edit,
            self.ffmpeg_search_param_spinbox,
            self.ffmpeg_scd_threshold_spinbox,
            self.ffmpeg_mb_size_edit,
            self.ffmpeg_unsharp_group, # Monitor the group check state
            self.ffmpeg_unsharp_lx_spinbox,
            self.ffmpeg_unsharp_ly_spinbox,
            self.ffmpeg_unsharp_la_spinbox,
            self.ffmpeg_unsharp_cx_spinbox,
            self.ffmpeg_unsharp_cy_spinbox,
            self.ffmpeg_ca_spinbox,
            self.ffmpeg_quality_combo, # Monitoring this will set Custom if user picks Custom
            self.ffmpeg_crf_spinbox,
            self.ffmpeg_bitrate_spinbox,
            self.ffmpeg_bufsize_spinbox,
            self.ffmpeg_pix_fmt_combo,
            self.ffmpeg_filter_preset_combo,
        ]

        for control in controls_to_monitor:
            # Ensure control exists before connecting
            if control is None:
                LOGGER.warning(f"Control reference is None during signal connection.")
                continue

            if isinstance(control, (QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox)):
                if hasattr(control, 'currentTextChanged'):
                    control.currentTextChanged.connect(self._on_ffmpeg_setting_changed)
                elif hasattr(control, 'textChanged'):
                    control.textChanged.connect(self._on_ffmpeg_setting_changed)
                elif hasattr(control, 'valueChanged'):
                    control.valueChanged.connect(self._on_ffmpeg_setting_changed)
            elif isinstance(control, QCheckBox):
                 control.stateChanged.connect(self._on_ffmpeg_setting_changed)
            elif isinstance(control, QGroupBox):
                 control.toggled.connect(self._on_ffmpeg_setting_changed) # Connect toggled signal

        # Connect signals that should trigger a preview update when changed
        # Access widgets via self references
        preview_update_controls = [
            self.in_dir_edit,
            self.mid_count_spinbox,
            self.encoder_combo,
            self.rife_model_combo, # Changing RIFE model affects preview
            self.sanchez_false_colour_checkbox, # Sanchez settings affect preview
            self.sanchez_res_combo, # Sanchez settings affect preview
            # FFmpeg interpolation settings also affect preview
            self.ffmpeg_mi_mode_combo,
            self.ffmpeg_mc_mode_combo,
            self.ffmpeg_me_mode_combo,
            self.ffmpeg_vsbmc_checkbox,
            self.ffmpeg_scd_combo,
            self.ffmpeg_me_algo_edit,
            self.ffmpeg_search_param_spinbox,
            self.ffmpeg_scd_threshold_spinbox,
            self.ffmpeg_mb_size_edit,
            self.ffmpeg_unsharp_group, # Unsharp affects preview
            self.ffmpeg_unsharp_lx_spinbox,
            self.ffmpeg_unsharp_ly_spinbox,
            self.ffmpeg_unsharp_la_spinbox,
            self.ffmpeg_unsharp_cx_spinbox,
            self.ffmpeg_unsharp_cy_spinbox,
            self.ffmpeg_ca_spinbox,
        ]

        for control in preview_update_controls:
             # Ensure control exists before connecting
            if control is None:
                LOGGER.warning(f"Control reference is None during preview signal connection.")
                continue

            # Access the signal via self reference
            preview_signal = self.request_previews_update

            if isinstance(control, (QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox)):
                if hasattr(control, 'currentTextChanged'):
                    control.currentTextChanged.connect(self._emit_preview_update_signal)
                elif hasattr(control, 'textChanged'):
                    control.textChanged.connect(self._emit_preview_update_signal)
                elif hasattr(control, 'valueChanged'):
                    control.valueChanged.connect(self._emit_preview_update_signal)
            elif isinstance(control, QCheckBox):
                 control.stateChanged.connect(self._emit_preview_update_signal)
            elif isinstance(control, QGroupBox):
                 control.toggled.connect(self._emit_preview_update_signal)

    def _emit_preview_update_signal(self, *args: Any) -> None:
        """Slot to emit the request_previews_update signal."""
        self.request_previews_update.emit()

    def _on_profile_selected(self, profile_name: str) -> None:
        LOGGER.debug(f"Entering _on_profile_selected... profile_name={profile_name}")
        """Load settings from the selected FFmpeg profile."""
        if profile_name == "Custom":
            # Do nothing, settings are already custom
            return

        profile_dict = FFMPEG_PROFILES.get(profile_name)
        if not profile_dict:
            LOGGER.warning(f"Unknown FFmpeg profile selected: {profile_name}")
            return

        # Block signals while updating widgets to prevent _on_ffmpeg_setting_changed from firing
        # Access widgets via self references
        widgets_to_block = [
            self.ffmpeg_mi_mode_combo,
            self.ffmpeg_mc_mode_combo,
            self.ffmpeg_me_mode_combo,
            self.ffmpeg_vsbmc_checkbox,
            self.ffmpeg_scd_combo,
            self.ffmpeg_me_algo_edit,
            self.ffmpeg_search_param_spinbox,
            self.ffmpeg_scd_threshold_spinbox,
            self.ffmpeg_mb_size_edit,
            self.ffmpeg_unsharp_group,
            self.ffmpeg_unsharp_lx_spinbox,
            self.ffmpeg_unsharp_ly_spinbox,
            self.ffmpeg_unsharp_la_spinbox,
            self.ffmpeg_unsharp_cx_spinbox,
            self.ffmpeg_unsharp_cy_spinbox,
            self.ffmpeg_ca_spinbox,
            self.ffmpeg_quality_combo,
            self.ffmpeg_crf_spinbox,
            self.ffmpeg_bitrate_spinbox,
            self.ffmpeg_bufsize_spinbox,
            self.ffmpeg_pix_fmt_combo,
            self.ffmpeg_filter_preset_combo,
        ]

        for widget in widgets_to_block:
            if widget: # Check if widget exists
                widget.blockSignals(True)

        try:
            # Update interpolation settings
            self.ffmpeg_mi_mode_combo.setCurrentText(profile_dict["mi_mode"])
            self.ffmpeg_mc_mode_combo.setCurrentText(profile_dict["mc_mode"])
            self.ffmpeg_me_mode_combo.setCurrentText(profile_dict["me_mode"])
            self.ffmpeg_vsbmc_checkbox.setChecked(profile_dict["vsbmc"])
            self.ffmpeg_scd_combo.setCurrentText(profile_dict["scd"])
            self.ffmpeg_me_algo_edit.setText(profile_dict["me_algo"])
            self.ffmpeg_search_param_spinbox.setValue(profile_dict["search_param"])
            self.ffmpeg_scd_threshold_spinbox.setValue(profile_dict["scd_threshold"])
            self.ffmpeg_mb_size_edit.setText(profile_dict["mb_size"])

            # Update unsharp settings
            self.ffmpeg_unsharp_group.setChecked(profile_dict["apply_unsharp"])
            self.ffmpeg_unsharp_lx_spinbox.setValue(profile_dict["unsharp_lx"])
            self.ffmpeg_unsharp_ly_spinbox.setValue(profile_dict["unsharp_ly"])
            self.ffmpeg_unsharp_la_spinbox.setValue(profile_dict["unsharp_la"])
            self.ffmpeg_unsharp_cx_spinbox.setValue(profile_dict["unsharp_cx"])
            self.ffmpeg_unsharp_cy_spinbox.setValue(profile_dict["unsharp_cy"])
            self.ffmpeg_ca_spinbox.setValue(profile_dict["unsharp_ca"])

            # Update quality settings
            self.ffmpeg_quality_combo.setCurrentText(profile_dict["preset_text"])
            # Setting the quality combo text should trigger _update_quality_controls_state in MainWindow
            # which handles setting CRF/Bitrate/Bufsize/PixFmt based on the preset text.

            self.ffmpeg_filter_preset_combo.setCurrentText(profile_dict["filter_preset"])

        finally:
            # Unblock signals
            for widget in widgets_to_block:
                 if widget: # Check if widget exists
                    widget.blockSignals(False)

        # After loading a profile, check if the current settings still match the loaded profile
        # If they don't, the profile combo should revert to "Custom".
        # Access profile combo via self reference
        if not self._check_settings_match_profile(profile_dict):
             LOGGER.debug(f"Current settings do not match profile '{profile_name}', setting profile combo to 'Custom'.")
             self.ffmpeg_profile_combo.setCurrentText("Custom")
        else:
             LOGGER.debug(f"Current settings match profile '{profile_name}'.")


    def _on_ffmpeg_setting_changed(self, *args: Any) -> None:
        LOGGER.debug("Entering _on_ffmpeg_setting_changed...")
        """Handle changes to FFmpeg settings to set the profile combo to 'Custom'."""
        # Check if the current settings match any known profile
        matching_profile_name = None
        for name, profile_dict in FFMPEG_PROFILES.items():
            if self._check_settings_match_profile(profile_dict):
                matching_profile_name = name
                break

        # Access profile combo via self reference
        profile_combo = self.ffmpeg_profile_combo

        # If settings match a profile, set the combo box to that profile
        if matching_profile_name and profile_combo.currentText() != matching_profile_name:
            LOGGER.debug(f"Settings match profile '{matching_profile_name}', setting profile combo.")
            profile_combo.blockSignals(True) # Block to prevent re-triggering
            profile_combo.setCurrentText(matching_profile_name)
            profile_combo.blockSignals(False)
        # If settings don't match any profile and the current text is not already "Custom", set it to "Custom"
        elif not matching_profile_name and profile_combo.currentText() != "Custom":
            LOGGER.debug("Settings do not match any profile, setting profile combo to 'Custom'.")
            # No need to block signals here, just set the text if it's not already "Custom"
            # Avoid infinite loops by checking current text first.
            if profile_combo.currentText() != "Custom":
                 profile_combo.blockSignals(True)
                 profile_combo.setCurrentText("Custom")
                 profile_combo.blockSignals(False)


    def _check_settings_match_profile(self, profile_dict: FfmpegProfile) -> bool:
        """Checks if current FFmpeg settings match a given profile dictionary."""
        # Access widgets via self references
        # Note: This rebuilds the settings dict every time. Consider caching if performance is an issue.
        try:
            current_settings = {
                # Interpolation Group
                "use_ffmpeg_interp": self.ffmpeg_settings_group.isChecked(), # Assuming the main group is checkable
                "mi_mode": self.ffmpeg_mi_mode_combo.currentText(),
                "mc_mode": self.ffmpeg_mc_mode_combo.currentText(),
                "me_mode": self.ffmpeg_me_mode_combo.currentText(),
                "vsbmc": self.ffmpeg_vsbmc_checkbox.isChecked(),
                "scd": self.ffmpeg_scd_combo.currentText(), # Key name in profile is 'scd'
                "me_algo": self.ffmpeg_me_algo_edit.text(),
                "search_param": self.ffmpeg_search_param_spinbox.value(),
                "scd_threshold": self.ffmpeg_scd_threshold_spinbox.value(),
                "mb_size": self.ffmpeg_mb_size_edit.text(),
                # Unsharp Group
                "apply_unsharp": self.ffmpeg_unsharp_group.isChecked(),
                "unsharp_lx": self.ffmpeg_unsharp_lx_spinbox.value(),
                "unsharp_ly": self.ffmpeg_unsharp_ly_spinbox.value(),
                "unsharp_la": self.ffmpeg_unsharp_la_spinbox.value(),
                "unsharp_cx": self.ffmpeg_unsharp_cx_spinbox.value(),
                "unsharp_cy": self.ffmpeg_unsharp_cy_spinbox.value(),
                "unsharp_ca": self.ffmpeg_ca_spinbox.value(),
                 # Quality Group
                "crf": self.ffmpeg_crf_spinbox.value(),
                "bitrate": self.ffmpeg_bitrate_spinbox.value(),
                "bufsize": self.ffmpeg_bufsize_spinbox.value(),
                "pix_fmt": self.ffmpeg_pix_fmt_combo.currentText(),
                "filter_preset": self.ffmpeg_filter_preset_combo.currentText(),
                # "preset_text" is derived, not a direct widget value, so exclude from current_settings
            }
        except AttributeError as e:
             LOGGER.error(f"Error accessing widget reference in _check_settings_match_profile: {e}. Ensure all widgets were passed correctly.")
             return False # Cannot compare if widgets are missing

        # Compare current settings with the profile dictionary
        # Explicitly list keys from FfmpegProfile *excluding* 'preset_text'
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
                 LOGGER.warning(f"Key '{key}' in profile but not in current settings dict.")
                 return False # Should not happen if dict construction is correct

            current_value = current_settings[key]
            # Use cast to satisfy type checker for TypedDict access
            profile_value = cast(Any, profile_dict[key]) # type: ignore[literal-required]

            # Special handling for float comparison
            if key == "scd_threshold":
                # Compare only if scd is not "none" in *both* current and profile
                current_scd_mode = current_settings.get("scd")
                profile_scd_mode = profile_dict.get("scd")

                # Only compare threshold if both modes are not 'none' and values exist
                if current_scd_mode != "none" and profile_scd_mode != "none":
                    # Ensure values are not None before attempting float conversion
                    if current_value is not None and profile_value is not None:
                        try:
                            # Attempt conversion and comparison
                            # Explicitly cast to str before float for type safety
                            if abs(float(str(current_value)) - float(str(profile_value))) > 1e-9:
                                LOGGER.debug(f"Mismatch on '{key}': Current={current_value}, Profile={profile_value}")
                                return False
                        except (ValueError, TypeError) as e:
                            # Log error if conversion fails, indicating unexpected data type
                            LOGGER.error(f"Error converting scd_threshold values to float: {e}. Current={current_value}, Profile={profile_value}")
                            return False # Treat conversion error as a mismatch
                    elif current_value is not None or profile_value is not None:
                        # If one value exists but the other doesn't, it's a mismatch
                        LOGGER.debug(f"Mismatch on '{key}': One value is None. Current={current_value}, Profile={profile_value}")
                        return False
                    # If both are None, they match in this context (though potentially problematic)

                elif current_scd_mode != profile_scd_mode: # One is "none", the other isn't
                    LOGGER.debug(f"Mismatch on '{key}' (due to scd mode): Current={current_value} (scd={current_scd_mode}), Profile={profile_value} (scd={profile_scd_mode})")
                    return False
                # If both are "none", threshold doesn't matter, continue loop
            # Special handling for me_algo and mb_size "(default)" vs empty string
            elif key in ["me_algo", "mb_size"]:
                 current_norm = "" if current_value == "(default)" else current_value
                 profile_norm = "" if profile_value == "(default)" else profile_value
                 if current_norm != profile_norm:
                      LOGGER.debug(f"Mismatch on '{key}': Current={current_value} (norm={current_norm}), Profile={profile_value} (norm={profile_norm})")
                      return False
            # Direct comparison for other keys (handle potential type differences if necessary)
            elif str(current_value) != str(profile_value):
                LOGGER.debug(f"Mismatch on '{key}': Current={current_value} (type={type(current_value)}), Profile={profile_value} (type={type(profile_value)})")
                return False

        LOGGER.debug(f"Settings match profile '{profile_dict.get('preset_text', 'Unknown')}'")
        return True # All settings match