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

        try:
            # Create the actual tab widget
            tab_widget = self.tab_factories[index]()

            # Store the loaded widget
            self.loaded_tabs[index] = tab_widget

            # Get current tab properties
            tab_text = self.tab_widget.tabText(index)
            tab_icon = self.tab_widget.tabIcon(index)
            tab_tooltip = self.tab_widget.tabToolTip(index)

            # Replace placeholder with actual widget
            self.tab_widget.removeTab(index)
            self.tab_widget.insertTab(index, tab_widget, tab_text)

            if not tab_icon.isNull():
                self.tab_widget.setTabIcon(index, tab_icon)
            if tab_tooltip:
                self.tab_widget.setTabToolTip(index, tab_tooltip)

            # Make sure the tab stays selected
            self.tab_widget.setCurrentIndex(index)

            LOGGER.info(f"Successfully loaded tab at index {index}")

        except Exception:
            LOGGER.exception(f"Error loading tab at index {index}")

            # Show error in placeholder
            if index in self.placeholder_widgets:
                from PyQt6.QtWidgets import QLabel

                error_widget = QLabel("Error loading tab")
                error_widget.setProperty("class", "ErrorLabel")

                tab_text = self.tab_widget.tabText(index)
                self.tab_widget.removeTab(index)
                self.tab_widget.insertTab(index, error_widget, tab_text)

    def load_all_tabs(self) -> None:
        """Force load all registered tabs (useful for testing)."""
        for index in self.tab_factories:
            if index not in self.loaded_tabs:
                self._load_tab(index)

    def is_tab_loaded(self, index: int) -> bool:
        """Check if a tab has been loaded.

        Args:
            index: Tab index

        Returns:
            True if the tab is loaded, False otherwise
        """
        return index in self.loaded_tabs
