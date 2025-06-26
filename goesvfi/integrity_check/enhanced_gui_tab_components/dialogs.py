"""Dialog classes for the enhanced integrity check GUI tab."""

from typing import Any, Dict, List, Optional

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from goesvfi.integrity_check.enhanced_view_model import EnhancedMissingTimestamp


class AWSConfigDialog(QDialog):
    """Dialog for configuring AWS S3 settings."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setWindowTitle(self.tr("AWS S3 Configuration"))
        self.setMinimumWidth(500)

        # Create layout
        layout = QVBoxLayout(self)

        # Info label about unsigned access
        info_label = QLabel(
            "<b>Important:</b> AWS credentials are <b>NOT</b> required to access NOAA GOES data. "
            "This application uses unsigned S3 access for the public NOAA buckets."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("QLabel { padding: 10px; border-radius: 5px; }")
        layout.addWidget(info_label)

        form_layout = QFormLayout()

        # AWS profile
        self.profile_edit = QLineEdit()
        self.profile_edit.setPlaceholderText("Leave empty for unsigned access")
        form_layout.addRow("AWS Profile (optional):", self.profile_edit)

        # AWS region
        self.region_combo = QComboBox()
        regions = [
            "us-east-1",
            "us-east-2",
            "us-west-1",
            "us-west-2",
            "eu-west-1",
            "eu-west-2",
            "eu-central-1",
            "ap-northeast-1",
            "ap-northeast-2",
            "ap-southeast-1",
            "ap-southeast-2",
            "sa-east-1",
        ]
        self.region_combo.addItems(regions)
        self.region_combo.setCurrentText("us-east-1")  # GOES data is in us-east-1
        form_layout.addRow("AWS Region:", self.region_combo)

        # Note about credentials
        note_label = QLabel(
            "Note: NOAA GOES data is stored in the <b>us-east-1</b> region in public S3 buckets. "
            "The application uses unsigned S3 access by default, which requires no credentials. "
            "Only provide a profile if you need to access private buckets."
        )
        note_label.setWordWrap(True)
        note_label.setStyleSheet("QLabel { }")

        layout.addLayout(form_layout)
        layout.addWidget(note_label)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_aws_profile(self) -> Optional[str]:
        """Get the AWS profile name."""
        profile = self.profile_edit.text().strip()
        return profile if profile else None

    def get_aws_region(self) -> str:
        """Get the AWS region."""
        return str(self.region_combo.currentText())

    def set_aws_profile(self, profile: Optional[str]) -> None:
        """Set the AWS profile name."""
        self.profile_edit.setText(profile or "")

    def set_aws_region(self, region: str) -> None:
        """Set the AWS region."""
        self.region_combo.setCurrentText(region)


class CDNConfigDialog(QDialog):
    """Dialog for configuring CDN settings."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setWindowTitle(self.tr("CDN Configuration"))
        self.setMinimumWidth(400)

        # Create layout
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        # Resolution
        self.resolution_combo = QComboBox()
        resolutions = ["1000m", "500m", "250m", "100m"]
        self.resolution_combo.addItems(resolutions)
        self.resolution_combo.setCurrentText("1000m")  # Default CDN resolution
        form_layout.addRow("Resolution:", self.resolution_combo)

        # Note about resolutions
        note_label = QLabel(
            "Note: Lower resolutions download faster but have less detail. "
            "The NOAA STAR CDN may not provide all resolutions for all images."
        )
        note_label.setWordWrap(True)
        note_label.setStyleSheet("QLabel { }")

        layout.addLayout(form_layout)
        layout.addWidget(note_label)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_cdn_resolution(self) -> str:
        """Get the CDN resolution."""
        return str(self.resolution_combo.currentText())

    def set_cdn_resolution(self, resolution: str) -> None:
        """Set the CDN resolution."""
        self.resolution_combo.setCurrentText(resolution)


