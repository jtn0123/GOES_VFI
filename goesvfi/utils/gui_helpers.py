"""
GUI Helper Utilities for GOES-VFI

This module provides helper functions for the GUI, including RIFE capability detection
and UI element management.
"""

import pathlib
import logging
from typing import Dict, Optional, Tuple

from PyQt6.QtWidgets import QWidget, QCheckBox, QSpinBox, QLineEdit, QComboBox, QLabel

from goesvfi.utils.config import find_rife_executable
from goesvfi.utils.rife_analyzer import RifeCapabilityDetector

# Set up logging
logger = logging.getLogger(__name__)


class RifeCapabilityManager:
    """
    Manages RIFE CLI capabilities and updates UI elements accordingly.

    This class detects the capabilities of the RIFE CLI executable and
    updates UI elements to reflect what options are available.
    """

    def __init__(self, model_key: str = "rife-v4.6"):
        """
        Initialize the capability manager.

        Args:
            model_key: The model key to use for finding the RIFE executable
        """
        self.model_key = model_key
        self.detector: Optional[RifeCapabilityDetector] = None
        self.capabilities: Dict[str, bool] = {}
        self.exe_path: Optional[pathlib.Path] = None
        self.version: Optional[str] = None

        # Try to detect capabilities
        self._detect_capabilities()

    def _detect_capabilities(self) -> None:
        """
        Detect the capabilities of the RIFE CLI executable.
        """
        try:
            # Find the RIFE executable
            self.exe_path = find_rife_executable(self.model_key)

            # Create a capability detector
            self.detector = RifeCapabilityDetector(self.exe_path)

            # Store capabilities
            self.capabilities = {
                "tiling": self.detector.supports_tiling(),
                "uhd": self.detector.supports_uhd(),
                "tta_spatial": self.detector.supports_tta_spatial(),
                "tta_temporal": self.detector.supports_tta_temporal(),
                "thread_spec": self.detector.supports_thread_spec(),
                "batch_processing": self.detector.supports_batch_processing(),
                "timestep": self.detector.supports_timestep(),
                "model_path": self.detector.supports_model_path(),
                "gpu_id": self.detector.supports_gpu_id(),
            }

            # Store version
            self.version = self.detector.version

            logger.info(f"RIFE capabilities detected: {self.capabilities}")
            logger.info(f"RIFE version detected: {self.version}")

        except Exception as e:
            logger.error(f"Error detecting RIFE capabilities: {e}")
            # Set all capabilities to False
            self.capabilities = {
                "tiling": False,
                "uhd": False,
                "tta_spatial": False,
                "tta_temporal": False,
                "thread_spec": False,
                "batch_processing": False,
                "timestep": False,
                "model_path": False,
                "gpu_id": False,
            }

    def update_ui_elements(
        self,
        tile_enable_cb: QCheckBox,
        tile_size_spin: QSpinBox,
        uhd_mode_cb: QCheckBox,
        thread_spec_edit: QLineEdit,
        thread_spec_label: QLabel,
        tta_spatial_cb: QCheckBox,
        tta_temporal_cb: QCheckBox,
    ) -> None:
        """
        Update UI elements based on detected capabilities.

        Args:
            tile_enable_cb: The tiling enable checkbox
            tile_size_spin: The tile size spinner
            uhd_mode_cb: The UHD mode checkbox
            thread_spec_edit: The thread specification text field
            thread_spec_label: The thread specification label
            tta_spatial_cb: The TTA spatial checkbox
            tta_temporal_cb: The TTA temporal checkbox
        """
        # Update tiling elements
        if self.capabilities.get("tiling", False):
            tile_enable_cb.setEnabled(True)
            tile_enable_cb.setToolTip("Enable tiling for large images")
            # Only enable tile size spinner if tiling is enabled
            tile_size_spin.setEnabled(tile_enable_cb.isChecked())
        else:
            tile_enable_cb.setEnabled(False)
            tile_enable_cb.setToolTip("Tiling not supported by this RIFE executable")
            tile_size_spin.setEnabled(False)
            tile_size_spin.setToolTip("Tiling not supported by this RIFE executable")

        # Update UHD mode
        if self.capabilities.get("uhd", False):
            uhd_mode_cb.setEnabled(True)
            uhd_mode_cb.setToolTip(
                "Enable UHD mode for 4K+ images (slower but better quality)"
            )
        else:
            uhd_mode_cb.setEnabled(False)
            uhd_mode_cb.setToolTip("UHD mode not supported by this RIFE executable")

        # Update thread specification
        if self.capabilities.get("thread_spec", False):
            thread_spec_edit.setEnabled(True)
            thread_spec_label.setEnabled(True)
            thread_spec_edit.setToolTip("Thread specification (load:proc:save)")
        else:
            thread_spec_edit.setEnabled(False)
            thread_spec_label.setEnabled(False)
            thread_spec_edit.setToolTip(
                "Thread specification not supported by this RIFE executable"
            )

        # Update TTA spatial
        if self.capabilities.get("tta_spatial", False):
            tta_spatial_cb.setEnabled(True)
            tta_spatial_cb.setToolTip(
                "Enable spatial test-time augmentation (slower but better quality)"
            )
        else:
            tta_spatial_cb.setEnabled(False)
            tta_spatial_cb.setToolTip(
                "Spatial TTA not supported by this RIFE executable"
            )

        # Update TTA temporal
        if self.capabilities.get("tta_temporal", False):
            tta_temporal_cb.setEnabled(True)
            tta_temporal_cb.setToolTip(
                "Enable temporal test-time augmentation (slower but better quality)"
            )
        else:
            tta_temporal_cb.setEnabled(False)
            tta_temporal_cb.setToolTip(
                "Temporal TTA not supported by this RIFE executable"
            )

    def get_capability_summary(self) -> str:
        """
        Get a summary of the detected capabilities.

        Returns:
            A string summarizing the detected capabilities
        """
        if not self.detector:
            return "RIFE capabilities not detected"

        version_str = f"v{self.version}" if self.version else "unknown version"

        # Count supported features
        supported_count = sum(1 for v in self.capabilities.values() if v)
        total_count = len(self.capabilities)

        return (
            f"RIFE {version_str} - {supported_count}/{total_count} features supported"
        )
