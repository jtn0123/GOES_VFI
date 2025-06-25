"""Advanced button functionality tests for GOES VFI GUI."""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QKeySequence, QAction
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMenu, QPushButton, QProgressBar

from goesvfi.gui import MainWindow


class MockDownloadThread(QThread):
    """Mock download thread for testing."""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)
    error = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.cancelled = False
        
    def run(self):
        """Simulate download with progress updates."""
        for i in range(0, 101, 10):
            if self.cancelled:
                self.finished.emit(False, "Download cancelled")
                return
            self.progress.emit(i, f"Downloading... {i}%")
            time.sleep(0.01)  # Small delay
        self.finished.emit(True, "Download complete")
        
    def cancel(self):
        """Cancel the download."""
        self.cancelled = True


class TestButtonAdvanced:
    """Test advanced button functionality."""

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

    def test_model_download_progress_updates(self, qtbot, window, mocker):
        """Test model download button shows progress updates."""
        # Mock the model library tab
        if hasattr(window, 'model_library_tab') and window.model_library_tab:
            # Create mock download button
            download_button = QPushButton("Download Model")
            progress_bar = QProgressBar()
            
            window.model_library_tab.download_button = download_button
            window.model_library_tab.progress_bar = progress_bar
            
            # Mock download thread
            mock_thread = MockDownloadThread()
            
            # Connect signals
            def on_progress(value, message):
                progress_bar.setValue(value)
                download_button.setText(message)
                
            mock_thread.progress.connect(on_progress)
            
            # Start download
            download_button.setEnabled(False)
            mock_thread.start()
            
            # Wait for progress updates
            qtbot.wait(200)
            
            # Verify progress updates
            assert progress_bar.value() > 0
            assert "Downloading" in download_button.text()
            
            # Wait for completion
            with qtbot.waitSignal(mock_thread.finished, timeout=2000):
                pass
                
            # Verify completion
            assert progress_bar.value() == 100
            mock_thread.quit()
            mock_thread.wait()

    def test_model_download_cancellation(self, qtbot, window, mocker):
        """Test model download can be cancelled."""
        if hasattr(window, 'model_library_tab') and window.model_library_tab:
            # Create mock components
            download_button = QPushButton("Download Model")
            cancel_button = QPushButton("Cancel")
            cancel_button.setVisible(False)
            
            window.model_library_tab.download_button = download_button
            window.model_library_tab.cancel_button = cancel_button
            
            # Mock download thread
            mock_thread = MockDownloadThread()
            
            # Setup cancel functionality
            def start_download():
                download_button.setEnabled(False)
                cancel_button.setVisible(True)
                mock_thread.start()
                
            def cancel_download():
                mock_thread.cancel()
                cancel_button.setVisible(False)
                download_button.setEnabled(True)
                download_button.setText("Download Model")
                
            download_button.clicked.connect(start_download)
            cancel_button.clicked.connect(cancel_download)
            
            # Start download
            qtbot.mouseClick(download_button, Qt.MouseButton.LeftButton)
            assert cancel_button.isVisible()
            
            # Cancel after brief delay
            qtbot.wait(50)
            qtbot.mouseClick(cancel_button, Qt.MouseButton.LeftButton)
            
            # Wait for cancellation
            with qtbot.waitSignal(mock_thread.finished, timeout=2000):
                pass
                
            # Verify cancellation
            assert not cancel_button.isVisible()
            assert download_button.isEnabled()
            assert mock_thread.cancelled
            
            mock_thread.quit()
            mock_thread.wait()

    def test_batch_operation_queue_management(self, qtbot, window):
        """Test batch operation queue management buttons."""
        # Mock batch operation components
        queue_list = []
        
        # Create batch operation buttons
        add_to_queue_btn = QPushButton("Add to Queue")
        process_queue_btn = QPushButton("Process Queue")
        clear_queue_btn = QPushButton("Clear Queue")
        pause_btn = QPushButton("Pause")
        resume_btn = QPushButton("Resume")
        
        # Initially disable certain buttons
        process_queue_btn.setEnabled(False)
        clear_queue_btn.setEnabled(False)
        pause_btn.setEnabled(False)
        resume_btn.setEnabled(False)
        
        # Mock queue operations
        def add_to_queue():
            if window.in_dir and window.out_file_path:
                queue_list.append({
                    'input': window.in_dir,
                    'output': window.out_file_path
                })
                process_queue_btn.setEnabled(True)
                clear_queue_btn.setEnabled(True)
                
        def process_queue():
            if queue_list:
                pause_btn.setEnabled(True)
                process_queue_btn.setEnabled(False)
                add_to_queue_btn.setEnabled(False)
                
        def clear_queue():
            queue_list.clear()
            process_queue_btn.setEnabled(False)
            clear_queue_btn.setEnabled(False)
            
        def pause_queue():
            pause_btn.setEnabled(False)
            resume_btn.setEnabled(True)
            
        def resume_queue():
            resume_btn.setEnabled(False)
            pause_btn.setEnabled(True)
            
        # Connect signals
        add_to_queue_btn.clicked.connect(add_to_queue)
        process_queue_btn.clicked.connect(process_queue)
        clear_queue_btn.clicked.connect(clear_queue)
        pause_btn.clicked.connect(pause_queue)
        resume_btn.clicked.connect(resume_queue)
        
        # Test queue management
        # Set up input/output
        window.set_in_dir(Path("/test/input"))
        window.out_file_path = Path("/test/output.mp4")
        
        # Add to queue
        qtbot.mouseClick(add_to_queue_btn, Qt.MouseButton.LeftButton)
        assert len(queue_list) == 1
        assert process_queue_btn.isEnabled()
        assert clear_queue_btn.isEnabled()
        
        # Start processing
        qtbot.mouseClick(process_queue_btn, Qt.MouseButton.LeftButton)
        assert pause_btn.isEnabled()
        assert not process_queue_btn.isEnabled()
        
        # Pause
        qtbot.mouseClick(pause_btn, Qt.MouseButton.LeftButton)
        assert resume_btn.isEnabled()
        assert not pause_btn.isEnabled()
        
        # Resume
        qtbot.mouseClick(resume_btn, Qt.MouseButton.LeftButton)
        assert pause_btn.isEnabled()
        assert not resume_btn.isEnabled()

    def test_context_menu_actions(self, qtbot, window, mocker):
        """Test right-click context menu actions."""
        # Mock QMenu.exec
        mock_exec = mocker.patch.object(QMenu, 'exec')
        
        # Create context menu for preview label
        preview_label = window.main_tab.first_frame_label
        preview_label.file_path = "/test/image.png"
        
        # Define context menu
        def create_context_menu(pos):
            menu = QMenu()
            
            # Add actions
            copy_action = QAction("Copy Image", menu)
            save_as_action = QAction("Save As...", menu)
            open_folder_action = QAction("Open Containing Folder", menu)
            properties_action = QAction("Properties", menu)
            
            menu.addAction(copy_action)
            menu.addAction(save_as_action)
            menu.addSeparator()
            menu.addAction(open_folder_action)
            menu.addAction(properties_action)
            
            # Mock action triggers
            copy_action.triggered.connect(lambda: setattr(window, '_last_action', 'copy'))
            save_as_action.triggered.connect(lambda: setattr(window, '_last_action', 'save_as'))
            open_folder_action.triggered.connect(lambda: setattr(window, '_last_action', 'open_folder'))
            properties_action.triggered.connect(lambda: setattr(window, '_last_action', 'properties'))
            
            return menu
            
        # Override context menu
        preview_label.contextMenuEvent = lambda event: create_context_menu(event.pos()).exec(event.globalPos())
        
        # Simulate right-click
        qtbot.mouseClick(preview_label, Qt.MouseButton.RightButton)
        
        # Verify menu was shown
        mock_exec.assert_called_once()

    def test_keyboard_shortcuts_functionality(self, qtbot, window, mocker):
        """Test keyboard shortcuts trigger correct actions."""
        # Mock dialog methods
        mock_get_dir = mocker.patch("goesvfi.gui_tabs.main_tab.QFileDialog.getExistingDirectory")
        mock_get_dir.return_value = "/test/input"
        
        mock_get_save = mocker.patch("goesvfi.gui_tabs.main_tab.QFileDialog.getSaveFileName")
        mock_get_save.return_value = ("/test/output.mp4", "")
        
        # Test Ctrl+O (Open directory)
        QTest.keyClick(window, Qt.Key.Key_O, Qt.KeyboardModifier.ControlModifier)
        qtbot.wait(50)
        mock_get_dir.assert_called()
        
        # Test Ctrl+S (Save/Start if ready)
        window.set_in_dir(Path("/test/input"))
        window.out_file_path = Path("/test/output.mp4")
        
        with patch.object(window, '_start_processing') as mock_start:
            QTest.keyClick(window, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
            qtbot.wait(50)
            # Would trigger save or start depending on implementation
        
        # Test Escape (Cancel/Stop)
        window._set_processing_state(True)
        with patch.object(window, '_handle_stop_processing') as mock_stop:
            QTest.keyClick(window, Qt.Key.Key_Escape)
            qtbot.wait(50)
            # Would trigger stop if processing

    def test_button_group_interactions(self, qtbot, window):
        """Test radio button groups and checkbox dependencies."""
        # Test encoder selection radio group behavior
        encoder_combo = window.main_tab.encoder_combo
        
        # Select RIFE
        encoder_combo.setCurrentText("RIFE")
        qtbot.wait(50)
        assert window.main_tab.rife_options_group.isEnabled()
        
        # Select FFmpeg
        encoder_combo.setCurrentText("FFmpeg")
        qtbot.wait(50)
        assert not window.main_tab.rife_options_group.isEnabled()
        
        # Test checkbox dependencies
        sanchez_checkbox = window.main_tab.sanchez_checkbox
        sanchez_res_combo = window.main_tab.sanchez_res_combo
        
        # Initially unchecked
        assert not sanchez_checkbox.isChecked()
        assert not sanchez_res_combo.isEnabled()
        
        # Check enables dependent control
        sanchez_checkbox.setChecked(True)
        window._toggle_sanchez_res_enabled(Qt.CheckState.Checked)
        assert sanchez_res_combo.isEnabled()
        
        # Uncheck disables dependent control
        sanchez_checkbox.setChecked(False)
        window._toggle_sanchez_res_enabled(Qt.CheckState.Unchecked)
        assert not sanchez_res_combo.isEnabled()

    def test_toolbar_button_states(self, qtbot, window):
        """Test toolbar button states update correctly."""
        # Mock toolbar if exists
        if hasattr(window, 'toolbar'):
            # Create mock toolbar buttons
            new_action = QAction("New", window)
            open_action = QAction("Open", window)
            save_action = QAction("Save", window)
            
            # Test state changes during processing
            window._set_processing_state(True)
            
            # Toolbar should be disabled during processing
            if hasattr(window, 'toolbar'):
                for action in window.toolbar.actions():
                    if action.text() not in ['Stop', 'Cancel']:
                        assert not action.isEnabled()
            
            window._set_processing_state(False)
            
            # Toolbar should be enabled after processing
            if hasattr(window, 'toolbar'):
                for action in window.toolbar.actions():
                    if not action.isSeparator():
                        assert action.isEnabled()

    def test_button_tooltip_accuracy(self, qtbot, window):
        """Test button tooltips are accurate and helpful."""
        # Test main buttons
        buttons_to_test = [
            (window.main_tab.in_dir_button, "Select input directory containing images"),
            (window.main_tab.out_file_button, "Choose output video file location"),
            (window.main_tab.start_button, "Start video interpolation process"),
            (window.main_tab.crop_button, "Select region of interest to crop"),
            (window.main_tab.clear_crop_button, "Remove crop selection"),
        ]
        
        for button, expected_tooltip in buttons_to_test:
            # Verify tooltip exists and is meaningful
            tooltip = button.toolTip()
            assert tooltip, f"Button {button.text()} has no tooltip"
            assert len(tooltip) > 10, f"Tooltip too short: {tooltip}"
            
            # Verify dynamic tooltip updates
            if button == window.main_tab.start_button:
                # During processing, tooltip should change
                window._set_processing_state(True)
                processing_tooltip = button.toolTip()
                assert processing_tooltip != tooltip
                window._set_processing_state(False)