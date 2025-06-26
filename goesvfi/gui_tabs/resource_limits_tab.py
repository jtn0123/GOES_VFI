"""Resource Limits Configuration Tab for GOES_VFI GUI.

This module provides a user interface for configuring resource limits
such as memory usage, processing time, and file handles.
"""

from typing import Any, Dict, Optional

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from goesvfi.pipeline.resource_manager import ResourceLimits
from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class ResourceLimitsTab(QWidget):
    """Tab for configuring resource limits and monitoring usage."""

    # Signal emitted when resource limits are changed
    limits_changed = pyqtSignal(object)  # ResourceLimits object

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the Resource Limits tab."""
        super().__init__(parent)

        self.monitor: Optional[object] = None
        self.system_info: Dict[str, Any] = {}  # TODO: Implement system resource info

        self._setup_ui()
        self._setup_monitoring()
        self._load_system_defaults()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout(self)

        # System Information Group
        self._create_system_info_group(layout)

        # Resource Limits Configuration Group
        self._create_limits_config_group(layout)

        # Real-time Monitoring Group
        self._create_monitoring_group(layout)

        # Stretch to push everything to the top
        layout.addStretch()

    def _create_system_info_group(self, parent_layout: QVBoxLayout) -> None:
        """Create the system information display group."""
        group = QGroupBox("System Resources")
        layout = QFormLayout(group)

        # Memory information
        memory_info = self.system_info.get("memory", {})
        total_memory = memory_info.get("total_mb", 0)
        self.memory_info_label = QLabel(f"{total_memory:.0f} MB total")
        layout.addRow("System Memory:", self.memory_info_label)

        # CPU information
        cpu_info = self.system_info.get("cpu", {})
        cpu_count = cpu_info.get("count", "Unknown")
        self.cpu_info_label = QLabel(f"{cpu_count} cores")
        layout.addRow("CPU Cores:", self.cpu_info_label)

        # Disk information
        disk_info = self.system_info.get("disk", {})
        total_disk = disk_info.get("total_gb", 0)
        free_disk = disk_info.get("free_gb", 0)
        self.disk_info_label = QLabel(f"{free_disk:.1f} GB free of {total_disk:.1f} GB")
        layout.addRow("Disk Space:", self.disk_info_label)

        parent_layout.addWidget(group)

    def _create_limits_config_group(self, parent_layout: QVBoxLayout) -> None:
        """Create the resource limits configuration group."""
        group = QGroupBox("Resource Limits Configuration")
        layout = QFormLayout(group)

        # Memory limit
        memory_layout = QHBoxLayout()
        self.memory_limit_checkbox = QCheckBox("Enable memory limit")
        self.memory_limit_spinbox = QSpinBox()
        self.memory_limit_spinbox.setRange(100, 32000)  # 100 MB to 32 GB
        self.memory_limit_spinbox.setValue(2048)  # Default 2 GB
        self.memory_limit_spinbox.setSuffix(" MB")
        self.memory_limit_spinbox.setEnabled(False)

        memory_layout.addWidget(self.memory_limit_checkbox)
        memory_layout.addWidget(self.memory_limit_spinbox)
        memory_layout.addStretch()
        layout.addRow("Memory Limit:", memory_layout)

        # Processing time limit
        time_layout = QHBoxLayout()
        self.time_limit_checkbox = QCheckBox("Enable processing time limit")
        self.time_limit_spinbox = QSpinBox()
        self.time_limit_spinbox.setRange(60, 7200)  # 1 minute to 2 hours
        self.time_limit_spinbox.setValue(1800)  # Default 30 minutes
        self.time_limit_spinbox.setSuffix(" seconds")
        self.time_limit_spinbox.setEnabled(False)

        time_layout.addWidget(self.time_limit_checkbox)
        time_layout.addWidget(self.time_limit_spinbox)
        time_layout.addStretch()
        layout.addRow("Processing Time Limit:", time_layout)

        # CPU usage limit
        cpu_layout = QHBoxLayout()
        self.cpu_limit_checkbox = QCheckBox("Enable CPU usage limit")
        self.cpu_limit_spinbox = QSpinBox()
        self.cpu_limit_spinbox.setRange(10, 100)  # 10% to 100%
        self.cpu_limit_spinbox.setValue(80)  # Default 80%
        self.cpu_limit_spinbox.setSuffix(" %")
        self.cpu_limit_spinbox.setEnabled(False)

        cpu_layout.addWidget(self.cpu_limit_checkbox)
        cpu_layout.addWidget(self.cpu_limit_spinbox)
        cpu_layout.addStretch()
        layout.addRow("CPU Usage Limit:", cpu_layout)

        # Open files limit
        files_layout = QHBoxLayout()
        self.files_limit_checkbox = QCheckBox("Enable open files limit")
        self.files_limit_spinbox = QSpinBox()
        self.files_limit_spinbox.setRange(10, 10000)
        self.files_limit_spinbox.setValue(1000)  # Default 1000 files
        self.files_limit_spinbox.setSuffix(" files")
        self.files_limit_spinbox.setEnabled(False)

        files_layout.addWidget(self.files_limit_checkbox)
        files_layout.addWidget(self.files_limit_spinbox)
        files_layout.addStretch()
        layout.addRow("Open Files Limit:", files_layout)

        # Swap memory option
        self.swap_limit_checkbox = QCheckBox("Include swap memory in memory limit")
        self.swap_limit_checkbox.setChecked(True)
        layout.addRow("Swap Memory:", self.swap_limit_checkbox)

        # Connect signals
        self.memory_limit_checkbox.toggled.connect(self.memory_limit_spinbox.setEnabled)
        self.time_limit_checkbox.toggled.connect(self.time_limit_spinbox.setEnabled)
        self.cpu_limit_checkbox.toggled.connect(self.cpu_limit_spinbox.setEnabled)
        self.files_limit_checkbox.toggled.connect(self.files_limit_spinbox.setEnabled)

        # Connect value change signals
        self.memory_limit_checkbox.toggled.connect(self._emit_limits_changed)
        self.memory_limit_spinbox.valueChanged.connect(self._emit_limits_changed)
        self.time_limit_checkbox.toggled.connect(self._emit_limits_changed)
        self.time_limit_spinbox.valueChanged.connect(self._emit_limits_changed)
        self.cpu_limit_checkbox.toggled.connect(self._emit_limits_changed)
        self.cpu_limit_spinbox.valueChanged.connect(self._emit_limits_changed)
        self.files_limit_checkbox.toggled.connect(self._emit_limits_changed)
        self.files_limit_spinbox.valueChanged.connect(self._emit_limits_changed)
        self.swap_limit_checkbox.toggled.connect(self._emit_limits_changed)

        parent_layout.addWidget(group)

    def _create_monitoring_group(self, parent_layout: QVBoxLayout) -> None:
        """Create the real-time resource monitoring group."""
        group = QGroupBox("Current Resource Usage")
        layout = QFormLayout(group)

        # Memory usage bar
        self.memory_progress = QProgressBar()
        self.memory_progress.setRange(0, 100)
        self.memory_usage_label = QLabel("0 MB (0%)")
        memory_layout = QHBoxLayout()
        memory_layout.addWidget(self.memory_progress)
        memory_layout.addWidget(self.memory_usage_label)
        layout.addRow("Memory:", memory_layout)

        # CPU usage bar
        self.cpu_progress = QProgressBar()
        self.cpu_progress.setRange(0, 100)
        self.cpu_usage_label = QLabel("0%")
        cpu_layout = QHBoxLayout()
        cpu_layout.addWidget(self.cpu_progress)
        cpu_layout.addWidget(self.cpu_usage_label)
        layout.addRow("CPU:", cpu_layout)

        # Processing time
        self.time_usage_label = QLabel("0 seconds")
        layout.addRow("Processing Time:", self.time_usage_label)

        # Open files
        self.files_usage_label = QLabel("0 files")
        layout.addRow("Open Files:", self.files_usage_label)

        parent_layout.addWidget(group)

    def _setup_monitoring(self) -> None:
        """Set up real-time resource monitoring."""
        # Create a timer to update the monitoring display
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._update_monitoring_display)
        self.monitor_timer.start(2000)  # Update every 2 seconds

    def _load_system_defaults(self) -> None:
        """Load reasonable defaults based on system capabilities."""
        memory_info = self.system_info.get("memory", {})
        total_memory_mb = memory_info.get("total_mb", 4096)

        # Set memory limit to 50% of available memory by default
        default_memory_limit = min(max(int(total_memory_mb * 0.5), 512), 8192)
        self.memory_limit_spinbox.setValue(default_memory_limit)

        # CPU cores information for reasonable defaults
        cpu_info = self.system_info.get("cpu", {})
        cpu_count = cpu_info.get("count", 1)

        # Adjust file limits based on system (more cores = potentially more files)
        default_file_limit = min(max(cpu_count * 100, 500), 2000)
        self.files_limit_spinbox.setValue(default_file_limit)

    def get_current_limits(self) -> ResourceLimits:
        """Get the currently configured resource limits.

        Returns:
            ResourceLimits object with current configuration
        """
        # Get values with defaults for ResourceLimits
        memory_mb = self.memory_limit_spinbox.value() if self.memory_limit_checkbox.isChecked() else 4096
        cpu_percent = float(self.cpu_limit_spinbox.value()) if self.cpu_limit_checkbox.isChecked() else 80.0

        return ResourceLimits(
            max_memory_mb=memory_mb,
            max_cpu_percent=cpu_percent,
            # Note: ResourceLimits doesn't support max_processing_time_sec, max_open_files, enable_swap_limit
        )

    def set_limits(self, limits: ResourceLimits) -> None:
        """Set the resource limits configuration.

        Args:
            limits: ResourceLimits object to apply
        """
        # Block signals while updating to avoid recursive emissions
        self.blockSignals(True)

        try:
            # Memory limit
            if limits.max_memory_mb is not None:
                self.memory_limit_checkbox.setChecked(True)
                self.memory_limit_spinbox.setValue(limits.max_memory_mb)
                self.memory_limit_spinbox.setEnabled(True)
            else:
                self.memory_limit_checkbox.setChecked(False)
                self.memory_limit_spinbox.setEnabled(False)

            # CPU limit
            if limits.max_cpu_percent is not None:
                self.cpu_limit_checkbox.setChecked(True)
                self.cpu_limit_spinbox.setValue(int(limits.max_cpu_percent))
                self.cpu_limit_spinbox.setEnabled(True)
            else:
                self.cpu_limit_checkbox.setChecked(False)
                self.cpu_limit_spinbox.setEnabled(False)

            # Processing time limit (not supported by ResourceLimits)
            # Note: max_processing_time_sec not available in ResourceLimits
            self.time_limit_checkbox.setChecked(False)
            self.time_limit_spinbox.setEnabled(False)

            # Open files limit (not supported by ResourceLimits)
            # Note: max_open_files not available in ResourceLimits
            # File limit (currently not supported)
            self.files_limit_checkbox.setChecked(False)
            self.files_limit_spinbox.setEnabled(False)

            # Swap limit
            # Note: ResourceLimits doesn't have enable_swap_limit attribute
            self.swap_limit_checkbox.setChecked(False)

        finally:
            self.blockSignals(False)

    def _emit_limits_changed(self) -> None:
        """Emit the limits_changed signal with current limits."""
        limits = self.get_current_limits()
        self.limits_changed.emit(limits)

    def _update_monitoring_display(self) -> None:
        """Update the real-time monitoring display."""
        try:
            if self.monitor is None:
                # TODO: Implement ResourceMonitor
                self.monitor = None

            if self.monitor is not None and hasattr(self.monitor, "get_current_usage"):
                usage = self.monitor.get_current_usage()
            else:
                return

            # Update memory display
            memory_percent = min(int(usage.memory_percent), 100)
            self.memory_progress.setValue(memory_percent)
            self.memory_usage_label.setText(f"{usage.memory_mb:.0f} MB ({usage.memory_percent:.1f}%)")

            # Update CPU display
            cpu_percent = min(int(usage.cpu_percent), 100)
            self.cpu_progress.setValue(cpu_percent)
            self.cpu_usage_label.setText(f"{usage.cpu_percent:.1f}%")

            # Update processing time
            self.time_usage_label.setText(f"{usage.processing_time_sec:.1f} seconds")

            # Update open files
            self.files_usage_label.setText(f"{usage.open_files} files")

            # Color-code progress bars based on usage levels
            self._update_progress_bar_colors(self.memory_progress, memory_percent)
            self._update_progress_bar_colors(self.cpu_progress, cpu_percent)

        except Exception as e:
            LOGGER.error("Error updating monitoring display: %s", e)

    def _update_progress_bar_colors(self, progress_bar: QProgressBar, value: int) -> None:
        """Update progress bar colors based on usage level.

        Args:
            progress_bar: Progress bar to update
            value: Current value (0-100)
        """
        # Use theme classes instead of hardcoded colors
        if value < 50:
            progress_bar.setProperty("class", "StatusSuccess")
        elif value < 80:
            progress_bar.setProperty("class", "StatusWarning")
        else:
            progress_bar.setProperty("class", "StatusError")

        progress_bar.setStyleSheet(
            """
            QProgressBar::chunk {
                border-radius: 3px;
            }}
        """
        )

    def start_monitoring(self) -> None:
        """Start resource monitoring."""
        if self.monitor is None:
            self.get_current_limits()
            # TODO: Implement ResourceMonitor
            self.monitor = None
        if self.monitor is not None and hasattr(self.monitor, "start_monitoring"):
            self.monitor.start_monitoring()

    def stop_monitoring(self) -> None:
        """Stop resource monitoring."""
        if self.monitor:
            if hasattr(self.monitor, "stop_monitoring"):
                self.monitor.stop_monitoring()

    def get_monitor(self) -> Optional[object]:
        """Get the current resource monitor."""
        return self.monitor
