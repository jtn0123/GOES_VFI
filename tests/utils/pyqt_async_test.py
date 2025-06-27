"""Utilities for testing PyQt applications with async functionality.

This module provides base classes and utilities for testing PyQt components
that use async/await patterns, helping to avoid segmentation faults and
provide more reliable tests.
"""

import asyncio
import contextlib
import sys
import unittest

from PyQt6.QtCore import QCoreApplication, QObject
from PyQt6.QtWidgets import QApplication


class PyQtAsyncTestCase(unittest.TestCase):
    """Base class for PyQt tests that use async/await functionality.

    This test case handles proper setup and teardown of event loops and
    PyQt application instances, helping to avoid segmentation faults
    when testing PyQt components that use async operations.

    Features:
    - Sets up a clean event loop for each test
    - Provides integration between PyQt and asyncio
    - Ensures proper cleanup of resources
    - Handles common signal/slot connection issues
    """

    # Class variable to track QApplication instances across tests
    _app_instance: QApplication | None = None

    @classmethod
    def setUpClass(cls) -> None:
        """Set up class-level test fixtures.

        Creates a QApplication instance if needed.
        """
        super().setUpClass()

        # Ensure Qt uses the offscreen platform when running tests
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

        # Create QApplication if it doesn't exist yet
        if QApplication.instance() is None:
            try:
                # Store as class variable to prevent garbage collection
                cls._app_instance = QApplication(sys.argv)
            except Exception as e:
                # If QApplication creation fails, skip GUI tests
                import pytest

                pytest.skip(f"QApplication creation failed: {e}")

    def setUp(self) -> None:
        """Set up test fixtures.

        Creates a fresh event loop for each test.
        """
        super().setUp()

        # Check if QApplication is available
        if QApplication.instance() is None:
            import pytest

            pytest.skip("QApplication not available - skipping GUI test")

        # Set up a separate event loop for each test to avoid conflicts
        self._old_event_loop = asyncio.get_event_loop()
        self._event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._event_loop)

        # Track active tasks for cleanup
        self._active_tasks: set[asyncio.Task] = set()

        # List of objects to disconnect signals from during cleanup
        self._objects_with_signals: list[QObject] = []

    def tearDown(self) -> None:
        """Clean up test resources."""
        # Process any pending Qt events before teardown
        QCoreApplication.processEvents()

        # Disconnect signals
        for obj in self._objects_with_signals:
            self._disconnect_all_signals(obj)

        # Cancel any tasks we created
        if hasattr(self, "_event_loop") and self._event_loop is not None:
            try:
                self._cancel_all_tasks()
                self._event_loop.close()
            except Exception:
                pass

        # Restore previous event loop
        if hasattr(self, "_old_event_loop"):
            asyncio.set_event_loop(self._old_event_loop)

        # Call parent tearDown
        super().tearDown()

    def run_async(self, coro):
        """Run an async coroutine in the test's event loop.

        Args:
            coro: The coroutine to run

        Returns:
            The result of the coroutine
        """
        # Create a task and add it to our tracked tasks
        task = self._event_loop.create_task(coro)
        self._active_tasks.add(task)

        # Run the task and remove it from tracking when done
        try:
            return self._event_loop.run_until_complete(task)
        finally:
            self._active_tasks.discard(task)

    def track_signals(self, obj: QObject) -> None:
        """Track a QObject to disconnect its signals during tearDown.

        Args:
            obj: The QObject whose signals should be disconnected during cleanup
        """
        if isinstance(obj, QObject) and obj not in self._objects_with_signals:
            self._objects_with_signals.append(obj)

    def _disconnect_all_signals(self, obj: QObject) -> None:
        """Disconnect all signals from a QObject.

        Args:
            obj: The QObject to disconnect signals from
        """
        if not isinstance(obj, QObject):
            return

        # Safely disconnect signals
        try:
            # Get all signals
            meta_object = obj.metaObject()
            if meta_object:
                for i in range(meta_object.methodCount()):
                    method = meta_object.method(i)
                    if method.methodType() == method.MethodType.Signal:
                        # Get signal name
                        method_name = method.name()
                        if not method_name:
                            continue
                        name = method_name.data().decode("utf-8")
                        if hasattr(obj, name):
                            # Try to disconnect
                            try:
                                signal = getattr(obj, name)
                                signal.disconnect()
                            except Exception:
                                # It's normal for this to fail if the signal wasn't connected
                                pass
        except Exception:
            pass

    def _cancel_all_tasks(self) -> None:
        """Cancel all tracked tasks."""
        # Get all tasks from the event loop
        pending = asyncio.all_tasks(self._event_loop)

        if not pending:
            return

        # Cancel all tasks
        for task in pending:
            task.cancel()

        # Run the event loop once more to process cancellations
        self._event_loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))


class AsyncSignalWaiter:
    """Utility class to wait for a signal to be emitted.

    This class allows you to asynchronously wait for a Qt signal
    to be emitted, making it easier to test asynchronous workflows.

    Example:
        ```python
        # Create a waiter for the signal
        waiter = AsyncSignalWaiter(my_object.data_changed)

        # Start an operation that will eventually emit the signal
        my_object.start_loading()

        # Wait for the signal (with timeout)
        result = await waiter.wait(timeout=1.0)

        # Check if the signal was received
        self.assertTrue(result.received)

        # Access the signal arguments
        self.assertEqual(result.args[0], expected_value)
        ```
    """

    class SignalResult:
        """Result from waiting for a signal."""

        def __init__(self, received: bool, args=None):
            self.received = received
            self.args = args or []

    def __init__(self, signal) -> None:
        """Initialize with the signal to wait for.

        Args:
            signal: The Qt signal to wait for
        """
        self.signal = signal
        self.args = None
        self.future = None
        self._old_connection = None

    def _signal_callback(self, *args) -> None:
        """Callback for when the signal is emitted."""
        if self.future and not self.future.done():
            self.args = args
            self.future.set_result(True)

    async def wait(self, timeout: float = 5.0) -> SignalResult:
        """Wait for the signal to be emitted.

        Args:
            timeout: Timeout in seconds. Default 5.0.

        Returns:
            SignalResult with received status and signal arguments
        """
        # Create a future to wait on
        loop = asyncio.get_event_loop()
        self.future = loop.create_future()
        self.args = None

        # Connect the signal
        try:
            # Get the connect method - new style connection
            self._old_connection = self.signal.connect(self._signal_callback)

            # Wait for the future to complete or timeout
            try:
                await asyncio.wait_for(self.future, timeout)
                return self.SignalResult(True, self.args)
            except TimeoutError:
                return self.SignalResult(False)
        finally:
            # Disconnect the signal
            with contextlib.suppress(Exception):
                self.signal.disconnect(self._signal_callback)


def async_test(coro):
    """Decorator for running async test methods in PyQtAsyncTestCase.

    Used to automatically run async test methods in PyQtAsyncTestCase
    without having to call run_async explicitly.

    Example:
        ```python
        class MyTest(PyQtAsyncTestCase):
            @async_test
            async def test_async_function(self):
                # This test will run correctly in the test event loop
                result = await some_async_function()
                self.assertEqual(result, expected_value)
        ```

    Args:
        coro: The async test coroutine

    Returns:
        A wrapped test function
    """

    def wrapper(self, *args, **kwargs):
        if not isinstance(self, PyQtAsyncTestCase):
            msg = "async_test can only be used with PyQtAsyncTestCase"
            raise TypeError(msg)
        return self.run_async(coro(self, *args, **kwargs))

    return wrapper
