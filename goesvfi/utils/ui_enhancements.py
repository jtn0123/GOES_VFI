"""UI/UX Enhancements for GOES VFI.

This module provides tooltips, help buttons, progress information,
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
import time


drag-and-drop support, and keyboard shortcuts for the GUI.
"""

QEasingCurve,
QObject,
QPoint,
QPropertyAnimation,
QRect,
QSequentialAnimationGroup,
QSize,
Qt,
QTimer,
pyqtSignal,
)
QAction,
QDragEnterEvent,
QDropEvent,
QKeySequence,
QMovie,
)
QGraphicsOpacityEffect,
QHBoxLayout,
QLabel,
QMessageBox,
QProgressBar,
QToolButton,
QToolTip,
QVBoxLayout,
QWidget,
)

from goesvfi.utils.log import get_logger

LOGGER = get_logger(__name__)

class TooltipHelper:
    """Helper class for adding consistent tooltips to widgets."""

    # Standard tooltips for common settings
    TOOLTIPS = {
    # Main processing settings
    "fps": "Frames per second for the output video. Higher values create smoother motion but larger files.",
    "mid_count": "Number of intermediate frames to generate between each pair of input frames. Higher values create smoother transitions.",
    "max_workers": "Maximum number of parallel worker threads. More workers can speed up processing but use more memory.",
    "encoder": "Video encoder to use. NVENC uses GPU acceleration (requires NVIDIA),
    x264/x265 use CPU.",

    # FFmpeg settings
    "profile": "Preset quality profile. Higher quality profiles produce better output but take longer to encode.",
    "crf": "Constant Rate Factor (0-51). Lower values mean higher quality but larger file sizes. 18-23 is usually good.",

    "preset": "Encoding speed preset. Slower presets achieve better compression at the same quality level.",
    "audio_bitrate": "Audio bitrate in kbps. Higher values mean better audio quality.",
    "video_bitrate": "Video bitrate in Mbps. Higher values mean better video quality but larger files.",
    # Crop settings
    "crop_enable": "Enable cropping to remove unwanted areas from the video.",
    "crop_preview": "Preview the crop area on the current frame.",
    # File paths
    "input_path": "Path to the input video file or image sequence.",
    "output_path": "Path where the processed video will be saved.",
    # Integrity check
    "satellite": "Select which GOES satellite to check (GOES-16 East or GOES-17 West).",
    "product": "Select the data product type (Full Disk, CONUS, Mesoscale).",
    "band": "Select the spectral band/channel for the satellite imagery.",
    "date_range": "Select the date range to check for available satellite data.",
    # Model selection
    "rife_model": "AI model for frame interpolation. Different models have different quality/speed tradeoffs.",
    "model_library": "Browse and download additional RIFE models from the library.",
    }

    @staticmethod
    def add_tooltip(widget: QWidget, key: str, custom_text: Optional[str] = None
    ) -> None:
        """Add a tooltip to a widget."""
        tooltip_text = custom_text or TooltipHelper.TOOLTIPS.get(key, "")
        if tooltip_text:
            pass
            widget.setToolTip(tooltip_text)
            # Enable rich text tooltips for better formatting
            widget.setToolTipDuration(5000)  # Show for 5 seconds

