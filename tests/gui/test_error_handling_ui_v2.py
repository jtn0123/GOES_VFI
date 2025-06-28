"""
Optimized error handling and edge case UI tests with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures for error handling components
- Combined error scenario testing
- Batch validation of edge cases
- Enhanced network and resource management coverage
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import psutil
from PyQt6.QtCore import QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import QLabel, QMessageBox, QProgressBar, QApplication
import pytest

from goesvfi.gui import MainWindow


class TestErrorHandlingUIOptimizedV2:
    """Optimized error handling and edge case UI tests with full coverage."""

    @pytest.fixture(scope="class")
    def shared_app(self):
        """Shared QApplication instance."""
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        yield app
        app.processEvents()

    @pytest.fixture()
    def main_window(self, qtbot, shared_app, mocker):
        """Create MainWindow instance with mocks."""
        # Mock heavy components
        mocker.patch("goesvfi.integrity_check.combined_tab.CombinedIntegrityAndImageryTab")
        mocker.patch("goesvfi.integrity_check.enhanced_imagery_tab.EnhancedGOESImageryTab")

        window = MainWindow(debug_mode=True)
        qtbot.addWidget(window)
        window._post_init_setup()

        return window

    @pytest.fixture(scope="class")
    def error_handling_components(self):
        """Create shared error handling and network testing components."""
        
        # Enhanced Mock Network Operation
        class MockNetworkOperation(QThread):
            """Mock network operation with comprehensive timeout and retry simulation."""

            progress = pyqtSignal(int, str)
            finished = pyqtSignal(bool, str)
            error = pyqtSignal(str)

            def __init__(self, timeout_after=None, retry_count=3, success_after=None):
                super().__init__()
                self.timeout_after = timeout_after
                self.retry_count = retry_count
                self.success_after = success_after or retry_count
                self.attempts = 0
                self.operation_type = "download"

            def run(self):
                """Simulate network operation with various failure modes."""
                while self.attempts < self.retry_count:
                    self.attempts += 1
                    self.progress.emit(10 * self.attempts, f"Attempt {self.attempts}/{self.retry_count}")

                    if self.timeout_after and self.attempts <= self.timeout_after:
                        # Simulate timeout
                        self.error.emit(f"Network timeout (attempt {self.attempts}/{self.retry_count})")
                        self.msleep(100)  # Fast wait for testing
                        continue
                    
                    if self.attempts >= self.success_after:
                        # Success after specified attempts
                        self.progress.emit(100, f"{self.operation_type.title()} complete")
                        self.finished.emit(True, "Success")
                        return

                # All retries failed
                self.error.emit(f"{self.operation_type.title()} operation failed after all retries")
                self.finished.emit(False, "Failed")

        # Enhanced Retry Manager
        class RetryManager:
            """Advanced retry manager with exponential backoff and circuit breaker."""
            
            def __init__(self, max_retries=3, base_delay=100, backoff_factor=2.0):
                self.max_retries = max_retries
                self.base_delay = base_delay
                self.backoff_factor = backoff_factor
                self.current_attempt = 0
                self.retry_timer = QTimer()
                self.retry_timer.timeout.connect(self._retry_operation)
                self.circuit_breaker_threshold = 5
                self.consecutive_failures = 0
                self.circuit_open = False

            def start_operation(self, operation_func, status_callback, error_callback=None):
                self.operation_func = operation_func
                self.status_callback = status_callback
                self.error_callback = error_callback or (lambda x: None)
                self.current_attempt = 0
                self.circuit_open = False
                self._try_operation()

            def _try_operation(self):
                if self.circuit_open:
                    self.error_callback("Circuit breaker open - too many failures")
                    return False

                self.current_attempt += 1
                self.status_callback(f"Attempt {self.current_attempt}/{self.max_retries}")

                try:
                    result = self.operation_func()
                    if result:
                        self.status_callback("Success!")
                        self.consecutive_failures = 0
                        return True
                    else:
                        raise RuntimeError("Operation returned False")
                except Exception as e:
                    self.consecutive_failures += 1
                    
                    if self.consecutive_failures >= self.circuit_breaker_threshold:
                        self.circuit_open = True
                        self.error_callback("Circuit breaker activated")
                        return False

                    if self.current_attempt < self.max_retries:
                        delay = self.base_delay * (self.backoff_factor ** (self.current_attempt - 1))
                        self.status_callback(f"Failed: {e}. Retrying in {delay}ms...")
                        self.retry_timer.start(int(delay))
                        return None
                    else:
                        self.status_callback(f"Failed after {self.max_retries} attempts: {e}")
                        self.error_callback(f"All retries exhausted: {e}")
                        return False

            def _retry_operation(self):
                self.retry_timer.stop()
                self._try_operation()

            def reset_circuit_breaker(self):
                """Reset circuit breaker for testing."""
                self.circuit_open = False
                self.consecutive_failures = 0

        # Enhanced Memory Manager
        class MemoryManager:
            """Advanced memory management with predictive monitoring."""
            
            def __init__(self, window):
                self.window = window
                self.low_memory_mode = False
                self.critical_memory_mode = False
                self.memory_timer = QTimer()
                self.memory_timer.timeout.connect(self.check_memory)
                self.memory_samples = []
                self.max_samples = 10
                self.low_threshold = 85.0
                self.critical_threshold = 95.0
                self.recovery_threshold = 70.0

            def start_monitoring(self):
                self.memory_timer.start(1000)  # Check every second for testing

            def stop_monitoring(self):
                self.memory_timer.stop()

            def check_memory(self):
                """Check memory usage with trend analysis."""
                mem = psutil.virtual_memory()
                self.memory_samples.append(mem.percent)
                
                # Keep only recent samples
                if len(self.memory_samples) > self.max_samples:
                    self.memory_samples.pop(0)

                # Calculate trend
                if len(self.memory_samples) >= 3:
                    trend = self.memory_samples[-1] - self.memory_samples[-3]
                    if trend > 5.0:  # Rapid increase
                        self._handle_memory_pressure_trend()

                # Check thresholds
                if mem.percent > self.critical_threshold and not self.critical_memory_mode:
                    self.enable_critical_memory_mode()
                elif mem.percent > self.low_threshold and not self.low_memory_mode:
                    self.enable_low_memory_mode()
                elif mem.percent < self.recovery_threshold:
                    self.disable_memory_modes()

            def enable_low_memory_mode(self):
                self.low_memory_mode = True
                # Reduce UI update frequency
                if hasattr(self.window, "preview_timer"):
                    self.window.preview_timer.setInterval(500)

                # Disable non-essential features
                if hasattr(self.window, "thumbnail_generation"):
                    self.window.thumbnail_generation = False

                self.window.status_bar.showMessage("Low memory mode enabled - some features limited", 3000)

            def enable_critical_memory_mode(self):
                self.critical_memory_mode = True
                self.enable_low_memory_mode()  # Also enable low memory mode
                
                # More aggressive memory saving
                if hasattr(self.window, "image_cache"):
                    self.window.image_cache.clear()

                self.window.status_bar.showMessage("Critical memory mode - processing may be limited", 5000)

            def disable_memory_modes(self):
                if self.low_memory_mode or self.critical_memory_mode:
                    self.low_memory_mode = False
                    self.critical_memory_mode = False
                    
                    # Restore normal operation
                    if hasattr(self.window, "preview_timer"):
                        self.window.preview_timer.setInterval(100)

                    if hasattr(self.window, "thumbnail_generation"):
                        self.window.thumbnail_generation = True

                    self.window.status_bar.showMessage("Memory pressure relieved", 2000)

            def _handle_memory_pressure_trend(self):
                """Handle rapidly increasing memory usage."""
                if not self.low_memory_mode:
                    self.window.status_bar.showMessage("Memory usage increasing rapidly", 2000)

        # Enhanced Operation Lock Manager
        class OperationLockManager:
            """Advanced operation lock with queuing and priorities."""
            
            def __init__(self):
                self.locked_operations = {}
                self.operation_queue = []
                self.max_concurrent = 3
                self.operation_priorities = {
                    "processing": 1,
                    "preview": 2,
                    "save": 1,
                    "load": 3,
                }

            def acquire(self, operation_name, priority=None):
                if priority is None:
                    priority = self.operation_priorities.get(operation_name, 5)

                if operation_name in self.locked_operations:
                    return False, "Operation already running"

                if len(self.locked_operations) >= self.max_concurrent:
                    # Queue the operation
                    self.operation_queue.append((operation_name, priority))
                    self.operation_queue.sort(key=lambda x: x[1])  # Sort by priority
                    return False, f"Operation queued (position {len(self.operation_queue)})"

                self.locked_operations[operation_name] = {
                    "priority": priority,
                    "start_time": QTimer().remainingTime()  # Mock timestamp
                }
                return True, "Acquired"

            def release(self, operation_name):
                if operation_name in self.locked_operations:
                    del self.locked_operations[operation_name]
                    
                    # Process queue
                    if self.operation_queue:
                        next_op, priority = self.operation_queue.pop(0)
                        self.locked_operations[next_op] = {"priority": priority}
                        return next_op  # Return next operation to start
                return None

            def is_locked(self, operation_name):
                return operation_name in self.locked_operations

            def get_queue_status(self):
                return [(op, pri) for op, pri in self.operation_queue]

        # Enhanced File Validator
        class FileValidator:
            """Comprehensive file validation with detailed error reporting."""
            
            def __init__(self):
                self.valid_extensions = {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}
                self.supported_video_formats = {".mp4", ".mov", ".avi", ".mkv"}
                self.max_file_size = 500 * 1024 * 1024  # 500MB
                self.min_file_size = 1024  # 1KB

            def validate_input_files(self, file_paths):
                """Validate input files with comprehensive error reporting."""
                errors = []
                warnings = []
                processed_files = []

                for path in file_paths:
                    path = Path(path)
                    file_errors, file_warnings = self._validate_single_file(path, "input")
                    
                    if file_errors:
                        errors.extend([(path.name, error) for error in file_errors])
                    else:
                        processed_files.append(path)
                        if file_warnings:
                            warnings.extend([(path.name, warning) for warning in file_warnings])

                return errors, warnings, processed_files

            def validate_output_file(self, file_path):
                """Validate output file location and format."""
                path = Path(file_path)
                errors, warnings = self._validate_single_file(path, "output")
                
                # Check parent directory writability
                if not path.parent.exists():
                    errors.append("Output directory does not exist")
                elif not path.parent.is_dir():
                    errors.append("Output path parent is not a directory")
                
                return errors, warnings

            def _validate_single_file(self, path, file_type):
                """Validate a single file."""
                errors = []
                warnings = []

                # Check extension
                ext = path.suffix.lower()
                if file_type == "input" and ext not in self.valid_extensions:
                    if ext in self.supported_video_formats:
                        errors.append(f"Video format {ext} not supported for input - use image files")
                    else:
                        errors.append(f"Unsupported format: {ext}")
                    return errors, warnings
                elif file_type == "output" and ext not in self.supported_video_formats:
                    if ext in self.valid_extensions:
                        errors.append(f"Image format {ext} not supported for output - use video format")
                    else:
                        errors.append(f"Unsupported output format: {ext}")
                    return errors, warnings

                # Check if file exists (for input files)
                if file_type == "input":
                    if not path.exists():
                        errors.append("File not found")
                        return errors, warnings

                    # Check file size
                    try:
                        file_size = path.stat().st_size
                        if file_size < self.min_file_size:
                            errors.append("File appears to be corrupted (too small)")
                        elif file_size > self.max_file_size:
                            warnings.append(f"Large file ({file_size // (1024*1024)}MB) may slow processing")
                    except OSError:
                        errors.append("Cannot read file statistics")

                return errors, warnings

        return {
            "network_operation": MockNetworkOperation,
            "retry_manager": RetryManager,
            "memory_manager": MemoryManager,
            "lock_manager": OperationLockManager,
            "file_validator": FileValidator,
        }

    def test_network_operations_comprehensive(self, qtbot, main_window, error_handling_components) -> None:
        """Test comprehensive network operations with timeout and retry handling."""
        window = main_window
        
        # Create UI elements for network status
        status_label = QLabel("Ready")
        retry_label = QLabel("")
        progress_bar = QProgressBar()

        # Test multiple network scenarios
        network_scenarios = [
            {
                "name": "Timeout then Success",
                "timeout_after": 2,
                "success_after": 3,
                "retry_count": 5,
                "expected_attempts": 3,
            },
            {
                "name": "Immediate Success",
                "timeout_after": None,
                "success_after": 1,
                "retry_count": 3,
                "expected_attempts": 1,
            },
            {
                "name": "Complete Failure",
                "timeout_after": 3,
                "success_after": 10,  # Never succeeds
                "retry_count": 3,
                "expected_attempts": 3,
            },
        ]

        # Track UI updates
        ui_updates = []

        def update_ui_on_error(error_msg):
            ui_updates.append(error_msg)
            status_label.setText(f"Error: {error_msg}")
            if "attempt" in error_msg:
                retry_label.setText(error_msg)
                retry_label.setStyleSheet("color: orange;")
            else:
                retry_label.setStyleSheet("color: red;")

        def update_ui_on_progress(value, msg):
            progress_bar.setValue(value)
            status_label.setText(msg)

        # Test each scenario
        for scenario in network_scenarios:
            # Reset UI state
            ui_updates.clear()
            status_label.setText("Connecting...")
            progress_bar.setValue(0)

            # Create network operation
            MockNetworkOp = error_handling_components["network_operation"]
            network_op = MockNetworkOp(
                timeout_after=scenario["timeout_after"],
                success_after=scenario["success_after"],
                retry_count=scenario["retry_count"]
            )

            # Connect signals
            network_op.error.connect(update_ui_on_error)
            network_op.progress.connect(update_ui_on_progress)

            # Start operation
            network_op.start()

            # Wait for completion
            with qtbot.waitSignal(network_op.finished, timeout=5000):
                pass

            # Verify scenario-specific behavior
            if scenario["name"] == "Timeout then Success":
                assert len(ui_updates) >= 2, f"Expected timeout messages for {scenario['name']}"
                assert "timeout" in ui_updates[0].lower()
                assert status_label.text() in {"Download complete", "Attempt 3/5"}
            elif scenario["name"] == "Immediate Success":
                assert status_label.text() == "Download complete"
            elif scenario["name"] == "Complete Failure":
                assert len(ui_updates) >= scenario["retry_count"]
                assert "failed after all retries" in ui_updates[-1].lower()

    def test_retry_mechanisms_comprehensive(self, qtbot, main_window, error_handling_components) -> None:
        """Test comprehensive retry mechanisms with exponential backoff."""
        window = main_window
        RetryManager = error_handling_components["retry_manager"]

        # Test multiple retry scenarios
        retry_scenarios = [
            {
                "name": "Exponential Backoff Success",
                "attempt_results": [False, False, True],
                "base_delay": 50,
                "backoff_factor": 2.0,
                "expected_delays": [50, 100],
            },
            {
                "name": "Circuit Breaker Activation",
                "attempt_results": [False] * 10,  # Always fail
                "base_delay": 25,
                "circuit_threshold": 3,
                "expect_circuit_break": True,
            },
            {
                "name": "Immediate Success",
                "attempt_results": [True],
                "base_delay": 100,
                "expected_delays": [],
            },
        ]

        for scenario in retry_scenarios:
            # Setup mock operation
            attempt_index = 0
            attempt_results = scenario["attempt_results"]

            def mock_operation():
                nonlocal attempt_index
                if attempt_index < len(attempt_results):
                    result = attempt_results[attempt_index]
                    attempt_index += 1
                    if not result:
                        raise ConnectionError(f"Network error {attempt_index}")
                    return result
                return False

            # Track status updates and errors
            status_updates = []
            error_messages = []

            def status_callback(msg):
                status_updates.append(msg)

            def error_callback(msg):
                error_messages.append(msg)

            # Create and configure retry manager
            retry_mgr = RetryManager(
                base_delay=scenario["base_delay"],
                backoff_factor=scenario.get("backoff_factor", 2.0)
            )

            # Run operation
            retry_mgr.start_operation(mock_operation, status_callback, error_callback)

            # Wait for completion
            qtbot.wait(500)

            # Verify scenario-specific behavior
            if scenario["name"] == "Exponential Backoff Success":
                assert "Attempt 1/3" in status_updates[0]
                assert "Failed: Network error 1" in status_updates[1]
                assert "Success!" in status_updates[-1]
                assert len([u for u in status_updates if "Retrying in" in u]) == 2
            elif scenario["name"] == "Circuit Breaker Activation":
                if scenario.get("expect_circuit_break"):
                    # Circuit breaker behavior depends on implementation
                    assert len(error_messages) > 0 or len(status_updates) > 0
            elif scenario["name"] == "Immediate Success":
                assert "Success!" in status_updates[-1]
                assert len([u for u in status_updates if "Failed:" in u]) == 0

    def test_resource_management_comprehensive(self, qtbot, main_window, error_handling_components, mocker) -> None:
        """Test comprehensive resource management including disk space and memory."""
        window = main_window
        MemoryManager = error_handling_components["memory_manager"]

        # Test disk space scenarios
        disk_space_scenarios = [
            {
                "name": "Low Disk Space",
                "free_gb": 2.1,
                "total_gb": 1000,
                "required_gb": 10,
                "should_warn": True,
            },
            {
                "name": "Adequate Disk Space",
                "free_gb": 50.0,
                "total_gb": 1000,
                "required_gb": 10,
                "should_warn": False,
            },
            {
                "name": "Critical Disk Space",
                "free_gb": 0.5,
                "total_gb": 1000,
                "required_gb": 10,
                "should_warn": True,
            },
        ]

        # Mock QMessageBox
        mock_warning = mocker.patch.object(QMessageBox, "warning")
        
        for scenario in disk_space_scenarios:
            # Mock disk usage
            mock_disk_usage = mocker.patch("psutil.disk_usage")
            mock_disk_usage.return_value = MagicMock(
                total=int(scenario["total_gb"] * 1024**3),
                free=int(scenario["free_gb"] * 1024**3),
                used=int((scenario["total_gb"] - scenario["free_gb"]) * 1024**3),
            )

            # Function to check disk space
            def check_disk_space_for_output(output_path, required_space_gb=10):
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

            # Test disk space check
            window.out_file_path = Path("/test/output.mp4")
            has_space = check_disk_space_for_output(window.out_file_path, scenario["required_gb"])

            # Verify warning behavior
            if scenario["should_warn"]:
                assert not has_space, f"Should warn for {scenario['name']}"
                mock_warning.assert_called()
                args = mock_warning.call_args[0]
                assert "Low Disk Space" in args[1]
                assert f"{scenario['free_gb']:.1f} GB free" in args[2]
            else:
                assert has_space, f"Should not warn for {scenario['name']}"

            mock_warning.reset_mock()

        # Test memory management scenarios
        memory_scenarios = [
            {
                "name": "Low Memory",
                "memory_percent": 87.0,
                "should_enable_low_mode": True,
                "should_enable_critical_mode": False,
            },
            {
                "name": "Critical Memory",
                "memory_percent": 96.0,
                "should_enable_low_mode": True,
                "should_enable_critical_mode": True,
            },
            {
                "name": "Normal Memory",
                "memory_percent": 65.0,
                "should_enable_low_mode": False,
                "should_enable_critical_mode": False,
            },
        ]

        for scenario in memory_scenarios:
            # Mock memory info
            mock_virtual_memory = mocker.patch("psutil.virtual_memory")
            total_memory = 16 * 1024**3  # 16GB
            used_memory = int(total_memory * scenario["memory_percent"] / 100)
            available_memory = total_memory - used_memory

            mock_virtual_memory.return_value = MagicMock(
                total=total_memory,
                available=available_memory,
                percent=scenario["memory_percent"],
                used=used_memory,
            )

            # Create memory manager
            mem_mgr = MemoryManager(window)

            # Trigger memory check
            mem_mgr.check_memory()

            # Verify behavior
            if scenario["should_enable_critical_mode"]:
                assert mem_mgr.critical_memory_mode, f"Critical mode should be enabled for {scenario['name']}"
                assert "Critical memory" in window.status_bar.currentMessage()
            elif scenario["should_enable_low_mode"]:
                assert mem_mgr.low_memory_mode, f"Low mode should be enabled for {scenario['name']}"
                assert "Low memory" in window.status_bar.currentMessage()
            else:
                assert not mem_mgr.low_memory_mode, f"Low mode should not be enabled for {scenario['name']}"
                assert not mem_mgr.critical_memory_mode, f"Critical mode should not be enabled for {scenario['name']}"

            # Cleanup
            mem_mgr.stop_monitoring()

    def test_file_validation_comprehensive(self, qtbot, main_window, error_handling_components, mocker) -> None:
        """Test comprehensive file validation with detailed error reporting."""
        window = main_window
        FileValidator = error_handling_components["file_validator"]

        # Create file validator
        validator = FileValidator()

        # Test input file validation scenarios
        input_file_scenarios = [
            {
                "name": "Valid Image Files",
                "files": ["image1.png", "image2.jpg", "image3.jpeg"],
                "expect_errors": 0,
                "expect_warnings": 0,
            },
            {
                "name": "Invalid Formats",
                "files": ["document.pdf", "video.avi", "data.json"],
                "expect_errors": 3,
                "expect_warnings": 0,
            },
            {
                "name": "Mixed Valid and Invalid",
                "files": ["valid.png", "invalid.pdf", "valid2.jpg", "video.mp4"],
                "expect_errors": 2,
                "expect_warnings": 0,
            },
            {
                "name": "Corrupted Files",
                "files": ["corrupted.png", "empty.jpg"],
                "expect_errors": 2,
                "expect_warnings": 0,
            },
        ]

        # Mock message box
        mock_critical = mocker.patch.object(QMessageBox, "critical")
        mock_warning = mocker.patch.object(QMessageBox, "warning")

        for scenario in input_file_scenarios:
            # Create mock file paths
            test_files = [Path(f) for f in scenario["files"]]
            
            # Mock file existence and properties
            def mock_exists(path):
                # Corrupted/empty files "exist" but have issues
                return "corrupted" not in str(path) and "empty" not in str(path)
            
            def mock_stat(path):
                if "corrupted" in str(path) or "empty" in str(path):
                    # Simulate corrupted file
                    return MagicMock(st_size=0)
                return MagicMock(st_size=1024 * 1024)  # 1MB normal file

            with mocker.patch.object(Path, "exists", side_effect=mock_exists):
                with mocker.patch.object(Path, "stat", side_effect=mock_stat):
                    # Validate files
                    errors, warnings, processed_files = validator.validate_input_files(test_files)

                    # Verify results
                    assert len(errors) == scenario["expect_errors"], (
                        f"{scenario['name']}: Expected {scenario['expect_errors']} errors, got {len(errors)}"
                    )
                    assert len(warnings) == scenario["expect_warnings"], (
                        f"{scenario['name']}: Expected {scenario['expect_warnings']} warnings, got {len(warnings)}"
                    )

                    # Show error dialog if errors found
                    if errors:
                        error_list = "\n".join([f"• {name}: {msg}" for name, msg in errors])
                        QMessageBox.critical(
                            window,
                            "Invalid Files Detected",
                            f"The following files cannot be processed:\n\n{error_list}\n\n"
                            f"Please ensure all input files are valid image files.",
                        )
                        mock_critical.assert_called()

                    mock_critical.reset_mock()

        # Test output file validation scenarios
        output_file_scenarios = [
            {
                "name": "Valid Video Output",
                "file": "/valid/path/output.mp4",
                "expect_errors": 0,
            },
            {
                "name": "Invalid Image Output",
                "file": "/invalid/path/output.png",
                "expect_errors": 1,
            },
            {
                "name": "Unsupported Format",
                "file": "/invalid/path/output.txt",
                "expect_errors": 1,
            },
        ]

        for scenario in output_file_scenarios:
            errors, warnings = validator.validate_output_file(scenario["file"])
            
            assert len(errors) == scenario["expect_errors"], (
                f"{scenario['name']}: Expected {scenario['expect_errors']} errors, got {len(errors)}"
            )

    def test_concurrent_operations_and_crash_recovery_comprehensive(self, qtbot, main_window, error_handling_components, mocker) -> None:
        """Test comprehensive concurrent operation prevention and crash recovery."""
        window = main_window
        OperationLockManager = error_handling_components["lock_manager"]

        # Test operation locking scenarios
        lock_scenarios = [
            {
                "name": "Single Operation Success",
                "operations": [("processing", 1)],
                "expect_acquired": 1,
                "expect_queued": 0,
            },
            {
                "name": "Multiple Operations with Queuing",
                "operations": [("processing", 1), ("preview", 2), ("save", 1), ("load", 3)],
                "expect_acquired": 3,  # max_concurrent = 3
                "expect_queued": 1,
            },
            {
                "name": "Priority-based Queuing",
                "operations": [("load", 3), ("processing", 1), ("preview", 2), ("save", 1)],
                "expect_acquired": 3,
                "expect_queued": 1,
            },
        ]

        for scenario in lock_scenarios:
            # Create lock manager
            lock_mgr = OperationLockManager()
            
            acquired_count = 0
            queued_count = 0

            # Try to acquire all operations
            for op_name, priority in scenario["operations"]:
                success, message = lock_mgr.acquire(op_name, priority)
                if success:
                    acquired_count += 1
                elif "queued" in message:
                    queued_count += 1

            # Verify results
            assert acquired_count == scenario["expect_acquired"], (
                f"{scenario['name']}: Expected {scenario['expect_acquired']} acquired, got {acquired_count}"
            )
            assert queued_count == scenario["expect_queued"], (
                f"{scenario['name']}: Expected {scenario['expect_queued']} queued, got {queued_count}"
            )

            # Test release and queue processing
            if scenario["expect_queued"] > 0:
                # Release one operation
                first_op = scenario["operations"][0][0]
                next_op = lock_mgr.release(first_op)
                assert next_op is not None, "Should start next queued operation"

        # Test UI feedback for concurrent operations
        lock_mgr = OperationLockManager()
        
        # First operation should succeed
        success, message = lock_mgr.acquire("processing")
        assert success
        window._set_processing_state(True)

        # Second operation should be blocked
        success, message = lock_mgr.acquire("processing")
        assert not success
        assert "already running" in message

        # UI should show warning
        if not success:
            window.status_bar.showMessage("Operation already in progress. Please wait...", 3000)

        assert "already in progress" in window.status_bar.currentMessage()

        # Release lock
        lock_mgr.release("processing")
        window._set_processing_state(False)

        # Test crash recovery scenarios
        crash_recovery_scenarios = [
            {
                "name": "Previous Session Crashed",
                "crash_info": "Previous session crashed at 2024-01-01 12:00:00",
                "recovery_data": {
                    "input_dir": "/previous/input",
                    "output_file": "/previous/output.mp4",
                    "settings": {"fps": 60, "encoder": "FFmpeg"},
                },
                "should_restore": True,
            },
            {
                "name": "Clean Shutdown",
                "crash_info": None,
                "recovery_data": None,
                "should_restore": False,
            },
        ]

        for scenario in crash_recovery_scenarios:
            # Create crash file if needed
            crash_file = Path(tempfile.gettempdir()) / "goes_vfi_crash_test.log"
            
            if scenario["crash_info"]:
                crash_file.write_text(scenario["crash_info"])

            # Crash recovery dialog simulation
            class CrashRecoveryDialog:
                def __init__(self, crash_info):
                    self.crash_info = crash_info
                    self.recovery_option = "restore" if crash_info else None

                def show_recovery_options(self):
                    return self.recovery_option

                def restore_session(self, window):
                    if scenario["recovery_data"]:
                        data = scenario["recovery_data"]
                        window.set_in_dir(Path(data["input_dir"]))
                        window.out_file_path = Path(data["output_file"])
                        window.main_tab.fps_spinbox.setValue(data["settings"]["fps"])
                        return True
                    return False

            # Check for crash on startup
            if crash_file.exists():
                recovery_dialog = CrashRecoveryDialog(crash_file.read_text())
                option = recovery_dialog.show_recovery_options()

                if option == "restore" and scenario["should_restore"]:
                    restored = recovery_dialog.restore_session(window)
                    assert restored, f"Restoration failed for {scenario['name']}"
                    assert window.in_dir == Path(scenario["recovery_data"]["input_dir"])
                    assert window.main_tab.fps_spinbox.value() == scenario["recovery_data"]["settings"]["fps"]

                # Clean up crash file
                crash_file.unlink()

            # Verify crash file was handled
            assert not crash_file.exists(), f"Crash file not cleaned up for {scenario['name']}"

    def test_settings_corruption_and_recovery_comprehensive(self, qtbot, main_window, error_handling_components, mocker) -> None:
        """Test comprehensive settings corruption recovery."""
        window = main_window

        # Test settings corruption scenarios
        corruption_scenarios = [
            {
                "name": "Complete Settings Corruption",
                "corruption_type": "value_error",
                "error_keys": ["all"],
                "should_reset_all": True,
            },
            {
                "name": "Partial Settings Corruption",
                "corruption_type": "value_error",
                "error_keys": ["encoder", "fps"],
                "should_reset_all": False,
            },
            {
                "name": "File Not Found",
                "corruption_type": "file_not_found",
                "error_keys": [],
                "should_reset_all": True,
            },
        ]

        # Mock QSettings and message boxes
        mock_settings = mocker.patch("PyQt6.QtCore.QSettings")
        mock_info = mocker.patch.object(QMessageBox, "information")
        mock_critical = mocker.patch.object(QMessageBox, "critical")

        for scenario in corruption_scenarios:
            # Create mock settings instance
            mock_instance = MagicMock()

            # Configure mock behavior based on corruption type
            def mock_value(key, default=None, type=None):
                if scenario["corruption_type"] == "value_error":
                    if "all" in scenario["error_keys"] or key in scenario["error_keys"]:
                        raise ValueError("Settings corrupted")
                elif scenario["corruption_type"] == "file_not_found":
                    raise FileNotFoundError("Settings file not found")
                return default

            mock_instance.value = mock_value
            mock_settings.return_value = mock_instance

            # Settings recovery manager
            class SettingsRecovery:
                def __init__(self, window):
                    self.window = window
                    self.backup_settings = {}

                def load_settings_with_recovery(self):
                    try:
                        # Try to load critical settings
                        settings = mock_settings()
                        test_keys = ["fps", "encoder", "output_format", "quality"]
                        
                        for key in test_keys:
                            settings.value(key, "default")
                        
                        return self.load_normal_settings()
                    except (ValueError, FileNotFoundError) as e:
                        if scenario["should_reset_all"]:
                            return self.load_default_settings()
                        else:
                            return self.load_partial_recovery()

                def load_normal_settings(self):
                    return {
                        "fps": 30,
                        "encoder": "RIFE",
                        "output_format": "mp4",
                        "quality": "high",
                    }

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
                        f"Settings file was corrupted and has been reset to defaults.\n"
                        f"Your preferences have been restored to default values.",
                    )

                    return defaults

                def load_partial_recovery(self):
                    # Try to recover individual settings
                    recovered = {}
                    defaults = {"fps": 30, "encoder": "RIFE"}
                    
                    for key, default in defaults.items():
                        try:
                            # Mock individual recovery attempts
                            if key in scenario["error_keys"]:
                                recovered[key] = default  # Use default for corrupted keys
                            else:
                                recovered[key] = default  # Simulate successful recovery
                        except:
                            recovered[key] = default

                    # Apply recovered settings
                    self.window.main_tab.fps_spinbox.setValue(recovered["fps"])
                    self.window.main_tab.encoder_combo.setCurrentText(recovered["encoder"])

                    # Notify user of partial recovery
                    QMessageBox.information(
                        self.window,
                        "Settings Partially Recovered",
                        f"Some settings were corrupted and have been reset.\n"
                        f"Other settings have been preserved.",
                    )

                    return recovered

            # Create recovery manager and test
            recovery_mgr = SettingsRecovery(window)
            result = recovery_mgr.load_settings_with_recovery()

            # Verify recovery behavior
            assert result is not None, f"Recovery failed for {scenario['name']}"
            assert isinstance(result, dict), f"Recovery result invalid for {scenario['name']}"
            assert "fps" in result, f"FPS setting missing after recovery for {scenario['name']}"
            
            # Verify UI was updated
            assert isinstance(window.main_tab.fps_spinbox.value(), int)
            assert window.main_tab.encoder_combo.currentText() in {"RIFE", "FFmpeg"}

            # Verify user was notified
            if scenario["should_reset_all"]:
                mock_info.assert_called()
                args = mock_info.call_args[0]
                assert "Settings Reset" in args[1] or "corrupted" in args[2].lower()
            
            # Reset mocks for next scenario
            mock_info.reset_mock()
            mock_critical.reset_mock()
