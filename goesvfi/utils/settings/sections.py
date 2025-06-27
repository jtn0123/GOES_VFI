"""Concrete settings sections for different areas of the application.

Each section handles a focused group of related settings, reducing complexity
by organizing the massive saveSettings/loadSettings functions.
"""

import logging
from typing import Any

from goesvfi.utils.errors import ErrorClassifier

from .base import SettingsSection
from .widget_accessor import SafeWidgetAccessor

LOGGER = logging.getLogger(__name__)


class MainTabSettings(SettingsSection):
    """Settings section for main tab widgets."""

    def __init__(self, classifier: ErrorClassifier | None = None) -> None:
        super().__init__("main_tab", classifier)
        self.accessor = SafeWidgetAccessor(classifier)

    def extract_values(self, source_object: Any) -> dict[str, Any]:
        """Extract main tab settings from GUI."""
        values: dict[str, Any] = {}
        main_tab = getattr(source_object, "main_tab", None)

        if main_tab is None:
            LOGGER.warning("No main_tab found on source object")
            return values

        # Extract basic numeric settings
        values["fps"] = self.accessor.get_spinbox_value(main_tab, "fps_spinbox", 30)
        values["mid_count"] = self.accessor.get_spinbox_value(main_tab, "mid_count_spinbox", 1)
        values["max_workers"] = self.accessor.get_spinbox_value(main_tab, "max_workers_spinbox", 1)

        # Extract combo box settings
        values["encoder"] = self.accessor.get_combobox_text(main_tab, "encoder_combo", "")

        # Extract RIFE model settings (might be on main window)
        model_combo = getattr(source_object, "model_combo", None)
        if model_combo is not None:
            values["rife_model_key"] = self.accessor.safe_get_value(
                source_object, "model_combo", "currentText", default=""
            )

        # Extract RIFE configuration settings
        values["rife_tile_enable"] = self.accessor.get_checkbox_checked(main_tab, "rife_tile_checkbox", False)
        values["rife_tile_size"] = self.accessor.get_spinbox_value(main_tab, "rife_tile_size_spinbox", 256)
        values["rife_uhd_mode"] = self.accessor.get_checkbox_checked(main_tab, "rife_uhd_checkbox", False)
        values["rife_thread_spec"] = self.accessor.get_lineedit_text(main_tab, "rife_thread_spec_edit", "")
        values["rife_tta_spatial"] = self.accessor.get_checkbox_checked(main_tab, "rife_tta_spatial_checkbox", False)
        values["rife_tta_temporal"] = self.accessor.get_checkbox_checked(main_tab, "rife_tta_temporal_checkbox", False)

        return values

    def apply_values(self, target_object: Any, values: dict[str, Any]) -> None:
        """Apply main tab settings to GUI."""
        main_tab = getattr(target_object, "main_tab", None)

        if main_tab is None:
            LOGGER.warning("No main_tab found on target object")
            return

        # Apply basic numeric settings
        self.accessor.set_spinbox_value(main_tab, "fps_spinbox", values.get("fps", 30))
        self.accessor.set_spinbox_value(main_tab, "mid_count_spinbox", values.get("mid_count", 1))
        self.accessor.set_spinbox_value(main_tab, "max_workers_spinbox", values.get("max_workers", 1))

        # Apply combo box settings
        self.accessor.set_combobox_text(main_tab, "encoder_combo", values.get("encoder", ""))

        # Apply RIFE model settings
        model_combo = getattr(target_object, "model_combo", None)
        if model_combo is not None:
            self.accessor.safe_set_value(
                target_object,
                "model_combo",
                values.get("rife_model_key", ""),
                "setCurrentText",
            )

        # Apply RIFE configuration settings
        self.accessor.set_checkbox_checked(main_tab, "rife_tile_checkbox", values.get("rife_tile_enable", False))
        self.accessor.set_spinbox_value(main_tab, "rife_tile_size_spinbox", values.get("rife_tile_size", 256))
        self.accessor.set_checkbox_checked(main_tab, "rife_uhd_checkbox", values.get("rife_uhd_mode", False))
        self.accessor.set_lineedit_text(main_tab, "rife_thread_spec_edit", values.get("rife_thread_spec", ""))
        self.accessor.set_checkbox_checked(main_tab, "rife_tta_spatial_checkbox", values.get("rife_tta_spatial", False))
        self.accessor.set_checkbox_checked(
            main_tab,
            "rife_tta_temporal_checkbox",
            values.get("rife_tta_temporal", False),
        )

    def get_setting_keys(self) -> list[str]:
        """Get list of settings keys handled by this section."""
        return [
            "fps",
            "mid_count",
            "max_workers",
            "encoder",
            "rife_model_key",
            "rife_tile_enable",
            "rife_tile_size",
            "rife_uhd_mode",
            "rife_thread_spec",
            "rife_tta_spatial",
            "rife_tta_temporal",
        ]


