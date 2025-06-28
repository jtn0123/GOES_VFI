"""Batch processing tab for GOES-VFI GUI.

This module provides the GUI interface for managing batch processing jobs
with queue visualization and control.
"""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from goesvfi.pipeline.batch_queue import (
    BatchProcessor,
    BatchQueue,
    JobPriority,
    JobStatus,
)
from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class BatchProcessingTab(QWidget):
    """Tab for batch processing management."""

    def __init__(
        self,
        process_function: Callable[..., Any] | None = None,
        resource_manager: Any | None = None,
        settings_provider: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        """Initialize batch processing tab."""
        super().__init__()

        self.process_function = process_function
        self.resource_manager = resource_manager
        self.batch_processor = BatchProcessor(resource_manager)
        self.batch_queue: BatchQueue | None = None
        self.settings_provider = settings_provider

        self._init_ui()
        self._init_batch_queue()

        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_queue_display)
        self.update_timer.start(1000)  # Update every second

    def _init_ui(self) -> None:
        """Initialize UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Add header
        header = QLabel("📦 Batch Processing")
        header.setProperty("class", "AppHeader")
        layout.addWidget(header)

        # Add Jobs section
        add_group = QGroupBox("➕ Add Jobs")
        add_layout = QVBoxLayout()

        # Input selection
        input_layout = QHBoxLayout()
        input_label = QLabel("Input:")
        input_label.setProperty("class", "StandardLabel")
        input_layout.addWidget(input_label)
        self.input_paths_list = QListWidget()
        self.input_paths_list.setMaximumHeight(100)
        input_layout.addWidget(self.input_paths_list)

        input_buttons = QVBoxLayout()
        self.add_files_btn = QPushButton("📄 Add Files...")
        self.add_files_btn.setProperty("class", "DialogButton")
        self.add_files_btn.setToolTip("Add individual files to the batch queue")
        self.add_files_btn.clicked.connect(self._add_files)
        input_buttons.addWidget(self.add_files_btn)

        self.add_folder_btn = QPushButton("📁 Add Folder...")
        self.add_folder_btn.setProperty("class", "DialogButton")
        self.add_folder_btn.setToolTip("Add all files from a folder to the batch queue")
        self.add_folder_btn.clicked.connect(self._add_folder)
        input_buttons.addWidget(self.add_folder_btn)

        self.clear_inputs_btn = QPushButton("🗑️ Clear")
        self.clear_inputs_btn.setProperty("class", "DialogButton")
        self.clear_inputs_btn.setToolTip("Clear all input files")
        self.clear_inputs_btn.clicked.connect(self._clear_inputs)
        input_buttons.addWidget(self.clear_inputs_btn)

        input_layout.addLayout(input_buttons)
        add_layout.addLayout(input_layout)

        # Output directory
        output_layout = QHBoxLayout()
        output_label = QLabel("Output Directory:")
        output_label.setProperty("class", "StandardLabel")
        output_layout.addWidget(output_label)
        self.output_dir_label = QLabel("Not selected")
        output_layout.addWidget(self.output_dir_label)
        self.select_output_btn = QPushButton("📁 Select...")
        self.select_output_btn.setProperty("class", "DialogButton")
        self.select_output_btn.setToolTip("Select output directory for processed files")
        self.select_output_btn.clicked.connect(self._select_output_dir)
        output_layout.addWidget(self.select_output_btn)
        add_layout.addLayout(output_layout)

        # Priority selection
        priority_layout = QHBoxLayout()
        priority_label = QLabel("Priority:")
        priority_label.setProperty("class", "StandardLabel")
        priority_layout.addWidget(priority_label)
        self.priority_combo = QComboBox()
        for priority in JobPriority:
            self.priority_combo.addItem(priority.name, priority)
        self.priority_combo.setCurrentText(JobPriority.NORMAL.name)
        priority_layout.addWidget(self.priority_combo)
        priority_layout.addStretch()
        add_layout.addLayout(priority_layout)

        # Add to queue button
        self.add_to_queue_btn = QPushButton("➕ Add to Queue")
        self.add_to_queue_btn.setProperty("class", "StartButton")
        self.add_to_queue_btn.setToolTip("Add selected files to the processing queue")
        self.add_to_queue_btn.clicked.connect(self._add_to_queue)
        self.add_to_queue_btn.setEnabled(False)
        add_layout.addWidget(self.add_to_queue_btn)

        add_group.setLayout(add_layout)
        layout.addWidget(add_group)

        # Queue Management section
        queue_group = QGroupBox("📋 Queue Management")
        queue_layout = QVBoxLayout()

        # Controls
        controls_layout = QHBoxLayout()

        self.start_btn = QPushButton("▶️ Start Processing")
        self.start_btn.setProperty("class", "StartButton")
        self.start_btn.setToolTip("Start processing jobs in the queue")
        self.start_btn.clicked.connect(self._start_processing)
        controls_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹️ Stop Processing")
        self.stop_btn.setProperty("class", "StopButton")
        self.stop_btn.setToolTip("Stop processing jobs")
        self.stop_btn.clicked.connect(self._stop_processing)
        self.stop_btn.setEnabled(False)
        controls_layout.addWidget(self.stop_btn)

        concurrent_label = QLabel("Concurrent Jobs:")
        concurrent_label.setProperty("class", "StandardLabel")
        controls_layout.addWidget(concurrent_label)
        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setMinimum(1)
        self.concurrent_spin.setMaximum(4)
        self.concurrent_spin.setValue(1)
        self.concurrent_spin.valueChanged.connect(self._update_concurrent_jobs)
        controls_layout.addWidget(self.concurrent_spin)

        controls_layout.addStretch()

        self.clear_completed_btn = QPushButton("🧹 Clear Completed")
        self.clear_completed_btn.setProperty("class", "DialogButton")
        self.clear_completed_btn.setToolTip("Remove completed jobs from the queue")
        self.clear_completed_btn.clicked.connect(self._clear_completed)
        controls_layout.addWidget(self.clear_completed_btn)

        queue_layout.addLayout(controls_layout)

        # Queue table
        self.queue_table = QTableWidget()
        self.queue_table.setColumnCount(7)
        self.queue_table.setHorizontalHeaderLabels([
            "Name",
            "Status",
            "Priority",
            "Progress",
            "Created",
            "Duration",
            "Actions",
        ])
        table_header = self.queue_table.horizontalHeader()
        if table_header:
            table_header.setStretchLastSection(False)
            table_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.queue_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        queue_layout.addWidget(self.queue_table)

        queue_group.setLayout(queue_layout)
        layout.addWidget(queue_group)

        # Statistics
        stats_layout = QHBoxLayout()
        self.stats_label = QLabel("Queue: 0 pending, 0 running, 0 completed")
        self.stats_label.setProperty("class", "StatusInfo")
        stats_layout.addWidget(self.stats_label)
        stats_layout.addStretch()
        layout.addLayout(stats_layout)

    def _init_batch_queue(self) -> None:
        """Initialize the batch queue."""
        if not self.process_function:
            LOGGER.warning("No process function provided for batch queue")
            return

        self.batch_queue = self.batch_processor.create_queue(
            process_function=self.process_function,
            max_concurrent=self.concurrent_spin.value(),
        )

        # Connect signals
        self.batch_queue.job_added.connect(self._on_job_added)
        self.batch_queue.job_started.connect(self._on_job_started)
        self.batch_queue.job_progress.connect(self._on_job_progress)
        self.batch_queue.job_completed.connect(self._on_job_completed)
        self.batch_queue.job_failed.connect(self._on_job_failed)
        self.batch_queue.job_cancelled.connect(self._on_job_cancelled)
        self.batch_queue.queue_empty.connect(self._on_queue_empty)

        # Load existing jobs
        self._update_queue_display()

    @pyqtSlot()
    def _add_files(self) -> None:
        """Add individual files to input list."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Input Files",
            "",
            "Image Files (*.png *.jpg *.jpeg);;All Files (*.*)",
        )

        for file in files:
            self.input_paths_list.addItem(file)

        self._update_add_button()

    @pyqtSlot()
    def _add_folder(self) -> None:
        """Add all files from a folder."""
        folder = QFileDialog.getExistingDirectory(self, "Select Input Folder")

        if folder:
            # Add folder path with special marker
            self.input_paths_list.addItem(f"[FOLDER] {folder}")

        self._update_add_button()

    @pyqtSlot()
    def _clear_inputs(self) -> None:
        """Clear input list."""
        self.input_paths_list.clear()
        self._update_add_button()

    @pyqtSlot()
    def _select_output_dir(self) -> None:
        """Select output directory."""
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")

        if directory:
            self.output_dir_label.setText(directory)
            self._update_add_button()

    def _update_add_button(self) -> None:
        """Update add to queue button state."""
        has_inputs = self.input_paths_list.count() > 0
        has_output = self.output_dir_label.text() != "Not selected"
        self.add_to_queue_btn.setEnabled(has_inputs and has_output)

    @pyqtSlot()
    def _add_to_queue(self) -> None:
        """Add current inputs to processing queue."""
        if not self.batch_queue:
            QMessageBox.warning(self, "Error", "Batch queue not initialized")
            return

        output_dir = Path(self.output_dir_label.text())
        priority = self.priority_combo.currentData()

        if self.settings_provider:
            try:
                settings = self.settings_provider()
            except Exception as exc:  # pragma: no cover - defensive
                LOGGER.exception("Failed to obtain settings")
                settings = {}
        else:
            settings = {}

        job_ids = []

        # Process each input
        for i in range(self.input_paths_list.count()):
            item = self.input_paths_list.item(i)
            if not item:
                continue
            item_text = item.text()

            if item_text.startswith("[FOLDER] "):
                # Process folder
                folder_path = Path(item_text[9:])
                folder_job_ids = self.batch_processor.add_directory(
                    input_dir=folder_path,
                    output_dir=output_dir,
                    settings=settings,
                    pattern="*.png",
                    priority=priority,
                )
                job_ids.extend(folder_job_ids)
            else:
                # Process individual file
                input_path = Path(item_text)
                jobs = self.batch_processor.create_job_from_paths(
                    input_paths=[input_path],
                    output_dir=output_dir,
                    settings=settings,
                    priority=priority,
                )
                for job in jobs:
                    self.batch_queue.add_job(job)
                    job_ids.append(job.id)

        # Clear inputs after adding
        self.input_paths_list.clear()
        self._update_add_button()

        QMessageBox.information(self, "Jobs Added", f"Added {len(job_ids)} jobs to the queue")

    @pyqtSlot()
    def _start_processing(self) -> None:
        """Start batch processing."""
        if self.batch_queue:
            self.batch_queue.start()
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)

    @pyqtSlot()
    def _stop_processing(self) -> None:
        """Stop batch processing."""
        if self.batch_queue:
            self.batch_queue.stop()
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)

    @pyqtSlot(int)
    def _update_concurrent_jobs(self, value: int) -> None:
        """Update maximum concurrent jobs."""
        if self.batch_queue:
            self.batch_queue.max_concurrent_jobs = value

    @pyqtSlot()
    def _clear_completed(self) -> None:
        """Clear completed jobs from queue."""
        if self.batch_queue:
            count = self.batch_queue.clear_completed()
            self._update_queue_display()
            QMessageBox.information(self, "Cleared", f"Removed {count} completed/cancelled jobs")

    def _update_queue_display(self) -> None:
        """Update the queue table display."""
        if not self.batch_queue:
            return

        jobs = self.batch_queue.get_all_jobs()

        # Update table
        self.queue_table.setRowCount(len(jobs))

        for row, job in enumerate(jobs):
            # Name
            self.queue_table.setItem(row, 0, QTableWidgetItem(job.name))

            # Status
            status_item = QTableWidgetItem(job.status.value)
            if job.status == JobStatus.RUNNING:
                status_item.setForeground(Qt.GlobalColor.blue)
            elif job.status == JobStatus.COMPLETED:
                status_item.setForeground(Qt.GlobalColor.green)
            elif job.status == JobStatus.FAILED:
                status_item.setForeground(Qt.GlobalColor.red)
            self.queue_table.setItem(row, 1, status_item)

            # Priority
            self.queue_table.setItem(row, 2, QTableWidgetItem(job.priority.name))

            # Progress
            progress_text = f"{job.progress:.1f}%" if job.status == JobStatus.RUNNING else ""
            self.queue_table.setItem(row, 3, QTableWidgetItem(progress_text))

            # Created
            created_text = job.created_at.strftime("%H:%M:%S")
            self.queue_table.setItem(row, 4, QTableWidgetItem(created_text))

            # Duration
            duration_text = ""
            if job.started_at:
                end_time = job.completed_at or datetime.now()
                duration = end_time - job.started_at
                duration_text = f"{duration.total_seconds():.1f}s"
            self.queue_table.setItem(row, 5, QTableWidgetItem(duration_text))

            # Actions
            if job.status == JobStatus.PENDING:
                cancel_btn = QPushButton("❌ Cancel")
                cancel_btn.setProperty("class", "DialogButton")
                cancel_btn.setToolTip("Cancel this job")
                cancel_btn.clicked.connect(lambda _checked, jid=job.id: self._cancel_job(jid))
                self.queue_table.setCellWidget(row, 6, cancel_btn)
            else:
                # Create empty widget for consistency
                empty_widget = QWidget()
                self.queue_table.setCellWidget(row, 6, empty_widget)

        # Update statistics
        stats = {
            JobStatus.PENDING: 0,
            JobStatus.RUNNING: 0,
            JobStatus.COMPLETED: 0,
            JobStatus.FAILED: 0,
            JobStatus.CANCELLED: 0,
        }

        for job in jobs:
            stats[job.status] += 1

        self.stats_label.setText(
            f"Queue: {stats[JobStatus.PENDING]} pending, "
            f"{stats[JobStatus.RUNNING]} running, "
            f"{stats[JobStatus.COMPLETED]} completed, "
            f"{stats[JobStatus.FAILED]} failed"
        )

    def _cancel_job(self, job_id: str) -> None:
        """Cancel a specific job."""
        if self.batch_queue and self.batch_queue.cancel_job(job_id):
            self._update_queue_display()

    # Signal handlers
    @pyqtSlot(str)
    def _on_job_added(self, _job_id: str) -> None:
        """Handle job added signal."""
        self._update_queue_display()

    @pyqtSlot(str)
    def _on_job_started(self, _job_id: str) -> None:
        """Handle job started signal."""
        self._update_queue_display()

    @pyqtSlot(str, float)
    def _on_job_progress(self, job_id: str, progress: float) -> None:
        """Handle job progress signal."""
        # Find job row and update progress
        if not self.batch_queue:
            return

        jobs = self.batch_queue.get_all_jobs()
        for row, job in enumerate(jobs):
            if job.id == job_id:
                self.queue_table.setItem(row, 3, QTableWidgetItem(f"{progress:.1f}%"))
                break

    @pyqtSlot(str)
    def _on_job_completed(self, _job_id: str) -> None:
        """Handle job completed signal."""
        self._update_queue_display()

    @pyqtSlot(str, str)
    def _on_job_failed(self, job_id: str, error: str) -> None:
        """Handle job failed signal."""
        self._update_queue_display()

        # Show error message
        if self.batch_queue:
            job = self.batch_queue.get_job(job_id)
            if job:
                QMessageBox.critical(self, "Job Failed", f"Job '{job.name}' failed:\n{error}")

    @pyqtSlot(str)
    def _on_job_cancelled(self, _job_id: str) -> None:
        """Handle job cancelled signal."""
        self._update_queue_display()

    @pyqtSlot()
    def _on_queue_empty(self) -> None:
        """Handle queue empty signal."""
        LOGGER.info("Batch queue is empty")

    def set_process_function(self, func: Callable[..., Any]) -> None:
        """Set the process function for batch jobs."""
        self.process_function = func
        if self.batch_queue:
            self.batch_queue.process_function = func

    def get_current_settings(self) -> dict[str, Any]:
        """Get current batch processing settings."""
        return {
            "max_concurrent_jobs": self.concurrent_spin.value(),
            "output_directory": self.output_dir_label.text(),
        }

    def closeEvent(self, event: QCloseEvent | None) -> None:
        """Handle widget close event."""
        # Stop the update timer to prevent crashes
        if hasattr(self, "update_timer") and self.update_timer:
            self.update_timer.stop()

        # Stop batch processing if running
        if self.batch_queue and hasattr(self.batch_queue, "stop"):
            self.batch_queue.stop()

        # Accept the close event
        if event is not None:
            event.accept()