class HelpButton(QToolButton):
    """A small help button that shows detailed help when clicked."""

    help_requested = pyqtSignal(str)  # Emits the help topic

    def __init__(self, topic: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.topic = topic

        # Set button appearance
        self.setText("?")
        self.setFixedSize(20, 20)
        self.setCursor(Qt.CursorShape.WhatsThisCursor)
        self.setStyleSheet()
        """
        QToolButton {
        border: 1px solid #555;
        border-radius: 10px;
        background-color: #3a3a3a;
        color: #e0e0e0;
        font-weight: bold;
        font-size: 12px;
        }
        QToolButton:hover {
        background-color: #4a4a4a;
        border-color: #777;
        }
        QToolButton:pressed {
        background-color: #2a2a2a;
        }
        """
        )

        # Connect click signal
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self) -> None:
        """Handle button click."""
        self.help_requested.emit(self.topic)

        # Also show a popup with help text
        help_text = self._get_help_text(self.topic)
        if help_text:
            pass
            QToolTip.showText()
            self.mapToGlobal(QPoint(20, 0)), help_text, self, QRect(), 10000
            )

    def _get_help_text(self, topic: str) -> str:
        """Get detailed help text for a topic."""
        help_texts = {
        "fps": """<b>Frames Per Second (FPS)</b><br><br>
        This controls the frame rate of your output video.<br><br>
        <b>Common values:</b><br>
        • 24 fps - Cinematic look<br>
        • 30 fps - Standard video<br>
        • 60 fps - Smooth motion<br>
        • 120+ fps - Slow motion capable<br><br>
        Higher FPS creates smoother motion but larger files.""",
        "mid_count": """<b>Intermediate Frame Count</b><br><br>
        Number of frames to generate between each pair of input frames.<br><br>
        <b>Examples:</b><br>
        • 1 = Double the frame rate<br>
        • 3 = Quadruple the frame rate<br>
        • 7 = 8x the frame rate<br><br>
        More frames = smoother motion but longer processing time.""",
        "crf": """<b>Constant Rate Factor (CRF)</b><br><br>"
        Controls video quality vs file size.<br><br>
        <b>Scale: 0-51</b> (lower = better quality)<br>
        • 0 = Lossless (huge files)<br>
        • 18 = Visually lossless<br>
        • 23 = Default (good quality)<br>
        • 28 = Acceptable quality<br>
        • 51 = Worst quality<br><br>
        Each +6 roughly doubles file size.""",
        "encoder": """<b>Video Encoder Selection</b><br><br>
        <b>Hardware (GPU):</b><br>
        • NVENC - NVIDIA GPUs (fastest)<br>
        • QuickSync - Intel GPUs<br>
        • AMF - AMD GPUs<br><br>
        <b>Software (CPU):</b><br>
        • x264 - Widely compatible<br>
        • x265 - Better compression<br><br>
        GPU encoders are much faster but may have slightly lower quality.""",
        }

        return help_texts.get(topic, f"Help for {topic}")

