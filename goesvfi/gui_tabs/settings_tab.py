"""Settings tab for GOES-VFI application configuration."""

from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from goesvfi.gui_components.theme_manager import AVAILABLE_THEMES, ThemeManager
from goesvfi.utils import config, log

LOGGER = log.get_logger(__name__)


class SettingsTab(QWidget):
    """Settings tab for application configuration."""

    # Signals
    themeChanged = pyqtSignal(str)  # Emitted when theme changes
    settingsChanged = pyqtSignal()  # Emitted when any setting changes

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the settings tab."""
        super().__init__(parent)
        self.theme_manager = ThemeManager()
        self._setup_ui()
        self._load_current_settings()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Create header
        header = self._create_header()
        layout.addWidget(header)

        # Create tab widget for different setting categories
        self.settings_tabs = QTabWidget()
        self.settings_tabs.setTabPosition(QTabWidget.TabPosition.North)

        # Appearance settings tab
        appearance_tab = self._create_appearance_tab()
        self.settings_tabs.addTab(appearance_tab, "🎨 Appearance")

        # Application settings tab
        app_tab = self._create_application_tab()
        self.settings_tabs.addTab(app_tab, "⚙️ Application")

        # Advanced settings tab
        advanced_tab = self._create_advanced_tab()
        self.settings_tabs.addTab(advanced_tab, "🔧 Advanced")

        layout.addWidget(self.settings_tabs)

        # Action buttons
        button_layout = self._create_action_buttons()
        layout.addLayout(button_layout)

    def _create_header(self) -> QLabel:
        """Create the settings header."""
        header = QLabel("⚙️ Application Settings")
        header.setProperty("class", "AppHeader")
        header.setStyleSheet(
            """
            QLabel {
                font-size: 18px;
                font-weight: bold;
                padding: 12px 16px;
                border-radius: 8px;
                margin-bottom: 10px;
            }
            """
        )
        return header

    def _create_appearance_tab(self) -> QWidget:
        """Create the appearance settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Theme settings group
        theme_group = QGroupBox("Theme Settings")
        theme_layout = QFormLayout(theme_group)

        # Theme selection
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(AVAILABLE_THEMES)
        self.theme_combo.setToolTip("Select the application theme")
        theme_layout.addRow("Theme:", self.theme_combo)

        # Custom overrides
        self.custom_overrides_checkbox = QCheckBox("Enable custom GOES-VFI styling")
        self.custom_overrides_checkbox.setToolTip("Apply domain-specific styling for satellite data visualization")
        theme_layout.addRow("Custom styling:", self.custom_overrides_checkbox)

        # Density scale
        self.density_scale_combo = QComboBox()
        self.density_scale_combo.addItems(
            ["0 (Normal)", "-1 (Compact)", "-2 (Very Compact)", "1 (Spacious)", "2 (Very Spacious)"]
        )
        self.density_scale_combo.setToolTip("Adjust UI element spacing and sizing")
        theme_layout.addRow("UI Density:", self.density_scale_combo)

        # Theme preview
        preview_label = QLabel("Theme preview will update when you change themes")
        preview_label.setProperty("class", "StatusInfo")
        preview_label.setWordWrap(True)
        theme_layout.addRow("Preview:", preview_label)

        layout.addWidget(theme_group)

        # Theme actions
        theme_actions = QGroupBox("Theme Actions")
        actions_layout = QVBoxLayout(theme_actions)

        apply_theme_btn = QPushButton("Apply Theme Now")
        apply_theme_btn.setToolTip("Apply the selected theme immediately")
        apply_theme_btn.clicked.connect(self._apply_theme_immediately)
        actions_layout.addWidget(apply_theme_btn)

        reset_theme_btn = QPushButton("Reset to Default")
        reset_theme_btn.setToolTip("Reset theme to application default")
        reset_theme_btn.clicked.connect(self._reset_theme_to_default)
        actions_layout.addWidget(reset_theme_btn)

        layout.addWidget(theme_actions)
        layout.addStretch()

        return tab

    def _create_application_tab(self) -> QWidget:
        """Create the application settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # General settings
        general_group = QGroupBox("General Settings")
        general_layout = QFormLayout(general_group)

        # Auto-save settings
        self.auto_save_checkbox = QCheckBox("Auto-save settings on change")
        self.auto_save_checkbox.setToolTip("Automatically save settings when changed")
        general_layout.addRow("Auto-save:", self.auto_save_checkbox)

        # Debug mode
        self.debug_mode_checkbox = QCheckBox("Enable debug mode")
        self.debug_mode_checkbox.setToolTip("Enable debug logging and additional diagnostics")
        general_layout.addRow("Debug mode:", self.debug_mode_checkbox)

        layout.addWidget(general_group)

        # Performance settings
        performance_group = QGroupBox("Performance")
        performance_layout = QFormLayout(performance_group)

        # Preview update delay
        self.preview_delay_spinbox = QSpinBox()
        self.preview_delay_spinbox.setRange(100, 5000)
        self.preview_delay_spinbox.setSuffix(" ms")
        self.preview_delay_spinbox.setValue(100)
        self.preview_delay_spinbox.setToolTip("Delay before updating previews after changes")
        performance_layout.addRow("Preview delay:", self.preview_delay_spinbox)

        # Thread pool size
        self.thread_pool_spinbox = QSpinBox()
        self.thread_pool_spinbox.setRange(1, 16)
        self.thread_pool_spinbox.setValue(4)
        self.thread_pool_spinbox.setToolTip("Number of worker threads for processing")
        performance_layout.addRow("Worker threads:", self.thread_pool_spinbox)

        layout.addWidget(performance_group)
        layout.addStretch()

        return tab

    def _create_advanced_tab(self) -> QWidget:
        """Create the advanced settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # System settings
        system_group = QGroupBox("System Settings")
        system_layout = QFormLayout(system_group)

        # Fallback mode
        self.fallback_checkbox = QCheckBox("Enable theme fallback")
        self.fallback_checkbox.setToolTip("Fall back to basic theme if qt-material fails to load")
        system_layout.addRow("Theme fallback:", self.fallback_checkbox)

        # Logging level
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level_combo.setToolTip("Set the application logging level")
        system_layout.addRow("Log level:", self.log_level_combo)

        layout.addWidget(system_group)

        # Development settings
        dev_group = QGroupBox("Development")
        dev_layout = QVBoxLayout(dev_group)

        # Config file location
        config_location_label = QLabel(f"Config: {config.get_config_path()}")
        config_location_label.setWordWrap(True)
        config_location_label.setProperty("class", "StatusInfo")
        dev_layout.addWidget(config_location_label)

        # Settings file location
        if hasattr(self.parent(), "settings"):
            settings_location = getattr(self.parent().settings, "fileName", lambda: "Unknown")()
            settings_location_label = QLabel(f"Settings: {settings_location}")
        else:
            settings_location_label = QLabel("Settings: Unknown location")
        settings_location_label.setWordWrap(True)
        settings_location_label.setProperty("class", "StatusInfo")
        dev_layout.addWidget(settings_location_label)

        layout.addWidget(dev_group)
        layout.addStretch()

        return tab

    def _create_action_buttons(self) -> QHBoxLayout:
        """Create action buttons at the bottom."""
        layout = QHBoxLayout()
        layout.addStretch()

        # Save button
        save_btn = QPushButton("💾 Save Settings")
        save_btn.setToolTip("Save all settings to configuration files")
        save_btn.clicked.connect(self._save_settings)
        layout.addWidget(save_btn)

        # Reset button
        reset_btn = QPushButton("🔄 Reset to Defaults")
        reset_btn.setToolTip("Reset all settings to their default values")
        reset_btn.clicked.connect(self._reset_to_defaults)
        layout.addWidget(reset_btn)

        # Reload button
        reload_btn = QPushButton("⚡ Reload Settings")
        reload_btn.setToolTip("Reload settings from configuration files")
        reload_btn.clicked.connect(self._reload_settings)
        layout.addWidget(reload_btn)

        return layout

    def _load_current_settings(self) -> None:
        """Load current settings into the UI."""
        try:
            # Theme settings
            current_theme = config.get_theme_name()
            if current_theme in AVAILABLE_THEMES:
                self.theme_combo.setCurrentText(current_theme)

            self.custom_overrides_checkbox.setChecked(config.get_theme_custom_overrides())
            self.fallback_checkbox.setChecked(config.get_theme_fallback_enabled())

            # Density scale
            density_scale = config.get_theme_density_scale()
            density_mapping = {"0": 0, "-1": 1, "-2": 2, "1": 3, "2": 4}
            if density_scale in density_mapping:
                self.density_scale_combo.setCurrentIndex(density_mapping[density_scale])

            # Log level
            log_level = config.get_logging_level()
            if log_level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
                self.log_level_combo.setCurrentText(log_level)

            LOGGER.info("Settings loaded successfully")
        except Exception as e:
            LOGGER.error(f"Failed to load settings: {e}")

    def _connect_signals(self) -> None:
        """Connect widget signals to handlers."""
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        self.custom_overrides_checkbox.toggled.connect(self._on_setting_changed)
        self.density_scale_combo.currentTextChanged.connect(self._on_setting_changed)
        self.fallback_checkbox.toggled.connect(self._on_setting_changed)

    def _on_theme_changed(self, theme_name: str) -> None:
        """Handle theme selection change."""
        LOGGER.info(f"Theme changed to: {theme_name}")
        self.themeChanged.emit(theme_name)
        self._on_setting_changed()

    def _on_setting_changed(self) -> None:
        """Handle any setting change."""
        self.settingsChanged.emit()

    def _apply_theme_immediately(self) -> None:
        """Apply the selected theme immediately."""
        theme_name = self.theme_combo.currentText()
        try:
            from PyQt6.QtWidgets import QApplication

            app = QApplication.instance()
            if app:
                self.theme_manager.change_theme(app, theme_name)
                LOGGER.info(f"Applied theme: {theme_name}")
            else:
                LOGGER.error("No QApplication instance found")
        except Exception as e:
            LOGGER.error(f"Failed to apply theme: {e}")

    def _reset_theme_to_default(self) -> None:
        """Reset theme to default."""
        from goesvfi.gui_components.theme_manager import DEFAULT_THEME

        self.theme_combo.setCurrentText(DEFAULT_THEME)
        self._apply_theme_immediately()

    def _save_settings(self) -> None:
        """Save all settings."""
        try:
            # This would typically save to config files
            # For now, just emit the settings changed signal
            self.settingsChanged.emit()
            LOGGER.info("Settings saved")
        except Exception as e:
            LOGGER.error(f"Failed to save settings: {e}")

    def _reset_to_defaults(self) -> None:
        """Reset all settings to defaults."""
        try:
            self._reset_theme_to_default()
            self.custom_overrides_checkbox.setChecked(True)
            self.fallback_checkbox.setChecked(True)
            self.density_scale_combo.setCurrentIndex(0)  # Normal
            self.log_level_combo.setCurrentText("INFO")
            self.auto_save_checkbox.setChecked(True)
            self.debug_mode_checkbox.setChecked(False)
            LOGGER.info("Settings reset to defaults")
        except Exception as e:
            LOGGER.error(f"Failed to reset settings: {e}")

    def _reload_settings(self) -> None:
        """Reload settings from configuration files."""
        try:
            # Clear the config cache to force reload
            config._load_config.cache_clear()
            self._load_current_settings()
            LOGGER.info("Settings reloaded")
        except Exception as e:
            LOGGER.error(f"Failed to reload settings: {e}")

    def get_current_theme(self) -> str:
        """Get the currently selected theme."""
        return self.theme_combo.currentText()

    def get_current_settings(self) -> dict:
        """Get all current settings as a dictionary."""
        density_values = ["0", "-1", "-2", "1", "2"]
        density_index = self.density_scale_combo.currentIndex()
        density_value = density_values[density_index] if 0 <= density_index < len(density_values) else "0"

        return {
            "theme": {
                "name": self.theme_combo.currentText(),
                "custom_overrides": self.custom_overrides_checkbox.isChecked(),
                "density_scale": density_value,
                "fallback_enabled": self.fallback_checkbox.isChecked(),
            },
            "logging": {
                "level": self.log_level_combo.currentText(),
            },
            "app": {
                "auto_save": self.auto_save_checkbox.isChecked(),
                "debug_mode": self.debug_mode_checkbox.isChecked(),
                "preview_delay": self.preview_delay_spinbox.value(),
                "thread_pool_size": self.thread_pool_spinbox.value(),
            },
        }
