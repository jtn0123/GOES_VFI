import sys
import types

import pytest
from PyQt6.QtWidgets import QApplication, QLabel, QLineEdit, QProgressBar, QWidget


# Fixture to mock goesvfi.utils.ui_enhancements before importing the tab
@pytest.fixture
def mock_ui_enhancements(monkeypatch):
    class DummySignal:
        def __init__(self):
            self._slots = []

        def connect(self, slot):
            self._slots.append(slot)

        def emit(self, *args, **kwargs):
            for slot in self._slots:
                slot(*args, **kwargs)

    class DummyDragDropWidget:
        def __init__(self):
            self.files_dropped = DummySignal()

        def dragEnterEvent(self, event):
            pass

        def dragLeaveEvent(self, event):
            pass

        def dropEvent(self, event):
            pass

    class DummyFadeInNotification:
        def __init__(self, parent=None):
            self.messages = []

        def show_message(self, message, duration=None):
            self.messages.append(message)

    class DummyProgressTracker:
        def __init__(self):
            self.started = False
            self.stopped = False
            self.updated = []
            self.stats_updated = DummySignal()

        def start(self):
            self.started = True

        def stop(self):
            self.stopped = True

        def update_progress(self, items=0, bytes_transferred=0):
            self.updated.append((items, bytes_transferred))

    class DummyShortcutManager:
        def __init__(self, parent=None):
            self.callbacks = None

        def setup_standard_shortcuts(self, callbacks):
            self.callbacks = callbacks

        def show_shortcuts(self):
            pass

    class DummyLoadingSpinner:
        def __init__(self, parent=None):
            self.started = False
            self.stopped = False

        def start(self):
            self.started = True

        def stop(self):
            self.stopped = True

    class DummyTooltipHelper:
        @staticmethod
        def add_tooltip(widget, topic, text=None):
            pass

    class DummyStatusWidget(QWidget):
        def __init__(self):
            super().__init__()
            self.status_label = QLabel()
            self.speed_label = QLabel()
            self.eta_label = QLabel()
            self.progress_bar = QProgressBar()

    def create_status_widget(parent=None):
        return DummyStatusWidget()

    module = types.ModuleType("goesvfi.utils.ui_enhancements")
    module.DragDropWidget = DummyDragDropWidget
    module.FadeInNotification = DummyFadeInNotification
    module.HelpButton = object
    module.LoadingSpinner = DummyLoadingSpinner
    module.ProgressTracker = DummyProgressTracker
    module.ShortcutManager = DummyShortcutManager
    module.TooltipHelper = DummyTooltipHelper
    module.create_status_widget = create_status_widget

    monkeypatch.setitem(sys.modules, "goesvfi.utils.ui_enhancements", module)
    yield module


@pytest.fixture
def tab(qtbot, mock_ui_enhancements, monkeypatch):
    import importlib

    import goesvfi.gui_tabs.main_tab_enhanced as m

    importlib.reload(m)

    def dummy_init(self):
        QWidget.__init__(self)
        self.in_dir_edit = QLineEdit()
        self.out_file_edit = QLineEdit()
        self._progress_tracker = mock_ui_enhancements.ProgressTracker()
        self._notification = mock_ui_enhancements.FadeInNotification(self)
        self._loading_spinner = mock_ui_enhancements.LoadingSpinner(self)
        self._status_widget = mock_ui_enhancements.create_status_widget(self)

    monkeypatch.setattr(m.EnhancedMainTab, "__init__", dummy_init)
    t = m.EnhancedMainTab()
    qtbot.addWidget(t)
    return t


def test_drop_directory_updates_input(tab, tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    tab._handle_dropped_files([str(d)])
    assert tab.in_dir_edit.text() == str(d)
    assert "Input directory" in tab._notification.messages[-1]


def test_drop_video_updates_output(tab, tmp_path):
    f = tmp_path / "video.mp4"
    f.touch()
    tab._handle_dropped_files([str(f)])
    assert tab.out_file_edit.text() == str(f)
    assert "Output file" in tab._notification.messages[-1]


def test_progress_stats_update(tab):
    stats = {"speed_human": "1MB/s", "eta_human": "1m", "progress_percent": 25}
    tab._update_progress_stats(stats)
    assert tab._status_widget.status_label.text() == "Processing..."
    assert tab._status_widget.speed_label.text() == "Speed: 1MB/s"
    assert tab._status_widget.eta_label.text() == "ETA: 1m"
    assert tab._status_widget.progress_bar.value() == 25


def test_start_stop_notifications_and_progress(tab):
    tab._handle_start_vfi()
    assert tab._progress_tracker.started
    assert tab._loading_spinner.started
    assert tab._notification.messages[-1] == "Processing started..."

    tab._handle_stop_vfi()
    assert tab._progress_tracker.stopped
    assert tab._loading_spinner.stopped
    assert tab._status_widget.progress_bar.value() == 0
    assert tab._notification.messages[-1] == "Processing stopped"


def test_update_progress(tab):
    tab.update_progress(5, 10)
    assert tab._progress_tracker.updated[-1] == (1, 0)
    assert tab._status_widget.progress_bar.value() == 50