class ProgressTracker(QObject):
    """Tracks and calculates progress statistics."""

    stats_updated = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.start_time: Optional[float] = None
        self.total_items = 0
        self.processed_items = 0
        self.current_speed = 0.0
        self.bytes_transferred = 0
        self.total_bytes = 0
        self._speed_history: List[Tuple[float, float]] = []  # (timestamp, bytes)
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._calculate_stats)
        self._update_timer.setInterval(1000)  # Update every second

    def start(self, total_items: int = 0, total_bytes: int = 0) -> None:
        """Start tracking progress."""
        self.start_time = time.time()
        self.total_items = total_items
        self.total_bytes = total_bytes
        self.processed_items = 0
        self.bytes_transferred = 0
        self._speed_history.clear()
        self._update_timer.start()

    def stop(self) -> None:
        """Stop tracking progress."""
        self._update_timer.stop()

    def update_progress(self, items: int = 0, bytes_transferred: int = 0) -> None:
        """Update progress counters."""
        self.processed_items += items
        self.bytes_transferred += bytes_transferred

        # Record for speed calculation
        current_time = time.time()
        self._speed_history.append((current_time, self.bytes_transferred))

        # Keep only last 10 seconds of history
        cutoff_time = current_time - 10
        self._speed_history = [  # pylint: disable=attribute-defined-outside-init
        (t, b) for t, b in self._speed_history if t > cutoff_time
        ]

    def _calculate_stats(self) -> None:
        pass
        """Calculate and emit progress statistics."""
        if not self.start_time:
            pass
            return

        current_time = time.time()
        elapsed = current_time - self.start_time

        # Calculate speed from recent history
        if len(self._speed_history) >= 2:
            pass
            recent_time = self._speed_history[-1][0] - self._speed_history[0][0]
            recent_bytes = self._speed_history[-1][1] - self._speed_history[0][1]
            if recent_time > 0:
                pass
                self.current_speed = recent_bytes / recent_time

        # Calculate ETA
        eta_seconds = 0.0
        if self.total_items > 0 and self.processed_items > 0:
            pass
            items_per_second = self.processed_items / elapsed
            remaining_items = self.total_items - self.processed_items
            eta_seconds = ()
            remaining_items / items_per_second if items_per_second > 0 else 0
            )
        elif self.total_bytes > 0 and self.current_speed > 0:
            pass
            remaining_bytes = self.total_bytes - self.bytes_transferred
            eta_seconds = remaining_bytes / self.current_speed

        stats = {
        "elapsed": elapsed,
        "eta_seconds": eta_seconds,
        "speed_bps": self.current_speed,
        "speed_human": self._format_speed(self.current_speed),
        "eta_human": self._format_time(eta_seconds),
        "elapsed_human": self._format_time(elapsed),
        "progress_percent": self._calculate_percent(),
        }

        self.stats_updated.emit(stats)

    def _calculate_percent(self) -> float:
        """Calculate progress percentage."""
        if self.total_items > 0:
            pass
            return (self.processed_items / self.total_items) * 100
        elif self.total_bytes > 0:
            pass
            return (self.bytes_transferred / self.total_bytes) * 100
        return 0

    @staticmethod
    def _format_speed(bytes_per_second: float) -> str:
        """Format speed in human-readable units."""
        if bytes_per_second <= 0:
            pass
            return "0 B/s"

        units = ["B/s", "KB/s", "MB/s", "GB/s"]
        unit_index = 0
        speed = bytes_per_second

        while speed >= 1024 and unit_index < len(units) - 1:
            speed /= 1024
            unit_index += 1

        return f"{speed:.1f} {units[unit_index]}"

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format time duration in human-readable format."""
        if seconds <= 0:
            pass
            return "0:00"

        if seconds < 60:
            pass
            return f"0:{int(seconds):02d}"
        elif seconds < 3600:
            pass
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}:{secs:02d}"
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours}:{minutes:02d}:{secs:02d}"

class LoadingSpinner(QLabel):
    """An animated loading spinner widget."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(32, 32)
        self._movie: Optional[QMovie] = None

        # Try to load a GIF spinner, fall back to text if not available
        spinner_path = Path(__file__).parent.parent / "resources" / "spinner.gif"
        if spinner_path.exists():
            pass
            self._movie = QMovie(str(spinner_path))
            self._movie.setScaledSize(QSize(32, 32))
            self.setMovie(self._movie)
        else:
            # Fallback to animated text
            self.setText("◐")
            self.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setStyleSheet("font-size: 24px; color: #4a90e2;")
            self._animation_timer = QTimer()  # pylint: disable=attribute-defined-outside-init
            self._animation_timer.timeout.connect(self._animate_text)
            self._animation_state = 0  # pylint: disable=attribute-defined-outside-init

    def start(self) -> None:
        """Start the spinner animation."""
        if self._movie is not None:
            pass
            self._movie.start()
        else:
            self._animation_timer.start(100)
        self.show()

    def stop(self) -> None:
        """Stop the spinner animation."""
        if self._movie is not None:
            pass
            self._movie.stop()
        else:
            self._animation_timer.stop()
        self.hide()

    def _animate_text(self) -> None:
        """Animate text-based spinner."""
        frames = ["◐", "◓", "◑", "◒"]
        self.setText(frames[self._animation_state])
        self._animation_state = (self._animation_state + 1) % len(frames)  # pylint: disable=attribute-defined-outside-init

