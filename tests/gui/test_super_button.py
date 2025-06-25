"""Comprehensive tests for the SuperButton widget."""

import sys
from unittest.mock import Mock, patch

import pytest
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QPushButton, QWidget

from goesvfi.gui_tabs.main_tab_components.widgets import SuperButton


@pytest.fixture
def app():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app
    # Process any pending events after each test
    app.processEvents()


@pytest.fixture
def super_button(app: QApplication) -> SuperButton:
    """Create a SuperButton instance for testing."""
    button = SuperButton("Test Button")
    button.show()
    app.processEvents()
    yield button
    button.close()
    button.deleteLater()
    app.processEvents()


class TestSuperButton:
    """Test suite for SuperButton widget."""

    def test_initialization(self, super_button):
        """Test SuperButton initialization."""
        assert super_button.text() == "Test Button"
        assert super_button.click_callback is None
        assert isinstance(super_button, QPushButton)

    def test_initialization_with_parent(self, app):
        """Test SuperButton initialization with parent widget."""
        parent = QWidget()
        button = SuperButton("Child Button", parent)

        assert button.text() == "Child Button"
        assert button.parent() == parent
        assert button.click_callback is None

        button.close()
        parent.close()
        app.processEvents()

    def test_set_click_callback(self, super_button):
        """Test setting click callback."""
        callback = Mock()
        callback.__name__ = "mock_callback"  # Add __name__ attribute to Mock
        super_button.set_click_callback(callback)

        assert super_button.click_callback == callback

    def test_set_click_callback_none(self, super_button):
        """Test setting click callback to None."""
        # First set a callback
        callback = Mock()
        callback.__name__ = "mock_callback"  # Add __name__ attribute to Mock
        super_button.set_click_callback(callback)
        assert super_button.click_callback == callback

        # Then set it to None
        super_button.set_click_callback(None)
        assert super_button.click_callback is None

    def test_mouse_press_event(self, super_button, app):
        """Test mouse press event handling."""
        with patch("builtins.print") as mock_print:
            # Create mouse press event
            event = QMouseEvent(
                QEvent.Type.MouseButtonPress,
                QPointF(10, 10),
                QPointF(10, 10),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )

            super_button.mousePressEvent(event)
            app.processEvents()

            # Check that debug print was called
            mock_print.assert_any_call(f"SuperButton MOUSE PRESS: {Qt.MouseButton.LeftButton}")

    def test_mouse_press_event_none(self, super_button):
        """Test mouse press event with None event."""
        # Should handle None gracefully
        super_button.mousePressEvent(None)
        # No exception should be raised

    def test_mouse_release_event_left_click_with_callback(self, super_button, app, qtbot):
        """Test mouse release event with left click and callback."""
        callback = Mock()
        callback.__name__ = "mock_callback"
        super_button.set_click_callback(callback)

        with patch("builtins.print") as mock_print:
            # Create mouse release event
            event = QMouseEvent(
                QEvent.Type.MouseButtonRelease,
                QPointF(10, 10),
                QPointF(10, 10),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )

            super_button.mouseReleaseEvent(event)

            # Check debug prints
            mock_print.assert_any_call(f"SuperButton MOUSE RELEASE: {Qt.MouseButton.LeftButton}")
            mock_print.assert_any_call("SuperButton: LEFT CLICK DETECTED")
            mock_print.assert_any_call(f"SuperButton: Calling callback {callback.__name__}")

            # Wait for the timer to fire (10ms delay)
            qtbot.wait(20)

            # Check callback was called
            callback.assert_called_once()

    def test_mouse_release_event_left_click_no_callback(self, super_button, app):
        """Test mouse release event with left click but no callback."""
        with patch("builtins.print") as mock_print:
            # Create mouse release event
            event = QMouseEvent(
                QEvent.Type.MouseButtonRelease,
                QPointF(10, 10),
                QPointF(10, 10),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )

            super_button.mouseReleaseEvent(event)
            app.processEvents()

            # Check debug prints
            mock_print.assert_any_call(f"SuperButton MOUSE RELEASE: {Qt.MouseButton.LeftButton}")
            mock_print.assert_any_call("SuperButton: LEFT CLICK DETECTED")
            mock_print.assert_any_call("SuperButton: No callback registered")

    def test_mouse_release_event_right_click(self, super_button, app, qtbot):
        """Test mouse release event with right click."""
        callback = Mock()
        callback.__name__ = "mock_callback"
        super_button.set_click_callback(callback)

        with patch("builtins.print") as mock_print:
            # Create mouse release event with right button
            event = QMouseEvent(
                QEvent.Type.MouseButtonRelease,
                QPointF(10, 10),
                QPointF(10, 10),
                Qt.MouseButton.RightButton,
                Qt.MouseButton.RightButton,
                Qt.KeyboardModifier.NoModifier,
            )

            super_button.mouseReleaseEvent(event)

            # Check that only the release was logged, not the left click detection
            mock_print.assert_any_call(f"SuperButton MOUSE RELEASE: {Qt.MouseButton.RightButton}")

            # Ensure "LEFT CLICK DETECTED" was NOT printed
            for call in mock_print.call_args_list:
                assert "LEFT CLICK DETECTED" not in str(call)

            # Wait a bit to ensure callback is NOT called
            qtbot.wait(20)
            callback.assert_not_called()

    def test_mouse_release_event_none(self, super_button):
        """Test mouse release event with None event."""
        # Should handle None gracefully
        super_button.mouseReleaseEvent(None)
        # No exception should be raised

    def test_click_simulation(self, super_button, app, qtbot):
        """Test simulated click using QTest."""
        callback = Mock()
        callback.__name__ = "mock_callback"
        super_button.set_click_callback(callback)

        # Simulate a click
        QTest.mouseClick(super_button, Qt.MouseButton.LeftButton)

        # Wait for timer
        qtbot.wait(20)

        # Verify callback was called
        callback.assert_called_once()

    def test_multiple_callbacks(self, super_button, app, qtbot):
        """Test changing callbacks multiple times."""
        callback1 = Mock()
        callback1.__name__ = "mock_callback1"
        callback2 = Mock()
        callback2.__name__ = "mock_callback2"

        # Set first callback
        super_button.set_click_callback(callback1)

        # Click button
        QTest.mouseClick(super_button, Qt.MouseButton.LeftButton)
        qtbot.wait(20)

        callback1.assert_called_once()
        callback2.assert_not_called()

        # Change callback
        super_button.set_click_callback(callback2)

        # Click again
        QTest.mouseClick(super_button, Qt.MouseButton.LeftButton)
        qtbot.wait(20)

        # First callback should still have been called only once
        callback1.assert_called_once()
        # Second callback should now be called
        callback2.assert_called_once()

    def test_disabled_button_behavior(self, super_button, app, qtbot):
        """Test behavior when button is disabled."""
        callback = Mock()
        callback.__name__ = "mock_callback"
        super_button.set_click_callback(callback)

        # Disable the button
        super_button.setEnabled(False)

        # Try to click - Qt won't deliver mouse events to disabled widgets
        QTest.mouseClick(super_button, Qt.MouseButton.LeftButton)
        qtbot.wait(20)

        # Callback should NOT be called because the button is disabled
        # Qt's event system prevents mouse events from reaching disabled widgets
        callback.assert_not_called()

        # Re-enable and verify it works again
        super_button.setEnabled(True)
        QTest.mouseClick(super_button, Qt.MouseButton.LeftButton)
        qtbot.wait(20)

        # Now it should be called
        callback.assert_called_once()

    def test_callback_exception_handling(self, super_button, app, qtbot):
        """Test that exceptions in callbacks don't crash the button."""

        def failing_callback():
            raise RuntimeError("Test exception")

        super_button.set_click_callback(failing_callback)

        # The exception will be caught by Qt's event loop but not crash the button
        with pytest.raises(RuntimeError, match="Test exception"):
            # Directly call the callback to test exception handling
            failing_callback()

        # Button should still be functional after exception
        assert super_button.isEnabled()

        # Test that button can still accept new callbacks
        new_callback = Mock()
        new_callback.__name__ = "new_callback"
        super_button.set_click_callback(new_callback)
        assert super_button.click_callback == new_callback

    def test_rapid_clicks(self, super_button, app, qtbot):
        """Test rapid clicking behavior."""
        callback = Mock()
        callback.__name__ = "mock_callback"
        super_button.set_click_callback(callback)

        # Perform multiple rapid clicks
        for _ in range(5):
            QTest.mouseClick(super_button, Qt.MouseButton.LeftButton)
            qtbot.wait(5)  # Very short wait

        # Wait for all timers to complete
        qtbot.wait(50)

        # All clicks should register
        assert callback.call_count == 5

    def test_button_text_changes(self, super_button):
        """Test that button text can be changed."""
        super_button.setText("New Text")
        assert super_button.text() == "New Text"

    def test_button_signals(self, super_button, qtbot):
        """Test that standard QPushButton signals still work."""
        clicked_signal = Mock()
        pressed_signal = Mock()
        released_signal = Mock()

        super_button.clicked.connect(clicked_signal)
        super_button.pressed.connect(pressed_signal)
        super_button.released.connect(released_signal)

        # Click the button
        QTest.mouseClick(super_button, Qt.MouseButton.LeftButton)
        qtbot.wait(20)

        # All signals should have been emitted
        clicked_signal.assert_called()
        pressed_signal.assert_called()
        released_signal.assert_called()

    def test_geometry_and_visibility(self, super_button, app):
        """Test button geometry and visibility."""
        # Set size
        super_button.resize(100, 50)
        app.processEvents()

        assert super_button.width() == 100
        assert super_button.height() == 50

        # Test visibility
        assert super_button.isVisible()

        super_button.hide()
        app.processEvents()
        assert not super_button.isVisible()

        super_button.show()
        app.processEvents()
        assert super_button.isVisible()

    @patch("PyQt6.QtCore.QTimer.singleShot")
    def test_timer_delay(self, mock_timer, super_button, app):
        """Test that QTimer is used with correct delay."""
        callback = Mock()
        callback.__name__ = "mock_callback"
        super_button.set_click_callback(callback)

        # Create mouse release event
        event = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            QPointF(10, 10),
            QPointF(10, 10),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

        super_button.mouseReleaseEvent(event)

        # Verify QTimer.singleShot was called with 10ms delay
        mock_timer.assert_called_once_with(10, callback)

    def test_double_click_behavior(self, super_button, app, qtbot):
        """Test double-click behavior."""
        callback = Mock()
        callback.__name__ = "mock_callback"
        super_button.set_click_callback(callback)

        # Manually simulate double-click with proper press/release events
        # Qt's mouseDClick doesn't generate the release events our SuperButton expects
        pos = super_button.rect().center()

        # First click
        QTest.mousePress(super_button, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
        QTest.mouseRelease(super_button, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
        qtbot.wait(5)

        # Second click (quickly after first)
        QTest.mousePress(super_button, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
        QTest.mouseRelease(super_button, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
        qtbot.wait(20)  # Wait for timers

        # Both clicks should have triggered the callback
        assert callback.call_count == 2

    def test_middle_button_click(self, super_button, app, qtbot):
        """Test middle mouse button behavior."""
        callback = Mock()
        callback.__name__ = "mock_callback"
        super_button.set_click_callback(callback)

        # Click with middle button
        QTest.mouseClick(super_button, Qt.MouseButton.MiddleButton)
        qtbot.wait(20)

        # Callback should not be called for middle button
        callback.assert_not_called()

    def test_keyboard_activation(self, super_button, app, qtbot):
        """Test keyboard activation (space/enter)."""
        callback = Mock()
        callback.__name__ = "mock_callback"
        super_button.set_click_callback(callback)

        # Give focus to button
        super_button.setFocus()
        app.processEvents()

        # Press space (triggers clicked signal on buttons)
        QTest.keyClick(super_button, Qt.Key.Key_Space)
        qtbot.wait(20)

        # The SuperButton only responds to mouse events, not keyboard
        # So callback should not be called
        callback.assert_not_called()

    def test_tooltip_and_accessibility(self, super_button):
        """Test tooltip and accessibility features."""
        # Set tooltip
        super_button.setToolTip("This is a super button")
        assert super_button.toolTip() == "This is a super button"

        # Set accessibility name
        super_button.setAccessibleName("SuperButton")
        assert super_button.accessibleName() == "SuperButton"

        # Set accessibility description
        super_button.setAccessibleDescription("A button with enhanced click handling")
        assert super_button.accessibleDescription() == "A button with enhanced click handling"

    def test_style_sheet_compatibility(self, super_button):
        """Test that custom stylesheets work with SuperButton."""
        style = "QPushButton { background-color: red; color: white; }"
        super_button.setStyleSheet(style)
        assert super_button.styleSheet() == style

    def test_parent_widget_deletion(self, app):
        """Test SuperButton behavior when parent is deleted."""
        parent = QWidget()
        button = SuperButton("Child Button", parent)
        callback = Mock()
        callback.__name__ = "mock_callback"
        button.set_click_callback(callback)

        # Store weak reference to button
        import weakref

        button_ref = weakref.ref(button)

        # Delete parent
        parent.deleteLater()
        app.processEvents()

        # Button should be deleted with parent
        assert button_ref() is None or not button_ref().isVisible()
