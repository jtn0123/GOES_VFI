"""RIFE UI elements management for the GUI."""

from typing import Any

from goesvfi.utils import config, log
from goesvfi.utils.gui_helpers import RifeCapabilityManager

LOGGER = log.get_logger(__name__)


class RifeUIManager:
    """Manages RIFE-specific UI element updates."""

    def update_rife_ui_elements(
        self,
        main_tab: Any,
        current_encoder: str,
        current_model_key: str,
        ffmpeg_settings_tab: Any,
    ) -> None:
        """Updates the visibility and state of RIFE-specific UI elements.

        Args:
            main_tab: The MainTab instance
            current_encoder: Current encoder selection
            current_model_key: Current RIFE model key
            ffmpeg_settings_tab: The FFmpeg settings tab instance
        """
        LOGGER.debug("Entering _update_rife_ui_elements...")
        is_rife = current_encoder == "RIFE"
        is_ffmpeg = current_encoder == "FFmpeg"

        # Toggle visibility of RIFE options group
        rife_options_parent = main_tab.rife_options_group.parentWidget()
        if rife_options_parent is not None:
            rife_options_parent.setVisible(is_rife)

        # Use model_combo alias
        model_combo = main_tab.rife_model_combo
        model_combo_parent = model_combo.parentWidget()
        if model_combo_parent is not None:
            model_combo_parent.setVisible(is_rife)

        # Update state of RIFE options based on capability
        if is_rife:
            self._update_rife_capabilities(main_tab, current_model_key)

        # Enable/disable RIFE specific controls on MainTab
        main_tab.rife_model_combo.setEnabled(is_rife)
        main_tab.rife_tile_checkbox.setEnabled(is_rife)
        # Ensure tile size spinbox state depends on checkbox state *and* RIFE selection
        main_tab.rife_tile_size_spinbox.setEnabled(is_rife and main_tab.rife_tile_checkbox.isChecked())
        main_tab.rife_uhd_checkbox.setEnabled(is_rife)
        main_tab.rife_tta_spatial_checkbox.setEnabled(is_rife)
        main_tab.rife_tta_temporal_checkbox.setEnabled(is_rife)
        main_tab.rife_thread_spec_edit.setEnabled(is_rife)

        # Enable/disable the entire FFmpeg settings tab content
        if ffmpeg_settings_tab is not None:
            ffmpeg_settings_tab.set_enabled(is_ffmpeg)
            LOGGER.debug("Called ffmpeg_settings_tab.set_enabled(%s)", is_ffmpeg)
        else:
            LOGGER.debug("ffmpeg_settings_tab is None, skipping set_enabled call")

    def _update_rife_capabilities(self, main_tab: Any, current_model_key: str) -> None:
        """Update RIFE UI elements based on model capabilities.

        Args:
            main_tab: The MainTab instance
            current_model_key: Current RIFE model key
        """
        try:
            # Check if RIFE executable exists
            config.find_rife_executable(current_model_key)

            capability_detector = RifeCapabilityManager(model_key=current_model_key)

            # Update UI elements based on capabilities
            main_tab.rife_tile_checkbox.setEnabled(capability_detector.capabilities.get("tiling", False))
            main_tab.rife_uhd_checkbox.setEnabled(capability_detector.capabilities.get("uhd", False))
            main_tab.rife_thread_spec_edit.setEnabled(capability_detector.capabilities.get("thread_spec", False))
            main_tab.rife_tta_spatial_checkbox.setEnabled(capability_detector.capabilities.get("tta_spatial", False))
            main_tab.rife_tta_temporal_checkbox.setEnabled(capability_detector.capabilities.get("tta_temporal", False))

            # Warn if selected model doesn't support features
            self._check_capability_warnings(main_tab, capability_detector, current_model_key)

        except FileNotFoundError:
            # If RIFE executable is not found, disable all RIFE options
            self._disable_all_rife_options(main_tab)
            LOGGER.warning(
                "RIFE executable not found for model '%s'. RIFE options disabled.",
                current_model_key,
            )
        except Exception as e:
            LOGGER.exception(
                "Error checking RIFE capabilities for model '%s': %s",
                current_model_key,
                e,
            )
            # Disable options on error
            self._disable_all_rife_options(main_tab)

    def _check_capability_warnings(
        self,
        main_tab: Any,
        capability_detector: RifeCapabilityManager,
        current_model_key: str,
    ) -> None:
        """Check and log warnings for unsupported capabilities.

        Args:
            main_tab: The MainTab instance
            capability_detector: The capability detector instance
            current_model_key: Current RIFE model key
        """
        if main_tab.rife_tile_checkbox.isChecked() and not capability_detector.capabilities.get("tiling", False):
            LOGGER.warning("Selected model '%s' does not support tiling.", current_model_key)

        if main_tab.rife_uhd_checkbox.isChecked() and not capability_detector.capabilities.get("uhd", False):
            LOGGER.warning("Selected model '%s' does not support UHD mode.", current_model_key)

        if main_tab.rife_thread_spec_edit.text() != "1:2:2" and not capability_detector.capabilities.get(
            "thread_spec", False
        ):
            LOGGER.warning(
                "Selected model '%s' does not support custom thread specification.",
                current_model_key,
            )

        if main_tab.rife_tta_spatial_checkbox.isChecked() and not capability_detector.capabilities.get(
            "tta_spatial", False
        ):
            LOGGER.warning("Selected model '%s' does not support spatial TTA.", current_model_key)

        if main_tab.rife_tta_temporal_checkbox.isChecked() and not capability_detector.capabilities.get(
            "tta_temporal", False
        ):
            LOGGER.warning("Selected model '%s' does not support temporal TTA.", current_model_key)

    def _disable_all_rife_options(self, main_tab: Any) -> None:
        """Disable all RIFE options.

        Args:
            main_tab: The MainTab instance
        """
        main_tab.rife_tile_checkbox.setEnabled(False)
        main_tab.rife_tile_size_spinbox.setEnabled(False)
        main_tab.rife_uhd_checkbox.setEnabled(False)
        main_tab.rife_thread_spec_edit.setEnabled(False)
        main_tab.rife_tta_spatial_checkbox.setEnabled(False)
        main_tab.rife_tta_temporal_checkbox.setEnabled(False)