class DragDropWidget(QWidget):
    """Mixin class to add drag-and-drop support to any widget."""

    files_dropped = pyqtSignal(list)  # List of file paths

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)
        self._drag_style = """
        QWidget {
        border: 2px dashed #4a90e2;
        background-color: rgba(74, 144, 226, 0.1);
        }
        """
        self._original_style = ""

    def dragEnterEvent(self, event: Optional[QDragEnterEvent]) -> None:
        """Handle drag enter event."""
        if event is None:
            pass
            return
        mime_data = event.mimeData()
        if mime_data and mime_data.hasUrls():
            pass
            event.acceptProposedAction()
            self._original_style = self.styleSheet()  # pylint: disable=attribute-defined-outside-init
            self.setStyleSheet(self._original_style + self._drag_style)
            LOGGER.debug("Drag entered with files")

    def dragLeaveEvent(self, event) -> None:
        """Handle drag leave event."""
        self.setStyleSheet(self._original_style)

    def dropEvent(self, event: Optional[QDropEvent]) -> None:
        """Handle drop event."""
        self.setStyleSheet(self._original_style)

        if event is None:
            pass
            return
        mime_data = event.mimeData()
        if mime_data and mime_data.hasUrls():
            pass
            event.acceptProposedAction()

            # Extract file paths
            file_paths = []
            for url in mime_data.urls():
                if url.isLocalFile():
                    pass
                    file_paths.append(url.toLocalFile())

            if file_paths:
                pass
                LOGGER.info("Files dropped: %s", file_paths)
                self.files_dropped.emit(file_paths)

class ShortcutManager:
    """Manages keyboard shortcuts for the application."""

    def __init__(self, parent: QWidget):
        self.parent = parent
        self.shortcuts: Dict[str, QAction] = {}

    def add_shortcut(self, name: str, key_sequence: str, callback: Callable, description: str
    ) -> QAction:
        """Add a keyboard shortcut."""
        action = QAction(description, self.parent)
        action.setShortcut(QKeySequence(key_sequence))
        action.triggered.connect(callback)
        self.parent.addAction(action)
        self.shortcuts[name] = action
        LOGGER.debug("Added shortcut: %s (%s)", name, key_sequence)
        return action

    def setup_standard_shortcuts(self, callbacks: Dict[str, Callable]) -> None:
        """Set up standard application shortcuts."""
        standard_shortcuts = [
        ("open", "Ctrl+O", "open_file", "Open file"),
        ("save", "Ctrl+S", "save_file", "Save file"),
        ("quit", "Ctrl+Q", "quit_app", "Quit application"),
        ("start", "Ctrl+R", "start_processing", "Start processing"),
        ("stop", "Ctrl+X", "stop_processing", "Stop processing"),
        ("preview", "Ctrl+P", "toggle_preview", "Toggle preview"),
        ("help", "F1", "show_help", "Show help"),
        ("settings", "Ctrl+,", "show_settings", "Show settings"),
        ]

        for name, key, callback_name, description in standard_shortcuts:
            if callback_name in callbacks:
                pass
                self.add_shortcut(name, key, callbacks[callback_name], description)

    def show_shortcuts(self) -> None:
        """Display a dialog showing all keyboard shortcuts."""
        shortcuts_text = "<h3>Keyboard Shortcuts</h3><table>"
        for _name, action in self.shortcuts.items():
            shortcut = action.shortcut().toString()
            description = action.text()
            shortcuts_text += ()
            f"<tr><td><b>{shortcut}</b></td><td>{description}</td></tr>"
            )
        shortcuts_text += "</table>"

        msg = QMessageBox(self.parent)
        msg.setWindowTitle("Keyboard Shortcuts")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(shortcuts_text)
        msg.exec()