class SanchezSettings(SettingsSection):
    """Settings section for Sanchez-related widgets."""

    def __init__(self, classifier: ErrorClassifier | None = None) -> None:
        super().__init__("sanchez", classifier)
        self.accessor = SafeWidgetAccessor(classifier)

    def extract_values(self, source_object: Any) -> dict[str, Any]:
        """Extract Sanchez settings from GUI."""
        values: dict[str, Any] = {}
        main_tab = getattr(source_object, "main_tab", None)

        if main_tab is None:
            LOGGER.warning("No main_tab found for Sanchez settings")
            return values

        # Extract Sanchez settings
        values["sanchez_false_colour"] = self.accessor.get_checkbox_checked(
            main_tab, "sanchez_false_colour_checkbox", False
        )

        # Handle resolution combo (might be aliased)
        sanchez_res_combo = getattr(source_object, "sanchez_res_km_combo", None)
        if sanchez_res_combo is not None:
            values["sanchez_res_km"] = self.accessor.safe_get_value(
                source_object, "sanchez_res_km_combo", "currentText", default=""
            )

        return values

    def apply_values(self, target_object: Any, values: dict[str, Any]) -> None:
        """Apply Sanchez settings to GUI."""
        main_tab = getattr(target_object, "main_tab", None)

        if main_tab is None:
            LOGGER.warning("No main_tab found for Sanchez settings")
            return

        # Apply Sanchez settings
        self.accessor.set_checkbox_checked(
            main_tab,
            "sanchez_false_colour_checkbox",
            values.get("sanchez_false_colour", False),
        )

        # Handle resolution combo
        sanchez_res_combo = getattr(target_object, "sanchez_res_km_combo", None)
        if sanchez_res_combo is not None:
            self.accessor.safe_set_value(
                target_object,
                "sanchez_res_km_combo",
                values.get("sanchez_res_km", ""),
                "setCurrentText",
            )

    def get_setting_keys(self) -> list[str]:
        """Get list of settings keys handled by this section."""
        return ["sanchez_false_colour", "sanchez_res_km"]


