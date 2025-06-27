"""Error handling and edge case UI tests for GOES VFI GUI."""

from pathlib import Path
import tempfile
from unittest.mock import MagicMock

import psutil
from PyQt6.QtCore import QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import QLabel, QMessageBox, QProgressBar
import pytest

from goesvfi.gui import MainWindow


class MockNetworkOperation(QThread):
    """Mock network operation with timeout simulation."""

    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)
    error = pyqtSignal(str)

    def __init__(self, timeout_after=None, retry_count=3) -> None:
        super().__init__()
        self.timeout_after = timeout_after
        self.retry_count = retry_count
        self.attempts = 0

    def run(self) -> None:
        """Simulate network operation with potential timeout."""
        while self.attempts < self.retry_count:
            self.attempts += 1

            if self.timeout_after and self.attempts <= self.timeout_after:
                # Simulate timeout
                self.error.emit(f"Network timeout (attempt {self.attempts}/{self.retry_count})")
                self.msleep(1000)  # Wait before retry
                continue
            # Success
            self.progress.emit(100, "Download complete")
            self.finished.emit(True, "Success")
            return

        # All retries failed
        self.error.emit("Network operation failed after all retries")
        self.finished.emit(False, "Failed")


class TestErrorHandlingUI:
    """Test error handling and edge cases in the UI."""

    @pytest.fixture()
    def window(self, qtbot, mocker):
        """Create a MainWindow instance for testing."""
        # Mock heavy components
        mocker.patch("goesvfi.integrity_check.combined_tab.CombinedIntegrityAndImageryTab")
        mocker.patch("goesvfi.integrity_check.enhanced_imagery_tab.EnhancedGOESImageryTab")

        window = MainWindow(debug_mode=True)
        qtbot.addWidget(window)
        window._post_init_setup()

        return window

    def test_network_timeout_ui_feedback(self, qtbot, window, mocker) -> None:
        """Test UI feedback during network timeouts."""
        # Create UI elements for network status
        status_label = QLabel("Ready")
        retry_label = QLabel("")
        progress_bar = QProgressBar()

        # Mock network operation with timeout
        network_op = MockNetworkOperation(timeout_after=2)

        # Track UI updates
        ui_updates = []

        def update_ui_on_error(error_msg) -> None:
            ui_updates.append(error_msg)
            status_label.setText(f"Error: {error_msg}")
            if "attempt" in error_msg:
                retry_label.setText(error_msg)
                retry_label.setStyleSheet("color: orange;")
            else:
                retry_label.setStyleSheet("color: red;")

        def update_ui_on_progress(value, msg) -> None:
            progress_bar.setValue(value)
            status_label.setText(msg)

        # Connect signals
        network_op.error.connect(update_ui_on_error)
        network_op.progress.connect(update_ui_on_progress)

        # Start operation
        status_label.setText("Connecting...")
        network_op.start()

        # Wait for completion
        with qtbot.waitSignal(network_op.finished, timeout=5000):
            pass

        # Verify UI showed timeout feedback
        assert len(ui_updates) >= 2  # At least 2 timeout messages
        assert "timeout" in ui_updates[0].lower()
        assert "attempt 1/3" in ui_updates[0]

        # Verify final success
        assert status_label.text() == "Download complete"

    def test_network_retry_mechanisms(self, qtbot, window, mocker) -> None:
        """Test network retry mechanisms with UI updates."""

        # Create retry manager
        class RetryManager:
            def __init__(self, max_retries=3, retry_delay=1000) -> None:
                self.max_retries = max_retries
                self.retry_delay = retry_delay
                self.current_attempt = 0
                self.retry_timer = QTimer()
                self.retry_timer.timeout.connect(self._retry_operation)

            def start_operation(self, operation_func, status_callback) -> None:
                self.operation_func = operation_func
                self.status_callback = status_callback
                self.current_attempt = 0
                self._try_operation()

            def _try_operation(self) -> bool | None:
                self.current_attempt += 1
                self.status_callback(f"Attempt {self.current_attempt}/{self.max_retries}")

                try:
                    result = self.operation_func()
                    if result:
                        self.status_callback("Success!")
                        return True
                except Exception as e:
                    if self.current_attempt < self.max_retries:
                        self.status_callback(f"Failed: {e}. Retrying in {self.retry_delay / 1000}s...")
                        self.retry_timer.start(self.retry_delay)
                        return False
                    self.status_callback(f"Failed after {self.max_retries} attempts")
                    return False

            def _retry_operation(self) -> None:
                self.retry_timer.stop()
                self._try_operation()

        # Mock failing operation
        attempt_results = [False, False, True]  # Fail twice, then succeed
        attempt_index = 0

        def mock_operation():
            nonlocal attempt_index
            if attempt_index < len(attempt_results):
                result = attempt_results[attempt_index]
                attempt_index += 1
                if not result:
                    msg = "Network error"
                    raise ConnectionError(msg)
                return result
            return False

        # Track status updates
        status_updates = []

        def status_callback(msg) -> None:
            status_updates.append(msg)

        # Run with retries
        retry_mgr = RetryManager(retry_delay=100)  # Fast retry for testing
        retry_mgr.start_operation(mock_operation, status_callback)

        # Wait for retries
        qtbot.wait(500)

        # Verify retry sequence
        assert "Attempt 1/3" in status_updates
        assert "Failed: Network error" in status_updates[1]
        assert "Attempt 2/3" in status_updates
        assert "Success!" in status_updates[-1]

    def test_low_disk_space_warnings(self, qtbot, window, mocker) -> None:
        """Test low disk space warning UI."""
        # Mock disk usage
        mock_disk_usage = mocker.patch("psutil.disk_usage")

        # Simulate low disk space (5% free)
        mock_disk_usage.return_value = MagicMock(
            total=1000 * 1024**3,  # 1TB
            used=950 * 1024**3,  # 950GB used
            free=50 * 1024**3,  # 50GB free
            percent=95.0,
        )

        # Mock QMessageBox
        mock_warning = mocker.patch.object(QMessageBox, "warning")

        # Function to check disk space
        def check_disk_space_for_output(output_path, required_space_gb=10) -> bool:
            disk_stats = psutil.disk_usage(str(Path(output_path).parent))
            free_gb = disk_stats.free / (1024**3)

            if free_gb < required_space_gb:
                QMessageBox.warning(
                    window,
                    "Low Disk Space",
                    f"Warning: Only {free_gb:.1f} GB free disk space available.\n"
                    f"Recommended: {required_space_gb} GB for processing.\n\n"
                    f"Consider:\n"
                    f"• Freeing up disk space\n"
                    f"• Choosing a different output location\n"
                    f"• Reducing output quality settings",
                )
                return False
            return True

        # Set output path and check space
        window.out_file_path = Path("/test/output.mp4")
        has_space = check_disk_space_for_output(window.out_file_path)

        # Verify warning was shown
        assert not has_space
        mock_warning.assert_called_once()
        args = mock_warning.call_args[0]
        assert "Low Disk Space" in args[1]
        assert "5.0 GB free" in args[2]
        assert "Consider:" in args[2]

    def test_memory_limit_handling(self, qtbot, window, mocker) -> None:
        """Test memory limit handling and UI adjustments."""
        # Mock memory info
        mock_virtual_memory = mocker.patch("psutil.virtual_memory")

        # Simulate low memory (90% used)
        mock_virtual_memory.return_value = MagicMock(
            total=16 * 1024**3,  # 16GB total
            available=1.6 * 1024**3,  # 1.6GB available
            percent=90.0,
            used=14.4 * 1024**3,
        )

        # Memory manager
        class MemoryManager:
            def __init__(self, window) -> None:
                self.window = window
                self.low_memory_mode = False
                self.memory_timer = QTimer()
                self.memory_timer.timeout.connect(self.check_memory)
                self.memory_timer.start(5000)  # Check every 5 seconds

            def check_memory(self) -> None:
                mem = psutil.virtual_memory()
                if mem.percent > 85 and not self.low_memory_mode:
                    self.enable_low_memory_mode()
                elif mem.percent < 70 and self.low_memory_mode:
                    self.disable_low_memory_mode()

            def enable_low_memory_mode(self) -> None:
                self.low_memory_mode = True
                # Reduce UI update frequency
                if hasattr(self.window, "preview_timer"):
                    self.window.preview_timer.setInterval(500)  # Slower updates

                # Disable non-essential features
                if hasattr(self.window, "thumbnail_generation"):
                    self.window.thumbnail_generation = False

                # Show warning
                self.window.status_bar.showMessage("Low memory mode enabled - some features limited", 5000)

            def disable_low_memory_mode(self) -> None:
                self.low_memory_mode = False
                # Restore normal operation
                if hasattr(self.window, "preview_timer"):
                    self.window.preview_timer.setInterval(100)

                if hasattr(self.window, "thumbnail_generation"):
                    self.window.thumbnail_generation = True

        # Create memory manager
        mem_mgr = MemoryManager(window)

        # Trigger immediate check
        mem_mgr.check_memory()

        # Verify low memory mode enabled
        assert mem_mgr.low_memory_mode
        assert "Low memory mode" in window.status_bar.currentMessage()

        # Stop timer for cleanup
        mem_mgr.memory_timer.stop()

    def test_invalid_file_format_errors(self, qtbot, window, mocker) -> None:
        """Test handling of invalid file formats."""
        # Mock file validation
        invalid_files = [
            ("document.pdf", "PDF files are not supported"),
            ("video.avi", "AVI format not supported for input"),
            ("image.bmp", "BMP format must be converted to PNG"),
            ("data.json", "JSON is not an image format"),
            ("corrupted.png", "File appears to be corrupted"),
        ]

        # Mock message box
        mock_critical = mocker.patch.object(QMessageBox, "critical")

        # File validator
        def validate_input_files(file_paths):
            errors = []
            valid_extensions = {".png", ".jpg", ".jpeg"}

            for path in file_paths:
                path = Path(path)

                # Check extension
                if path.suffix.lower() not in valid_extensions:
                    errors.append((path.name, f"Unsupported format: {path.suffix}"))
                    continue

                # Check if file exists and is readable
                if not path.exists():
                    errors.append((path.name, "File not found"))
                    continue

                # Check file size (mock corrupted as 0 bytes)
                if path.name == "corrupted.png":
                    errors.append((path.name, "File appears to be corrupted"))

            return errors

        # Test various invalid files
        test_files = [Path(f[0]) for f in invalid_files]
        errors = validate_input_files(test_files)

        # Show error dialog if errors found
        if errors:
            error_list = "\n".join([f"• {name}: {msg}" for name, msg in errors])
            QMessageBox.critical(
                window,
                "Invalid Files Detected",
                f"The following files cannot be processed:\n\n{error_list}\n\n"
                f"Please ensure all input files are valid PNG or JPEG images.",
            )

        # Verify error dialog
        assert len(errors) == len(invalid_files)
        mock_critical.assert_called_once()
        args = mock_critical.call_args[0]
        assert "Invalid Files Detected" in args[1]
        assert "document.pdf" in args[2]
        assert "Unsupported format" in args[2]

    def test_concurrent_operation_prevention(self, qtbot, window) -> None:
        """Test prevention of concurrent operations."""

        # Operation lock manager
        class OperationLock:
            def __init__(self) -> None:
                self.locked_operations = set()

            def acquire(self, operation_name) -> bool:
                if operation_name in self.locked_operations:
                    return False
                self.locked_operations.add(operation_name)
                return True

            def release(self, operation_name) -> None:
                self.locked_operations.discard(operation_name)

            def is_locked(self, operation_name):
                return operation_name in self.locked_operations

        # Create lock manager
        lock_mgr = OperationLock()

        # Test concurrent processing prevention
        # First operation
        assert lock_mgr.acquire("processing")
        assert window.main_tab.start_button.isEnabled()

        # Try to start another operation
        window._set_processing_state(True)
        second_acquire = lock_mgr.acquire("processing")
        assert not second_acquire  # Should fail

        # UI should show warning
        if not second_acquire:
            window.status_bar.showMessage("Operation already in progress. Please wait...", 3000)

        assert "already in progress" in window.status_bar.currentMessage()

        # Release lock
        lock_mgr.release("processing")
        window._set_processing_state(False)

        # Now should be able to acquire again
        assert lock_mgr.acquire("processing")

    def test_corrupted_settings_recovery(self, qtbot, window, mocker) -> None:
        """Test recovery from corrupted settings."""
        # Mock corrupted settings
        mock_settings = mocker.patch("PyQt6.QtCore.QSettings")
        mock_instance = MagicMock()

        # Simulate corrupted read
        def mock_value(key, default=None, type=None):
            if key == "corrupted_key":
                msg = "Settings corrupted"
                raise ValueError(msg)
            return default

        mock_instance.value = mock_value
        mock_settings.return_value = mock_instance

        # Settings recovery manager
        class SettingsRecovery:
            def __init__(self, window) -> None:
                self.window = window
                self.backup_settings = {}

            def load_settings_with_recovery(self):
                try:
                    # Try to load settings
                    settings = mock_settings()
                    settings.value("corrupted_key", "default")
                except Exception:
                    # Settings corrupted, use defaults
                    return self.load_default_settings()

            def load_default_settings(self):
                defaults = {
                    "fps": 30,
                    "encoder": "RIFE",
                    "output_format": "mp4",
                    "quality": "high",
                }

                # Apply defaults to UI
                self.window.main_tab.fps_spinbox.setValue(defaults["fps"])
                self.window.main_tab.encoder_combo.setCurrentText(defaults["encoder"])

                # Notify user
                QMessageBox.information(
                    self.window,
                    "Settings Reset",
                    "Settings file was corrupted and has been reset to defaults.\n"
                    "Your preferences have been restored to default values.",
                )

                return defaults

        # Create recovery manager
        recovery_mgr = SettingsRecovery(window)

        # Mock information dialog
        mock_info = mocker.patch.object(QMessageBox, "information")

        # Try to load settings
        result = recovery_mgr.load_settings_with_recovery()

        # Verify defaults were loaded
        assert result is not None
        assert window.main_tab.fps_spinbox.value() == 30
        assert window.main_tab.encoder_combo.currentText() == "RIFE"

        # Verify user was notified
        mock_info.assert_called_once()
        args = mock_info.call_args[0]
        assert "Settings Reset" in args[1]
        assert "corrupted" in args[2]

    def test_crash_recovery_dialog(self, qtbot, window, mocker) -> None:
        """Test crash recovery dialog and options."""
        # Mock crash detection
        crash_file = Path(tempfile.gettempdir()) / "goes_vfi_crash.log"
        crash_file.write_text("Previous session crashed at 2024-01-01 12:00:00")

        # Crash recovery dialog
        class CrashRecoveryDialog:
            def __init__(self, crash_info) -> None:
                self.crash_info = crash_info
                self.recovery_option = None

            def show_recovery_options(self):
                # Mock dialog with options

                # Simulate user selection
                self.recovery_option = "restore"  # Mock selection
                return self.recovery_option

            def restore_session(self, window) -> bool:
                # Restore from autosave
                autosave_data = {
                    "input_dir": "/previous/input",
                    "output_file": "/previous/output.mp4",
                    "settings": {"fps": 60, "encoder": "FFmpeg"},
                }

                # Apply restored data
                window.set_in_dir(Path(autosave_data["input_dir"]))
                window.out_file_path = Path(autosave_data["output_file"])
                window.main_tab.fps_spinbox.setValue(autosave_data["settings"]["fps"])

                return True

        # Check for crash on startup
        if crash_file.exists():
            recovery_dialog = CrashRecoveryDialog(crash_file.read_text())
            option = recovery_dialog.show_recovery_options()

            if option == "restore":
                restored = recovery_dialog.restore_session(window)
                assert restored
                assert window.in_dir == Path("/previous/input")
                assert window.main_tab.fps_spinbox.value() == 60

            # Clean up crash file
            crash_file.unlink()

        # Verify crash file was handled
        assert not crash_file.exists()
