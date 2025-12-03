import sys
import os
import requests
import yt_dlp
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QScrollArea, QGridLayout, 
                             QFrame, QSizePolicy, QMessageBox, QSlider, QStyle)
from PyQt6.QtCore import Qt, pyqtSignal, QRunnable, QThreadPool, QObject, QSize, QUrl
from PyQt6.QtGui import QPixmap, QFont, QIcon, QColor, QPainter, QPainterPath
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
import qdarktheme
from youtube_api import YouTubeManager

# --- Styles ---
STYLESHEET = """
QMainWindow {
    background-color: #1e1e1e;
}
QLineEdit {
    padding: 12px;
    border-radius: 8px;
    border: 1px solid #333;
    background-color: #2d2d2d;
    color: #fff;
    font-size: 14px;
}
QLineEdit:focus {
    border: 1px solid #0078d4;
}
QPushButton {
    padding: 12px 24px;
    border-radius: 8px;
    background-color: #0078d4;
    color: white;
    font-weight: bold;
    font-size: 14px;
    border: none;
}
QPushButton:hover {
    background-color: #1084d9;
}
QPushButton:pressed {
    background-color: #006cc1;
}
QPushButton:disabled {
    background-color: #333;
    color: #888;
}
QScrollArea {
    border: none;
    background-color: transparent;
}
QWidget#scrollContent {
    background-color: transparent;
}
QLabel#statusLabel {
    color: #888;
    font-size: 12px;
    margin-top: 10px;
}
QSlider::groove:horizontal {
    border: 1px solid #333;
    height: 4px;
    background: #333;
    margin: 2px 0;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #0078d4;
    border: 1px solid #0078d4;
    width: 12px;
    height: 12px;
    margin: -4px 0;
    border-radius: 6px;
}
"""

CARD_STYLE = """
QFrame {
    background-color: #2d2d2d;
    border-radius: 12px;
    border: 1px solid #333;
}
QFrame:hover {
    border: 1px solid #444;
    background-color: #323232;
}
QLabel#titleLabel {
    color: #fff;
    font-weight: bold;
    font-size: 14px;
}
QLabel#dateLabel {
    color: #aaa;
    font-size: 12px;
}
QPushButton#playBtn {
    background-color: transparent;
    border: none;
    border-radius: 20px; 
}
QPushButton#playBtn:hover {
    background-color: rgba(255, 255, 255, 0.1);
}
"""

# --- Worker Signals ---
class WorkerSignals(QObject):
    finished = pyqtSignal(list, str) # videos, next_page_token
    error = pyqtSignal(str)
    image_loaded = pyqtSignal(int, bytes) # index, data
    url_ready = pyqtSignal(str, str) # video_id, stream_url

# --- Fetch Worker ---
class FetchWorker(QRunnable):
    def __init__(self, channel_id):
        super().__init__()
        self.channel_id = channel_id
        self.signals = WorkerSignals()

    def run(self):
        try:
            yt = YouTubeManager()
            videos = yt.get_channel_videos(self.channel_id)
            self.signals.finished.emit(videos, "")
        except Exception as e:
            self.signals.error.emit(str(e))

# --- Image Worker ---
class ImageWorker(QRunnable):
    def __init__(self, url, index):
        super().__init__()
        self.url = url
        self.index = index
        self.signals = WorkerSignals()

    def run(self):
        try:
            response = requests.get(self.url, timeout=10)
            if response.status_code == 200:
                self.signals.image_loaded.emit(self.index, response.content)
        except:
            pass

# --- Stream URL Worker ---
class StreamUrlWorker(QRunnable):
    def __init__(self, video_id):
        super().__init__()
        self.video_id = video_id
        self.signals = WorkerSignals()

    def run(self):
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True, # Ensure we don't fetch playlist info
                'extract_flat': False, # We need the stream URL
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={self.video_id}", download=False)
                url = info['url']
                self.signals.url_ready.emit(self.video_id, url)
        except Exception as e:
            print(f"Error fetching stream URL: {e}")
            self.signals.error.emit(str(e))

