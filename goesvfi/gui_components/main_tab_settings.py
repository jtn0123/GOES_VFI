"""Settings management for MainTab - consolidates direct QSettings usage.

This module replaces the numerous direct QSettings calls in MainTab with
a centralized, type-safe settings management system.
"""

from PyQt6.QtCore import QSettings

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class MainTabSettings:
    """Centralized settings management for MainTab."""

    def __init__(self, qsettings: QSettings) -> None:
        """Initialize MainTab settings manager.

        Args:
            qsettings: QSettings instance
        """
        self.settings = qsettings

    # Model and Processing Settings
    def get_model_key(self) -> str:
        """Get the last selected RIFE model key."""
        value = self.settings.value("rife/modelKey", "rife-v4.6", type=str)
        return str(value) if value is not None else "rife-v4.6"

    def set_model_key(self, model_key: str) -> None:
        """Set the RIFE model key."""
        self.settings.setValue("rife/modelKey", model_key)

    def get_fps(self) -> int:
        """Get processing FPS setting."""
        value = self.settings.value("processing/fps", 60, type=int)
        return int(value) if value is not None else 60

    def set_fps(self, fps: int) -> None:
        """Set processing FPS setting."""
        self.settings.setValue("processing/fps", fps)

    def get_multiplier(self) -> int:
        """Get frame multiplier setting."""
        value = self.settings.value("processing/multiplier", 2, type=int)
        return int(value) if value is not None else 2

    def set_multiplier(self, multiplier: int) -> None:
        """Set frame multiplier setting."""
        self.settings.setValue("processing/multiplier", multiplier)

    def get_max_workers(self, default_workers: int = 4) -> int:
        """Get max workers setting."""
        value = self.settings.value("processing/maxWorkers", default_workers, type=int)
        return int(value) if value is not None else default_workers

    def set_max_workers(self, max_workers: int) -> None:
        """Set max workers setting."""
        self.settings.setValue("processing/maxWorkers", max_workers)

    def get_encoder(self) -> str:
        """Get encoder setting."""
        value = self.settings.value("processing/encoder", "RIFE", type=str)
        return str(value) if value is not None else "RIFE"

    def set_encoder(self, encoder: str) -> None:
        """Set encoder setting."""
        self.settings.setValue("processing/encoder", encoder)

    # RIFE Settings
    def get_tile_size(self) -> int:
        """Get RIFE tile size setting."""
        value = self.settings.value("rife/tileSize", 256, type=int)
        return int(value) if value is not None else 256

    def set_tile_size(self, tile_size: int) -> None:
        """Set RIFE tile size setting."""
        self.settings.setValue("rife/tileSize", tile_size)

    def get_tiling_enabled(self) -> bool:
        """Get RIFE tiling enabled setting."""
        value = self.settings.value("rife/tilingEnabled", False, type=bool)
        return bool(value) if value is not None else False

    def set_tiling_enabled(self, enabled: bool) -> None:
        """Set RIFE tiling enabled setting."""
        self.settings.setValue("rife/tilingEnabled", enabled)

    def get_uhd_mode(self) -> bool:
        """Get RIFE UHD mode setting."""
        value = self.settings.value("rife/uhdMode", False, type=bool)
        return bool(value) if value is not None else False

    def set_uhd_mode(self, enabled: bool) -> None:
        """Set RIFE UHD mode setting."""
        self.settings.setValue("rife/uhdMode", enabled)

    def get_thread_spec(self) -> str:
        """Get RIFE thread specification."""
        value = self.settings.value("rife/threadSpec", "", type=str)
        return str(value) if value is not None else ""

    def set_thread_spec(self, thread_spec: str) -> None:
        """Set RIFE thread specification."""
        self.settings.setValue("rife/threadSpec", thread_spec)

    def get_tta_spatial(self) -> bool:
        """Get RIFE TTA spatial setting."""
        value = self.settings.value("rife/ttaSpatial", False, type=bool)
        return bool(value) if value is not None else False

    def set_tta_spatial(self, enabled: bool) -> None:
        """Set RIFE TTA spatial setting."""
        self.settings.setValue("rife/ttaSpatial", enabled)

    def get_tta_temporal(self) -> bool:
        """Get RIFE TTA temporal setting."""
        value = self.settings.value("rife/ttaTemporal", False, type=bool)
        return bool(value) if value is not None else False

    def set_tta_temporal(self, enabled: bool) -> None:
        """Set RIFE TTA temporal setting."""
        self.settings.setValue("rife/ttaTemporal", enabled)

    # Sanchez Settings
    def get_sanchez_false_color_enabled(self) -> bool:
        """Get Sanchez false color enabled setting."""
        value = self.settings.value("sanchez/falseColorEnabled", False, type=bool)
        return bool(value) if value is not None else False

    def set_sanchez_false_color_enabled(self, enabled: bool) -> None:
        """Set Sanchez false color enabled setting."""
        self.settings.setValue("sanchez/falseColorEnabled", enabled)

    def get_sanchez_resolution_km(self) -> str:
        """Get Sanchez resolution km setting."""
        value = self.settings.value("sanchez/resolutionKm", "4", type=str)
        return str(value) if value is not None else "4"

    def set_sanchez_resolution_km(self, res_km: str) -> None:
        """Set Sanchez resolution km setting."""
        self.settings.setValue("sanchez/resolutionKm", res_km)

    # Path Settings
    def get_input_directory(self) -> str:
        """Get input directory path."""
        value = self.settings.value("paths/inputDirectory", "", type=str)
        return str(value) if value is not None else ""

    def set_input_directory(self, path: str) -> None:
        """Set input directory path with redundancy."""
        self.settings.setValue("paths/inputDirectory", path)
        self.settings.setValue("inputDir", path)  # Alternate key for redundancy

    def get_output_file(self) -> str:
        """Get output file path."""
        value = self.settings.value("paths/outputFile", "", type=str)
        return str(value) if value is not None else ""

    def set_output_file(self, path: str) -> None:
        """Set output file path."""
        self.settings.setValue("paths/outputFile", path)

    # Preview Settings
    def get_crop_rectangle(self) -> str:
        """Get crop rectangle string."""
        value = self.settings.value("preview/cropRectangle", "", type=str)
        return str(value) if value is not None else ""

    def set_crop_rectangle(self, rect_str: str) -> None:
        """Set crop rectangle string with redundancy."""
        self.settings.setValue("preview/cropRectangle", rect_str)
        self.settings.setValue("cropRect", rect_str)  # Alternate key for redundancy

    # Generic value accessor with logging
    def get_value(self, key: str, default=None, value_type=None):
        """Get a value with type safety and logging.

        Args:
            key: Settings key
            default: Default value if key doesn't exist
            value_type: Type to cast the value to

        Returns:
            The setting value or default
        """
        try:
            if value_type:
                return self.settings.value(key, default, type=value_type)
            return self.settings.value(key, default)
        except Exception:
            LOGGER.exception(f"Error retrieving setting '{key}', using default: {default}")
            return default

    def set_value(self, key: str, value) -> None:
        """Set a value with error handling.

        Args:
            key: Settings key
            value: Value to set
        """
        try:
            self.settings.setValue(key, value)
        except Exception:
            LOGGER.exception(f"Error setting '{key}' to '{value}'")

    # Batch operations for efficiency
    def load_all_processing_settings(self) -> dict:
        """Load all processing-related settings at once.

        Returns:
            Dictionary with all processing settings
        """
        import multiprocessing

        default_workers = max(1, multiprocessing.cpu_count() - 1)

        return {
            "fps": self.get_fps(),
            "multiplier": self.get_multiplier(),
            "max_workers": self.get_max_workers(default_workers),
            "encoder": self.get_encoder(),
        }

    def save_all_processing_settings(self, fps: int, multiplier: int, max_workers: int, encoder: str) -> None:
        """Save all processing settings at once.

        Args:
            fps: FPS setting
            multiplier: Frame multiplier
            max_workers: Max workers
            encoder: Encoder type
        """
        self.set_fps(fps)
        self.set_multiplier(multiplier)
        self.set_max_workers(max_workers)
        self.set_encoder(encoder)

    def load_all_rife_settings(self) -> dict:
        """Load all RIFE-related settings at once.

        Returns:
            Dictionary with all RIFE settings
        """
        return {
            "model_key": self.get_model_key(),
            "tile_size": self.get_tile_size(),
            "tiling_enabled": self.get_tiling_enabled(),
            "uhd_mode": self.get_uhd_mode(),
            "thread_spec": self.get_thread_spec(),
            "tta_spatial": self.get_tta_spatial(),
            "tta_temporal": self.get_tta_temporal(),
        }

    def save_all_rife_settings(
        self,
        model_key: str,
        tile_enabled: bool,
        tile_size: int,
        uhd_mode: bool,
        thread_spec: str,
        tta_spatial: bool,
        tta_temporal: bool,
    ) -> None:
        """Save all RIFE settings at once.

        Args:
            model_key: Model key
            tile_enabled: Tiling enabled
            tile_size: Tile size
            uhd_mode: UHD mode
            thread_spec: Thread specification
            tta_spatial: TTA spatial
            tta_temporal: TTA temporal
        """
        self.set_model_key(model_key)
        self.set_tiling_enabled(tile_enabled)
        self.set_tile_size(tile_size)
        self.set_uhd_mode(uhd_mode)
        self.set_thread_spec(thread_spec)
        self.set_tta_spatial(tta_spatial)
        self.set_tta_temporal(tta_temporal)

    def load_all_sanchez_settings(self) -> dict:
        """Load all Sanchez-related settings at once.

        Returns:
            Dictionary with all Sanchez settings
        """
        return {
            "false_color_enabled": self.get_sanchez_false_color_enabled(),
            "resolution_km": self.get_sanchez_resolution_km(),
        }

    def save_all_sanchez_settings(self, false_color: bool, res_km: str) -> None:
        """Save all Sanchez settings at once.

        Args:
            false_color: False color enabled
            res_km: Resolution in km
        """
        self.set_sanchez_false_color_enabled(false_color)
        self.set_sanchez_resolution_km(res_km)
