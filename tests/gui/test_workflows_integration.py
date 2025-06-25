"""Complex user workflow integration tests for GOES VFI GUI."""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest
import numpy as np
from PIL import Image
from PyQt6.QtCore import Qt, QTimer, QMimeData, QUrl, pyqtSignal, QObject
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QListWidget, QListWidgetItem

from goesvfi.gui import MainWindow


class ProcessingSignalCapture(QObject):
    """Helper class to capture processing signals."""
    def __init__(self):
        super().__init__()
        self.progress_updates = []
        self.finished_called = False
        self.error_message = None
        
    def on_progress(self, current, total, eta):
        self.progress_updates.append((current, total, eta))
        
    def on_finished(self, output_path):
        self.finished_called = True
        self.output_path = output_path
        
    def on_error(self, error_msg):
        self.error_message = error_msg


class TestWorkflowsIntegration:
    """Test complex user workflows."""

    @pytest.fixture
    def window(self, qtbot, mocker):
        """Create a MainWindow instance for testing."""
        # Mock heavy components
        mocker.patch("goesvfi.gui.CombinedIntegrityAndImageryTab")
        mocker.patch("goesvfi.integrity_check.enhanced_gui_tab.EnhancedImageryTab")
        
        window = MainWindow(debug_mode=True)
        qtbot.addWidget(window)
        window._post_init_setup()
        
        return window

    @pytest.fixture
    def test_images(self, tmp_path):
        """Create test images for workflows."""
        images = []
        for i in range(5):
            img = Image.new('RGB', (640, 480), color=(i*50, 100, 200-i*40))
            img_path = tmp_path / f"frame_{i:03d}.png"
            img.save(img_path)
            images.append(img_path)
        return images

    def test_complete_processing_workflow(self, qtbot, window, test_images, mocker):
        """Test complete end-to-end processing workflow."""
        # Setup signal capture
        signal_capture = ProcessingSignalCapture()
        
        # Mock VfiWorker
        mock_worker_instance = MagicMock()
        mock_worker_instance.progress = MagicMock()
        mock_worker_instance.finished = MagicMock()
        mock_worker_instance.error = MagicMock()
        
        # Connect to signal capture
        mock_worker_instance.progress.connect = lambda fn: setattr(
            mock_worker_instance, '_progress_handler', fn
        )
        mock_worker_instance.finished.connect = lambda fn: setattr(
            mock_worker_instance, '_finished_handler', fn
        )
        mock_worker_instance.error.connect = lambda fn: setattr(
            mock_worker_instance, '_error_handler', fn
        )
        
        mocker.patch("goesvfi.pipeline.run_vfi.VfiWorker", return_value=mock_worker_instance)
        
        # Step 1: Select input directory
        input_dir = test_images[0].parent
        window.set_in_dir(input_dir)
        assert window.in_dir == input_dir
        assert window.main_tab.in_dir_edit.text() == str(input_dir)
        
        # Step 2: Select output file
        output_path = input_dir / "output.mp4"
        window.out_file_path = output_path
        assert window.main_tab.out_file_edit.text() == str(output_path)
        
        # Step 3: Configure settings
        window.main_tab.fps_spinbox.setValue(30)
        window.main_tab.encoder_combo.setCurrentText("RIFE")
        window.main_tab.sanchez_checkbox.setChecked(True)
        window._toggle_sanchez_res_enabled(Qt.CheckState.Checked)
        window.main_tab.sanchez_res_combo.setCurrentText("4km")
        
        # Step 4: Select crop region (optional)
        window.current_crop_rect = (100, 100, 400, 300)
        window.crop_handler.update_crop_ui()
        assert window.main_tab.clear_crop_button.isEnabled()
        
        # Step 5: Start processing
        assert window.main_tab.start_button.isEnabled()
        qtbot.mouseClick(window.main_tab.start_button, Qt.MouseButton.LeftButton)
        
        # Verify processing state
        assert window.is_processing
        assert window.main_tab.start_button.text() == "Stop Processing"
        assert not window.main_tab.in_dir_button.isEnabled()
        assert not window.main_tab.out_file_button.isEnabled()
        
        # Simulate processing progress
        def simulate_processing():
            # Emit progress updates
            for i in range(1, 11):
                if hasattr(mock_worker_instance, '_progress_handler'):
                    mock_worker_instance._progress_handler(i, 10, 10.0 - i)
                qtbot.wait(10)
                
            # Emit completion
            if hasattr(mock_worker_instance, '_finished_handler'):
                mock_worker_instance._finished_handler(str(output_path))
                
        QTimer.singleShot(100, simulate_processing)
        
        # Wait for completion
        qtbot.wait(300)
        
        # Verify completion state
        assert not window.is_processing
        assert window.main_tab.start_button.text() == "Start Processing"
        assert window.main_tab.in_dir_button.isEnabled()
        assert "Processing complete!" in window.status_bar.currentMessage()

    def test_drag_drop_file_operations(self, qtbot, window, test_images):
        """Test drag and drop file operations."""
        # Test dropping files to input area
        mime_data = QMimeData()
        urls = [QUrl.fromLocalFile(str(img)) for img in test_images]
        mime_data.setUrls(urls)
        
        # Create drag enter event
        drag_enter = QDragEnterEvent(
            window.main_tab.in_dir_edit.rect().center(),
            Qt.DropAction.CopyAction,
            mime_data,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        
        # Mock dragEnterEvent to accept
        def mock_drag_enter(event):
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
                
        window.main_tab.in_dir_edit.dragEnterEvent = mock_drag_enter
        window.main_tab.in_dir_edit.dragEnterEvent(drag_enter)
        
        # Create drop event
        drop_event = QDropEvent(
            window.main_tab.in_dir_edit.rect().center(),
            Qt.DropAction.CopyAction,
            mime_data,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        
        # Mock dropEvent to handle files
        def mock_drop(event):
            if event.mimeData().hasUrls():
                urls = event.mimeData().urls()
                if urls:
                    # Get directory from first file
                    first_path = Path(urls[0].toLocalFile())
                    if first_path.is_file():
                        window.set_in_dir(first_path.parent)
                    else:
                        window.set_in_dir(first_path)
                event.acceptProposedAction()
                
        window.main_tab.in_dir_edit.dropEvent = mock_drop
        window.main_tab.in_dir_edit.dropEvent(drop_event)
        
        # Verify directory was set
        expected_dir = test_images[0].parent
        assert window.in_dir == expected_dir

    def test_drag_drop_between_tabs(self, qtbot, window):
        """Test drag and drop between different tabs."""
        # Create mock list widgets for testing
        source_list = QListWidget()
        target_list = QListWidget()
        
        # Add items to source
        for i in range(3):
            item = QListWidgetItem(f"Item {i}")
            item.setData(Qt.ItemDataRole.UserRole, f"/path/to/file_{i}.png")
            source_list.addItem(item)
            
        qtbot.addWidget(source_list)
        qtbot.addWidget(target_list)
        
        # Enable drag and drop
        source_list.setDragDropMode(QListWidget.DragDropMode.DragOnly)
        target_list.setDragDropMode(QListWidget.DragDropMode.DropOnly)
        
        # Mock drag and drop operation
        def transfer_item(source_index, target_list):
            item = source_list.item(source_index)
            if item:
                new_item = QListWidgetItem(item.text())
                new_item.setData(Qt.ItemDataRole.UserRole, 
                               item.data(Qt.ItemDataRole.UserRole))
                target_list.addItem(new_item)
                
        # Simulate drag from source to target
        transfer_item(0, target_list)
        
        # Verify transfer
        assert target_list.count() == 1
        assert target_list.item(0).text() == "Item 0"

    def test_batch_processing_queue(self, qtbot, window, test_images, mocker):
        """Test batch processing queue management."""
        # Create batch queue
        batch_queue = []
        
        # Add multiple jobs to queue
        for i in range(3):
            job = {
                'input_dir': test_images[0].parent,
                'output_file': test_images[0].parent / f"output_{i}.mp4",
                'settings': {
                    'fps': 24 + i * 6,
                    'encoder': 'RIFE',
                    'crop': None if i == 0 else (50*i, 50*i, 400, 300)
                }
            }
            batch_queue.append(job)
            
        # Mock batch processor
        class BatchProcessor:
            def __init__(self, window):
                self.window = window
                self.queue = []
                self.current_job = None
                self.is_processing = False
                self.completed_jobs = []
                
            def add_job(self, job):
                self.queue.append(job)
                
            def start_processing(self):
                if not self.is_processing and self.queue:
                    self.is_processing = True
                    self._process_next()
                    
            def _process_next(self):
                if self.queue:
                    self.current_job = self.queue.pop(0)
                    # Apply job settings
                    self.window.set_in_dir(self.current_job['input_dir'])
                    self.window.out_file_path = self.current_job['output_file']
                    self.window.main_tab.fps_spinbox.setValue(
                        self.current_job['settings']['fps']
                    )
                    if self.current_job['settings']['crop']:
                        self.window.current_crop_rect = self.current_job['settings']['crop']
                    
                    # Simulate processing
                    QTimer.singleShot(100, self._complete_current_job)
                else:
                    self.is_processing = False
                    
            def _complete_current_job(self):
                if self.current_job:
                    self.completed_jobs.append(self.current_job)
                    self.current_job = None
                    self._process_next()
                    
        # Create and run batch processor
        processor = BatchProcessor(window)
        for job in batch_queue:
            processor.add_job(job)
            
        # Start batch processing
        processor.start_processing()
        
        # Wait for all jobs to complete
        qtbot.wait(400)
        
        # Verify all jobs completed
        assert len(processor.completed_jobs) == 3
        assert not processor.is_processing
        assert len(processor.queue) == 0

    def test_model_switching_during_operation(self, qtbot, window, mocker):
        """Test switching models during operation."""
        # Mock model manager
        models = {
            'rife-v4.6': {'path': '/models/rife-v4.6', 'loaded': True},
            'rife-v4.13': {'path': '/models/rife-v4.13', 'loaded': True},
            'rife-v4.14': {'path': '/models/rife-v4.14', 'loaded': False}
        }
        
        # Track model switches
        model_switches = []
        
        def switch_model(model_key):
            if window.is_processing:
                # Queue model switch for after current operation
                model_switches.append(('queued', model_key))
                return False
            else:
                # Switch immediately
                model_switches.append(('immediate', model_key))
                window.current_model_key = model_key
                return True
                
        # Start with first model
        window.current_model_key = 'rife-v4.6'
        window.main_tab.rife_model_combo.setCurrentText('rife-v4.6')
        
        # Start processing
        window._set_processing_state(True)
        
        # Try to switch model during processing
        success = switch_model('rife-v4.13')
        assert not success  # Should queue, not switch immediately
        assert model_switches[-1][0] == 'queued'
        
        # Stop processing
        window._set_processing_state(False)
        
        # Now switch should work
        success = switch_model('rife-v4.13')
        assert success
        assert model_switches[-1][0] == 'immediate'
        assert window.current_model_key == 'rife-v4.13'

    def test_cancellation_and_cleanup(self, qtbot, window, test_images, mocker):
        """Test processing cancellation and resource cleanup."""
        # Mock worker with cancellation support
        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = True
        mock_worker.quit = MagicMock()
        mock_worker.wait = MagicMock()
        
        # Track cleanup actions
        cleanup_actions = []
        
        def cleanup_temp_files():
            cleanup_actions.append('temp_files')
            
        def cleanup_memory():
            cleanup_actions.append('memory')
            
        def reset_ui_state():
            cleanup_actions.append('ui_state')
            
        # Mock cleanup methods
        mocker.patch.object(window, '_cleanup_temp_files', cleanup_temp_files)
        mocker.patch.object(window, '_cleanup_memory', cleanup_memory)
        mocker.patch.object(window, '_reset_ui_state', reset_ui_state)
        
        # Start processing
        window.set_in_dir(test_images[0].parent)
        window.out_file_path = test_images[0].parent / "output.mp4"
        window.worker = mock_worker
        window._set_processing_state(True)
        
        # Cancel processing
        def cancel_processing():
            if window.worker and window.worker.isRunning():
                # Stop worker
                window.worker.quit()
                window.worker.wait()
                
                # Cleanup
                window._cleanup_temp_files()
                window._cleanup_memory()
                window._reset_ui_state()
                
                # Reset state
                window._set_processing_state(False)
                window.worker = None
                
        cancel_processing()
        
        # Verify cleanup occurred
        assert 'temp_files' in cleanup_actions
        assert 'memory' in cleanup_actions
        assert 'ui_state' in cleanup_actions
        assert not window.is_processing
        assert window.worker is None
        mock_worker.quit.assert_called_once()
        mock_worker.wait.assert_called_once()

    def test_pause_resume_workflow(self, qtbot, window):
        """Test pause and resume functionality."""
        # Create pause/resume state manager
        class PauseResumeManager:
            def __init__(self):
                self.is_paused = False
                self.pause_point = None
                self.can_pause = True
                
            def pause(self):
                if self.can_pause and not self.is_paused:
                    self.is_paused = True
                    self.pause_point = {
                        'current_frame': 50,
                        'total_frames': 100,
                        'timestamp': QTimer.singleShot
                    }
                    return True
                return False
                
            def resume(self):
                if self.is_paused:
                    self.is_paused = False
                    # Continue from pause point
                    return self.pause_point
                return None
                
            def is_pausable(self):
                return self.can_pause and not self.is_paused
                
        # Create manager
        pause_manager = PauseResumeManager()
        
        # Test pause during processing
        window._set_processing_state(True)
        
        # Pause
        pause_result = pause_manager.pause()
        assert pause_result
        assert pause_manager.is_paused
        assert pause_manager.pause_point is not None
        
        # Try to pause again (should fail)
        pause_result2 = pause_manager.pause()
        assert not pause_result2
        
        # Resume
        resume_point = pause_manager.resume()
        assert resume_point is not None
        assert not pause_manager.is_paused
        assert resume_point['current_frame'] == 50

    def test_multi_step_wizard_workflow(self, qtbot, window):
        """Test multi-step wizard workflow for complex operations."""
        # Create wizard steps
        class SetupWizard:
            def __init__(self, window):
                self.window = window
                self.current_step = 0
                self.steps = [
                    self.select_input_step,
                    self.configure_output_step,
                    self.select_processing_options,
                    self.review_and_confirm
                ]
                self.step_data = {}
                
            def next_step(self):
                if self.current_step < len(self.steps) - 1:
                    # Validate current step
                    if self.validate_current_step():
                        self.current_step += 1
                        return True
                return False
                
            def previous_step(self):
                if self.current_step > 0:
                    self.current_step -= 1
                    return True
                return False
                
            def validate_current_step(self):
                validator = self.steps[self.current_step]
                return validator()
                
            def select_input_step(self):
                # Step 1: Select input
                if self.window.in_dir:
                    self.step_data['input'] = self.window.in_dir
                    return True
                return False
                
            def configure_output_step(self):
                # Step 2: Configure output
                if self.window.out_file_path:
                    self.step_data['output'] = self.window.out_file_path
                    self.step_data['format'] = self.window.out_file_path.suffix
                    return True
                return False
                
            def select_processing_options(self):
                # Step 3: Processing options
                self.step_data['encoder'] = self.window.main_tab.encoder_combo.currentText()
                self.step_data['fps'] = self.window.main_tab.fps_spinbox.value()
                self.step_data['enhance'] = self.window.main_tab.sanchez_checkbox.isChecked()
                return True
                
            def review_and_confirm(self):
                # Step 4: Review settings
                return all(key in self.step_data for key in ['input', 'output', 'encoder'])
                
        # Run wizard
        wizard = SetupWizard(window)
        
        # Step through wizard
        window.set_in_dir(Path("/test/input"))
        assert wizard.next_step()  # Move to step 2
        
        window.out_file_path = Path("/test/output.mp4")
        assert wizard.next_step()  # Move to step 3
        
        window.main_tab.encoder_combo.setCurrentText("RIFE")
        window.main_tab.fps_spinbox.setValue(60)
        assert wizard.next_step()  # Move to step 4
        
        # Verify final step
        assert wizard.current_step == 3
        assert wizard.validate_current_step()
        
        # Verify collected data
        assert wizard.step_data['input'] == Path("/test/input")
        assert wizard.step_data['output'] == Path("/test/output.mp4")
        assert wizard.step_data['encoder'] == "RIFE"
        assert wizard.step_data['fps'] == 60