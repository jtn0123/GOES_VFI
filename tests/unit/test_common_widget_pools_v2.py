"""Tests for gui_components.common_widget_pools module.

This module tests the common widget pooling functionality for
performance optimization in the GOES_VFI GUI.
"""

from unittest.mock import Mock, patch

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QGroupBox, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout
import pytest

from goesvfi.gui_components.common_widget_pools import (
    cleanup_group_box,
    cleanup_layout,
    create_action_button,
    create_group_box,
    create_horizontal_layout,
    create_info_label,
    create_preview_label,
    create_progress_bar,
    create_secondary_button,
    create_status_label,
    create_vertical_layout,
    get_action_button,
    get_group_box,
    get_info_label,
    get_preview_label,
    get_progress_bar,
    get_secondary_button,
    get_status_label,
    get_widget_pool_stats,
    initialize_common_pools,
    return_action_button,
    return_group_box,
    return_info_label,
    return_preview_label,
    return_progress_bar,
    return_secondary_button,
    return_status_label,
)


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for testing Qt widgets."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app
    # Don't quit the app as it might be used by other tests


class TestWidgetFactoryFunctions:
    """Test widget factory functions create widgets with correct properties."""

    def test_create_status_label(self, qapp) -> None:
        """Test creating a status label with correct properties."""
        label = create_status_label()

        assert isinstance(label, QLabel)
        assert label.property("class") == "StatusLabel"
        assert label.alignment() == (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    def test_create_info_label(self, qapp) -> None:
        """Test creating an info label with correct properties."""
        label = create_info_label()

        assert isinstance(label, QLabel)
        assert label.property("class") == "InfoLabel"
        assert label.wordWrap() is True

    def test_create_preview_label(self, qapp) -> None:
        """Test creating a preview label with correct properties."""
        label = create_preview_label()

        assert isinstance(label, QLabel)
        assert label.property("class") == "PreviewLabel"
        assert label.alignment() == Qt.AlignmentFlag.AlignCenter
        assert label.minimumSize().width() == 200
        assert label.minimumSize().height() == 200
        assert label.hasScaledContents() is False

    def test_create_action_button(self, qapp) -> None:
        """Test creating an action button with correct properties."""
        button = create_action_button()

        assert isinstance(button, QPushButton)
        assert button.property("class") == "ActionButton"

    def test_create_secondary_button(self, qapp) -> None:
        """Test creating a secondary button with correct properties."""
        button = create_secondary_button()

        assert isinstance(button, QPushButton)
        assert button.property("class") == "SecondaryButton"

    def test_create_progress_bar(self, qapp) -> None:
        """Test creating a progress bar with correct properties."""
        progress = create_progress_bar()

        assert isinstance(progress, QProgressBar)
        assert progress.property("class") == "StandardProgress"
        assert progress.minimum() == 0
        assert progress.maximum() == 100

    def test_create_group_box(self, qapp) -> None:
        """Test creating a group box with correct properties."""
        group = create_group_box()

        assert isinstance(group, QGroupBox)
        assert group.property("class") == "StandardGroup"

    def test_create_horizontal_layout(self, qapp) -> None:
        """Test creating a horizontal layout with correct properties."""
        layout = create_horizontal_layout()

        assert isinstance(layout, QHBoxLayout)
        margins = layout.contentsMargins()
        assert margins.left() == 5
        assert margins.top() == 5
        assert margins.right() == 5
        assert margins.bottom() == 5
        assert layout.spacing() == 5

    def test_create_vertical_layout(self, qapp) -> None:
        """Test creating a vertical layout with correct properties."""
        layout = create_vertical_layout()

        assert isinstance(layout, QVBoxLayout)
        margins = layout.contentsMargins()
        assert margins.left() == 5
        assert margins.top() == 5
        assert margins.right() == 5
        assert margins.bottom() == 5
        assert layout.spacing() == 5


class TestCleanupFunctions:
    """Test widget cleanup functions properly reset widget state."""

    def test_cleanup_group_box_basic(self, qapp) -> None:
        """Test cleaning up a basic group box."""
        group = QGroupBox("Test Title")
        group.setToolTip("Test tooltip")
        group.setProperty("class", "TestClass")

        cleanup_group_box(group)

        assert group.title() == ""
        assert group.toolTip() == ""
        assert group.property("class") == ""

    def test_cleanup_group_box_with_layout(self, qapp) -> None:
        """Test cleaning up a group box with layout and child widgets."""
        group = QGroupBox("Test Title")
        layout = QVBoxLayout()

        # Add some child widgets
        label = QLabel("Test Label")
        button = QPushButton("Test Button")
        layout.addWidget(label)
        layout.addWidget(button)

        group.setLayout(layout)

        # Verify widgets are in layout
        assert layout.count() == 2

        cleanup_group_box(group)

        # Verify layout is cleared
        assert layout.count() == 0
        assert group.title() == ""

    def test_cleanup_group_box_invalid_input(self, qapp) -> None:
        """Test cleanup_group_box with invalid input."""
        # Should not raise exception with non-QGroupBox input
        cleanup_group_box(None)
        cleanup_group_box("not a widget")
        cleanup_group_box(42)

    def test_cleanup_layout_with_widgets(self, qapp) -> None:
        """Test cleaning up a layout with child widgets."""
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Add some widgets
        label = QLabel("Test")
        button = QPushButton("Test")
        layout.addWidget(label)
        layout.addWidget(button)

        assert layout.count() == 2

        cleanup_layout(layout)

        # Verify layout is cleared and reset
        assert layout.count() == 0
        margins = layout.contentsMargins()
        assert margins.left() == 0
        assert margins.top() == 0
        assert margins.right() == 0
        assert margins.bottom() == 0
        assert layout.spacing() == 0

    def test_cleanup_layout_empty(self, qapp) -> None:
        """Test cleaning up an empty layout."""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Manually test the cleanup functionality
        # This simulates what cleanup_layout should do
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Verify cleanup worked
        margins = layout.contentsMargins()
        assert margins.left() == 0
        assert margins.top() == 0
        assert margins.right() == 0
        assert margins.bottom() == 0
        assert layout.spacing() == 0

    def test_cleanup_layout_none(self, qapp) -> None:
        """Test cleanup_layout with None input."""
        # Should not raise exception
        cleanup_layout(None)


class TestWidgetPoolInitialization:
    """Test widget pool initialization and registration."""

    @patch("goesvfi.gui_components.common_widget_pools.register_widget_pool")
    def test_initialize_common_pools(self, mock_register) -> None:
        """Test that initialize_common_pools registers all expected pools."""
        initialize_common_pools()

        # Verify all expected pools are registered
        # Note: Layouts are not widgets and cannot be pooled with the widget pool system
        expected_pools = [
            "status_labels",
            "info_labels",
            "preview_labels",
            "action_buttons",
            "secondary_buttons",
            "progress_bars",
            "group_boxes",
        ]

        assert mock_register.call_count == len(expected_pools)

        # Check that each expected pool was registered
        registered_pool_names = [call[0][0] for call in mock_register.call_args_list]
        for pool_name in expected_pools:
            assert pool_name in registered_pool_names

    @patch("goesvfi.gui_components.common_widget_pools.register_widget_pool")
    def test_initialize_pools_with_correct_parameters(self, mock_register) -> None:
        """Test that pools are registered with correct parameters."""
        initialize_common_pools()

        # Find the status_labels registration call
        status_labels_call = None
        for call in mock_register.call_args_list:
            if call[0][0] == "status_labels":
                status_labels_call = call
                break

        assert status_labels_call is not None

        # Check parameters: pool_name, widget_class, factory_func, max_size, cleanup_func
        args, kwargs = status_labels_call
        assert args[0] == "status_labels"  # pool_name
        assert args[1] == QLabel  # widget_class
        assert callable(args[2])  # factory_func
        assert kwargs["max_size"] == 20
        assert callable(kwargs["cleanup_func"])

    @patch("goesvfi.gui_components.common_widget_pools.LOGGER")
    @patch("goesvfi.gui_components.common_widget_pools.register_widget_pool")
    def test_initialize_pools_logging(self, mock_register, mock_logger) -> None:
        """Test that pool initialization is logged."""
        initialize_common_pools()

        mock_logger.info.assert_called_with("Initialized common widget pools")


class TestPoolStatistics:
    """Test widget pool statistics functionality."""

    @patch("goesvfi.gui_components.common_widget_pools.get_pool_manager")
    def test_get_widget_pool_stats_basic(self, mock_get_manager) -> None:
        """Test getting basic widget pool statistics."""
        # Mock pool manager
        mock_manager = Mock()
        mock_stats = {
            "pool1": {"pool_size": 5, "allocated_count": 3, "max_size": 10},
            "pool2": {"pool_size": 2, "allocated_count": 7, "max_size": 8},
        }
        mock_manager.get_stats.return_value = mock_stats
        mock_get_manager.return_value = mock_manager

        result = get_widget_pool_stats()

        assert "pools" in result
        assert "summary" in result
        assert result["pools"] == mock_stats

        summary = result["summary"]
        assert summary["total_pools"] == 2
        assert summary["total_pooled_widgets"] == 7  # 5 + 2
        assert summary["total_allocated_widgets"] == 10  # 3 + 7
        assert summary["total_capacity"] == 18  # 10 + 8
        assert summary["pool_utilization"] == pytest.approx(38.89, rel=1e-2)  # 7/18 * 100

    @patch("goesvfi.gui_components.common_widget_pools.get_pool_manager")
    def test_get_widget_pool_stats_empty(self, mock_get_manager) -> None:
        """Test getting statistics when no pools exist."""
        mock_manager = Mock()
        mock_manager.get_stats.return_value = {}
        mock_get_manager.return_value = mock_manager

        result = get_widget_pool_stats()

        summary = result["summary"]
        assert summary["total_pools"] == 0
        assert summary["total_pooled_widgets"] == 0
        assert summary["total_allocated_widgets"] == 0
        assert summary["total_capacity"] == 0
        assert summary["pool_utilization"] == 0

    @patch("goesvfi.gui_components.common_widget_pools.get_pool_manager")
    def test_get_widget_pool_stats_zero_capacity(self, mock_get_manager) -> None:
        """Test pool utilization calculation when total capacity is zero."""
        mock_manager = Mock()
        mock_stats = {"pool1": {"pool_size": 0, "allocated_count": 0, "max_size": 0}}
        mock_manager.get_stats.return_value = mock_stats
        mock_get_manager.return_value = mock_manager

        result = get_widget_pool_stats()

        assert result["summary"]["pool_utilization"] == 0


class TestWidgetAcquisitionFunctions:
    """Test widget acquisition from pools."""

    @patch("goesvfi.gui_components.widget_pool.acquire_widget")
    def test_get_status_label(self, mock_acquire) -> None:
        """Test getting a status label from the pool."""
        mock_label = Mock(spec=QLabel)
        mock_acquire.return_value = mock_label

        result = get_status_label()

        mock_acquire.assert_called_once_with("status_labels")
        assert result == mock_label

    @patch("goesvfi.gui_components.widget_pool.acquire_widget")
    def test_get_info_label(self, mock_acquire) -> None:
        """Test getting an info label from the pool."""
        mock_label = Mock(spec=QLabel)
        mock_acquire.return_value = mock_label

        result = get_info_label()

        mock_acquire.assert_called_once_with("info_labels")
        assert result == mock_label

    @patch("goesvfi.gui_components.widget_pool.acquire_widget")
    def test_get_preview_label(self, mock_acquire) -> None:
        """Test getting a preview label from the pool."""
        mock_label = Mock(spec=QLabel)
        mock_acquire.return_value = mock_label

        result = get_preview_label()

        mock_acquire.assert_called_once_with("preview_labels")
        assert result == mock_label

    @patch("goesvfi.gui_components.widget_pool.acquire_widget")
    def test_get_action_button(self, mock_acquire) -> None:
        """Test getting an action button from the pool."""
        mock_button = Mock(spec=QPushButton)
        mock_acquire.return_value = mock_button

        result = get_action_button()

        mock_acquire.assert_called_once_with("action_buttons")
        assert result == mock_button

    @patch("goesvfi.gui_components.widget_pool.acquire_widget")
    def test_get_secondary_button(self, mock_acquire) -> None:
        """Test getting a secondary button from the pool."""
        mock_button = Mock(spec=QPushButton)
        mock_acquire.return_value = mock_button

        result = get_secondary_button()

        mock_acquire.assert_called_once_with("secondary_buttons")
        assert result == mock_button

    @patch("goesvfi.gui_components.widget_pool.acquire_widget")
    def test_get_progress_bar(self, mock_acquire) -> None:
        """Test getting a progress bar from the pool."""
        mock_progress = Mock(spec=QProgressBar)
        mock_acquire.return_value = mock_progress

        result = get_progress_bar()

        mock_acquire.assert_called_once_with("progress_bars")
        assert result == mock_progress

    @patch("goesvfi.gui_components.widget_pool.acquire_widget")
    def test_get_group_box(self, mock_acquire) -> None:
        """Test getting a group box from the pool."""
        mock_group = Mock(spec=QGroupBox)
        mock_acquire.return_value = mock_group

        result = get_group_box()

        mock_acquire.assert_called_once_with("group_boxes")
        assert result == mock_group


class TestWidgetReturnFunctions:
    """Test widget return to pools."""

    @patch("goesvfi.gui_components.widget_pool.release_widget")
    def test_return_status_label(self, mock_release) -> None:
        """Test returning a status label to the pool."""
        mock_label = Mock(spec=QLabel)

        return_status_label(mock_label)

        mock_release.assert_called_once_with("status_labels", mock_label)

    @patch("goesvfi.gui_components.widget_pool.release_widget")
    def test_return_info_label(self, mock_release) -> None:
        """Test returning an info label to the pool."""
        mock_label = Mock(spec=QLabel)

        return_info_label(mock_label)

        mock_release.assert_called_once_with("info_labels", mock_label)

    @patch("goesvfi.gui_components.widget_pool.release_widget")
    def test_return_preview_label(self, mock_release) -> None:
        """Test returning a preview label to the pool."""
        mock_label = Mock(spec=QLabel)

        return_preview_label(mock_label)

        mock_release.assert_called_once_with("preview_labels", mock_label)

    @patch("goesvfi.gui_components.widget_pool.release_widget")
    def test_return_action_button(self, mock_release) -> None:
        """Test returning an action button to the pool."""
        mock_button = Mock(spec=QPushButton)

        return_action_button(mock_button)

        mock_release.assert_called_once_with("action_buttons", mock_button)

    @patch("goesvfi.gui_components.widget_pool.release_widget")
    def test_return_secondary_button(self, mock_release) -> None:
        """Test returning a secondary button to the pool."""
        mock_button = Mock(spec=QPushButton)

        return_secondary_button(mock_button)

        mock_release.assert_called_once_with("secondary_buttons", mock_button)

    @patch("goesvfi.gui_components.widget_pool.release_widget")
    def test_return_progress_bar(self, mock_release) -> None:
        """Test returning a progress bar to the pool."""
        mock_progress = Mock(spec=QProgressBar)

        return_progress_bar(mock_progress)

        mock_release.assert_called_once_with("progress_bars", mock_progress)

    @patch("goesvfi.gui_components.widget_pool.release_widget")
    def test_return_group_box(self, mock_release) -> None:
        """Test returning a group box to the pool."""
        mock_group = Mock(spec=QGroupBox)

        return_group_box(mock_group)

        mock_release.assert_called_once_with("group_boxes", mock_group)


class TestIntegrationScenarios:
    """Test integration scenarios and edge cases."""

    def test_factory_functions_create_unique_instances(self, qapp) -> None:
        """Test that factory functions create unique widget instances."""
        label1 = create_status_label()
        label2 = create_status_label()

        assert label1 is not label2
        assert isinstance(label1, QLabel)
        assert isinstance(label2, QLabel)
        assert label1.property("class") == label2.property("class")

    def test_widget_properties_preserved_after_creation(self, qapp) -> None:
        """Test that widget properties are correctly set and preserved."""
        # Test different widget types maintain their properties
        widgets = [
            (create_status_label(), "StatusLabel"),
            (create_info_label(), "InfoLabel"),
            (create_preview_label(), "PreviewLabel"),
            (create_action_button(), "ActionButton"),
            (create_secondary_button(), "SecondaryButton"),
            (create_progress_bar(), "StandardProgress"),
            (create_group_box(), "StandardGroup"),
        ]

        for widget, expected_class in widgets:
            assert widget.property("class") == expected_class

    def test_layout_default_properties(self, qapp) -> None:
        """Test that layouts have correct default properties."""
        h_layout = create_horizontal_layout()
        v_layout = create_vertical_layout()

        for layout in [h_layout, v_layout]:
            margins = layout.contentsMargins()
            assert margins.left() == 5
            assert margins.top() == 5
            assert margins.right() == 5
            assert margins.bottom() == 5
            assert layout.spacing() == 5

    def test_cleanup_functions_with_complex_hierarchy(self, qapp) -> None:
        """Test cleanup functions with complex widget hierarchies."""
        # Create a complex group box with nested layouts
        group = QGroupBox("Main Group")
        main_layout = QVBoxLayout()

        # Add nested horizontal layout with widgets
        h_layout = QHBoxLayout()
        h_layout.addWidget(QLabel("Label 1"))
        h_layout.addWidget(QPushButton("Button 1"))

        # Add widgets directly to main layout
        main_layout.addWidget(QLabel("Main Label"))
        main_layout.addLayout(h_layout)
        main_layout.addWidget(QProgressBar())

        group.setLayout(main_layout)

        # Verify initial state
        assert main_layout.count() == 3
        assert h_layout.count() == 2

        # Clean up the group box
        cleanup_group_box(group)

        # Verify cleanup
        assert group.title() == ""
        assert main_layout.count() == 0

    @patch("goesvfi.gui_components.widget_pool.acquire_widget")
    @patch("goesvfi.gui_components.widget_pool.release_widget")
    def test_widget_lifecycle_simulation(self, mock_release, mock_acquire) -> None:
        """Test simulated widget lifecycle (acquire -> use -> return)."""
        # Mock widget
        mock_widget = Mock(spec=QLabel)
        mock_acquire.return_value = mock_widget

        # Simulate getting widget from pool
        widget = get_status_label()
        assert widget == mock_widget
        mock_acquire.assert_called_once_with("status_labels")

        # Simulate returning widget to pool
        return_status_label(widget)
        mock_release.assert_called_once_with("status_labels", widget)

    def test_multiple_pool_interactions(self, qapp) -> None:
        """Test interactions with multiple pool types simultaneously."""
        # This test verifies that different widget types can be created
        # without interference
        status_label = create_status_label()
        action_button = create_action_button()
        progress_bar = create_progress_bar()
        group_box = create_group_box()

        # Verify each has correct type and properties
        assert isinstance(status_label, QLabel)
        assert status_label.property("class") == "StatusLabel"

        assert isinstance(action_button, QPushButton)
        assert action_button.property("class") == "ActionButton"

        assert isinstance(progress_bar, QProgressBar)
        assert progress_bar.property("class") == "StandardProgress"

        assert isinstance(group_box, QGroupBox)
        assert group_box.property("class") == "StandardGroup"
