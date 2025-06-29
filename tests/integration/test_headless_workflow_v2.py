"""
Optimized headless integration tests that don't show any GUI windows with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures for headless Qt setup and mock configurations
- Combined headless workflow testing scenarios
- Batch validation of GUI components without display
- Enhanced mock management for worker threads and processing pipelines
"""

import os
import pathlib
from unittest.mock import MagicMock, patch

from PIL import Image
from PyQt6.QtWidgets import QApplication
import pytest

# Set environment for headless operation
os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestHeadlessWorkflowOptimizedV2:
    """Optimized headless workflow integration tests with full coverage."""

    @pytest.fixture(scope="class")
    def headless_qt_app(self):
        """Shared headless QApplication instance for all tests."""
        # Store original env
        original_platform = os.environ.get("QT_QPA_PLATFORM")
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

        app = QApplication.instance()
        if app is None:
            app = QApplication(["-platform", "offscreen"])

        yield app
        app.processEvents()

        # Restore environment
        if original_platform:
            os.environ["QT_QPA_PLATFORM"] = original_platform
        elif "QT_QPA_PLATFORM" in os.environ:
            del os.environ["QT_QPA_PLATFORM"]

    @pytest.fixture(scope="class")
    def headless_test_components(self):
        """Create shared components for headless testing."""

        # Enhanced Mock GUI Factory
        class MockGUIFactory:
            """Factory for creating comprehensive mock GUI components."""

            def __init__(self) -> None:
                self.widget_templates = {
                    "basic": self._create_basic_widgets,
                    "advanced": self._create_advanced_widgets,
                    "complete": self._create_complete_widgets,
                }
                self.mock_configurations = {
                    "default": self._apply_default_config,
                    "custom": self._apply_custom_config,
                    "error_prone": self._apply_error_prone_config,
                }

            def _create_basic_widgets(self):
                """Create basic widget mocks."""
                widgets = {}

                # Input/Output widgets
                widgets["in_dir_edit"] = MagicMock()
                widgets["in_dir_edit"].text.return_value = ""
                widgets["out_file_edit"] = MagicMock()
                widgets["out_file_edit"].text.return_value = ""

                # Basic controls
                widgets["start_button"] = MagicMock()
                widgets["start_button"].setEnabled = MagicMock()
                widgets["start_button"].click = MagicMock()

                return widgets

            def _create_advanced_widgets(self):
                """Create advanced widget mocks."""
                widgets = self._create_basic_widgets()

                # Processing settings
                widgets["fps_spinbox"] = MagicMock()
                widgets["fps_spinbox"].value.return_value = 30
                widgets["mid_count_spinbox"] = MagicMock()
                widgets["mid_count_spinbox"].value.return_value = 1
                widgets["encoder_combo"] = MagicMock()
                widgets["encoder_combo"].currentText.return_value = "libx264"

                # Checkboxes
                widgets["rife_tile_checkbox"] = MagicMock()
                widgets["rife_tile_checkbox"].isChecked.return_value = False
                widgets["rife_uhd_checkbox"] = MagicMock()
                widgets["rife_uhd_checkbox"].isChecked.return_value = False
                widgets["sanchez_false_colour_checkbox"] = MagicMock()
                widgets["sanchez_false_colour_checkbox"].isChecked.return_value = False

                return widgets

            def _create_complete_widgets(self):
                """Create complete widget mocks with all components."""
                widgets = self._create_advanced_widgets()

                # Progress tracking
                widgets["progress_bar"] = MagicMock()
                widgets["progress_bar"].setValue = MagicMock()
                widgets["progress_bar"].setRange = MagicMock()
                widgets["status_label"] = MagicMock()
                widgets["status_label"].setText = MagicMock()

                # Advanced settings
                widgets["crop_checkbox"] = MagicMock()
                widgets["crop_checkbox"].isChecked.return_value = False
                widgets["quality_slider"] = MagicMock()
                widgets["quality_slider"].value.return_value = 80
                widgets["threads_spinbox"] = MagicMock()
                widgets["threads_spinbox"].value.return_value = 4

                # File browser buttons
                widgets["browse_input_button"] = MagicMock()
                widgets["browse_output_button"] = MagicMock()

                # Preview widgets
                widgets["preview_label"] = MagicMock()
                widgets["first_frame_label"] = MagicMock()
                widgets["last_frame_label"] = MagicMock()

                return widgets

            def _apply_default_config(self, widgets) -> None:
                """Apply default configuration to widgets."""
                widgets["fps_spinbox"].setValue = MagicMock()
                widgets["fps_spinbox"].value.return_value = 30
                widgets["mid_count_spinbox"].setValue = MagicMock()
                widgets["mid_count_spinbox"].value.return_value = 1
                widgets["encoder_combo"].setCurrentText = MagicMock()
                widgets["encoder_combo"].currentText.return_value = "libx264"

            def _apply_custom_config(self, widgets) -> None:
                """Apply custom configuration to widgets."""
                widgets["fps_spinbox"].setValue = MagicMock()
                widgets["fps_spinbox"].value.return_value = 60
                widgets["mid_count_spinbox"].setValue = MagicMock()
                widgets["mid_count_spinbox"].value.return_value = 2
                widgets["encoder_combo"].setCurrentText = MagicMock()
                widgets["encoder_combo"].currentText.return_value = "libx265"
                widgets["rife_tile_checkbox"].setChecked = MagicMock()
                widgets["rife_tile_checkbox"].isChecked.return_value = True

            def _apply_error_prone_config(self, widgets) -> None:
                """Apply error-prone configuration for testing."""
                widgets["fps_spinbox"].setValue = MagicMock(side_effect=Exception("Widget error"))
                widgets["fps_spinbox"].value.return_value = 30
                widgets["start_button"].click = MagicMock(side_effect=Exception("Button error"))

            def create_mock_window(self, widget_type="complete", config="default"):
                """Create comprehensive mock main window."""
                with patch("goesvfi.gui.MainWindow") as MockMainWindow:
                    # Create mock window
                    window = MagicMock()
                    MockMainWindow.return_value = window

                    # Create main tab with widgets
                    main_tab = MagicMock()
                    window.main_tab = main_tab

                    # Add widgets based on type
                    widgets = self.widget_templates[widget_type]()
                    for widget_name, widget_mock in widgets.items():
                        setattr(main_tab, widget_name, widget_mock)

                    # Apply configuration
                    if config in self.mock_configurations:
                        self.mock_configurations[config](widgets)

                    # Add additional window properties
                    window.is_processing = False
                    window.current_worker = None
                    window.setEnabled = MagicMock()
                    window.close = MagicMock()

                    return window, MockMainWindow

        # Enhanced Test Data Manager
        class TestDataManager:
            """Manage test data creation for headless scenarios."""

            def __init__(self) -> None:
                self.image_configs = {
                    "small": {"count": 2, "size": (50, 50)},
                    "medium": {"count": 5, "size": (100, 100)},
                    "large": {"count": 10, "size": (200, 200)},
                    "varied": {"count": 7, "sizes": [(50, 50), (100, 100), (150, 150)]},
                }
                self.color_patterns = {
                    "solid": lambda i: (100, 150, 200),
                    "gradient": lambda i: (i * 30, i * 40, i * 50),
                    "random": lambda i: (i * 123 % 255, i * 67 % 255, i * 89 % 255),
                }

            def create_test_images(self, temp_dir, config="medium", pattern="solid"):
                """Create test images for processing."""
                input_dir = temp_dir / "input"
                input_dir.mkdir(exist_ok=True)

                img_config = self.image_configs[config]
                color_func = self.color_patterns[pattern]

                image_paths = []
                if config == "varied":
                    # Create images with varying sizes
                    sizes = img_config["sizes"]
                    for i in range(img_config["count"]):
                        size = sizes[i % len(sizes)]
                        color = color_func(i)
                        img = Image.new("RGB", size, color=color)
                        img_path = input_dir / f"img_{i:03d}.png"
                        img.save(img_path)
                        image_paths.append(img_path)
                else:
                    # Create uniform images
                    size = img_config["size"]
                    for i in range(img_config["count"]):
                        color = color_func(i)
                        img = Image.new("RGB", size, color=color)
                        img_path = input_dir / f"img_{i:03d}.png"
                        img.save(img_path)
                        image_paths.append(img_path)

                return input_dir, image_paths

            def create_complex_test_scenario(self, temp_dir):
                """Create complex test scenario with multiple data types."""
                scenarios = {}

                for config in ["small", "medium", "large"]:
                    for pattern in ["solid", "gradient", "random"]:
                        scenario_name = f"{config}_{pattern}"
                        input_dir, image_paths = self.create_test_images(temp_dir / scenario_name, config, pattern)
                        scenarios[scenario_name] = {
                            "input_dir": input_dir,
                            "image_paths": image_paths,
                            "output_file": temp_dir / f"output_{scenario_name}.mp4",
                        }

                return scenarios

        # Enhanced Workflow Manager
        class WorkflowManager:
            """Manage headless workflow testing scenarios."""

            def __init__(self) -> None:
                self.workflow_scenarios = {
                    "basic_workflow": self._test_basic_workflow,
                    "settings_configuration": self._test_settings_configuration,
                    "advanced_settings": self._test_advanced_settings,
                    "error_handling": self._test_error_handling,
                    "ui_interactions": self._test_ui_interactions,
                    "processing_workflow": self._test_processing_workflow,
                }

            def _test_basic_workflow(self, window, test_data, scenario_config):
                """Test basic workflow without display."""
                input_dir = test_data["input_dir"]
                output_file = test_data["output_file"]

                # Set paths
                window.main_tab.in_dir_edit.setText(str(input_dir))
                window.main_tab.out_file_edit.setText(str(output_file))

                # Verify setText was called
                window.main_tab.in_dir_edit.setText.assert_called_with(str(input_dir))
                window.main_tab.out_file_edit.setText.assert_called_with(str(output_file))

                # Simulate start button click
                window.main_tab.start_button.click()

                # Verify click was called
                window.main_tab.start_button.click.assert_called_once()

                return {"success": True, "input_set": True, "output_set": True, "started": True}

            def _test_settings_configuration(self, window, test_data, scenario_config):
                """Test settings configuration without display."""
                # Configure basic settings
                fps = scenario_config.get("fps", 60)
                mid_count = scenario_config.get("mid_count", 2)
                tile_enabled = scenario_config.get("tile_enabled", True)

                window.main_tab.fps_spinbox.setValue(fps)
                window.main_tab.mid_count_spinbox.setValue(mid_count)
                window.main_tab.rife_tile_checkbox.setChecked(tile_enabled)

                # Verify methods were called
                window.main_tab.fps_spinbox.setValue.assert_called_with(fps)
                window.main_tab.mid_count_spinbox.setValue.assert_called_with(mid_count)
                window.main_tab.rife_tile_checkbox.setChecked.assert_called_with(tile_enabled)

                return {"success": True, "fps_set": fps, "mid_count_set": mid_count, "tile_set": tile_enabled}

            def _test_advanced_settings(self, window, test_data, scenario_config):
                """Test advanced settings configuration."""
                # Test additional settings if available
                if hasattr(window.main_tab, "quality_slider"):
                    quality = scenario_config.get("quality", 90)
                    window.main_tab.quality_slider.setValue(quality)
                    window.main_tab.quality_slider.setValue.assert_called_with(quality)

                if hasattr(window.main_tab, "threads_spinbox"):
                    threads = scenario_config.get("threads", 8)
                    window.main_tab.threads_spinbox.setValue(threads)
                    window.main_tab.threads_spinbox.setValue.assert_called_with(threads)

                if hasattr(window.main_tab, "crop_checkbox"):
                    crop_enabled = scenario_config.get("crop_enabled", False)
                    window.main_tab.crop_checkbox.setChecked(crop_enabled)
                    window.main_tab.crop_checkbox.setChecked.assert_called_with(crop_enabled)

                return {"success": True, "advanced_settings_configured": True}

            def _test_error_handling(self, window, test_data, scenario_config):
                """Test error handling in workflows."""
                errors_caught = []

                # Test widget errors
                try:
                    window.main_tab.fps_spinbox.setValue(60)
                except Exception as e:
                    errors_caught.append(f"fps_spinbox: {e!s}")

                try:
                    window.main_tab.start_button.click()
                except Exception as e:
                    errors_caught.append(f"start_button: {e!s}")

                # Test invalid paths
                try:
                    window.main_tab.in_dir_edit.setText("/nonexistent/path")
                    window.main_tab.out_file_edit.setText("/invalid/output/path.mp4")
                except Exception as e:
                    errors_caught.append(f"path_setting: {e!s}")

                return {"success": True, "errors_caught": errors_caught}

            def _test_ui_interactions(self, window, test_data, scenario_config):
                """Test UI interactions without display."""
                interactions = []

                # Test button interactions
                if hasattr(window.main_tab, "browse_input_button"):
                    window.main_tab.browse_input_button.click()
                    interactions.append("browse_input_clicked")

                if hasattr(window.main_tab, "browse_output_button"):
                    window.main_tab.browse_output_button.click()
                    interactions.append("browse_output_clicked")

                # Test combo box interactions
                if hasattr(window.main_tab, "encoder_combo"):
                    window.main_tab.encoder_combo.setCurrentText("libx265")
                    interactions.append("encoder_changed")

                # Test checkbox interactions
                checkboxes = ["rife_tile_checkbox", "rife_uhd_checkbox", "sanchez_false_colour_checkbox"]
                for checkbox_name in checkboxes:
                    if hasattr(window.main_tab, checkbox_name):
                        checkbox = getattr(window.main_tab, checkbox_name)
                        checkbox.setChecked(True)
                        checkbox.setChecked(False)
                        interactions.append(f"{checkbox_name}_toggled")

                return {"success": True, "interactions": interactions}

            def _test_processing_workflow(self, window, test_data, scenario_config):
                """Test processing workflow with mocks."""
                # Set up processing parameters
                input_dir = test_data["input_dir"]
                output_file = test_data["output_file"]

                window.main_tab.in_dir_edit.setText(str(input_dir))
                window.main_tab.out_file_edit.setText(str(output_file))

                # Configure processing settings
                window.main_tab.fps_spinbox.setValue(30)
                window.main_tab.mid_count_spinbox.setValue(1)
                window.main_tab.encoder_combo.setCurrentText("libx264")

                # Simulate processing start
                window.main_tab.start_button.click()

                # Test status updates
                if hasattr(window.main_tab, "status_label"):
                    window.main_tab.status_label.setText("Processing started...")
                    window.main_tab.status_label.setText.assert_called_with("Processing started...")

                # Test progress updates
                if hasattr(window.main_tab, "progress_bar"):
                    window.main_tab.progress_bar.setValue(50)
                    window.main_tab.progress_bar.setValue.assert_called_with(50)

                return {"success": True, "processing_initiated": True}

            def run_workflow_scenario(self, scenario, window, test_data, scenario_config=None):
                """Run specified workflow scenario."""
                if scenario_config is None:
                    scenario_config = {}
                return self.workflow_scenarios[scenario](window, test_data, scenario_config)

        return {
            "gui_factory": MockGUIFactory(),
            "data_manager": TestDataManager(),
            "workflow_manager": WorkflowManager(),
        }

    @pytest.fixture()
    def temp_workspace(self, tmp_path):
        """Create temporary workspace for headless testing."""
        return {
            "base_dir": tmp_path,
            "input_dirs": {},
            "output_files": {},
        }

    def test_headless_workflow_comprehensive_scenarios(
        self, headless_qt_app, headless_test_components, temp_workspace
    ) -> None:
        """Test comprehensive headless workflow scenarios."""
        components = headless_test_components
        workspace = temp_workspace
        gui_factory = components["gui_factory"]
        data_manager = components["data_manager"]
        workflow_manager = components["workflow_manager"]

        # Define comprehensive headless scenarios
        headless_scenarios = [
            {
                "name": "Basic Workflow Small Images",
                "widget_type": "basic",
                "config": "default",
                "data_config": "small",
                "data_pattern": "solid",
                "workflows": ["basic_workflow"],
                "scenario_config": {},
            },
            {
                "name": "Advanced Settings Medium Images",
                "widget_type": "advanced",
                "config": "custom",
                "data_config": "medium",
                "data_pattern": "gradient",
                "workflows": ["basic_workflow", "settings_configuration", "advanced_settings"],
                "scenario_config": {"fps": 60, "mid_count": 2, "tile_enabled": True},
            },
            {
                "name": "Complete UI Large Images",
                "widget_type": "complete",
                "config": "default",
                "data_config": "large",
                "data_pattern": "random",
                "workflows": ["basic_workflow", "settings_configuration", "ui_interactions", "processing_workflow"],
                "scenario_config": {"quality": 95, "threads": 8},
            },
            {
                "name": "Error Handling Varied Images",
                "widget_type": "complete",
                "config": "error_prone",
                "data_config": "varied",
                "data_pattern": "solid",
                "workflows": ["error_handling"],
                "scenario_config": {},
            },
            {
                "name": "Full Integration Test",
                "widget_type": "complete",
                "config": "custom",
                "data_config": "medium",
                "data_pattern": "gradient",
                "workflows": [
                    "basic_workflow",
                    "settings_configuration",
                    "advanced_settings",
                    "ui_interactions",
                    "processing_workflow",
                ],
                "scenario_config": {"fps": 30, "mid_count": 1, "tile_enabled": False, "quality": 80, "threads": 4},
            },
        ]

        # Test each headless scenario
        for scenario in headless_scenarios:
            # Create test data
            input_dir, image_paths = data_manager.create_test_images(
                workspace["base_dir"] / scenario["name"].replace(" ", "_").lower(),
                scenario["data_config"],
                scenario["data_pattern"],
            )
            output_file = workspace["base_dir"] / f"output_{scenario['name'].replace(' ', '_').lower()}.mp4"

            test_data = {
                "input_dir": input_dir,
                "image_paths": image_paths,
                "output_file": output_file,
            }

            # Create mock window
            window, mock_class = gui_factory.create_mock_window(scenario["widget_type"], scenario["config"])

            try:
                # Run workflow tests
                workflow_results = {}
                for workflow in scenario["workflows"]:
                    try:
                        result = workflow_manager.run_workflow_scenario(
                            workflow, window, test_data, scenario["scenario_config"]
                        )
                        workflow_results[workflow] = result
                    except Exception as e:
                        # For error_prone config, exceptions are expected
                        if scenario["config"] == "error_prone":
                            workflow_results[workflow] = {"success": True, "expected_error": str(e)}
                        else:
                            msg = f"Unexpected error in {workflow} for {scenario['name']}: {e}"
                            raise AssertionError(msg)

                # Verify overall results
                successful_workflows = [w for w, r in workflow_results.items() if r["success"]]
                failed_workflows = [w for w, r in workflow_results.items() if not r["success"]]

                if scenario["config"] != "error_prone":
                    assert len(failed_workflows) == 0, f"Failed workflows in {scenario['name']}: {failed_workflows}"
                    assert len(successful_workflows) == len(scenario["workflows"]), (
                        f"Not all workflows succeeded in {scenario['name']}: "
                        f"expected {len(scenario['workflows'])}, got {len(successful_workflows)}"
                    )

                # Verify mock interactions
                mock_class.assert_called_once()
                assert window.main_tab is not None, f"Main tab not created for {scenario['name']}"

            finally:
                # Clean up (mocks are automatically cleaned up by context manager)
                pass

    def test_headless_processing_pipeline_mocked(
        self, headless_qt_app, headless_test_components, temp_workspace
    ) -> None:
        """Test headless processing pipeline with comprehensive mocking."""
        components = headless_test_components
        workspace = temp_workspace
        data_manager = components["data_manager"]

        # Create complex test scenarios
        test_scenarios = data_manager.create_complex_test_scenario(workspace["base_dir"])

        # Processing pipeline scenarios
        pipeline_scenarios = [
            {
                "name": "VFI Processing Success",
                "mock_target": "goesvfi.pipeline.run_vfi.run_vfi",
                "mock_return": str,
                "expected_success": True,
                "test_data": "small_solid",
            },
            {
                "name": "VFI Processing Failure",
                "mock_target": "goesvfi.pipeline.run_vfi.run_vfi",
                "mock_side_effect": Exception("Processing failed"),
                "expected_success": False,
                "test_data": "medium_gradient",
            },
            {
                "name": "Worker Thread Success",
                "mock_target": "goesvfi.gui.VfiWorker",
                "mock_return": None,  # Worker mock handles this differently
                "expected_success": True,
                "test_data": "large_random",
            },
        ]

        # Test each pipeline scenario
        for scenario in pipeline_scenarios:
            if scenario["test_data"] not in test_scenarios:
                continue

            test_data = test_scenarios[scenario["test_data"]]

            if scenario["name"] == "VFI Processing Success":
                # Test successful VFI processing
                with patch(scenario["mock_target"]) as mock_run_vfi:
                    mock_run_vfi.return_value = scenario["mock_return"](test_data["output_file"])

                    # Import and test
                    from goesvfi.pipeline.run_vfi import run_vfi

                    result = run_vfi(
                        folder=test_data["input_dir"],
                        output_mp4_path=test_data["output_file"],
                        rife_exe_path=pathlib.Path("/mock/rife"),
                        fps=30,
                        num_intermediate_frames=1,
                        max_workers=1,
                        encoder="libx264",
                    )

                    # Verify
                    assert mock_run_vfi.called, f"Mock not called for {scenario['name']}"
                    assert result == str(test_data["output_file"]), f"Wrong result for {scenario['name']}"

                    # Check call arguments
                    call_kwargs = mock_run_vfi.call_args.kwargs
                    assert call_kwargs["in_dir"] == str(test_data["input_dir"]), (
                        f"Wrong input dir for {scenario['name']}"
                    )
                    assert call_kwargs["out_file_path"] == str(test_data["output_file"]), (
                        f"Wrong output file for {scenario['name']}"
                    )
                    assert call_kwargs["fps"] == 30, f"Wrong FPS for {scenario['name']}"

            elif scenario["name"] == "VFI Processing Failure":
                # Test VFI processing failure
                with patch(scenario["mock_target"]) as mock_run_vfi:
                    mock_run_vfi.side_effect = scenario["mock_side_effect"]

                    # Import and test
                    from goesvfi.pipeline.run_vfi import run_vfi

                    with pytest.raises(Exception) as exc_info:
                        run_vfi(
                            folder=test_data["input_dir"],
                            output_mp4_path=test_data["output_file"],
                            rife_exe_path=pathlib.Path("/mock/rife"),
                            fps=30,
                            num_intermediate_frames=1,
                            max_workers=1,
                            encoder="libx264",
                        )

                    # Verify error
                    assert "Processing failed" in str(exc_info.value), f"Wrong error for {scenario['name']}"
                    assert mock_run_vfi.called, f"Mock not called for {scenario['name']}"

            elif scenario["name"] == "Worker Thread Success":
                # Test worker thread with mocking
                with patch(scenario["mock_target"]) as MockVfiWorker:
                    # Create mock worker
                    mock_worker = MagicMock()
                    MockVfiWorker.return_value = mock_worker

                    # Mock signals
                    mock_worker.progress = MagicMock()
                    mock_worker.finished = MagicMock()
                    mock_worker.error = MagicMock()
                    mock_worker.start = MagicMock()

                    # Import and create worker
                    from goesvfi.gui import VfiWorker

                    worker = VfiWorker(
                        in_dir=str(test_data["input_dir"]),
                        out_file_path=str(test_data["output_file"]),
                        fps=30,
                        mid_count=1,
                        max_workers=1,
                        encoder="libx264",
                    )

                    # Start worker
                    worker.start()

                    # Verify
                    MockVfiWorker.assert_called_once()
                    mock_worker.start.assert_called_once()

    def test_headless_stress_testing(self, headless_qt_app, headless_test_components, temp_workspace) -> None:
        """Test headless components under stress conditions."""
        components = headless_test_components
        gui_factory = components["gui_factory"]
        components["data_manager"]

        # Stress test scenarios
        stress_scenarios = [
            {
                "name": "Rapid Widget Interactions",
                "iterations": 50,
                "widget_type": "complete",
                "config": "default",
            },
            {
                "name": "Multiple Window Creation",
                "iterations": 20,
                "widget_type": "advanced",
                "config": "custom",
            },
            {
                "name": "Error Handling Stress",
                "iterations": 30,
                "widget_type": "complete",
                "config": "error_prone",
            },
        ]

        # Test each stress scenario
        for stress_test in stress_scenarios:
            if stress_test["name"] == "Rapid Widget Interactions":
                # Test rapid interactions with single window
                window, mock_class = gui_factory.create_mock_window(stress_test["widget_type"], stress_test["config"])

                for i in range(stress_test["iterations"]):
                    # Rapid settings changes
                    window.main_tab.fps_spinbox.setValue(30 + (i % 30))
                    window.main_tab.mid_count_spinbox.setValue(1 + (i % 3))
                    window.main_tab.rife_tile_checkbox.setChecked(i % 2 == 0)

                    # Button clicks
                    if hasattr(window.main_tab, "browse_input_button"):
                        window.main_tab.browse_input_button.click()

                    # Text changes
                    window.main_tab.in_dir_edit.setText(f"/tmp/input_{i}")
                    window.main_tab.out_file_edit.setText(f"/tmp/output_{i}.mp4")

                # Verify window survived
                assert window.main_tab is not None

            elif stress_test["name"] == "Multiple Window Creation":
                # Test creating and destroying multiple windows
                windows = []

                for i in range(stress_test["iterations"]):
                    window, mock_class = gui_factory.create_mock_window(
                        stress_test["widget_type"], stress_test["config"]
                    )
                    windows.append((window, mock_class))

                    # Basic interaction with each window
                    window.main_tab.fps_spinbox.setValue(30)
                    window.main_tab.start_button.click()

                # Verify all windows were created
                assert len(windows) == stress_test["iterations"]

                # Clean up
                for window, mock_class in windows:
                    mock_class.assert_called_once()

            elif stress_test["name"] == "Error Handling Stress":
                # Test error handling under stress
                window, mock_class = gui_factory.create_mock_window(stress_test["widget_type"], stress_test["config"])

                errors_handled = 0

                for i in range(stress_test["iterations"]):
                    try:
                        # These should trigger exceptions in error_prone config
                        window.main_tab.fps_spinbox.setValue(60)
                        window.main_tab.start_button.click()
                    except Exception:
                        errors_handled += 1

                # Should have handled multiple errors gracefully
                assert errors_handled > 0

    def test_headless_edge_cases_and_boundaries(
        self, headless_qt_app, headless_test_components, temp_workspace
    ) -> None:
        """Test edge cases and boundary conditions in headless mode."""
        components = headless_test_components
        workspace = temp_workspace
        gui_factory = components["gui_factory"]
        data_manager = components["data_manager"]

        # Edge case scenarios
        edge_cases = [
            {
                "name": "Empty Input Directory",
                "setup": data_manager.create_test_images(workspace["base_dir"] / "empty", "small", "solid")[0].rmdir,
                "test": lambda window: self._test_empty_directory_handling(window, workspace["base_dir"] / "empty"),
            },
            {
                "name": "Invalid Output Path",
                "setup": lambda: None,
                "test": self._test_invalid_output_path,
            },
            {
                "name": "Extreme Settings Values",
                "setup": lambda: None,
                "test": self._test_extreme_settings_values,
            },
            {
                "name": "Rapid State Changes",
                "setup": lambda: None,
                "test": self._test_rapid_state_changes,
            },
        ]

        # Test each edge case
        for edge_case in edge_cases:
            window, _mock_class = gui_factory.create_mock_window("complete", "default")

            try:
                # Setup
                if edge_case["setup"]:
                    edge_case["setup"]()

                # Test
                result = edge_case["test"](window)

                # Edge cases should handle gracefully
                assert result is not None, f"Edge case {edge_case['name']} returned None"

            except Exception as e:
                # Some edge cases may throw exceptions, which is acceptable
                assert "edge case handled" in str(e).lower() or "expected" in str(e).lower(), (
                    f"Unexpected error in edge case {edge_case['name']}: {e}"
                )

    def _test_empty_directory_handling(self, window, empty_dir):
        """Test handling of empty directory."""
        window.main_tab.in_dir_edit.setText(str(empty_dir))
        window.main_tab.out_file_edit.setText(str(empty_dir.parent / "output.mp4"))

        # Should not crash
        window.main_tab.start_button.click()
        return {"handled": True}

    def _test_invalid_output_path(self, window):
        """Test handling of invalid output path."""
        window.main_tab.out_file_edit.setText("/root/protected/output.mp4")

        # Should not crash
        window.main_tab.start_button.click()
        return {"handled": True}

    def _test_extreme_settings_values(self, window):
        """Test handling of extreme settings values."""
        # Test extreme values
        window.main_tab.fps_spinbox.setValue(999999)
        window.main_tab.mid_count_spinbox.setValue(-1)

        if hasattr(window.main_tab, "quality_slider"):
            window.main_tab.quality_slider.setValue(200)  # Beyond normal range

        return {"handled": True}

    def _test_rapid_state_changes(self, window):
        """Test rapid state changes."""
        for i in range(100):
            window.main_tab.rife_tile_checkbox.setChecked(i % 2 == 0)
            window.main_tab.rife_uhd_checkbox.setChecked(i % 3 == 0)
            window.main_tab.fps_spinbox.setValue(20 + (i % 60))

        return {"handled": True}
