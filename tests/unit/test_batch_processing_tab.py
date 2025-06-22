from unittest.mock import patch

import pytest

from goesvfi.gui_tabs.batch_processing_tab import BatchProcessingTab
from goesvfi.pipeline.batch_queue import BatchJob, JobPriority


class DummySignal:
    def connect(self, *args, **kwargs):
        pass


class DummyQueue:
    def __init__(self) -> None:
        self.jobs = []
        self.job_added = DummySignal()
        self.job_started = DummySignal()
        self.job_progress = DummySignal()
        self.job_completed = DummySignal()
        self.job_failed = DummySignal()
        self.job_cancelled = DummySignal()
        self.queue_empty = DummySignal()

    def add_job(self, job: BatchJob) -> None:
        self.jobs.append(job)

    def get_all_jobs(self):
        return self.jobs


@pytest.fixture
def batch_tab(qtbot):
    dummy_queue = DummyQueue()
    selected_settings = {"target_fps": 24, "interpolation": "RIFE"}

    def provider():
        return selected_settings

    with patch("goesvfi.gui_tabs.batch_processing_tab.BatchProcessor") as MockProc, patch(
        "goesvfi.gui_tabs.batch_processing_tab.QMessageBox"
    ):
        proc_instance = MockProc.return_value
        proc_instance.create_queue.return_value = dummy_queue

        def fake_create_job_from_paths(input_paths, output_dir, settings, priority=JobPriority.NORMAL, **_):
            return [
                BatchJob(
                    id="job1",
                    name="Test",
                    input_path=input_paths[0],
                    output_path=output_dir / input_paths[0].name,
                    settings=settings,
                    priority=priority,
                )
            ]

        proc_instance.create_job_from_paths.side_effect = fake_create_job_from_paths

        tab = BatchProcessingTab(
            process_function=lambda *_: None,
            settings_provider=provider,
        )
        qtbot.addWidget(tab)

    return tab, dummy_queue, selected_settings, proc_instance


def test_add_to_queue_uses_current_settings(batch_tab):
    tab, queue, expected_settings, proc = batch_tab
    tab.output_dir_label.setText("/tmp/output")
    tab.input_paths_list.addItem("/tmp/input/file1.png")

    tab._add_to_queue()

    assert len(queue.jobs) == 1
    assert queue.jobs[0].settings == expected_settings
    proc.create_job_from_paths.assert_called_once()