class FFmpegSettings(SettingsSection):
    """Settings section for FFmpeg-related widgets."""

    def __init__(self, classifier: ErrorClassifier | None = None) -> None:
        super().__init__("ffmpeg", classifier)
        self.accessor = SafeWidgetAccessor(classifier)

    def extract_values(self, source_object: Any) -> dict[str, Any]:
        """Extract FFmpeg settings from GUI."""
        values: dict[str, Any] = {}
        ffmpeg_tab = getattr(source_object, "ffmpeg_settings_tab", None)

        if ffmpeg_tab is None:
            LOGGER.warning("No ffmpeg_settings_tab found on source object")
            return values

        # Extract FFmpeg settings
        values["ffmpeg_use_interp"] = self.accessor.get_checkbox_checked(
            ffmpeg_tab, "use_ffmpeg_interp_checkbox", False
        )

        # Extract combo box settings
        values["ffmpeg_filter_preset"] = self.accessor.get_combobox_text(ffmpeg_tab, "ffmpeg_filter_preset_combo", "")
        values["ffmpeg_mi_mode"] = self.accessor.get_combobox_text(ffmpeg_tab, "mi_mode_combo", "")
        values["ffmpeg_mc_mode"] = self.accessor.get_combobox_text(ffmpeg_tab, "mc_mode_combo", "")
        values["ffmpeg_me_mode"] = self.accessor.get_combobox_text(ffmpeg_tab, "me_mode_combo", "")
        values["ffmpeg_me_algo"] = self.accessor.get_combobox_text(ffmpeg_tab, "me_algo_combo", "")
        values["ffmpeg_scd_mode"] = self.accessor.get_combobox_text(ffmpeg_tab, "scd_combo", "")

        # Extract numeric settings
        values["ffmpeg_search_param"] = self.accessor.get_spinbox_value(ffmpeg_tab, "search_param_spinbox", 0)

        return values

    def apply_values(self, target_object: Any, values: dict[str, Any]) -> None:
        """Apply FFmpeg settings to GUI."""
        ffmpeg_tab = getattr(target_object, "ffmpeg_settings_tab", None)

        if ffmpeg_tab is None:
            LOGGER.warning("No ffmpeg_settings_tab found on target object")
            return

        # Apply FFmpeg settings
        self.accessor.set_checkbox_checked(
            ffmpeg_tab,
            "use_ffmpeg_interp_checkbox",
            values.get("ffmpeg_use_interp", False),
        )

        # Apply combo box settings
        self.accessor.set_combobox_text(
            ffmpeg_tab,
            "ffmpeg_filter_preset_combo",
            values.get("ffmpeg_filter_preset", ""),
        )
        self.accessor.set_combobox_text(ffmpeg_tab, "mi_mode_combo", values.get("ffmpeg_mi_mode", ""))
        self.accessor.set_combobox_text(ffmpeg_tab, "mc_mode_combo", values.get("ffmpeg_mc_mode", ""))
        self.accessor.set_combobox_text(ffmpeg_tab, "me_mode_combo", values.get("ffmpeg_me_mode", ""))
        self.accessor.set_combobox_text(ffmpeg_tab, "me_algo_combo", values.get("ffmpeg_me_algo", ""))
        self.accessor.set_combobox_text(ffmpeg_tab, "scd_combo", values.get("ffmpeg_scd_mode", ""))

        # Apply numeric settings
        self.accessor.set_spinbox_value(ffmpeg_tab, "search_param_spinbox", values.get("ffmpeg_search_param", 0))

    def get_setting_keys(self) -> list[str]:
        """Get list of settings keys handled by this section."""
        return [
            "ffmpeg_use_interp",
            "ffmpeg_filter_preset",
            "ffmpeg_mi_mode",
            "ffmpeg_mc_mode",
            "ffmpeg_me_mode",
            "ffmpeg_me_algo",
            "ffmpeg_scd_mode",
            "ffmpeg_search_param",
        ]


class BasicSettings(SettingsSection):
    """Settings section for basic non-widget settings."""

    def __init__(self, classifier: ErrorClassifier | None = None) -> None:
        super().__init__("basic", classifier)

    def extract_values(self, source_object: Any) -> dict[str, Any]:
        """Extract basic settings that don't require widget access."""
        values = {}

        # Extract basic path settings
        in_dir = getattr(source_object, "in_dir", None)
        values["in_dir"] = str(in_dir) if in_dir else ""

        out_file_path = getattr(source_object, "out_file_path", None)
        values["out_file_path"] = str(out_file_path) if out_file_path else ""

        # Extract crop rectangle
        crop_rect = getattr(source_object, "current_crop_rect", None)
        if crop_rect:
            x, y, w, h = crop_rect
            values["crop_rect"] = f"{x},{y},{w},{h}"
        else:
            values["crop_rect"] = ""

        return values

    def apply_values(self, target_object: Any, values: dict[str, Any]) -> None:
        """Apply basic settings to object."""
        from pathlib import Path

        # Apply settings with proper type conversion
        in_dir_str = values.get("in_dir", "")
        if in_dir_str and hasattr(target_object, "in_dir"):
            input_path = Path(in_dir_str)
            # Only set the path if it exists and is a directory
            if input_path.exists() and input_path.is_dir():
                target_object.in_dir = input_path
            else:
                LOGGER.warning("Input directory does not exist, skipping: %s", in_dir_str)
                target_object.in_dir = None

        out_file_path_str = values.get("out_file_path", "")
        if out_file_path_str and hasattr(target_object, "out_file_path"):
            target_object.out_file_path = Path(out_file_path_str)

        # Handle crop rect
        crop_rect_str = values.get("crop_rect", "")
        if crop_rect_str and hasattr(target_object, "current_crop_rect"):
            try:
                parts = crop_rect_str.split(",")
                if len(parts) == 4:
                    crop_rect = tuple(int(p) for p in parts)
                    target_object.current_crop_rect = crop_rect
            except (ValueError, AttributeError):
                LOGGER.warning("Failed to parse crop_rect: %s", crop_rect_str)

    def get_setting_keys(self) -> list[str]:
        """Get list of settings keys handled by this section."""
        return ["in_dir", "out_file_path", "crop_rect"]
