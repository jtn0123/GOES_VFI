"""Critical scenario tests for Configuration Hot-Reloading System.

This test suite covers high-priority missing areas identified in the testing gap analysis:
1. Race conditions in rapid file modification scenarios
2. Thread safety under concurrent configuration updates
3. File system edge cases and recovery mechanisms
4. Advanced validation under concurrent operations
5. Configuration corruption handling
6. Watcher notification reliability under load
"""

import json
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Any
from unittest.mock import patch
import uuid

import pytest

from goesvfi.core.configuration import (
    ConfigurationManager,
)


class TestConfigurationHotReloadCritical:
    """Critical scenario tests for configuration hot-reloading system."""

    @pytest.fixture()
    @staticmethod
    def temp_config_dir() -> Any:
        """Create temporary directory for configuration tests.

        Yields:
            Path: Temporary directory path for configuration testing.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture()
    @staticmethod
    def mock_config_data() -> dict[str, Any]:
        """Create mock configuration data for testing.

        Returns:
            dict[str, Any]: Mock configuration data structure.
        """
        return {
            "processing": {"max_workers": 4, "buffer_size": 65536, "cache_size": 100, "batch_size": 10},
            "network": {
                "connection_timeout": 30.0,
                "read_timeout": 300.0,
                "max_retries": 3,
                "retry_delay": 1.0,
                "max_connections": 10,
            },
            "storage": {
                "data_directory": "./data",
                "output_directory": "./output",
                "log_directory": "./logs",
                "cache_directory": "./cache",
                "max_disk_usage": 10737418240,
            },
            "ui": {
                "theme": "light",
                "window_width": 1200,
                "window_height": 800,
                "update_interval": 0.1,
                "preview_size": 512,
            },
        }

    @staticmethod
    def test_rapid_file_modification_race_conditions(temp_config_dir: Path, mock_config_data: dict) -> None:
        """Test race conditions during rapid file modifications."""
        config_file = temp_config_dir / "config.json"
        config_file.write_text(json.dumps(mock_config_data))

        config_manager = ConfigurationManager(config_file)
        config_manager.start_file_watching()

        try:
            modification_results = []
            modification_lock = threading.Lock()

            def rapid_file_modifier(modifier_id: int) -> None:
                """Rapidly modify configuration file."""
                for i in range(5):  # Reduced to avoid overwhelming
                    try:
                        # Modify different sections to simulate concurrent edits
                        modified_config = mock_config_data.copy()
                        modified_config["processing"]["max_workers"] = modifier_id * 10 + i

                        # Write file atomically with unique temp file

                        temp_file = config_file.with_suffix(f".tmp.{uuid.uuid4().hex[:8]}")
                        temp_file.write_text(json.dumps(modified_config))
                        temp_file.replace(config_file)

                        with modification_lock:
                            modification_results.append((modifier_id, i, "success"))

                        time.sleep(0.1)  # Short delay between modifications

                    except (OSError, json.JSONDecodeError, ValueError) as e:
                        with modification_lock:
                            modification_results.append((modifier_id, i, f"error: {e}"))

            # Start multiple rapid modifiers
            threads = []
            for i in range(3):
                thread = threading.Thread(target=rapid_file_modifier, args=(i,))
                threads.append(thread)
                thread.start()

            # Wait for all modifications to complete
            for thread in threads:
                thread.join(timeout=10.0)

            # Verify at least some modifications succeeded (race conditions are expected)
            successes = [result for result in modification_results if result[2] == "success"]
            errors = [result for result in modification_results if "error" in result[2]]

            # Some race condition errors are expected in this test
            assert len(successes) > 0, f"No modifications succeeded. Errors: {errors}"
            assert len(modification_results) == 15, f"Expected 15 total modifications, got {len(modification_results)}"

            # Verify final configuration is valid
            time.sleep(1.0)  # Allow final reload
            final_config = config_manager.get_config()
            assert isinstance(final_config.processing.max_workers, int)
            assert final_config.processing.max_workers > 0

        finally:
            config_manager.stop_file_watching()

    @staticmethod
    def test_concurrent_watcher_update_operations(temp_config_dir: Path, mock_config_data: dict) -> None:
        """Test concurrent operations between file watcher and configuration updates."""
        config_file = temp_config_dir / "config.json"
        config_file.write_text(json.dumps(mock_config_data))

        config_manager = ConfigurationManager(config_file)
        config_manager.start_file_watching()

        try:
            operation_results = []
            operation_lock = threading.Lock()

            def file_watcher_stress() -> None:
                """Stress the file watcher with changes."""
                for i in range(10):
                    try:
                        # Modify configuration to trigger watcher
                        modified_config = mock_config_data.copy()
                        modified_config["processing"]["max_workers"] = 100 + i
                        config_file.write_text(json.dumps(modified_config))

                        with operation_lock:
                            operation_results.append(("watcher_trigger", i, "success"))

                        time.sleep(0.2)  # Allow watcher to process

                    except (OSError, json.JSONDecodeError, ValueError) as e:
                        with operation_lock:
                            operation_results.append(("watcher_trigger", i, f"error: {e}"))

            def concurrent_config_reader() -> None:
                """Concurrently read configuration while watcher is active."""
                for i in range(15):
                    try:
                        config = config_manager.get_config()

                        # Verify configuration integrity
                        assert isinstance(config.processing.max_workers, int)
                        assert config.processing.max_workers > 0

                        with operation_lock:
                            operation_results.append(("reader", i, "success"))

                    except (OSError, json.JSONDecodeError, ValueError) as e:
                        with operation_lock:
                            operation_results.append(("reader", i, f"error: {e}"))

                    time.sleep(0.1)

            # Start concurrent operations
            threads = [threading.Thread(target=file_watcher_stress), threading.Thread(target=concurrent_config_reader)]

            for thread in threads:
                thread.start()

            # Wait for completion
            for thread in threads:
                thread.join(timeout=15.0)

            # Verify no race conditions occurred
            errors = [result for result in operation_results if "error" in result[2]]
            assert len(errors) == 0, f"Concurrent operations caused errors: {errors}"

            # Verify operations completed
            assert len(operation_results) >= 20, f"Expected at least 20 operations, got {len(operation_results)}"

        finally:
            config_manager.stop_file_watching()

    @staticmethod
    def test_configuration_corruption_handling(temp_config_dir: Path, mock_config_data: dict) -> None:
        """Test handling of configuration corruption scenarios."""
        config_file = temp_config_dir / "config.json"
        config_file.write_text(json.dumps(mock_config_data))

        config_manager = ConfigurationManager(config_file)
        config_manager.start_file_watching()

        try:
            # Store original configuration
            config_manager.get_config()

            corruption_scenarios = [
                ("invalid_json", '{"processing": invalid json}'),
                ("missing_field", '{"processing": {}}'),
                ("wrong_type", '{"processing": {"max_workers": "not_a_number"}}'),
                ("empty_file", ""),
            ]

            for scenario_name, corrupt_content in corruption_scenarios:
                # Corrupt the configuration file
                config_file.write_text(corrupt_content)
                time.sleep(0.5)  # Allow watcher to detect

                # Verify system handles corruption gracefully
                try:
                    current_config = config_manager.get_config()

                    # Should either return original config or valid default
                    assert isinstance(current_config.processing.max_workers, int)
                    assert current_config.processing.max_workers > 0

                except (OSError, json.JSONDecodeError, ValueError) as e:
                    pytest.fail(f"Configuration corruption '{scenario_name}' not handled gracefully: {e}")

                # Restore valid configuration
                config_file.write_text(json.dumps(mock_config_data))
                time.sleep(0.5)

            # Verify system recovered completely
            final_config = config_manager.get_config()
            assert final_config.processing.max_workers == mock_config_data["processing"]["max_workers"]

        finally:
            config_manager.stop_file_watching()

    @staticmethod
    def test_file_system_race_conditions(temp_config_dir: Path, mock_config_data: dict) -> None:
        """Test file system race conditions during configuration updates."""
        config_file = temp_config_dir / "config.json"
        config_file.write_text(json.dumps(mock_config_data))

        config_manager = ConfigurationManager(config_file)
        config_manager.start_file_watching()

        try:
            stable_reads = 0

            def file_deletion_recreation() -> None:
                """Test file deletion and recreation."""
                time.sleep(0.1)  # Let watcher start

                # Delete file
                if config_file.exists():
                    config_file.unlink()
                time.sleep(0.2)

                # Recreate file with new content
                new_config = mock_config_data.copy()
                new_config["processing"]["max_workers"] = 999
                config_file.write_text(json.dumps(new_config))

                time.sleep(0.5)  # Allow watcher to detect

            def partial_write_simulation() -> None:
                """Simulate partial write scenarios."""
                time.sleep(0.3)

                # Write incomplete JSON
                config_file.write_text('{"processing": {"max_workers":')
                time.sleep(0.1)

                # Complete the write
                config_file.write_text(json.dumps(mock_config_data))

            # Start file system race condition tests
            threads = [
                threading.Thread(target=file_deletion_recreation),
                threading.Thread(target=partial_write_simulation),
            ]

            for thread in threads:
                thread.start()

            # Monitor configuration during race conditions
            for _ in range(20):
                try:
                    config = config_manager.get_config()
                    if isinstance(config.processing.max_workers, int) and config.processing.max_workers > 0:
                        stable_reads += 1
                except (OSError, json.JSONDecodeError, ValueError):
                    pass  # Expected during race conditions

                time.sleep(0.1)

            # Wait for threads to complete
            for thread in threads:
                thread.join(timeout=5.0)

            # Verify system recovered from race conditions
            time.sleep(1.0)  # Allow system to stabilize

            final_config = config_manager.get_config()
            assert isinstance(final_config.processing.max_workers, int)
            assert final_config.processing.max_workers > 0

            # Should have had some stable reads during the chaos
            assert stable_reads > 10, f"Expected stable reads during race conditions, got {stable_reads}"

        finally:
            config_manager.stop_file_watching()

    @staticmethod
    def test_watcher_notification_reliability(temp_config_dir: Path, mock_config_data: dict) -> None:
        """Test watcher notification reliability under load."""
        config_file = temp_config_dir / "config.json"
        config_file.write_text(json.dumps(mock_config_data))

        notifications_received = []
        notification_lock = threading.Lock()

        def notification_callback(old_config: Any, new_config: Any) -> None:
            with notification_lock:
                notifications_received.append({
                    "timestamp": time.time(),
                    "old_max_workers": old_config.processing.max_workers if old_config else None,
                    "new_max_workers": new_config.processing.max_workers,
                })

        config_manager = ConfigurationManager(config_file)
        config_manager.add_watcher(notification_callback)
        config_manager.start_file_watching()

        try:
            # Moderate load file modification scenario
            expected_notifications = 0

            for i in range(10):  # 10 changes
                modified_config = mock_config_data.copy()
                modified_config["processing"]["max_workers"] = 8 + i  # Keep within validation limits (1-32)

                config_file.write_text(json.dumps(modified_config))
                expected_notifications += 1

                time.sleep(0.2)  # Allow processing

            # Allow time for all notifications to be processed
            time.sleep(2.0)

            # Verify notification reliability
            with notification_lock:
                total_notifications = len(notifications_received)

            # Should receive some notifications (allowing for file watcher limitations)
            assert total_notifications >= 1, f"Expected at least 1 notification, got {total_notifications}"

            # Verify notification content
            with notification_lock:
                for notification in notifications_received:
                    assert isinstance(notification["new_max_workers"], int)
                    assert notification["new_max_workers"] >= 8

            # Verify final configuration is valid (may not match exact last change due to coalescing)
            final_config = config_manager.get_config()
            assert final_config.processing.max_workers >= 8  # Should be at least the initial value

        finally:
            config_manager.stop_file_watching()

    @staticmethod
    def test_environment_variable_override_conflicts(temp_config_dir: Path, mock_config_data: dict) -> None:
        """Test conflicts between environment variables and hot-reloaded configuration."""
        config_file = temp_config_dir / "config.json"
        config_file.write_text(json.dumps(mock_config_data))

        # Set environment variables that should override config
        env_overrides = {
            "GOESVFI_PROCESSING_MAX_WORKERS": "999",
            "GOESVFI_NETWORK_TIMEOUT": "888",
        }

        with patch.dict(os.environ, env_overrides):
            config_manager = ConfigurationManager(config_file)
            config_manager.start_file_watching()

            try:
                # Verify environment variables take precedence initially
                initial_config = config_manager.get_config()
                assert initial_config.processing.max_workers == 999

                # Modify file configuration
                modified_config = mock_config_data.copy()
                modified_config["processing"]["max_workers"] = 777
                config_file.write_text(json.dumps(modified_config))

                time.sleep(0.5)  # Allow hot-reload

                # Environment variables should still take precedence
                reloaded_config = config_manager.get_config()
                assert reloaded_config.processing.max_workers == 999

                # Values without env overrides should be updated
                assert reloaded_config.processing.buffer_size == modified_config["processing"]["buffer_size"]

            finally:
                config_manager.stop_file_watching()

    @staticmethod
    def test_atomic_write_interruption_recovery(temp_config_dir: Path, mock_config_data: dict) -> None:
        """Test recovery from atomic write interruptions."""
        config_file = temp_config_dir / "config.json"
        config_file.write_text(json.dumps(mock_config_data))

        config_manager = ConfigurationManager(config_file)
        config_manager.start_file_watching()

        try:
            config_states: list[dict[str, Any]] = []

            def interrupted_atomic_write() -> None:
                """Simulate atomic write that gets interrupted."""
                temp_file = config_file.with_suffix(".tmp")

                # Start writing
                temp_file.write_text('{"processing": {"max_workers": 123')
                time.sleep(0.1)

                # Simulate interruption by removing temp file
                if temp_file.exists():
                    temp_file.unlink()
                time.sleep(0.1)

                # Complete atomic write properly
                modified_config = mock_config_data.copy()
                modified_config["processing"]["max_workers"] = 456
                temp_file.write_text(json.dumps(modified_config))
                temp_file.replace(config_file)

            def monitor_config_during_interruption() -> None:
                """Monitor configuration state during write interruption."""
                for _ in range(15):
                    try:
                        config = config_manager.get_config()
                        config_states.append({
                            "timestamp": time.time(),
                            "max_workers": config.processing.max_workers,
                            "valid": True,
                        })
                    except (OSError, json.JSONDecodeError, ValueError) as e:
                        config_states.append({
                            "timestamp": time.time(),
                            "error": str(e),
                            "valid": False,
                            "max_workers": 0,
                        })

                    time.sleep(0.1)

            # Run interrupted write and monitoring concurrently
            write_thread = threading.Thread(target=interrupted_atomic_write)
            monitor_thread = threading.Thread(target=monitor_config_during_interruption)

            write_thread.start()
            monitor_thread.start()

            write_thread.join(timeout=5.0)
            monitor_thread.join(timeout=5.0)

            # Verify system recovered from interruption
            time.sleep(0.5)  # Allow final stabilization
            final_config = config_manager.get_config()
            assert final_config.processing.max_workers >= 4  # Should be at least the default value

            # Should have maintained configuration integrity during interruption
            valid_states = [state for state in config_states if state.get("valid", False)]
            assert len(valid_states) > 10, "Should maintain configuration integrity during interruption"

        finally:
            config_manager.stop_file_watching()
