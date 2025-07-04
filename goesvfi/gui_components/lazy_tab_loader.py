"""Lazy tab loading functionality for improved startup performance."""

from collections.abc import Callable

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QTabWidget, QWidget

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class LazyTabLoader:
    """Manages lazy loading of tabs to improve application startup time."""

    def __init__(self, tab_widget: QTabWidget) -> None:
        """Initialize the lazy tab loader.

        Args:
            tab_widget: The QTabWidget to manage
        """
        self.tab_widget = tab_widget
        self.tab_factories: dict[int, Callable[[], QWidget]] = {}
        self.loaded_tabs: dict[int, QWidget] = {}
        self.placeholder_widgets: dict[int, QWidget] = {}

        # Connect to tab change signal
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

    def register_tab(self, index: int, factory: Callable[[], QWidget], placeholder: QWidget | None = None) -> None:
        """Register a tab for lazy loading.

        Args:
            index: Tab index
            factory: Factory function that creates the tab widget
            placeholder: Optional placeholder widget to show before loading
        """
        self.tab_factories[index] = factory

        if placeholder is None:
            # Create a simple placeholder
            from PyQt6.QtCore import Qt
            from PyQt6.QtWidgets import QLabel

            placeholder = QLabel("Loading...")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setProperty("class", "PlaceholderLabel")

        self.placeholder_widgets[index] = placeholder

    def setup_lazy_tab(self, index: int, title: str, icon: str | QIcon | None = None) -> None:
        """Set up a tab for lazy loading.

        Args:
            index: Tab index
            title: Tab title
            icon: Tab icon (emoji string or QIcon object)
        """
        if index in self.tab_factories and index in self.placeholder_widgets:
            # Insert placeholder widget
            if isinstance(icon, QIcon):
                # Use QIcon directly
                self.tab_widget.insertTab(index, self.placeholder_widgets[index], "")
                self.tab_widget.setTabIcon(index, icon)
                self.tab_widget.setTabText(index, title)
            elif isinstance(icon, str) and icon:
                # Legacy emoji string support
                self.tab_widget.insertTab(index, self.placeholder_widgets[index], icon)
            else:
                # No icon, just title
                self.tab_widget.insertTab(index, self.placeholder_widgets[index], title)

            LOGGER.debug(f"Set up lazy tab at index {index}: {title}")
        else:
            LOGGER.warning(f"Tab at index {index} not registered for lazy loading")

    def _on_tab_changed(self, index: int) -> None:
        """Handle tab change event.

        Args:
            index: Index of the newly selected tab
        """
        if index < 0:
            return

        # Check if this tab needs to be loaded
        if index in self.tab_factories and index not in self.loaded_tabs:
            self._load_tab(index)

    def _load_tab(self, index: int) -> None:
        """Load a tab on demand.

        Args:
            index: Tab index to load
        """
        if index not in self.tab_factories:
            return

        LOGGER.info(f"Lazy loading tab at index {index}")

        # Save current selection state before any modifications
        was_current = self.tab_widget.currentIndex() == index

        try:
            # Create the actual tab widget
            tab_widget = self.tab_factories[index]()

            # Store the loaded widget
            self.loaded_tabs[index] = tab_widget

            # Get current tab properties before modification
            tab_text = self.tab_widget.tabText(index)
            tab_icon = self.tab_widget.tabIcon(index)
            tab_tooltip = self.tab_widget.tabToolTip(index)
            tab_enabled = self.tab_widget.isTabEnabled(index)

            # Safe tab replacement without affecting other tabs
            old_widget = self.tab_widget.widget(index)

            # Block signals during replacement to prevent unwanted tab changes
            self.tab_widget.blockSignals(True)
            try:
                # Replace the widget directly instead of remove/insert
                self.tab_widget.removeTab(index)
                self.tab_widget.insertTab(index, tab_widget, tab_text)

                # Restore all tab properties
                if not tab_icon.isNull():
                    self.tab_widget.setTabIcon(index, tab_icon)
                if tab_tooltip:
                    self.tab_widget.setTabToolTip(index, tab_tooltip)
                self.tab_widget.setTabEnabled(index, tab_enabled)

                # Clean up old placeholder widget
                if old_widget and old_widget in self.placeholder_widgets.values():
                    old_widget.deleteLater()

            finally:
                # Always unblock signals
                self.tab_widget.blockSignals(False)

            # Restore selection only if this tab was previously selected
            if was_current:
                self.tab_widget.setCurrentIndex(index)

            LOGGER.info(f"Successfully loaded tab at index {index}")

        except Exception as e:
            LOGGER.exception(f"Error loading tab at index {index}: {e}")

            # Safe error handling - create error widget
            try:
                from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

                error_container = QWidget()
                error_layout = QVBoxLayout(error_container)

                error_label = QLabel(f"Error loading tab: {str(e)[:100]}")
                error_label.setProperty("class", "ErrorLabel")
                error_label.setWordWrap(True)

                retry_label = QLabel("Try switching to another tab and back to retry")
                retry_label.setProperty("class", "InfoLabel")

                error_layout.addWidget(error_label)
                error_layout.addWidget(retry_label)

                # Safe replacement with error widget
                self.tab_widget.blockSignals(True)
                try:
                    tab_text = self.tab_widget.tabText(index) if index < self.tab_widget.count() else "Error"
                    if index < self.tab_widget.count():
                        self.tab_widget.removeTab(index)
                    self.tab_widget.insertTab(index, error_container, tab_text)
                    self.tab_widget.setTabEnabled(index, True)  # Keep tab accessible for retry
                finally:
                    self.tab_widget.blockSignals(False)

                # Don't auto-select error tabs
                if was_current and index > 0:
                    self.tab_widget.setCurrentIndex(0)  # Switch to first tab instead

            except Exception:
                LOGGER.exception(f"Failed to create error widget for tab {index}")

    def retry_tab_loading(self, index: int) -> None:
        """Retry loading a failed tab.

        Args:
            index: Tab index to retry loading
        """
        if index in self.loaded_tabs:
            # Clear the loaded tab to force reload
            old_widget = self.loaded_tabs[index]
            del self.loaded_tabs[index]
            if old_widget:
                old_widget.deleteLater()
            LOGGER.info(f"Cleared failed tab {index} for retry")

        # Attempt to reload
        self._load_tab(index)

    def is_tab_loaded(self, index: int) -> bool:
        """Check if a tab is fully loaded.

        Args:
            index: Tab index to check

        Returns:
            True if tab is loaded, False if it's a placeholder or error
        """
        return index in self.loaded_tabs

    def get_tab_loading_state(self, index: int) -> str:
        """Get the loading state of a tab.

        Args:
            index: Tab index to check

        Returns:
            'loaded', 'placeholder', 'error', or 'unknown'
        """
        if index in self.loaded_tabs:
            return "loaded"
        if index in self.placeholder_widgets:
            # Check if it's an error widget
            widget = self.tab_widget.widget(index)
            if widget and hasattr(widget, "findChild"):
                from PyQt6.QtWidgets import QLabel

                error_label = widget.findChild(QLabel)
                if error_label and "Error loading tab" in error_label.text():
                    return "error"
            return "placeholder"
        return "unknown"

    def load_all_tabs(self) -> None:
        """Force load all registered tabs (useful for testing)."""
        for index in self.tab_factories:
            if index not in self.loaded_tabs:
                self._load_tab(index)