class AnimatedProgressBar(QProgressBar):
    """A progress bar with smooth animations."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setTextVisible(True)
        self._animation = QPropertyAnimation(self, b"value")
        self._animation.setDuration(250)  # 250ms animation
        self._animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        # Enhanced style
        self.setStyleSheet()
        """
        QProgressBar {
        border: 1px solid #555;
        border-radius: 5px;
        text-align: center;
        background-color: #2a2a2a;
        color: white;
        font-weight: bold;
        }
        QProgressBar::chunk {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,)
        stop:0 #4a90e2, stop:1 #5ba0f2);
        border-radius: 4px;
        }
        """
        )

    def setValue(self, value: int) -> None:
        """Set value with animation."""
        self._animation.stop()
        self._animation.setStartValue(self.value())
        self._animation.setEndValue(value)
        self._animation.start()

    def set_state(self, state: str) -> None:
        """Set visual state of progress bar."""
        if state == "error":
            pass
            self.setStyleSheet()
            self.styleSheet()
            .replace("#4a90e2", "#e74c3c")
            .replace("#5ba0f2", "#f75c4c")
            )
        elif state == "success":
            pass
            self.setStyleSheet()
            self.styleSheet()
            .replace("#4a90e2", "#27ae60")
            .replace("#5ba0f2", "#37be70")
            )
        else:  # normal
        self.setStyleSheet()
        self.styleSheet()
        .replace("#e74c3c", "#4a90e2")
        .replace("#f75c4c", "#5ba0f2")
        .replace("#27ae60", "#4a90e2")
        .replace("#37be70", "#5ba0f2")
        )

class StatusWidget(QWidget):
    """Status widget with progress bar and info labels."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Progress bar
        self.progress_bar = AnimatedProgressBar()
        layout.addWidget(self.progress_bar)

        # Status info layout
        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(0, 5, 0, 0)

        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #888; font-size: 12px;")
        info_layout.addWidget(self.status_label)

        info_layout.addStretch()

        # Speed label
        self.speed_label = QLabel("")
        self.speed_label.setStyleSheet("color: #888; font-size: 12px;")
        info_layout.addWidget(self.speed_label)

        # ETA label
        self.eta_label = QLabel("")
        self.eta_label.setStyleSheet("color: #888; font-size: 12px;")
        info_layout.addWidget(self.eta_label)

        layout.addLayout(info_layout)

def create_status_widget(parent: Optional[QWidget] = None) -> StatusWidget:
    """Create a status widget with progress bar and info labels."""
    return StatusWidget(parent)

class FadeInNotification(QLabel):
    pass
    """A notification that fades in and out."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet()
        """
        QLabel {
        background-color: rgba(50, 50, 50, 200);
        color: white;
        border-radius: 10px;
        padding: 10px 20px;
        font-size: 14px;
        }
        """
        )

        # Set up opacity effect
        self.opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.opacity_effect)

        # Animation group
        self.animation_group = QSequentialAnimationGroup()

        # Fade in
        self.fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in.setDuration(300)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)

        # Stay visible (using a dummy animation)
        self.stay = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.stay.setDuration(2000)
        self.stay.setStartValue(1.0)
        self.stay.setEndValue(1.0)

        # Fade out
        self.fade_out = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_out.setDuration(300)
        self.fade_out.setStartValue(1.0)
        self.fade_out.setEndValue(0.0)

        # Add to group
        self.animation_group.addAnimation(self.fade_in)
        self.animation_group.addAnimation(self.stay)
        self.animation_group.addAnimation(self.fade_out)

        # Hide when done
        self.animation_group.finished.connect(self.hide)

        self.hide()

    def show_message(self, message: str, duration: int = 2000) -> None:
        """Show a notification message."""
        self.setText(message)
        self.stay.setDuration(duration)

        # Position at top center of parent
        parent = self.parent()
        if parent is not None and isinstance(parent, QWidget):
            pass
            parent_rect = parent.rect()
            self.adjustSize()
            x = (parent_rect.width() - self.width()) // 2
            y = 50
            self.move(x, y)

        self.show()
        self.animation_group.start()