class AdvancedOptionsDialog(QDialog):
    """Dialog for configuring advanced integrity check options."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setWindowTitle(self.tr("Advanced Integrity Check Options"))
        self.setMinimumWidth(500)

        # Create layout
        layout = QVBoxLayout(self)

        # Connection Options Group
        connection_group = QGroupBox(self.tr("Connection Options"))
        connection_layout = QFormLayout()

        # Connection timeout
        self.timeout_spinbox = QSpinBox()
        self.timeout_spinbox.setRange(30, 300)
        self.timeout_spinbox.setValue(60)
        self.timeout_spinbox.setSuffix(" seconds")
        connection_layout.addRow("Connection Timeout:", self.timeout_spinbox)

        # Maximum concurrent downloads
        self.max_concurrent_spinbox = QSpinBox()
        self.max_concurrent_spinbox.setRange(1, 20)
        self.max_concurrent_spinbox.setValue(5)
        self.max_concurrent_spinbox.setToolTip(
            self.tr(
                "Maximum number of concurrent downloads. Higher values may improve speed but increase resource usage."
            )
        )
        connection_layout.addRow("Max Concurrent Downloads:", self.max_concurrent_spinbox)

        # Retry attempts
        self.retry_spinbox = QSpinBox()
        self.retry_spinbox.setRange(0, 5)
        self.retry_spinbox.setValue(2)
        self.retry_spinbox.setToolTip(self.tr("Number of times to retry failed downloads automatically"))
        connection_layout.addRow("Auto-retry Attempts:", self.retry_spinbox)

        connection_group.setLayout(connection_layout)
        layout.addWidget(connection_group)

        # Performance Options Group
        performance_group = QGroupBox(self.tr("Performance Options"))
        performance_layout = QFormLayout()

        # Network throttling
        self.throttle_checkbox = QCheckBox()
        self.throttle_checkbox.setToolTip(self.tr("Limit download speed to reduce impact on your network"))
        performance_layout.addRow("Enable Network Throttling:", self.throttle_checkbox)

        # Throttle speed
        self.throttle_spinbox = QSpinBox()
        self.throttle_spinbox.setRange(100, 10000)
        self.throttle_spinbox.setValue(1000)
        self.throttle_spinbox.setSuffix(" KB/s")
        self.throttle_spinbox.setEnabled(False)
        self.throttle_spinbox.setToolTip(self.tr("Maximum download speed per file"))
        performance_layout.addRow("Max Download Speed:", self.throttle_spinbox)
        self.throttle_checkbox.toggled.connect(self.throttle_spinbox.setEnabled)

        # Process priority
        self.priority_combo = QComboBox()
        self.priority_combo.addItems([self.tr("Normal"), self.tr("Low"), self.tr("High")])
        self.priority_combo.setCurrentText("Normal")
        self.priority_combo.setToolTip(self.tr("Process priority for download operations"))
        performance_layout.addRow("Process Priority:", self.priority_combo)

        performance_group.setLayout(performance_layout)
        layout.addWidget(performance_group)

        # Image Processing Options Group
        image_group = QGroupBox(self.tr("Image Processing Options"))
        image_layout = QFormLayout()

        # Auto-enhance images
        self.auto_enhance_checkbox = QCheckBox()
        self.auto_enhance_checkbox.setToolTip(self.tr("Automatically enhance downloaded images for better visibility"))
        image_layout.addRow("Auto-enhance Images:", self.auto_enhance_checkbox)

        # Apply false color
        self.false_color_checkbox = QCheckBox()
        self.false_color_checkbox.setToolTip(self.tr("Apply false coloring to IR images for better visualization"))
        image_layout.addRow("Apply False Color:", self.false_color_checkbox)

        # Automatically convert NetCDF
        self.convert_netcdf_checkbox = QCheckBox()
        self.convert_netcdf_checkbox.setChecked(True)
        self.convert_netcdf_checkbox.setToolTip(self.tr("Automatically convert NetCDF files to PNG after download"))
        image_layout.addRow("Auto-convert NetCDF:", self.convert_netcdf_checkbox)

        image_group.setLayout(image_layout)
        layout.addWidget(image_group)

        # Notification Options Group
        notification_group = QGroupBox(self.tr("Notification Options"))
        notification_layout = QFormLayout()

        # Desktop notifications
        self.desktop_notify_checkbox = QCheckBox()
        self.desktop_notify_checkbox.setToolTip(self.tr("Show desktop notifications when operations complete"))
        notification_layout.addRow("Desktop Notifications:", self.desktop_notify_checkbox)

        # Sound alerts
        self.sound_alerts_checkbox = QCheckBox()
        self.sound_alerts_checkbox.setToolTip(self.tr("Play sound when operations complete or errors occur"))
        notification_layout.addRow("Sound Alerts:", self.sound_alerts_checkbox)

        notification_group.setLayout(notification_layout)
        layout.addWidget(notification_group)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Connect signals
        self.throttle_checkbox.toggled.connect(self.throttle_spinbox.setEnabled)

    def get_options(self) -> Dict[str, Any]:
        """Get the options as a dictionary."""
        return {
            "timeout": self.timeout_spinbox.value(),
            "max_concurrent": self.max_concurrent_spinbox.value(),
            "retry_attempts": self.retry_spinbox.value(),
            "throttle_enabled": self.throttle_checkbox.isChecked(),
            "throttle_speed": (self.throttle_spinbox.value() if self.throttle_checkbox.isChecked() else 0),
            "process_priority": self.priority_combo.currentText().lower(),
            "auto_enhance": self.auto_enhance_checkbox.isChecked(),
            "false_color": self.false_color_checkbox.isChecked(),
            "convert_netcdf": self.convert_netcdf_checkbox.isChecked(),
            "desktop_notify": self.desktop_notify_checkbox.isChecked(),
            "sound_alerts": self.sound_alerts_checkbox.isChecked(),
        }

    def set_options(self, options: Dict[str, Any]) -> None:
        """Set the options from a dictionary."""
        if "timeout" in options:
            self.timeout_spinbox.setValue(options["timeout"])
        if "max_concurrent" in options:
            self.max_concurrent_spinbox.setValue(options["max_concurrent"])
        if "retry_attempts" in options:
            self.retry_spinbox.setValue(options["retry_attempts"])
        if "throttle_enabled" in options:
            self.throttle_checkbox.setChecked(options["throttle_enabled"])
        if "throttle_speed" in options and options["throttle_enabled"]:
            self.throttle_spinbox.setValue(options["throttle_speed"])
        if "process_priority" in options:
            self.priority_combo.setCurrentText(options["process_priority"].capitalize())
        if "auto_enhance" in options:
            self.auto_enhance_checkbox.setChecked(options["auto_enhance"])
        if "false_color" in options:
            self.false_color_checkbox.setChecked(options["false_color"])
        if "convert_netcdf" in options:
            self.convert_netcdf_checkbox.setChecked(options["convert_netcdf"])
        if "desktop_notify" in options:
            self.desktop_notify_checkbox.setChecked(options["desktop_notify"])
        if "sound_alerts" in options:
            self.sound_alerts_checkbox.setChecked(options["sound_alerts"])


class BatchOperationsDialog(QDialog):
    """Dialog for performing batch operations on integrity check results."""

    def __init__(self, items: List[EnhancedMissingTimestamp], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.items = items

        self.setWindowTitle(self.tr("Batch Operations"))
        self.setMinimumWidth(500)

        # Create layout
        layout = QVBoxLayout(self)

        # Operations selection
        operation_group = QGroupBox(self.tr("Select Operation"))
        operation_layout = QVBoxLayout()

        self.download_radio = QRadioButton("Download Selected Files")
        self.download_radio.setChecked(True)
        operation_layout.addWidget(self.download_radio)

        self.retry_radio = QRadioButton("Retry Failed Downloads")
        operation_layout.addWidget(self.retry_radio)

        self.export_radio = QRadioButton("Export Selected Items to CSV")
        operation_layout.addWidget(self.export_radio)

        self.delete_radio = QRadioButton("Delete Selected Files")
        operation_layout.addWidget(self.delete_radio)

        operation_group.setLayout(operation_layout)
        layout.addWidget(operation_group)

        # Filter options
        filter_group = QGroupBox(self.tr("Filter Options"))
        filter_layout = QVBoxLayout()

        self.filter_all_radio = QRadioButton("All Items")
        self.filter_all_radio.setChecked(True)
        filter_layout.addWidget(self.filter_all_radio)

        self.filter_selected_radio = QRadioButton("Selected Items Only")
        filter_layout.addWidget(self.filter_selected_radio)

        self.filter_failed_radio = QRadioButton("Failed Downloads Only")
        filter_layout.addWidget(self.filter_failed_radio)

        self.filter_missing_radio = QRadioButton("Missing Files Only")
        filter_layout.addWidget(self.filter_missing_radio)

        self.filter_downloaded_radio = QRadioButton("Downloaded Files Only")
        filter_layout.addWidget(self.filter_downloaded_radio)

        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        # Summary label
        self.summary_label = QLabel(self.tr("Selected operation will process X items"))
        layout.addWidget(self.summary_label)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Connect signals
        self.download_radio.toggled.connect(self._update_summary)
        self.retry_radio.toggled.connect(self._update_summary)
        self.export_radio.toggled.connect(self._update_summary)
        self.delete_radio.toggled.connect(self._update_summary)
        self.filter_all_radio.toggled.connect(self._update_summary)
        self.filter_selected_radio.toggled.connect(self._update_summary)
        self.filter_failed_radio.toggled.connect(self._update_summary)
        self.filter_missing_radio.toggled.connect(self._update_summary)
        self.filter_downloaded_radio.toggled.connect(self._update_summary)

        # Initial update
        self._update_summary()

    def _update_summary(self) -> None:
        """Update the summary label based on selected options."""
        operation = "Download"
        if self.retry_radio.isChecked():
            operation = "Retry"
        elif self.export_radio.isChecked():
            operation = "Export"
        elif self.delete_radio.isChecked():
            operation = "Delete"

        # Count items based on filter
        count = len(self.items)
        if self.filter_failed_radio.isChecked():
            count = sum(1 for item in self.items if not item.is_downloaded and item.download_error)
        elif self.filter_missing_radio.isChecked():
            count = sum(1 for item in self.items if not item.is_downloaded)
        elif self.filter_downloaded_radio.isChecked():
            count = sum(1 for item in self.items if item.is_downloaded)

        self.summary_label.setText(f"Selected operation will {operation.lower()} {count} items")

    def get_options(self) -> Dict[str, Any]:
        """Get the selected options."""
        operation = "download"
        if self.retry_radio.isChecked():
            operation = "retry"
        elif self.export_radio.isChecked():
            operation = "export"
        elif self.delete_radio.isChecked():
            operation = "delete"

        filter_type = "all"
        if self.filter_selected_radio.isChecked():
            filter_type = "selected"
        elif self.filter_failed_radio.isChecked():
            filter_type = "failed"
        elif self.filter_missing_radio.isChecked():
            filter_type = "missing"
        elif self.filter_downloaded_radio.isChecked():
            filter_type = "downloaded"

        return {
            "operation": operation,
            "filter": filter_type,
        }