# --- Video Card Widget ---
class VideoCard(QFrame):
    # Signals to communicate with MainWindow
    playClicked = pyqtSignal(str) # video_id
    seekRequested = pyqtSignal(str, int) # video_id, position

    def __init__(self, video_data):
        super().__init__()
        self.video_id = video_data['id']
        self.setStyleSheet(CARD_STYLE)
        self.setFixedHeight(90) # Compact height
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QHBoxLayout(self) # Horizontal layout
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # Thumbnail
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(120, 68) 
        self.thumb_label.setStyleSheet("background-color: #1a1a1a; border-radius: 5px;")
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setText("Loading...")
        layout.addWidget(self.thumb_label)

        # Info Area
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        # Title Row (Title + Play Button)
        title_row = QHBoxLayout()
        self.title_label = QLabel(video_data['title'])
        self.title_label.setObjectName("titleLabel")
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        title_row.addWidget(self.title_label)

        self.play_btn = QPushButton()
        self.play_btn.setObjectName("playBtn")
        self.play_btn.setFixedSize(32, 32) # Smaller button
        self.play_btn.setIcon(QIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)))
        self.play_btn.setIconSize(QSize(20, 20))
        self.play_btn.clicked.connect(self.on_play_click)
        title_row.addWidget(self.play_btn)
        
        info_layout.addLayout(title_row)

        # Date
        date_str = video_data['published_at'].split('T')[0]
        self.date_label = QLabel(date_str)
        self.date_label.setObjectName("dateLabel")
        info_layout.addWidget(self.date_label)

        # Slider Row (Current Time - Slider - Total Time)
        self.slider_row = QHBoxLayout()
        self.slider_row.setSpacing(5)
        
        self.lbl_current = QLabel("0:00")
        self.lbl_current.setStyleSheet("color: #aaa; font-size: 10px;")
        self.slider_row.addWidget(self.lbl_current)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.on_slider_move)
        self.slider.sliderPressed.connect(self.on_slider_press)
        self.slider.sliderReleased.connect(self.on_slider_release)
        self.slider_row.addWidget(self.slider)
        
        self.lbl_total = QLabel("0:00")
        self.lbl_total.setStyleSheet("color: #aaa; font-size: 10px;")
        self.slider_row.addWidget(self.lbl_total)
        
        # Hide slider row initially
        self.lbl_current.hide()
        self.slider.hide()
        self.lbl_total.hide()
        
        info_layout.addLayout(self.slider_row)
        
        info_layout.addStretch()
        layout.addLayout(info_layout)
        
        self.is_playing = False
        self.is_seeking = False

    def set_thumbnail(self, data):
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        scaled = pixmap.scaled(QSize(120, 68), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        x = (scaled.width() - 120) // 2
        y = (scaled.height() - 68) // 2
        cropped = scaled.copy(x, y, 120, 68)
        rounded = QPixmap(120, 68)
        rounded.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, 120, 68, 5, 5)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        self.thumb_label.setPixmap(rounded)
        self.thumb_label.setText("")

    def on_play_click(self):
        self.playClicked.emit(self.video_id)

    def set_playing_state(self, playing):
        self.is_playing = playing
        icon = QStyle.StandardPixmap.SP_MediaPause if playing else QStyle.StandardPixmap.SP_MediaPlay
        self.play_btn.setIcon(QIcon(QApplication.style().standardIcon(icon)))
        if playing:
            self.slider.show()
            self.lbl_current.show()
            self.lbl_total.show()
        else:
            pass 

    def format_time(self, ms):
        seconds = (ms // 1000) % 60
        minutes = (ms // 60000)
        return f"{minutes}:{seconds:02}"

    def update_slider(self, position, duration):
        if not self.is_seeking:
            self.slider.setMaximum(duration)
            self.slider.setValue(position)
        
        self.lbl_current.setText(self.format_time(position))
        self.lbl_total.setText(self.format_time(duration))

    def on_slider_move(self, position):
        self.lbl_current.setText(self.format_time(position))

    def on_slider_press(self):
        self.is_seeking = True

    def on_slider_release(self):
        self.is_seeking = False
        self.seekRequested.emit(self.video_id, self.slider.value())

    def reset_ui(self):
        self.set_playing_state(False)
        self.slider.hide()
        self.lbl_current.hide()
        self.lbl_total.hide()
        self.slider.setValue(0)
        self.lbl_current.setText("0:00")
        self.lbl_total.setText("0:00")

# --- Main Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Channel Fetcher")
        self.setGeometry(100, 100, 1000, 800)
        self.setStyleSheet(STYLESHEET)

        self.threadpool = QThreadPool()
        self.current_channel = None
        self.video_widgets = [] 
        self.video_map = {} # Map video_id to widget

        # Audio Player
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.positionChanged.connect(self.on_position_changed)
        self.player.durationChanged.connect(self.on_duration_changed)
        self.player.mediaStatusChanged.connect(self.on_media_status_changed)
        
        self.current_video_id = None
        self.is_fetching_url = False

        # Central Widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # Header / Search
        header_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter Channel ID or Handle (e.g. @GoogleDevelopers)")
        self.search_input.returnPressed.connect(self.start_new_search)
        header_layout.addWidget(self.search_input)

        self.search_btn = QPushButton("Fetch All Videos")
        self.search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_btn.clicked.connect(self.start_new_search)
        header_layout.addWidget(self.search_btn)

        main_layout.addLayout(header_layout)

        # Scroll Area for List
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("scrollContent")
        self.list_layout = QVBoxLayout(self.scroll_content) 
        self.list_layout.setSpacing(10)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll)

        # Status Label
        self.status_label = QLabel("Ready to fetch.")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.status_label)

    def start_new_search(self):
        channel = self.search_input.text().strip()
        if not channel:
            return

        # Stop any playing audio
        self.stop_current_video()
        
        self.current_channel = channel
        self.video_widgets.clear()
        self.video_map.clear()
        
        # Clear List
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self.status_label.setText("Fetching all videos... This might take a while.")
        self.search_btn.setEnabled(False)
        self.search_input.setEnabled(False)

        self.fetch_videos()

    def fetch_videos(self):
        worker = FetchWorker(self.current_channel)
        worker.signals.finished.connect(self.on_fetch_finished)
        worker.signals.error.connect(self.on_fetch_error)
        self.threadpool.start(worker)

    def on_fetch_finished(self, videos, _):
        self.search_btn.setEnabled(True)
        self.search_input.setEnabled(True)
        
        start_index = len(self.video_widgets)
        
        for i, video in enumerate(videos):
            card = VideoCard(video)
            # Connect signals
            card.playClicked.connect(self.handle_play_click)
            card.seekRequested.connect(self.handle_seek)
            
            self.list_layout.addWidget(card)
            self.video_widgets.append(card)
            self.video_map[video['id']] = card

            if video['thumbnail']:
                worker = ImageWorker(video['thumbnail'], start_index + i)
                worker.signals.image_loaded.connect(self.on_image_loaded)
                self.threadpool.start(worker)

        self.status_label.setText(f"Found {len(self.video_widgets)} videos.")

    def on_fetch_error(self, error):
        self.search_btn.setEnabled(True)
        self.search_input.setEnabled(True)
        self.status_label.setText("Error occurred.")
        QMessageBox.critical(self, "Error", str(error))

    def on_image_loaded(self, index, data):
        if 0 <= index < len(self.video_widgets):
            self.video_widgets[index].set_thumbnail(data)

    # --- Audio Player Logic ---
    def handle_play_click(self, video_id):
        if self.current_video_id == video_id:
            # Toggle Play/Pause
            if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.player.pause()
                self.video_map[video_id].set_playing_state(False)
            else:
                self.player.play()
                self.video_map[video_id].set_playing_state(True)
        else:
            # Stop previous and start new
            self.stop_current_video()
            self.current_video_id = video_id
            self.video_map[video_id].set_playing_state(True) # Show loading/playing state
            
            # Fetch URL
            self.status_label.setText("Fetching audio stream...")
            worker = StreamUrlWorker(video_id)
            worker.signals.url_ready.connect(self.on_url_ready)
            worker.signals.error.connect(self.on_stream_error)
            self.threadpool.start(worker)

    def stop_current_video(self):
        if self.current_video_id and self.current_video_id in self.video_map:
            self.video_map[self.current_video_id].reset_ui()
        self.player.stop()
        self.current_video_id = None

    def on_url_ready(self, video_id, url):
        if self.current_video_id != video_id:
            return # User switched video already
        
        self.player.setSource(QUrl(url))
        self.player.play()
        self.status_label.setText("Playing audio...")

    def on_stream_error(self, error):
        self.status_label.setText("Error fetching stream.")
        if self.current_video_id:
            self.video_map[self.current_video_id].set_playing_state(False)
        QMessageBox.warning(self, "Stream Error", str(error))

    def handle_seek(self, video_id, position):
        if self.current_video_id == video_id:
            self.player.setPosition(position)

    def on_position_changed(self, position):
        if self.current_video_id and self.current_video_id in self.video_map:
            duration = self.player.duration()
            self.video_map[self.current_video_id].update_slider(position, duration)

    def on_duration_changed(self, duration):
        if self.current_video_id and self.current_video_id in self.video_map:
            position = self.player.position()
            self.video_map[self.current_video_id].update_slider(position, duration)
            
    def on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.current_video_id:
                self.video_map[self.current_video_id].set_playing_state(False)
                self.video_map[self.current_video_id].slider.setValue(0)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    qdarktheme.setup_theme(additional_qss=STYLESHEET) 
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
