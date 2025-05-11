"""
Signal management utilities for integrity check tab connections.

This module provides a standardized approach for connecting signals between
different components in the integrity check system, ensuring proper data flow
and reducing redundant code across different tab implementations.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from PyQt6.QtCore import QObject, pyqtSignal

from .enhanced_view_model import EnhancedIntegrityCheckViewModel
from .view_model import MissingTimestamp

# Configure logging
LOGGER = logging.getLogger(__name__)


class SignalConnectionError(Exception):
    """Exception raised for signal connection errors."""

    pass


class TabSignalManager:
    """
    Manages signal connections between integrity check tabs.

    This class provides a standardized approach for connecting signals between
    different tabs in the integrity check system, ensuring consistent data flow
    and proper error handling.
    """

    def __init__(self) -> None:
        """Initialize the signal manager."""
        self._connections: Dict[str, List[Tuple[QObject, str]]] = {}
        self._signal_map: Dict[str, List[str]] = {}

        # Create a mapping of common signal names across tabs
        self._initialize_signal_map()

    def _initialize_signal_map(self) -> None:
        """Initialize the signal name mapping."""
        # Map common signal names between different tabs
        self._signal_map = {
            # Directory selection
            "directory_selection": [
                "directory_selected",
                "directorySelected",
                "dirChanged",
                "directoryChanged",
            ],
            # Date range selection
            "date_range_selection": [
                "date_range_changed",
                "dateRangeSelected",
                "dateRangeChanged",
                "dateSelected",
            ],
            # Timestamp selection
            "timestamp_selection": [
                "timestamp_selected",
                "timestampSelected",
                "timeSelected",
            ],
            # Item selection
            "item_selection": ["item_selected", "itemSelected", "missingItemSelected"],
            # Download actions
            "download_action": [
                "download_requested",
                "downloadRequested",
                "downloadItem",
                "downloadFile",
            ],
            # View actions
            "view_action": ["view_requested", "viewRequested", "viewItem", "viewFile"],
            # Scan completion
            "scan_completion": ["scan_completed", "scanCompleted", "scanFinished"],
            # Missing items update
            "missing_items_update": ["missing_items_updated", "missingItemsUpdated"],
        }

    def connect_tabs(self, tabs: Dict[str, QObject]) -> None:
        """
        Connect signals between multiple tabs.

        Args:
            tabs: Dictionary of tabs to connect, with keys as tab names
                 and values as tab objects.

        Example:
            signal_manager.connect_tabs({
                "integrity": integrity_tab,
                "timeline": timeline_tab,
                "results": results_tab
            })
        """
        LOGGER.info("Connecting signals between %d tabs", len(tabs))

        # Connect each tab's signals to other tabs
        for tab_name, tab in tabs.items():
            self._connect_tab_signals(tab_name, tab, tabs)

    def _connect_tab_signals(
        self, tab_name: str, tab: QObject, all_tabs: Dict[str, QObject]
    ) -> None:
        """
        Connect a tab's signals to other tabs.

        Args:
            tab_name: Name of the tab to connect
            tab: Tab object to connect
            all_tabs: Dictionary of all tabs
        """
        LOGGER.debug("Connecting signals for tab %r", tab_name)

        # Connect directory selection signals
        self._connect_signal_group(
            tab, "directory_selection", all_tabs, self._handle_directory_signal
        )

        # Connect date range selection signals
        self._connect_signal_group(
            tab, "date_range_selection", all_tabs, self._handle_date_range_signal
        )

        # Connect timestamp selection signals
        self._connect_signal_group(
            tab, "timestamp_selection", all_tabs, self._handle_timestamp_signal
        )

        # Connect item selection signals
        self._connect_signal_group(
            tab, "item_selection", all_tabs, self._handle_item_signal
        )

        # Connect download action signals
        self._connect_signal_group(
            tab, "download_action", all_tabs, self._handle_download_signal
        )

        # Connect view action signals
        self._connect_signal_group(
            tab, "view_action", all_tabs, self._handle_view_signal
        )

        # Connect scan completion signals if this is a view model
        if isinstance(tab, EnhancedIntegrityCheckViewModel):
            for signal_name in self._signal_map["scan_completion"]:
                if hasattr(tab, signal_name):
                    signal = getattr(tab, signal_name)
                    if isinstance(signal, pyqtSignal):
                        # This will update all tabs when scan completes
                        signal.connect(
                            lambda *args: self._handle_scan_completion(all_tabs, *args)
                        )
                        LOGGER.debug("Connected view model %s signal", signal_name)

        # Connect missing items updated signals if this is a view model
        if isinstance(tab, EnhancedIntegrityCheckViewModel):
            for signal_name in self._signal_map["missing_items_update"]:
                if hasattr(tab, signal_name):
                    signal = getattr(tab, signal_name)
                    if isinstance(signal, pyqtSignal):
                        # This will update all tabs when missing items are updated
                        signal.connect(
                            lambda items: self._handle_missing_items_update(
                                all_tabs, items
                            )
                        )
                        LOGGER.debug("Connected view model %s signal", signal_name)

    def _connect_signal_group(
        self,
        tab: QObject,
        group_key: str,
        all_tabs: Dict[str, QObject],
        handler: Callable,
    ) -> None:
        """
        Connect a group of similar signals from a tab to appropriate handlers.

        Args:
            tab: Tab object containing the signals
            group_key: Key for the signal group in the signal map
            all_tabs: Dictionary of all tabs
            handler: Handler function to connect to the signals
        """
        for signal_name in self._signal_map[group_key]:
            if hasattr(tab, signal_name):
                signal = getattr(tab, signal_name)
                if isinstance(signal, pyqtSignal):
                    try:
                        signal.connect(
                            lambda *args, sender=tab, signal=signal_name: handler(
                                all_tabs, sender, signal, *args
                            )
                        )
                        LOGGER.debug("Connected %s signal", signal_name)
                    except Exception as e:
                        LOGGER.error("Error connecting %s signal: %s", signal_name, e)
                        raise SignalConnectionError(
                            "Failed to connect %s: %s" % (signal_name, e)
                        ) from e

    def _update_tab_directory_via_method(
        self, tab: QObject, tab_name: str, directory: str
    ) -> bool:
        """
        Update a tab's directory using the set_directory method.

        Args:
            tab: The tab to update
            tab_name: Name of the tab (for logging)
            directory: Directory path to set

        Returns:
            bool: True if successful, False otherwise
        """
        if hasattr(tab, "set_directory"):
            try:
                tab.set_directory(directory)
                LOGGER.debug("Updated directory in %r using set_directory", tab_name)
                return True
            except Exception as e:
                LOGGER.error("Error setting directory in %r: %s", tab_name, e)
        return False

    def _update_tab_directory_via_edit(
        self, tab: QObject, tab_name: str, directory: str
    ) -> bool:
        """
        Update a tab's directory using the directory_edit widget.

        Args:
            tab: The tab to update
            tab_name: Name of the tab (for logging)
            directory: Directory path to set

        Returns:
            bool: True if successful, False otherwise
        """
        if hasattr(tab, "directory_edit") and hasattr(tab.directory_edit, "setText"):
            try:
                tab.directory_edit.setText(directory)
                LOGGER.debug("Updated directory in %r using directory_edit", tab_name)
                return True
            except Exception as e:
                LOGGER.error("Error setting directory text in %r: %s", tab_name, e)
        return False

    def _update_view_model_directory(
        self, tab: EnhancedIntegrityCheckViewModel, directory: str
    ) -> bool:
        """
        Update a view model's base_directory property.

        Args:
            tab: The view model to update
            directory: Directory path to set

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if isinstance(tab.base_directory, Path):
                tab.base_directory = Path(directory)
            else:
                tab.base_directory = directory
            LOGGER.debug("Updated directory in view model")
            return True
        except Exception as e:
            LOGGER.error("Error setting directory in view model: %s", e)
            return False

    def _handle_directory_signal(
        self,
        tabs: Dict[str, QObject],
        sender: QObject,
        signal_name: str,
        directory: str,
    ) -> None:
        """
        Handle directory selection signals.

        Args:
            tabs: Dictionary of all tabs
            sender: Tab that sent the signal
            signal_name: Name of the signal that was triggered
            directory: Directory path that was selected
        """
        LOGGER.info("Directory selected: %s", directory)

        # Update all tabs with the new directory
        for tab_name, tab in tabs.items():
            # Skip the sender to avoid circular signals
            if tab is sender:
                continue

            # Try updating the directory using different methods
            updated = self._update_tab_directory_via_method(tab, tab_name, directory)

            # If that didn't work, try updating via directory_edit
            if not updated:
                updated = self._update_tab_directory_via_edit(tab, tab_name, directory)

            # If it's a view model, update its base_directory property
            if isinstance(tab, EnhancedIntegrityCheckViewModel):
                self._update_view_model_directory(tab, directory)

    def _handle_date_range_signal(
        self,
        tabs: Dict[str, QObject],
        sender: QObject,
        signal_name: str,
        start: datetime,
        end: datetime,
    ) -> None:
        """
        Handle date range selection signals.

        Args:
            tabs: Dictionary of all tabs
            sender: Tab that sent the signal
            signal_name: Name of the signal that was triggered
            start: Start date
            end: End date
        """
        LOGGER.info("Date range selected: %s to %s", start, end)

        # Update all tabs with the new date range
        for tab_name, tab in tabs.items():
            # Skip the sender to avoid circular signals
            if tab is sender:
                continue

            # Try to find a suitable method to set the date range
            if hasattr(tab, "set_date_range"):
                try:
                    tab.set_date_range(start, end)
                    LOGGER.debug(
                        f"Updated date range in {tab_name!r} using set_date_range"
                    )
                except Exception as e:
                    LOGGER.error(f"Error setting date range in {tab_name!r}: {e}")

            # If it's a view model, update its properties
            if isinstance(tab, EnhancedIntegrityCheckViewModel):
                try:
                    tab.start_date = start
                    tab.end_date = end
                    LOGGER.debug("Updated date range in view model")
                except Exception as e:
                    LOGGER.error(f"Error setting date range in view model: {e}")

    def _handle_timestamp_signal(
        self,
        tabs: Dict[str, QObject],
        sender: QObject,
        signal_name: str,
        timestamp: datetime,
    ) -> None:
        """
        Handle timestamp selection signals.

        Args:
            tabs: Dictionary of all tabs
            sender: Tab that sent the signal
            signal_name: Name of the signal that was triggered
            timestamp: Selected timestamp
        """
        LOGGER.info("Timestamp selected: %s", timestamp)

        # Update all tabs with the selected timestamp
        for tab_name, tab in tabs.items():
            # Skip the sender to avoid circular signals
            if tab is sender:
                continue

            # If this is the results tab, try to highlight the corresponding item
            if hasattr(tab, "highlight_item"):
                try:
                    tab.highlight_item(timestamp)
                    LOGGER.debug(
                        f"Highlighted item in {tab_name!r} at timestamp {timestamp}"
                    )
                except Exception as e:
                    LOGGER.error(f"Error highlighting item in {tab_name!r}: {e}")

    def _handle_item_signal(
        self,
        tabs: Dict[str, QObject],
        sender: QObject,
        signal_name: str,
        item: MissingTimestamp,
    ) -> None:
        """
        Handle item selection signals.

        Args:
            tabs: Dictionary of all tabs
            sender: Tab that sent the signal
            signal_name: Name of the signal that was triggered
            item: Selected item
        """
        LOGGER.info("Item selected: %s", item.expected_filename)

        # Update all tabs with the selected item
        for tab_name, tab in tabs.items():
            # Skip the sender to avoid circular signals
            if tab is sender:
                continue

            # If this is the timeline tab, try to highlight the corresponding timestamp
            if hasattr(tab, "select_timestamp") and hasattr(item, "timestamp"):
                try:
                    tab.select_timestamp(item.timestamp)
                    LOGGER.debug(f"Selected timestamp in {tab_name!r}")
                except Exception as e:
                    LOGGER.error(f"Error selecting timestamp in {tab_name!r}: {e}")

    def _handle_download_signal(
        self,
        tabs: Dict[str, QObject],
        sender: QObject,
        signal_name: str,
        item: MissingTimestamp,
    ) -> None:
        """
        Handle download request signals.

        Args:
            tabs: Dictionary of all tabs
            sender: Tab that sent the signal
            signal_name: Name of the signal that was triggered
            item: Item to download
        """
        LOGGER.info("Download requested for: %s", item.expected_filename)

        # Find a tab that can handle downloads
        for tab_name, tab in tabs.items():
            if hasattr(tab, "download_item"):
                try:
                    tab.download_item(item)
                    LOGGER.debug(f"Requested download in {tab_name!r}")
                    break  # Only need one tab to handle it
                except Exception as e:
                    LOGGER.error(f"Error requesting download in {tab_name!r}: {e}")

    def _handle_view_signal(
        self,
        tabs: Dict[str, QObject],
        sender: QObject,
        signal_name: str,
        item: MissingTimestamp,
    ) -> None:
        """
        Handle view request signals.

        Args:
            tabs: Dictionary of all tabs
            sender: Tab that sent the signal
            signal_name: Name of the signal that was triggered
            item: Item to view
        """
        LOGGER.info("View requested for: %s", item.expected_filename)

        # Find the imagery tab to handle viewing
        for tab_name, tab in tabs.items():
            if tab_name.lower() == "imagery" or "imagery" in tab_name.lower():
                if (
                    hasattr(tab, "load_file")
                    and hasattr(item, "local_path")
                    and item.local_path
                ):
                    try:
                        tab.load_file(item.local_path)
                        LOGGER.debug(f"Loaded file in {tab_name!r}")
                        break  # Only need one tab to handle it
                    except Exception as e:
                        LOGGER.error(f"Error loading file in {tab_name!r}: {e}")

    def _handle_scan_completion(
        self, tabs: Dict[str, QObject], success: bool, message: str
    ) -> None:
        """
        Handle scan completion signals.

        Args:
            tabs: Dictionary of all tabs
            success: Whether the scan was successful
            message: Status message
        """
        LOGGER.info("Scan completed: %s, %s", success, message)

        if success:
            # Find the view model to get the updated data
            view_model = None
            for tab in tabs.values():
                if isinstance(tab, EnhancedIntegrityCheckViewModel):
                    view_model = tab
                    break

            if view_model is not None and hasattr(view_model, "missing_items"):
                self._update_tabs_after_scan(tabs, view_model)

    def _update_date_range_tab(
        self, tab: QObject, tab_name: str, start_date: datetime, end_date: datetime
    ) -> bool:
        """
        Update a tab with date range information.

        Args:
            tab: The tab to update
            tab_name: Name of the tab (for logging)
            start_date: Start date to set
            end_date: End date to set

        Returns:
            bool: True if successful, False otherwise
        """
        if hasattr(tab, "set_date_range"):
            try:
                tab.set_date_range(start_date, end_date)
                LOGGER.debug("Updated date range in %r", tab_name)
                return True
            except Exception as e:
                LOGGER.error("Error updating date range in %r: %s", tab_name, e)
        return False

    def _update_timeline_tab(
        self,
        tab: QObject,
        tab_name: str,
        missing_items: List[MissingTimestamp],
        start_date: datetime,
        end_date: datetime,
        interval_minutes: int
    ) -> bool:
        """
        Update a timeline tab with data.

        Args:
            tab: The tab to update
            tab_name: Name of the tab (for logging)
            missing_items: List of missing items to display
            start_date: Start date for the timeline
            end_date: End date for the timeline
            interval_minutes: Expected interval between timestamps in minutes

        Returns:
            bool: True if successful, False otherwise
        """
        if hasattr(tab, "set_data") and "timeline" in tab_name.lower():
            try:
                tab.set_data(missing_items, start_date, end_date, interval_minutes)
                LOGGER.debug("Updated data in %r", tab_name)
                return True
            except Exception as e:
                LOGGER.error("Error updating data in %r: %s", tab_name, e)
        return False

    def _update_results_tab(
        self,
        tab: QObject,
        tab_name: str,
        missing_items: List[MissingTimestamp],
        total_expected: int
    ) -> bool:
        """
        Update a results tab with items.

        Args:
            tab: The tab to update
            tab_name: Name of the tab (for logging)
            missing_items: List of missing items to display
            total_expected: Total number of expected items

        Returns:
            bool: True if successful, False otherwise
        """
        if hasattr(tab, "set_items") and "result" in tab_name.lower():
            try:
                tab.set_items(missing_items, total_expected)
                LOGGER.debug("Updated items in %r", tab_name)
                return True
            except Exception as e:
                LOGGER.error("Error updating items in %r: %s", tab_name, e)
        return False

    def _update_tabs_after_scan(
        self, tabs: Dict[str, QObject], view_model: EnhancedIntegrityCheckViewModel
    ) -> None:
        """
        Update all tabs with data after a successful scan.

        Args:
            tabs: Dictionary of all tabs
            view_model: View model containing the data
        """
        # Extract data from the view model
        missing_items = view_model.missing_items
        start_date = view_model.start_date
        end_date = view_model.end_date
        total_expected = getattr(view_model, "total_expected", len(missing_items))
        interval_minutes = getattr(view_model, "expected_interval_minutes", 60)

        LOGGER.info("Updating tabs with %d items", len(missing_items))

        # Process each tab by type
        for tab_name, tab in tabs.items():
            # Update date range for all tabs that support it
            self._update_date_range_tab(tab, tab_name, start_date, end_date)

            # Update timeline tabs with missing items data
            self._update_timeline_tab(
                tab, tab_name, missing_items, start_date, end_date, interval_minutes
            )

            # Update results tabs with missing items
            self._update_results_tab(tab, tab_name, missing_items, total_expected)

    def _handle_missing_items_update(
        self, tabs: Dict[str, QObject], items: List[MissingTimestamp]
    ) -> None:
        """
        Handle missing items update signals.

        Args:
            tabs: Dictionary of all tabs
            items: Updated list of missing items
        """
        LOGGER.info("Missing items updated: %d items", len(items))

        # Find the view model to get all data needed
        view_model = None
        for tab in tabs.values():
            if isinstance(tab, EnhancedIntegrityCheckViewModel):
                view_model = tab
                break

        if view_model is not None:
            self._update_tabs_after_scan(tabs, view_model)


