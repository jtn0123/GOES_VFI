"""Processing callbacks and state management for MainWindow."""

from typing import Any

from PyQt6.QtWidgets import QMessageBox

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class ProcessingCallbacks:
    """Handles processing callbacks and UI state updates during VFI processing."""

    def on_processing_progress(
        self, main_window: Any, current: int, total: int, eta: float
    ) -> None:
        """Handle progress updates from the VFI worker.

        Args:
            main_window: The MainWindow instance
            current: Current frame number
            total: Total frames
            eta: Estimated time remaining
        """
        # Calculate percentage
        value = int((current / total * 100)) if total > 0 else 0
        LOGGER.debug("Processing progress: %d%% (%d/%d)", value, current, total)

        # Update progress in view model with all values
        main_window.main_view_model.processing_vm.update_progress(current, total, eta)

        # Update progress bar if available
        if hasattr(main_window.main_tab, "progress_bar"):
            main_window.main_tab.progress_bar.setValue(value)

        # Update status message
        if value < 100:
            main_window.status_bar.showMessage(f"Processing... {value}%")

    def on_processing_finished(self, main_window: Any, output_path: str) -> None:
        """Handle successful completion of VFI processing.

        Args:
            main_window: The MainWindow instance
            output_path: Path to the generated output file
        """
        LOGGER.info("Processing completed successfully: %s", output_path)

        # Update processing state
        main_window.is_processing = False
        self.set_processing_state(main_window, False)

        # Update view model with success and output path
        main_window.main_view_model.processing_vm.finish_processing(True, output_path)

        # The view model will update the status bar via its signal,
        # so we don't need to update it directly here

        # Reset start button
        if hasattr(main_window.main_tab, "_reset_start_button"):
            main_window.main_tab._reset_start_button()

        # Show completion message
        QMessageBox.information(
            main_window, "Success", "Video interpolation completed successfully!"
        )

    def on_processing_error(self, main_window: Any, error_msg: str) -> None:
        """Handle errors during VFI processing.

        Args:
            main_window: The MainWindow instance
            error_msg: Error message from the worker
        """
        LOGGER.error("Processing error: %s", error_msg)

        # Update processing state
        main_window.is_processing = False
        self.set_processing_state(main_window, False)

        # Update view model
        main_window.main_view_model.processing_vm.handle_error(error_msg)

        # Update status
        main_window.status_bar.showMessage("Processing failed!")

        # Reset start button
        if hasattr(main_window.main_tab, "_reset_start_button"):
            main_window.main_tab._reset_start_button()

        # Show error message
        QMessageBox.critical(
            main_window,
            "Processing Error",
            f"An error occurred during processing:\n\n{error_msg}",
        )

    def set_processing_state(self, main_window: Any, is_processing: bool) -> None:
        """Update UI elements to reflect processing state.

        Args:
            main_window: The MainWindow instance
            is_processing: Whether processing is active
        """
        LOGGER.debug("Setting processing state to: %s", is_processing)

        # Update main tab state
        if hasattr(main_window, "main_tab"):
            # Disable/enable input controls
            if hasattr(main_window.main_tab, "in_dir_button"):
                main_window.main_tab.in_dir_button.setEnabled(not is_processing)
            if hasattr(main_window.main_tab, "out_file_button"):
                main_window.main_tab.out_file_button.setEnabled(not is_processing)
            if hasattr(main_window.main_tab, "encoder_combo"):
                main_window.main_tab.encoder_combo.setEnabled(not is_processing)

            # Update start/stop button
            if hasattr(main_window.main_tab, "start_button"):
                if is_processing:
                    main_window.main_tab.start_button.setText("Stop Processing")
                    main_window.main_tab.start_button.setEnabled(True)
                else:
                    main_window.main_tab.start_button.setText("Start Processing")
                    # Re-check button state based on inputs
                    if hasattr(main_window, "_update_start_button_state"):
                        main_window._update_start_button_state()

        # Disable/enable other tabs during processing
        if hasattr(main_window, "tab_widget"):
            for i in range(main_window.tab_widget.count()):
                if i != 0:  # Keep main tab enabled
                    main_window.tab_widget.setTabEnabled(i, not is_processing)

    def update_start_button_state(self, main_window: Any) -> None:
        """Update the start button enabled state based on current inputs.

        Args:
            main_window: The MainWindow instance
        """
        # Delegate to main tab if it has the method
        if hasattr(main_window.main_tab, "_update_start_button_state"):
            main_window.main_tab._update_start_button_state()
        else:
            # Fallback implementation
            enabled = bool(
                main_window.in_dir
                and main_window.out_file_path
                and not main_window.is_processing
            )
            if hasattr(main_window.main_tab, "start_button"):
                main_window.main_tab.start_button.setEnabled(enabled)

    def update_crop_buttons_state(self, main_window: Any) -> None:
        """Update crop button states based on current state.

        Args:
            main_window: The MainWindow instance
        """
        # Delegate to main tab if it has the method
        if hasattr(main_window.main_tab, "_update_crop_buttons_state"):
            main_window.main_tab._update_crop_buttons_state()
        else:
            # Fallback implementation
            has_input = bool(main_window.in_dir)
            has_crop = bool(main_window.current_crop_rect)

            if hasattr(main_window.main_tab, "crop_button"):
                main_window.main_tab.crop_button.setEnabled(has_input)
            if hasattr(main_window.main_tab, "clear_crop_button"):
                main_window.main_tab.clear_crop_button.setEnabled(has_crop)
