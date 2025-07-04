# goesvfi/gui_tabs/ffmpeg_settings_tab.py
from __future__ import annotations

import math  # For isnan check
from typing import Any, cast

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from goesvfi.gui_components.update_manager import register_update, request_update
from goesvfi.gui_components.widget_factory import WidgetFactory

# Setup logger
from goesvfi.utils import log

# Runtime import for constants defined in gui.py
from goesvfi.utils.config import (
    DEFAULT_FFMPEG_PROFILE,  # Import from config
    FFMPEG_PROFILES,
    FfmpegProfile,
)

LOGGER = log.get_logger(__name__)  # Use __name__ for specific logger

# Type annotations for complex function arguments


class FFmpegSettingsTab(QWidget):
    """QWidget containing the settings for FFmpeg interpolation and encoding."""

    # Signal emitted when any setting affecting previews changes
    # (This signal is no longer passed in, but defined here if needed for internal use
    # or if MainWindow needs to connect to it later)
    # preview_settings_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the FFmpegSettingsTab."""
        super().__init__(parent)

        # Apply a modern, styled look for the tab
        self._apply_stylesheet()

        # --- Create Widgets ---
        self._create_widgets()

        # --- Setup Layout ---
        self._setup_layout()

        # --- Connect Signals ---
        self._connect_signals()

        # --- Initialize Control States ---
        # Don't update control states here - let MainWindow set the initial state
        # based on the selected encoder
        # self._update_all_control_states()

        # --- Setup UpdateManager Integration ---
        self._setup_update_manager()

    def _create_header(self) -> None:
        """Create the enhanced header for the FFmpeg tab."""
        # This will be added to the layout in _setup_layout
        self.header_widget = WidgetFactory.create_label(
            "⚙️ FFmpeg Settings - Video Processing Configuration", style="header"
        )

    def _apply_stylesheet(self) -> None:
        """Apply enhanced stylesheet - most styling now handled by qt-material theme."""
        # Apply qt-material theme properties
        self.setProperty("class", "FFmpegSettingsTab")

    def _create_widgets(self) -> None:
        """Create all the widgets for the FFmpeg settings tab."""
        # Add enhanced header first
        self._create_header()

        # --- Profile Selection ---
        self.ffmpeg_profile_combo = WidgetFactory.create_combo_box(
            items=[*list(FFMPEG_PROFILES.keys()), "Custom"],
            tooltip=self.tr("Select a predefined FFmpeg settings profile or 'Custom'"),
        )

        # --- Interpolation Settings Group ---
        self.ffmpeg_settings_group = WidgetFactory.create_group_box(
            self.tr("⚙️ Interpolation (minterpolate filter)"),
            checkable=True,
            tooltip=self.tr("Enable and configure FFmpeg's motion interpolation filter"),
        )

        self.ffmpeg_mi_mode_combo = WidgetFactory.create_combo_box(
            items=[self.tr("dup"), self.tr("blend"), self.tr("mci")], tooltip=self.tr("Motion interpolation mode")
        )

        self.ffmpeg_mc_mode_combo = WidgetFactory.create_combo_box(
            items=[self.tr("obmc"), self.tr("aobmc")], tooltip=self.tr("Motion compensation mode")
        )

        self.ffmpeg_me_mode_combo = WidgetFactory.create_combo_box(
            items=[self.tr("bidir"), self.tr("bilat")], tooltip=self.tr("Motion estimation mode")
        )

        self.ffmpeg_vsbmc_checkbox = WidgetFactory.create_checkbox(
            self.tr("⚙️ VSBMC"), tooltip=self.tr("Variable size block motion compensation")
        )

        self.ffmpeg_scd_combo = WidgetFactory.create_combo_box(
            items=[self.tr("none"), self.tr("fdiff")], tooltip=self.tr("Scene change detection mode")
        )

        self.ffmpeg_me_algo_combo = QComboBox()  # Changed from QLineEdit
        self.ffmpeg_me_algo_combo.addItems([
            self.tr("(default)"),
            self.tr("esa"),
            self.tr("tss"),
            self.tr("tdls"),
            self.tr("ntss"),
            self.tr("fss"),
            self.tr("ds"),
            self.tr("hexbs"),
            self.tr("epzs"),
            self.tr("umh"),
        ])
        self.ffmpeg_me_algo_combo.setToolTip(
            self.tr("Motion estimation algorithm (leave as default unless you know why)")
        )

        self.ffmpeg_search_param_spinbox = QSpinBox()
        self.ffmpeg_search_param_spinbox.setRange(4, 2048)  # Example range, adjust if needed
        self.ffmpeg_search_param_spinbox.setToolTip(self.tr("Motion estimation search parameter"))

        self.ffmpeg_scd_threshold_spinbox = QDoubleSpinBox()
        self.ffmpeg_scd_threshold_spinbox.setRange(0.0, 100.0)
        self.ffmpeg_scd_threshold_spinbox.setDecimals(1)
        self.ffmpeg_scd_threshold_spinbox.setSingleStep(0.1)
        self.ffmpeg_scd_threshold_spinbox.setToolTip(self.tr("Scene change detection threshold (0-100)"))

        self.ffmpeg_mb_size_combo = QComboBox()  # Changed from QLineEdit
        self.ffmpeg_mb_size_combo.addItems([
            self.tr("(default)"),
            self.tr("8"),
            self.tr("16"),
            self.tr("32"),
            self.tr("64"),
        ])  # Common block sizes
        self.ffmpeg_mb_size_combo.setToolTip(self.tr("Macroblock size for motion estimation"))

        # --- Unsharp Mask Group ---
        self.ffmpeg_unsharp_group = WidgetFactory.create_group_box(
            self.tr("🔍 Sharpening (unsharp filter)"),
            checkable=True,
            tooltip=self.tr("Apply unsharp mask for sharpening"),
        )

        self.ffmpeg_unsharp_lx_spinbox = QSpinBox()
        self.ffmpeg_unsharp_lx_spinbox.setRange(3, 63)
        self.ffmpeg_unsharp_lx_spinbox.setSingleStep(2)
        self.ffmpeg_unsharp_lx_spinbox.setToolTip(self.tr("Luma matrix horizontal size (odd, 3-63)"))

        self.ffmpeg_unsharp_ly_spinbox = QSpinBox()
        self.ffmpeg_unsharp_ly_spinbox.setRange(3, 63)
        self.ffmpeg_unsharp_ly_spinbox.setSingleStep(2)
        self.ffmpeg_unsharp_ly_spinbox.setToolTip(self.tr("Luma matrix vertical size (odd, 3-63)"))

        self.ffmpeg_unsharp_la_spinbox = QDoubleSpinBox()
        self.ffmpeg_unsharp_la_spinbox.setRange(-10.0, 10.0)  # Wider range
        self.ffmpeg_unsharp_la_spinbox.setDecimals(2)
        self.ffmpeg_unsharp_la_spinbox.setSingleStep(0.1)
        self.ffmpeg_unsharp_la_spinbox.setToolTip(self.tr("Luma amount (-10 to 10)"))

        self.ffmpeg_unsharp_cx_spinbox = QSpinBox()
        self.ffmpeg_unsharp_cx_spinbox.setRange(3, 63)
        self.ffmpeg_unsharp_cx_spinbox.setSingleStep(2)
        self.ffmpeg_unsharp_cx_spinbox.setToolTip(self.tr("Chroma matrix horizontal size (odd, 3-63)"))

        self.ffmpeg_unsharp_cy_spinbox = QSpinBox()
        self.ffmpeg_unsharp_cy_spinbox.setRange(3, 63)
        self.ffmpeg_unsharp_cy_spinbox.setSingleStep(2)
        self.ffmpeg_unsharp_cy_spinbox.setToolTip(self.tr("Chroma matrix vertical size (odd, 3-63)"))

        self.ffmpeg_unsharp_ca_spinbox = QDoubleSpinBox()
        self.ffmpeg_unsharp_ca_spinbox.setRange(-10.0, 10.0)  # Wider range
        self.ffmpeg_unsharp_ca_spinbox.setDecimals(2)
        self.ffmpeg_unsharp_ca_spinbox.setSingleStep(0.1)
        self.ffmpeg_unsharp_ca_spinbox.setToolTip(self.tr("Chroma amount (-10 to 10)"))

        # --- Quality Settings Group ---
        self.ffmpeg_quality_group = WidgetFactory.create_group_box(
            self.tr("📹 Encoding Quality (libx264)"), tooltip=self.tr("Settings for the final video encoding")
        )

        self.ffmpeg_quality_combo = QComboBox()
        # Define presets similar to gui_backup.py
        self.quality_presets = {
            "Very High (CRF 16)": {
                "crf": 16,
                "bitrate": 15000,
                "bufsize": 22500,
                "pix_fmt": "yuv444p",
            },
            "High (CRF 18)": {
                "crf": 18,
                "bitrate": 12000,
                "bufsize": 18000,
                "pix_fmt": "yuv444p",
            },
            "Medium (CRF 20)": {
                "crf": 20,
                "bitrate": 10000,
                "bufsize": 15000,
                "pix_fmt": "yuv420p",
            },
            "Low (CRF 23)": {
                "crf": 23,
                "bitrate": 8000,
                "bufsize": 12000,
                "pix_fmt": "yuv420p",
            },
            "Very Low (CRF 26)": {
                "crf": 26,
                "bitrate": 5000,
                "bufsize": 7500,
                "pix_fmt": "yuv420p",
            },
            "Custom": {},  # Placeholder for custom settings
        }
        self.ffmpeg_quality_combo.addItems(list(self.quality_presets.keys()))
        self.ffmpeg_quality_combo.setToolTip(
            self.tr("Select a quality preset (adjusts CRF, Bitrate, Bufsize, Pixel Format)")
        )

        self.ffmpeg_crf_spinbox = QSpinBox()
        self.ffmpeg_crf_spinbox.setRange(0, 51)  # x264 CRF range
        self.ffmpeg_crf_spinbox.setToolTip(self.tr("Constant Rate Factor (0=lossless, 51=worst)"))

        self.ffmpeg_bitrate_spinbox = QSpinBox()
        self.ffmpeg_bitrate_spinbox.setRange(100, 100000)  # In kbps
        self.ffmpeg_bitrate_spinbox.setSuffix(" kbps")
        self.ffmpeg_bitrate_spinbox.setToolTip(
            self.tr("Target video bitrate (used if CRF is not the primary mode, often informational)")
        )
        self.ffmpeg_bitrate_spinbox.setDisabled(True)  # Typically controlled by preset/CRF

        self.ffmpeg_bufsize_spinbox = QSpinBox()
        self.ffmpeg_bufsize_spinbox.setRange(100, 200000)  # In kb
        self.ffmpeg_bufsize_spinbox.setSuffix(" kB")
        self.ffmpeg_bufsize_spinbox.setToolTip(self.tr("Decoder buffer size (often 1.5x-2x bitrate)"))
        self.ffmpeg_bufsize_spinbox.setDisabled(True)  # Typically controlled by preset/CRF

        self.ffmpeg_pix_fmt_combo = QComboBox()
        self.ffmpeg_pix_fmt_combo.addItems([
            self.tr("yuv444p"),
            self.tr("yuv420p"),
            self.tr("yuv422p"),
            self.tr("rgb24"),
        ])  # Common formats
        self.ffmpeg_pix_fmt_combo.setToolTip(self.tr("Pixel format for encoding (yuv444p recommended for quality)"))

        self.ffmpeg_filter_preset_combo = QComboBox()
        self.ffmpeg_filter_preset_combo.addItems([
            self.tr("ultrafast"),
            self.tr("superfast"),
            self.tr("veryfast"),
            self.tr("faster"),
            self.tr("fast"),
            self.tr("medium"),
            self.tr("slow"),
            self.tr("slower"),
            self.tr("veryslow"),
        ])
        self.ffmpeg_filter_preset_combo.setToolTip(
            self.tr("x264 encoding speed preset (slower = better compression/quality)")
        )

    def _setup_layout(self) -> None:
        """Setup the layout and add widgets."""
        main_layout = QVBoxLayout(self)

        # Add the header first
        main_layout.addWidget(self.header_widget)

        # Profile Selection Layout with enhanced styling
        profile_container = WidgetFactory.create_container(style="profile")

        profile_layout = QHBoxLayout(profile_container)
        profile_layout.setContentsMargins(10, 10, 10, 10)

        profile_label = WidgetFactory.create_label(self.tr("📋 FFmpeg Profile:"), style="standard")
        profile_label.setObjectName("profile_label")
        self.ffmpeg_profile_combo.setMinimumWidth(200)

        profile_layout.addWidget(profile_label)
        profile_layout.addWidget(self.ffmpeg_profile_combo)
        profile_layout.addStretch()

        main_layout.addWidget(profile_container)

        # Interpolation Settings Layout with improved labels and spacing
        # Update the group title with an icon
        self.ffmpeg_settings_group.setTitle("🔄 Interpolation (minterpolate filter)")

        interp_layout = QGridLayout(self.ffmpeg_settings_group)
        interp_layout.setSpacing(8)  # Increase spacing for better readability
        interp_layout.setContentsMargins(10, 15, 10, 10)  # More comfortable margins

        # Add styled labels with better descriptions
        mi_label = WidgetFactory.create_label(self.tr("Motion Interp:"), style="ffmpeg")
        interp_layout.addWidget(mi_label, 0, 0)
        interp_layout.addWidget(self.ffmpeg_mi_mode_combo, 0, 1)

        mc_label = WidgetFactory.create_label(self.tr("Motion Comp:"), style="ffmpeg")
        interp_layout.addWidget(mc_label, 0, 2)
        interp_layout.addWidget(self.ffmpeg_mc_mode_combo, 0, 3)

        me_label = WidgetFactory.create_label(self.tr("Motion Est:"), style="ffmpeg")
        interp_layout.addWidget(me_label, 1, 0)
        interp_layout.addWidget(self.ffmpeg_me_mode_combo, 1, 1)

        # Enhance checkbox with better contrast
        self.ffmpeg_vsbmc_checkbox.setText(self.tr("Variable Size Blocks"))
        # Checkbox styling handled by qt-material theme
        interp_layout.addWidget(self.ffmpeg_vsbmc_checkbox, 1, 2, 1, 2)  # Span 2 columns
        # Scene detection row with enhanced styling
        scd_label = WidgetFactory.create_label(self.tr("Scene Detect:"), style="ffmpeg")
        interp_layout.addWidget(scd_label, 2, 0)
        interp_layout.addWidget(self.ffmpeg_scd_combo, 2, 1)

        scd_thresh_label = WidgetFactory.create_label(self.tr("SCD Threshold:"), style="ffmpeg")
        interp_layout.addWidget(scd_thresh_label, 2, 2)
        interp_layout.addWidget(self.ffmpeg_scd_threshold_spinbox, 2, 3)

        # Advanced motion estimation row
        me_algo_label = WidgetFactory.create_label(self.tr("ME Algorithm:"), style="ffmpeg")
        interp_layout.addWidget(me_algo_label, 3, 0)
        interp_layout.addWidget(self.ffmpeg_me_algo_combo, 3, 1)

        search_param_label = WidgetFactory.create_label(self.tr("Search Range:"), style="ffmpeg")
        interp_layout.addWidget(search_param_label, 3, 2)
        interp_layout.addWidget(self.ffmpeg_search_param_spinbox, 3, 3)

        # Block size row
        mb_size_label = WidgetFactory.create_label(self.tr("Block Size:"), style="ffmpeg")
        interp_layout.addWidget(mb_size_label, 4, 0)
        interp_layout.addWidget(self.ffmpeg_mb_size_combo, 4, 1)
        interp_layout.setColumnStretch(1, 1)  # Allow combos/spinners to expand
        interp_layout.setColumnStretch(3, 1)
        main_layout.addWidget(self.ffmpeg_settings_group)

        # Unsharp Mask Layout with enhanced styling
        # Update the group title with an icon
        self.ffmpeg_unsharp_group.setTitle("🔍 Sharpening (unsharp filter)")

        unsharp_layout = QGridLayout(self.ffmpeg_unsharp_group)
        unsharp_layout.setSpacing(8)  # Increase spacing for better readability
        unsharp_layout.setContentsMargins(10, 15, 10, 10)  # More comfortable margins

        # Add section headers
        luma_header = WidgetFactory.create_label(self.tr("Luma (Brightness):"), style="ffmpeg")
        unsharp_layout.addWidget(luma_header, 0, 0, 1, 2)

        chroma_header = WidgetFactory.create_label(self.tr("Chroma (Color):"), style="ffmpeg")
        unsharp_layout.addWidget(chroma_header, 0, 3, 1, 2)

        # Luma controls
        luma_x_label = WidgetFactory.create_label(self.tr("X Size:"), style="ffmpeg")
        unsharp_layout.addWidget(luma_x_label, 1, 0)
        unsharp_layout.addWidget(self.ffmpeg_unsharp_lx_spinbox, 1, 1)

        luma_y_label = WidgetFactory.create_label(self.tr("Y Size:"), style="ffmpeg")
        unsharp_layout.addWidget(luma_y_label, 2, 0)
        unsharp_layout.addWidget(self.ffmpeg_unsharp_ly_spinbox, 2, 1)

        luma_amt_label = WidgetFactory.create_label(self.tr("Amount:"), style="ffmpeg")
        unsharp_layout.addWidget(luma_amt_label, 3, 0)
        unsharp_layout.addWidget(self.ffmpeg_unsharp_la_spinbox, 3, 1)

        # Add a visual separator
        separator = WidgetFactory.create_separator(orientation="vertical")
        unsharp_layout.addWidget(separator, 1, 2, 3, 1)

        # Chroma controls
        chroma_x_label = WidgetFactory.create_label(self.tr("X Size:"), style="ffmpeg")
        unsharp_layout.addWidget(chroma_x_label, 1, 3)
        unsharp_layout.addWidget(self.ffmpeg_unsharp_cx_spinbox, 1, 4)

        chroma_y_label = WidgetFactory.create_label(self.tr("Y Size:"), style="ffmpeg")
        unsharp_layout.addWidget(chroma_y_label, 2, 3)
        unsharp_layout.addWidget(self.ffmpeg_unsharp_cy_spinbox, 2, 4)

        chroma_amt_label = WidgetFactory.create_label(self.tr("Amount:"), style="ffmpeg")
        unsharp_layout.addWidget(chroma_amt_label, 3, 3)
        unsharp_layout.addWidget(self.ffmpeg_unsharp_ca_spinbox, 3, 4)

        # Add column stretch
        unsharp_layout.setColumnStretch(1, 1)
        unsharp_layout.setColumnStretch(4, 1)

        main_layout.addWidget(self.ffmpeg_unsharp_group)

        # Quality Settings Layout with enhanced styling
        # Update the group title with an icon
        self.ffmpeg_quality_group.setTitle("🎬 Encoding Quality (libx264)")

        quality_layout = QGridLayout(self.ffmpeg_quality_group)
        quality_layout.setSpacing(8)  # Increase spacing for better readability
        quality_layout.setContentsMargins(10, 15, 10, 10)  # More comfortable margins

        # Quality preset with styled label
        quality_preset_label = WidgetFactory.create_label(self.tr("Quality Preset:"), style="ffmpeg")
        quality_layout.addWidget(quality_preset_label, 0, 0)
        quality_layout.addWidget(self.ffmpeg_quality_combo, 0, 1)

        # CRF with emphasis
        crf_label = WidgetFactory.create_label(self.tr("CRF Value:"), style="ffmpeg")
        quality_layout.addWidget(crf_label, 0, 2)
        self.ffmpeg_crf_spinbox.setToolTip(self.tr("Constant Rate Factor: Lower values = higher quality (0-51)"))
        quality_layout.addWidget(self.ffmpeg_crf_spinbox, 0, 3)

        # Bitrate section
        bitrate_label = WidgetFactory.create_label(self.tr("Target Bitrate:"), style="ffmpeg")
        quality_layout.addWidget(bitrate_label, 1, 0)
        quality_layout.addWidget(self.ffmpeg_bitrate_spinbox, 1, 1)

        # Buffer size
        bufsize_label = WidgetFactory.create_label(self.tr("Buffer Size:"), style="ffmpeg")
        quality_layout.addWidget(bufsize_label, 1, 2)
        quality_layout.addWidget(self.ffmpeg_bufsize_spinbox, 1, 3)

        # Add a separator
        separator = WidgetFactory.create_separator(orientation="horizontal")
        quality_layout.addWidget(separator, 2, 0, 1, 4)

        # Format and presets section
        format_label = WidgetFactory.create_label(self.tr("Pixel Format:"), style="ffmpeg")
        quality_layout.addWidget(format_label, 3, 0)
        quality_layout.addWidget(self.ffmpeg_pix_fmt_combo, 3, 1)

        preset_label = WidgetFactory.create_label(self.tr("Encoder Speed:"), style="ffmpeg")
        quality_layout.addWidget(preset_label, 3, 2)
        quality_layout.addWidget(self.ffmpeg_filter_preset_combo, 3, 3)

        # Add a note about quality
        note_label = WidgetFactory.create_label(
            self.tr("<i>Note: Slower encoder presets generally produce better quality at the same bitrate</i>"),
            style="standard",
            wordWrap=True,
        )
        quality_layout.addWidget(note_label, 4, 0, 1, 4)

        quality_layout.setColumnStretch(1, 1)  # Allow combos/spinners to expand
        quality_layout.setColumnStretch(3, 1)

        main_layout.addWidget(self.ffmpeg_quality_group)

        # --- Filters Group (Crop) ---
        self.ffmpeg_filter_group = WidgetFactory.create_group_box(self.tr("Filters"))
        filter_layout = QVBoxLayout(self.ffmpeg_filter_group)
        filter_label = WidgetFactory.create_label(self.tr("Video Filters:"), style="ffmpeg")
        self.crop_filter_edit = WidgetFactory.create_line_edit(
            placeholder=self.tr("e.g. crop=width:height:x:y"), tooltip=self.tr("Additional FFmpeg filter string")
        )
        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self.crop_filter_edit)
        main_layout.addWidget(self.ffmpeg_filter_group)

        main_layout.addStretch()  # Push everything to the top
        self.setLayout(main_layout)

    def _connect_signals(self) -> None:
        """Connect signals for enabling/disabling controls and profile handling."""
        # Profile selection
        self.ffmpeg_profile_combo.currentTextChanged.connect(self._on_profile_selected)

        # Controls that affect dependent control states
        # Use UpdateManager for batched control state updates
        self.ffmpeg_settings_group.toggled.connect(lambda: request_update("ffmpeg_interpolation_controls"))
        self.ffmpeg_scd_combo.currentTextChanged.connect(lambda: request_update("ffmpeg_scd_controls"))
        self.ffmpeg_unsharp_group.toggled.connect(lambda: request_update("ffmpeg_unsharp_controls"))
        self.ffmpeg_quality_combo.currentTextChanged.connect(lambda: request_update("ffmpeg_quality_controls"))

        # All controls that should trigger the "Custom" profile state when changed
        controls_to_monitor = [
            self.ffmpeg_settings_group,  # Checkable groupbox itself
            self.ffmpeg_mi_mode_combo,
            self.ffmpeg_mc_mode_combo,
            self.ffmpeg_me_mode_combo,
            self.ffmpeg_vsbmc_checkbox,
            self.ffmpeg_scd_combo,
            self.ffmpeg_me_algo_combo,
            self.ffmpeg_search_param_spinbox,
            self.ffmpeg_scd_threshold_spinbox,
            self.ffmpeg_mb_size_combo,
            self.ffmpeg_unsharp_group,  # Checkable groupbox itself
            self.ffmpeg_unsharp_lx_spinbox,
            self.ffmpeg_unsharp_ly_spinbox,
            self.ffmpeg_unsharp_la_spinbox,
            self.ffmpeg_unsharp_cx_spinbox,
            self.ffmpeg_unsharp_cy_spinbox,
            self.ffmpeg_unsharp_ca_spinbox,
            self.ffmpeg_quality_combo,  # Changing quality preset affects others
            self.ffmpeg_crf_spinbox,
            # Bitrate/Bufsize are usually disabled, but connect anyway
            self.ffmpeg_bitrate_spinbox,
            self.ffmpeg_bufsize_spinbox,
            self.ffmpeg_pix_fmt_combo,
            self.ffmpeg_filter_preset_combo,
            self.crop_filter_edit,
        ]

        for control in controls_to_monitor:
            if isinstance(control, (QComboBox)):
                control.currentTextChanged.connect(self._on_ffmpeg_setting_changed)
            elif isinstance(control, QSpinBox | QDoubleSpinBox):
                control.valueChanged.connect(self._on_ffmpeg_setting_changed)
            elif isinstance(control, QCheckBox):
                control.stateChanged.connect(self._on_ffmpeg_setting_changed)
            elif isinstance(control, QGroupBox) and control.isCheckable():
                control.toggled.connect(self._on_ffmpeg_setting_changed)

    # --- UpdateManager Integration ---

    def _setup_update_manager(self) -> None:
        """Set up UpdateManager integration for batched UI updates."""
        # Register update operations with different priorities
        register_update("ffmpeg_interpolation_controls", self._update_interpolation_controls_state_batched, priority=2)
        register_update("ffmpeg_scd_controls", self._update_scd_thresh_state_batched, priority=2)
        register_update("ffmpeg_unsharp_controls", self._update_unsharp_controls_state_batched, priority=2)
        register_update("ffmpeg_quality_controls", self._update_quality_controls_state_batched, priority=2)
        register_update("ffmpeg_all_controls", self._update_all_control_states, priority=1)

        LOGGER.info("FFmpegSettingsTab integrated with UpdateManager")

    # --- Control State Update Methods (from gui_backup.py, adapted) ---

    def _update_all_control_states(self) -> None:
        """Update the enabled state of all dependent controls based on current selections."""
        self._update_interpolation_controls_state(self.ffmpeg_settings_group.isChecked())
        self._update_scd_thresh_state(self.ffmpeg_scd_combo.currentText())
        self._update_unsharp_controls_state(self.ffmpeg_unsharp_group.isChecked())
        self._update_quality_controls_state(self.ffmpeg_quality_combo.currentText())

    # Batched update wrapper methods for UpdateManager
    def _update_interpolation_controls_state_batched(self) -> None:
        """Batched wrapper for interpolation controls update."""
        self._update_interpolation_controls_state(self.ffmpeg_settings_group.isChecked())

    def _update_scd_thresh_state_batched(self) -> None:
        """Batched wrapper for SCD threshold update."""
        self._update_scd_thresh_state(self.ffmpeg_scd_combo.currentText())

    def _update_unsharp_controls_state_batched(self) -> None:
        """Batched wrapper for unsharp controls update."""
        self._update_unsharp_controls_state(self.ffmpeg_unsharp_group.isChecked())

    def _update_quality_controls_state_batched(self) -> None:
        """Batched wrapper for quality controls update."""
        self._update_quality_controls_state(self.ffmpeg_quality_combo.currentText())

    def request_control_updates(self, update_type: str = "all") -> None:
        """Request control state updates through UpdateManager.

        Args:
            update_type: Type of update ('all', 'interpolation', 'scd', 'unsharp', 'quality')
        """
        if update_type == "all":
            request_update("ffmpeg_all_controls")
        elif update_type == "interpolation":
            request_update("ffmpeg_interpolation_controls")
        elif update_type == "scd":
            request_update("ffmpeg_scd_controls")
        elif update_type == "unsharp":
            request_update("ffmpeg_unsharp_controls")
        elif update_type == "quality":
            request_update("ffmpeg_quality_controls")

    def _update_interpolation_controls_state(self, enable: bool) -> None:
        """Enable/disable interpolation controls based on the group checkbox."""
        widgets = [
            self.ffmpeg_mi_mode_combo,
            self.ffmpeg_mc_mode_combo,
            self.ffmpeg_me_mode_combo,
            self.ffmpeg_vsbmc_checkbox,
            self.ffmpeg_scd_combo,
            self.ffmpeg_me_algo_combo,
            self.ffmpeg_search_param_spinbox,
            self.ffmpeg_scd_threshold_spinbox,
            self.ffmpeg_mb_size_combo,
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
            self.ffmpeg_unsharp_lx_spinbox,
            self.ffmpeg_unsharp_ly_spinbox,
            self.ffmpeg_unsharp_la_spinbox,
            self.ffmpeg_unsharp_cx_spinbox,
            self.ffmpeg_unsharp_cy_spinbox,
            self.ffmpeg_unsharp_ca_spinbox,
        ]
        for widget in widgets:
            widget.setEnabled(enable)

    def _update_quality_controls_state(self, preset_text: str | None = None) -> None:
        """Update quality controls based on the selected preset."""
        if preset_text is None:
            preset_text = self.ffmpeg_quality_combo.currentText()

        preset_settings = self.quality_presets.get(preset_text)

        if preset_settings is None:  # Should not happen if "Custom" is handled
            LOGGER.warning("Unknown quality preset %s encountered.", preset_text)
            # Keep controls enabled if preset is unknown or "Custom"
            self.ffmpeg_crf_spinbox.setEnabled(True)
            self.ffmpeg_bitrate_spinbox.setEnabled(True)  # Enable custom bitrate/bufsize
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
                self.ffmpeg_crf_spinbox,
                self.ffmpeg_bitrate_spinbox,
                self.ffmpeg_bufsize_spinbox,
                self.ffmpeg_pix_fmt_combo,
            ]
            for w in widgets_to_block:
                w.blockSignals(True)
            try:
                if "crf" in preset_settings and isinstance(preset_settings["crf"], int):
                    self.ffmpeg_crf_spinbox.setValue(preset_settings["crf"])
                if "bitrate" in preset_settings and isinstance(preset_settings["bitrate"], int):
                    self.ffmpeg_bitrate_spinbox.setValue(preset_settings["bitrate"])
                if "bufsize" in preset_settings and isinstance(preset_settings["bufsize"], int):
                    self.ffmpeg_bufsize_spinbox.setValue(preset_settings["bufsize"])
                if "pix_fmt" in preset_settings and isinstance(preset_settings["pix_fmt"], str):
                    self.ffmpeg_pix_fmt_combo.setCurrentText(preset_settings["pix_fmt"])
            finally:
                for w in widgets_to_block:
                    w.blockSignals(False)

    # --- Profile Handling Methods (from gui_backup.py, adapted) ---

    def _on_profile_selected(self, profile_name: str) -> None:
        LOGGER.debug("FFmpeg profile selected: %s", profile_name)
        """Load settings from the selected FFmpeg profile."""
        if profile_name == "Custom":
            # When user explicitly selects "Custom", enable quality controls
            self.request_control_updates("quality")
            return  # Don't load any settings

        profile_dict = FFMPEG_PROFILES.get(profile_name)
        if not profile_dict:
            LOGGER.warning("Unknown FFmpeg profile selected: %s", profile_name)
            return

        # Block signals on the profile combo itself to prevent recursion
        self.ffmpeg_profile_combo.blockSignals(True)
        # Block signals on all other controls to prevent _on_ffmpeg_setting_changed firing prematurely
        all_controls = self._get_all_setting_controls()
        for widget in all_controls:
            if widget != self.ffmpeg_profile_combo:  # Don't double-block
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
            self.ffmpeg_me_algo_combo.setCurrentText(profile_dict["me_algo"])  # Use combo now
            self.ffmpeg_search_param_spinbox.setValue(profile_dict["search_param"])
            self.ffmpeg_scd_threshold_spinbox.setValue(profile_dict["scd_threshold"])
            self.ffmpeg_mb_size_combo.setCurrentText(profile_dict["mb_size"])  # Use combo now

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
            self.request_control_updates("all")

        except KeyError as e:
            LOGGER.exception("Profile %r is missing key: %s", profile_name, e)
        except Exception as e:
            LOGGER.error("Error applying profile %r: %s", profile_name, e, exc_info=True)
        finally:
            # Unblock signals
            for widget in all_controls:
                widget.blockSignals(False)
            self.ffmpeg_profile_combo.blockSignals(False)  # Unblock profile combo last

        # Verify if settings still match after applying (should match unless error occurred)
        # This prevents the combo immediately switching back to "Custom" if _update_quality_controls_state
        # had a side effect that didn't perfectly match the original profile dict (e.g., float precision)
        QTimer.singleShot(0, self._verify_profile_match)  # Check slightly later

    def _verify_profile_match(self) -> None:
        """Checks if current settings match the selected profile and updates combo if not."""
        current_profile_name = self.ffmpeg_profile_combo.currentText()

        if current_profile_name == "Custom":
            return  # Already custom

        profile_dict = FFMPEG_PROFILES.get(current_profile_name)
        if not profile_dict:
            return  # Unknown profile selected

        if not self._check_settings_match_profile(profile_dict):
            LOGGER.warning(
                "Settings drifted after applying profile %r. Setting to 'Custom'.",
                current_profile_name,
            )
            self.ffmpeg_profile_combo.blockSignals(True)
            self.ffmpeg_profile_combo.setCurrentText("Custom")
            self.ffmpeg_profile_combo.blockSignals(False)
            # Ensure quality controls are enabled when switching to Custom this way
            self.request_control_updates("quality")

    def _on_ffmpeg_setting_changed(self, *args: Any) -> None:
        """Handle changes to FFmpeg settings to set the profile combo to 'Custom' if needed."""
        LOGGER.debug("FFmpeg setting changed, checking profile match...")
        # If the current profile is already "Custom", do nothing more
        if self.ffmpeg_profile_combo.currentText() == "Custom":
            # If the quality preset was changed *to* "Custom", ensure controls are enabled
            if self.sender() == self.ffmpeg_quality_combo and self.ffmpeg_quality_combo.currentText() == "Custom":
                self.request_control_updates("quality")
            return

        # Check if the current settings match any known profile *other than* "Custom"
        matching_profile_name = None
        for name, profile_dict in FFMPEG_PROFILES.items():
            if self._check_settings_match_profile(profile_dict):
                matching_profile_name = name
                LOGGER.debug("Current settings match profile: %s", name)
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
            LOGGER.debug("Settings now match profile %r, updating combo.", matching_profile_name)
            self.ffmpeg_profile_combo.blockSignals(True)
            self.ffmpeg_profile_combo.setCurrentText(matching_profile_name)
            self.ffmpeg_profile_combo.blockSignals(False)
            # Update quality controls based on the matched profile's preset text
            matched_profile = FFMPEG_PROFILES.get(matching_profile_name)
            if matched_profile:
                self._update_quality_controls_state(matched_profile["preset_text"])

    def _compare_float_values(
        self,
        key: str,
        current_value: Any,
        profile_value: Any,
        current_settings: dict[str, Any] | None = None,
        profile_dict: FfmpegProfile | None = None,
    ) -> bool:
        """Compare float values with proper handling of None, NaN, and type conversions.

        Args:
            key: The setting key being compared
            current_value: The current value from UI
            profile_value: The value from the profile
            current_settings: Full current settings dict (needed for scd mode check)
            profile_dict: Full profile dict (needed for scd mode check)

        Returns:
            bool: True if values match, False if they don't
        """
        # Special check for scd_threshold - skip comparison if both SCDs are "none"
        if key == "scd_threshold" and current_settings and profile_dict:
            current_scd_mode = current_settings.get("scd")
            profile_scd_mode = profile_dict.get("scd")
            if current_scd_mode == "none" and profile_scd_mode == "none":
                return True  # Threshold doesn't matter if both are none, consider matching
            # No need to handle the case where one is "none" - the main key loop will catch it

        # Handle potential None values and NaN
        if (
            current_value is None
            or profile_value is None
            or (isinstance(current_value, float) and math.isnan(current_value))
            or (isinstance(profile_value, float) and math.isnan(profile_value))
        ):
            # Both are None or NaN - consider matching
            if current_value == profile_value:
                return True
            # One is None/NaN and other isn't - not matching
            return False

        # Handle type conversion if needed
        if not isinstance(current_value, float | int) or not isinstance(profile_value, float | int):
            LOGGER.warning(
                "Non-numeric value for float key %r. Current: %s, Profile: %s",
                key,
                current_value,
                profile_value,
            )
            # Try to convert both to float
            try:
                float_diff = abs(float(current_value) - float(profile_value))
                return float_diff <= 1e-6  # Within tolerance
            except (ValueError, TypeError):
                return False  # Can't convert, definitely not matching

        # Normal numeric comparison with tolerance
        return abs(float(current_value) - float(profile_value)) <= 1e-6

    def _compare_text_values(self, key: str, current_value: Any, profile_value: Any) -> bool:
        """Compare text values with handling for special cases like "(default)".

        Args:
            key: The setting key being compared
            current_value: The current value from UI
            profile_value: The value from profile

        Returns:
            bool: True if values match, False if they don't
        """
        # Handle "(default)" vs empty string equivalence
        current_text = current_value if current_value and current_value != "(default)" else "(default)"
        profile_text = profile_value if profile_value and profile_value != "(default)" else "(default)"
        return current_text == profile_text

    def _check_settings_match_profile(self, profile_dict: FfmpegProfile) -> bool:
        """Checks if current FFmpeg settings match a given profile dictionary."""
        try:
            current_settings = self.get_current_settings()  # Use getter method
        except Exception as e:
            LOGGER.error(
                "Error getting current settings in _check_settings_match_profile: %s",
                e,
                exc_info=True,
            )
            return False  # Cannot compare if widgets are missing or getters fail

        # Compare current settings with the profile dictionary
        # Explicitly list keys from FfmpegProfile *excluding* 'preset_text'
        # as preset_text is derived/used to set other values, not a direct setting itself.
        ffmpeg_profile_keys_to_compare: list[str] = [
            "use_ffmpeg_interp",
            "mi_mode",
            "mc_mode",
            "me_mode",
            "vsbmc",
            "scd",
            "me_algo",
            "search_param",
            "scd_threshold",
            "mb_size",
            "apply_unsharp",
            "unsharp_lx",
            "unsharp_ly",
            "unsharp_la",
            "unsharp_cx",
            "unsharp_cy",
            "unsharp_ca",
            "crf",
            "bitrate",
            "bufsize",
            "pix_fmt",
            "filter_preset",
        ]

        for key in ffmpeg_profile_keys_to_compare:
            # Ensure key exists in current_settings before accessing
            if key not in current_settings:
                LOGGER.warning("Key %r in profile but not returned by get_current_settings().", key)
                return False

            current_value = current_settings[key]
            # Use cast to satisfy type checker for TypedDict access
            profile_value = cast("Any", profile_dict[key])  # type: ignore[literal-required]

            # Choose appropriate comparison strategy based on key type
            # Float comparison for numeric values that need precision handling
            if key in {"scd_threshold", "unsharp_la", "unsharp_ca"}:
                if not self._compare_float_values(key, current_value, profile_value, current_settings, profile_dict):
                    return False

            # Special handling for text fields that might be "(default)" or empty
            elif key in {"me_algo", "mb_size"}:
                if not self._compare_text_values(key, current_value, profile_value):
                    return False

            # General comparison for other types (bool, int, str)
            elif current_value != profile_value:
                return False

        return True

    # --- Helper Methods ---

    def _get_all_setting_controls(self) -> list[QWidget]:
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
        LOGGER.debug("FFmpegSettingsTab.set_enabled called with enabled=%s", enabled)

        # Enable/disable the main group boxes first
        self.ffmpeg_settings_group.setEnabled(enabled)
        self.ffmpeg_unsharp_group.setEnabled(enabled)
        self.ffmpeg_quality_group.setEnabled(enabled)
        self.ffmpeg_profile_combo.setEnabled(enabled)  # Also enable/disable profile selection

        LOGGER.debug("Set ffmpeg_profile_combo.isEnabled() = %s", self.ffmpeg_profile_combo.isEnabled())

        # If enabling, restore the individual control states based on selections
        if enabled:
            self._update_all_control_states()
        else:
            # If disabling, ensure all child controls are also disabled
            # (though disabling the group boxes should handle most)
            for control in self._get_all_setting_controls():
                if control != self.ffmpeg_profile_combo:  # Already handled
                    control.setEnabled(False)

    def set_crop_rect(self, rect: tuple[int, int, int, int] | None) -> None:
        """Update crop filter to match selected rectangle."""
        if rect:
            x, y, w, h = rect
            new_filter = f"crop={w}:{h}:{x}:{y}"
            if w % 2 != 0 or h % 2 != 0:
                QMessageBox.warning(
                    self,
                    self.tr("Odd Dimensions"),
                    self.tr("Cropping to odd width or height may cause encoding errors."),
                )
        else:
            new_filter = ""

        current = self.crop_filter_edit.text()
        if current and current != new_filter:
            QMessageBox.warning(
                self,
                self.tr("Conflicting Crop"),
                self.tr("Crop filter differs from selection. Updating."),
            )
        self.crop_filter_edit.setText(new_filter)

    def get_current_settings(self) -> dict[str, Any]:
        """Returns a dictionary of the current FFmpeg settings from the UI."""
        # Handle "(default)" text for combo boxes that allow it
        me_algo = self.ffmpeg_me_algo_combo.currentText()
        mb_size = self.ffmpeg_mb_size_combo.currentText()

        return {
            # Interpolation Group
            "use_ffmpeg_interp": self.ffmpeg_settings_group.isChecked(),
            "mi_mode": self.ffmpeg_mi_mode_combo.currentText(),
            "mc_mode": self.ffmpeg_mc_mode_combo.currentText(),
            "me_mode": self.ffmpeg_me_mode_combo.currentText(),
            "vsbmc": self.ffmpeg_vsbmc_checkbox.isChecked(),
            "scd": self.ffmpeg_scd_combo.currentText(),
            "me_algo": (me_algo if me_algo != "(default)" else ""),  # Store empty string if default
            "search_param": self.ffmpeg_search_param_spinbox.value(),
            "scd_threshold": self.ffmpeg_scd_threshold_spinbox.value(),
            "mb_size": (mb_size if mb_size != "(default)" else ""),  # Store empty string if default
            # Unsharp Group
            "apply_unsharp": self.ffmpeg_unsharp_group.isChecked(),
            "unsharp_lx": self.ffmpeg_unsharp_lx_spinbox.value(),
            "unsharp_ly": self.ffmpeg_unsharp_ly_spinbox.value(),
            "unsharp_la": self.ffmpeg_unsharp_la_spinbox.value(),
            "unsharp_cx": self.ffmpeg_unsharp_cx_spinbox.value(),
            "unsharp_cy": self.ffmpeg_unsharp_cy_spinbox.value(),
            "unsharp_ca": self.ffmpeg_unsharp_ca_spinbox.value(),
            # Quality Group
            "preset_text": self.ffmpeg_quality_combo.currentText(),
            # Include the preset text itself
            "crf": self.ffmpeg_crf_spinbox.value(),
            "bitrate": self.ffmpeg_bitrate_spinbox.value(),
            "bufsize": self.ffmpeg_bufsize_spinbox.value(),
            "pix_fmt": self.ffmpeg_pix_fmt_combo.currentText(),
            "filter_preset": self.ffmpeg_filter_preset_combo.currentText(),
            "filter_string": self.crop_filter_edit.text(),
        }

    def get_selected_profile_name(self) -> str:
        """Returns the name of the currently selected profile."""
        return str(self.ffmpeg_profile_combo.currentText())

    def load_settings(self, settings: dict[str, Any]) -> None:
        """Loads settings into the UI elements, typically from QSettings."""
        LOGGER.debug("Loading FFmpeg settings into tab UI...")

        # Block signals during loading
        all_controls = self._get_all_setting_controls()
        for widget in all_controls:
            widget.blockSignals(True)

        try:
            # Load Profile Selection First
            profile_name = settings.get("ffmpeg_profile", "Default")  # Default to "Default"

            # Ensure the profile name exists in the combo box items
            items = [self.ffmpeg_profile_combo.itemText(i) for i in range(self.ffmpeg_profile_combo.count())]
            if profile_name not in items:
                LOGGER.warning(
                    "Saved profile %r not found in combo box, defaulting to 'Custom'.",
                    profile_name,
                )
                profile_name = "Custom"
            self.ffmpeg_profile_combo.setCurrentText(profile_name)

            # If the loaded profile is "Custom", load individual settings
            if profile_name == "Custom":
                LOGGER.debug("Loading individual custom FFmpeg settings...")
                # Interpolation
                self.ffmpeg_settings_group.setChecked(
                    settings.get("ffmpeg_use_interp", DEFAULT_FFMPEG_PROFILE["use_ffmpeg_interp"])
                )
                self.ffmpeg_mi_mode_combo.setCurrentText(
                    settings.get("ffmpeg_mi_mode", DEFAULT_FFMPEG_PROFILE["mi_mode"])
                )
                self.ffmpeg_mc_mode_combo.setCurrentText(
                    settings.get("ffmpeg_mc_mode", DEFAULT_FFMPEG_PROFILE["mc_mode"])
                )
                self.ffmpeg_me_mode_combo.setCurrentText(
                    settings.get("ffmpeg_me_mode", DEFAULT_FFMPEG_PROFILE["me_mode"])
                )
                self.ffmpeg_vsbmc_checkbox.setChecked(settings.get("ffmpeg_vsbmc", DEFAULT_FFMPEG_PROFILE["vsbmc"]))
                self.ffmpeg_scd_combo.setCurrentText(settings.get("ffmpeg_scd", DEFAULT_FFMPEG_PROFILE["scd"]))
                # Handle "(default)" vs empty string for loading
                me_algo_saved = settings.get("ffmpeg_me_algo", DEFAULT_FFMPEG_PROFILE["me_algo"])
                self.ffmpeg_me_algo_combo.setCurrentText(me_algo_saved or "(default)")
                self.ffmpeg_search_param_spinbox.setValue(
                    settings.get("ffmpeg_search_param", DEFAULT_FFMPEG_PROFILE["search_param"])
                )
                self.ffmpeg_scd_threshold_spinbox.setValue(
                    settings.get("ffmpeg_scd_threshold", DEFAULT_FFMPEG_PROFILE["scd_threshold"])
                )
                mb_size_saved = settings.get("ffmpeg_mb_size", DEFAULT_FFMPEG_PROFILE["mb_size"])
                self.ffmpeg_mb_size_combo.setCurrentText(mb_size_saved or "(default)")

                # Unsharp
                self.ffmpeg_unsharp_group.setChecked(
                    settings.get("ffmpeg_apply_unsharp", DEFAULT_FFMPEG_PROFILE["apply_unsharp"])
                )
                self.ffmpeg_unsharp_lx_spinbox.setValue(
                    settings.get("ffmpeg_unsharp_lx", DEFAULT_FFMPEG_PROFILE["unsharp_lx"])
                )
                self.ffmpeg_unsharp_ly_spinbox.setValue(
                    settings.get("ffmpeg_unsharp_ly", DEFAULT_FFMPEG_PROFILE["unsharp_ly"])
                )
                self.ffmpeg_unsharp_la_spinbox.setValue(
                    settings.get("ffmpeg_unsharp_la", DEFAULT_FFMPEG_PROFILE["unsharp_la"])
                )
                self.ffmpeg_unsharp_cx_spinbox.setValue(
                    settings.get("ffmpeg_unsharp_cx", DEFAULT_FFMPEG_PROFILE["unsharp_cx"])
                )
                self.ffmpeg_unsharp_cy_spinbox.setValue(
                    settings.get("ffmpeg_unsharp_cy", DEFAULT_FFMPEG_PROFILE["unsharp_cy"])
                )
                self.ffmpeg_unsharp_ca_spinbox.setValue(
                    settings.get("ffmpeg_unsharp_ca", DEFAULT_FFMPEG_PROFILE["unsharp_ca"])
                )

                # Quality - Load the preset text first, then individual values if preset is "Custom"
                quality_preset_text = settings.get("ffmpeg_quality_preset_text", DEFAULT_FFMPEG_PROFILE["preset_text"])
                # Ensure preset text exists
                quality_items = [
                    self.ffmpeg_quality_combo.itemText(i) for i in range(self.ffmpeg_quality_combo.count())
                ]
                if quality_preset_text not in quality_items:
                    LOGGER.warning(
                        "Saved quality preset %r not found, defaulting.",
                        quality_preset_text,
                    )
                    quality_preset_text = DEFAULT_FFMPEG_PROFILE["preset_text"]  # Or maybe "Custom"?

                self.ffmpeg_quality_combo.setCurrentText(quality_preset_text)

                # If the loaded quality preset is "Custom", load the specific values
                if quality_preset_text == "Custom":
                    self.ffmpeg_crf_spinbox.setValue(settings.get("ffmpeg_crf", DEFAULT_FFMPEG_PROFILE["crf"]))
                    self.ffmpeg_bitrate_spinbox.setValue(
                        settings.get("ffmpeg_bitrate", DEFAULT_FFMPEG_PROFILE["bitrate"])
                    )
                    self.ffmpeg_bufsize_spinbox.setValue(
                        settings.get("ffmpeg_bufsize", DEFAULT_FFMPEG_PROFILE["bufsize"])
                    )
                    self.ffmpeg_pix_fmt_combo.setCurrentText(
                        settings.get("ffmpeg_pix_fmt", DEFAULT_FFMPEG_PROFILE["pix_fmt"])
                    )
                # Else: _update_quality_controls_state (called later) will set values from preset

                # Filter Preset
                self.ffmpeg_filter_preset_combo.setCurrentText(
                    settings.get("ffmpeg_filter_preset", DEFAULT_FFMPEG_PROFILE["filter_preset"])
                )
                self.crop_filter_edit.setText(settings.get("ffmpeg_filter_string", ""))

            # If a specific profile was loaded, apply it (this handles non-"Custom" cases)
            else:
                LOGGER.debug("Applying loaded profile: %s", profile_name)
                self._on_profile_selected(profile_name)  # Apply the loaded profile

            # --- Update control states after loading all settings ---
            self._update_all_control_states()

        except Exception as e:
            LOGGER.error("Error loading FFmpeg settings into UI: %s", e, exc_info=True)
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
                LOGGER.warning(
                    "Settings drifted from loaded profile %r during load. Setting to 'Custom'.",
                    current_profile_name,
                )
                self.ffmpeg_profile_combo.blockSignals(True)
                self.ffmpeg_profile_combo.setCurrentText("Custom")
                self.ffmpeg_profile_combo.blockSignals(False)
                self._update_quality_controls_state("Custom")  # Ensure custom quality enabled
            return  # Already handled or matched

        # If "Custom" was loaded, check if the loaded values actually match a profile
        matching_profile_name = None
        for name, profile_dict in FFMPEG_PROFILES.items():
            if self._check_settings_match_profile(profile_dict):
                matching_profile_name = name
                break

        if matching_profile_name:
            LOGGER.info(
                "Loaded custom settings match profile %r. Updating profile combo.",
                matching_profile_name,
            )
            self.ffmpeg_profile_combo.blockSignals(True)
            self.ffmpeg_profile_combo.setCurrentText(matching_profile_name)
            self.ffmpeg_profile_combo.blockSignals(False)
            # Update quality controls based on the matched profile's preset text
            self._update_quality_controls_state(FFMPEG_PROFILES[matching_profile_name]["preset_text"])