# Module-level signal manager instance for singleton usage
signal_manager = TabSignalManager()


def connect_integrity_check_tabs(tabs: Dict[str, QObject]) -> None:
    """
    Connect signals between integrity check tabs using the standardized approach.

    Args:
        tabs: Dictionary of tabs to connect, with keys as tab names
             and values as tab objects.

    Example:
        connect_integrity_check_tabs({
            "integrity": integrity_tab,
            "timeline": timeline_tab,
            "results": results_tab
        })
    """
    signal_manager.connect_tabs(tabs)


def create_signal_flow_diagram(tabs: Dict[str, QObject]) -> str:
    """
    Generate a signal flow diagram for documentation.

    Args:
        tabs: Dictionary of tabs to document

    Returns:
        Markdown representation of the signal flow diagram
    """
    diagram = "# Signal Flow Diagram\n\n"
    diagram += "This diagram shows the flow of signals between the different tabs in the integrity check system.\n\n"

    # Document signal connections for each tab
    for tab_name, tab in tabs.items():
        diagram += f"## {tab_name}\n\n"

        # Find signals in this tab
        signals = []
        for attr in dir(tab):
            attr_value = getattr(tab, attr)
            if isinstance(attr_value, pyqtSignal):
                signals.append(attr)

        if signals:
            diagram += "### Emitted Signals\n\n"
            for signal in signals:
                diagram += f"- `{signal}`\n"
            diagram += "\n"

        # Document slots or methods that receive signals
        diagram += "### Handled Signals\n\n"
        handler_methods = []

        for method_name in dir(tab):
            if method_name.startswith("_on_") or method_name.startswith("handle_"):
                handler_methods.append(method_name)

        if handler_methods:
            for method in handler_methods:
                diagram += f"- `{method}`\n"
            diagram += "\n"
        else:
            diagram += "No explicit signal handlers found.\n\n"

    return diagram
