import sys
import os
import requests
import yt_dlp
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QScrollArea, QGridLayout, 
                             QFrame, QSizePolicy, QMessageBox, QSlider, QStyle, QStackedWidget,
                             QTabWidget, QCheckBox, QComboBox, QFileDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QRunnable, QThreadPool, QObject, QSize, QUrl, QSettings, QStandardPaths
from PyQt6.QtGui import QPixmap, QFont, QIcon, QColor, QPainter, QPainterPath
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
import qdarktheme
from youtube_api import YouTubeManager
from downloads import DownloadsView
import static_ffmpeg
static_ffmpeg.add_paths()

# --- Styles ---
# --- Styles ---
STYLESHEET = """
QMainWindow {
    background-color: #121212; /* Darker background */
}
/* Sidebar Styles */
QWidget#sidebar {
    background-color: #1e1e1e;
    border-right: 1px solid #2c2c2c;
}
QPushButton.nav-btn {
    background-color: transparent;
    color: #888;
    text-align: left;
    padding: 15px 20px;
    border: none;
    font-size: 14px;
    border-left: 3px solid transparent;
    font-family: "Segoe UI", sans-serif;
}
QPushButton.nav-btn:hover {
    background-color: #252525;
    color: #ddd;
}
QPushButton.nav-btn:checked {
    background-color: #2d2d2d;
    color: #fff;
    border-left: 3px solid #3ea6ff;
}

/* Content Styles */
QLineEdit {
    padding: 12px;
    border-radius: 20px; /* More rounded */
    border: 1px solid #333;
    background-color: #252525;
    color: #fff;
    font-size: 14px;
}
QLineEdit:focus {
    border: 1px solid #3ea6ff;
}
QPushButton.action-btn {
    padding: 10px 24px;
    border-radius: 20px;
    background-color: #3ea6ff;
    color: white;
    font-weight: bold;
    font-size: 14px;
    border: none;
}
QPushButton.action-btn:hover {
    background-color: #3095e8;
}
QPushButton.action-btn:pressed {
    background-color: #207bc4;
}
QPushButton.action-btn:disabled {
    background-color: #333;
    color: #666;
}
QScrollArea {
    border: none;
    background-color: transparent;
}
QWidget#scrollContent {
    background-color: transparent;
}
QLabel#statusLabel {
    color: #666;
    font-size: 12px;
    margin-top: 10px;
}

/* Slider Style - Glowing Effect */
QSlider::groove:horizontal {
    border: none;
    height: 4px;
    background: #333;
    margin: 2px 0;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00b4db, stop:1 #0083b0); /* Gradient Blue */
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #00b4db;
    border: 2px solid #00b4db;
    width: 10px;
    height: 10px;
    margin: -3px 0;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover {
    background: #fff;
}

/* Checkbox Style - Circular Button */
QCheckBox {
    spacing: 5px;
}
QCheckBox::indicator {
    width: 24px;
    height: 24px;
    border-radius: 12px;
    border: 2px solid #555;
    background: transparent;
}
QCheckBox::indicator:checked {
    border: 2px solid #3ea6ff;
    background: #3ea6ff;
    image: url(check_icon_placeholder); 
}
QCheckBox::indicator:hover {
    border-color: #777;
}

/* Tab Widget */
QTabWidget::pane {
    border: 1px solid #333;
    background: #1e1e1e;
}
QTabBar::tab {
    background: #252526;
    color: #aaa;
    padding: 10px 20px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
QTabBar::tab:selected {
    background: #1e1e1e;
    color: #fff;
    border-bottom: 2px solid #3ea6ff;
}
"""

CARD_STYLE = """
QFrame {
    background-color: #1f1f1f;
    border-radius: 16px;
    border: 1px solid #2c2c2c;
}
QFrame:hover {
    background-color: #252525;
    border: 1px solid #3ea6ff;
}
QLabel#titleLabel {
    color: #fff;
    font-weight: bold;
    font-size: 15px;
    font-family: "Segoe UI", sans-serif;
}
QLabel#dateLabel {
    color: #888;
    font-size: 11px;
}
QPushButton#controlBtn {
    background-color: #333;
    border: none;
    border-radius: 16px; 
}
QPushButton#controlBtn:hover {
    background-color: #444;
}
QPushButton#controlBtn:pressed {
    background-color: #222;
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
                'noplaylist': True,
                'extract_flat': False,
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
    playClicked = pyqtSignal(str) 
    seekRequested = pyqtSignal(str, int) 
    downloadClicked = pyqtSignal(str, str) # id, title

    def __init__(self, video_data):
        super().__init__()
        self.video_id = video_data['id']
        self.title = video_data['title']
        self.published_at = video_data['published_at'] 
        self.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border-radius: 12px;
                border: 1px solid #333;
            }
            QFrame:hover {
                border: 1px solid #444;
            }
            QLabel {
                background: transparent;
                border: none;
                font-family: "Segoe UI", sans-serif;
            }
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #333;
            }
        """)
        self.setFixedHeight(80) # More compact
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Main Layout: Horizontal
        layout = QHBoxLayout(self) 
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # 1. Left: Thumbnail
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(60, 60) 
        self.thumb_label.setStyleSheet("background-color: #121212; border-radius: 8px;")
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setText("")
        layout.addWidget(self.thumb_label)

        # 2. Center: Info & Controls
        center_layout = QVBoxLayout()
        center_layout.setSpacing(4)
        center_layout.setContentsMargins(0, 2, 0, 2)
        
        # Title
        self.title_label = QLabel(video_data['title'])
        self.title_label.setObjectName("titleLabel")
        self.title_label.setWordWrap(False) 
        self.title_label.setStyleSheet("color: #fff; font-weight: bold; font-size: 14px;")
        center_layout.addWidget(self.title_label)

        # Bottom Row: Date | Slider | Time | Controls
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(10)

        # Date Label
        date_str = video_data['published_at'].split('T')[0]
        self.date_label = QLabel(date_str)
        self.date_label.setStyleSheet("color: #888; font-size: 12px;")
        bottom_row.addWidget(self.date_label)
        
        # Slider
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.setFixedHeight(16)
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: none;
                height: 4px;
                background: #333;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #3ea6ff;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #3ea6ff;
                border: none;
                width: 10px;
                height: 10px;
                margin: -3px 0;
                border-radius: 5px;
            }
            QSlider::handle:horizontal:hover {
                background: #fff;
            }
        """)
        self.slider.sliderMoved.connect(self.on_slider_move)
        self.slider.sliderPressed.connect(self.on_slider_press)
        self.slider.sliderReleased.connect(self.on_slider_release)
        bottom_row.addWidget(self.slider)

        # Time Labels
        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setStyleSheet("color: #aaa; font-size: 11px;")
        bottom_row.addWidget(self.time_label)

        # Play Button
        self.play_btn = QPushButton()
        self.play_btn.setFixedSize(28, 28)
        self.play_btn.setIcon(QIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)))
        self.play_btn.setIconSize(QSize(14, 14))
        self.play_btn.clicked.connect(self.on_play_click)
        bottom_row.addWidget(self.play_btn)

        # Download Button
        self.download_btn = QPushButton()
        self.download_btn.setFixedSize(28, 28)
        self.download_btn.setIcon(QIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown))) 
        self.download_btn.setIconSize(QSize(14, 14))
        self.download_btn.clicked.connect(self.on_download_click)
        bottom_row.addWidget(self.download_btn)

        center_layout.addLayout(bottom_row)
        layout.addLayout(center_layout)

        # 3. Right: Checkbox
        self.checkbox = QCheckBox()
        self.checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.checkbox.setStyleSheet("""
            QCheckBox::indicator {
                width: 28px;
                height: 28px;
                border-radius: 14px;
                border: 2px solid #444;
                background: transparent;
            }
            QCheckBox::indicator:checked {
                background-color: #3ea6ff;
                border-color: #3ea6ff;
                image: url(none);
            }
            QCheckBox::indicator:hover {
                border-color: #666;
            }
        """)
        layout.addWidget(self.checkbox)

        self.is_playing = False
        self.is_seeking = False

    def is_checked(self):
        return self.checkbox.isChecked()

    def set_thumbnail(self, data):
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        
        # Crop to square 60x60
        size = 60
        scaled = pixmap.scaled(QSize(size, size), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        x = (scaled.width() - size) // 2
        y = (scaled.height() - size) // 2
        cropped = scaled.copy(x, y, size, size)
        
        # Rounded corners
        rounded = QPixmap(size, size)
        rounded.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, size, size, 8, 8)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        
        self.thumb_label.setPixmap(rounded)

    def on_play_click(self):
        self.playClicked.emit(self.video_id)

    def on_download_click(self):
        self.downloadClicked.emit(self.video_id, self.title)

    def set_playing_state(self, playing):
        self.is_playing = playing
        icon = QStyle.StandardPixmap.SP_MediaPause if playing else QStyle.StandardPixmap.SP_MediaPlay
        self.play_btn.setIcon(QIcon(QApplication.style().standardIcon(icon)))
        if playing:
            self.setStyleSheet(self.styleSheet() + "QFrame { border: 1px solid #3ea6ff; background-color: #2a2a2a; }")
        else:
            # Reset to default style (re-apply the init stylesheet)
            self.setStyleSheet("""
                QFrame {
                    background-color: #252526;
                    border-radius: 12px;
                    border: 1px solid #333;
                }
                QFrame:hover {
                    border: 1px solid #444;
                }
                QLabel {
                    background: transparent;
                    border: none;
                    font-family: "Segoe UI", sans-serif;
                }
                QPushButton {
                    background: transparent;
                    border: none;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #333;
                }
            """)

    def format_time(self, ms):
        seconds = (ms // 1000) % 60
        minutes = (ms // 60000)
        return f"{minutes}:{seconds:02}"

    def update_slider(self, position, duration):
        if not self.is_seeking:
            self.slider.setMaximum(duration)
            self.slider.setValue(position)
        
        curr = self.format_time(position)
        total = self.format_time(duration)
        self.time_label.setText(f"{curr} / {total}")

    def on_slider_move(self, position):
        pass

    def on_slider_press(self):
        self.is_seeking = True

    def on_slider_release(self):
        self.is_seeking = False
        self.seekRequested.emit(self.video_id, self.slider.value())

    def reset_ui(self):
        self.set_playing_state(False)
        self.slider.setValue(0)
        self.time_label.setText("0:00 / 0:00")

# --- Views ---

class HomeView(QWidget):
    requestDownload = pyqtSignal(str, str) # id, title

    def __init__(self):
        super().__init__()
        self.threadpool = QThreadPool()
        # ... (rest of init) ...
        self.current_channel = None
        self.video_widgets = [] 
        self.video_map = {} 

        # Audio Player
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.positionChanged.connect(self.on_position_changed)
        self.player.durationChanged.connect(self.on_duration_changed)
        self.player.mediaStatusChanged.connect(self.on_media_status_changed)
        
        self.current_video_id = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Header / Search
        header_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter Channel ID or Handle (e.g. @GoogleDevelopers)")
        self.search_input.returnPressed.connect(self.start_new_search)
        header_layout.addWidget(self.search_input)

        self.search_btn = QPushButton("Fetch All Videos")
        self.search_btn.setProperty("class", "action-btn")
        self.search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_btn.clicked.connect(self.start_new_search)
        header_layout.addWidget(self.search_btn)
        
        # Sort Dropdown
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Newest to Oldest", "Oldest to Newest"])
        self.sort_combo.currentIndexChanged.connect(self.sort_videos)
        self.sort_combo.setFixedWidth(150)
        self.sort_combo.setStyleSheet("""
            QComboBox {
                padding: 8px;
                border: 1px solid #333;
                border-radius: 6px;
                background-color: #252526;
                color: #fff;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        header_layout.addWidget(self.sort_combo)

        # Download Selected Button
        self.download_selected_btn = QPushButton("Download Selected")
        self.download_selected_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_selected_btn.clicked.connect(self.download_selected_videos)
        self.download_selected_btn.setStyleSheet("""
            QPushButton {
                background-color: #3ea6ff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #358cd6;
            }
        """)
        header_layout.addWidget(self.download_selected_btn)

        layout.addLayout(header_layout)

        # Scroll Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("scrollContent")
        self.list_layout = QVBoxLayout(self.scroll_content) 
        self.list_layout.setSpacing(10)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll.setWidget(self.scroll_content)
        layout.addWidget(self.scroll)

        # Status Label
        self.status_label = QLabel("Ready to fetch.")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

    def start_new_search(self):
        channel = self.search_input.text().strip()
        if not channel:
            return

        self.stop_current_video()
        self.current_channel = channel
        self.video_widgets.clear()
        self.video_map.clear()
        
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
            card.playClicked.connect(self.handle_play_click)
            card.seekRequested.connect(self.handle_seek)
            card.downloadClicked.connect(self.requestDownload.emit)
            self.list_layout.addWidget(card)
            self.video_widgets.append(card)
            self.video_map[video['id']] = card

            if video['thumbnail']:
                worker = ImageWorker(video['thumbnail'], start_index + i)
                worker.signals.image_loaded.connect(self.on_image_loaded)
                self.threadpool.start(worker)

        self.status_label.setText(f"Found {len(self.video_widgets)} videos.")
        self.sort_videos() 

    def sort_videos(self):
        if not self.video_widgets:
            return
            
        sort_mode = self.sort_combo.currentIndex() # 0 = Newest, 1 = Oldest
        
        # Remove all from layout
        for card in self.video_widgets:
            self.list_layout.removeWidget(card)
            
        # Sort
        reverse = (sort_mode == 0) 
        self.video_widgets.sort(key=lambda x: x.published_at, reverse=reverse)
        
        # Add back
        for card in self.video_widgets:
            self.list_layout.addWidget(card)

    def download_selected_videos(self):
        count = 0
        for card in self.video_widgets:
            if card.checkbox.isChecked():
                self.requestDownload.emit(card.video_id, card.title)
                count += 1
        
        if count > 0:
            QMessageBox.information(self, "Batch Download", f"Started {count} downloads.")
        else:
            QMessageBox.warning(self, "Batch Download", "No videos selected.")

    def on_fetch_error(self, error):
        self.search_btn.setEnabled(True)
        self.search_input.setEnabled(True)
        self.status_label.setText("Error occurred.")
        QMessageBox.critical(self, "Error", str(error))

    def on_image_loaded(self, index, data):
        if 0 <= index < len(self.video_widgets):
            self.video_widgets[index].set_thumbnail(data)

    def handle_play_click(self, video_id):
        if self.current_video_id == video_id:
            if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.player.pause()
                self.video_map[video_id].set_playing_state(False)
            else:
                self.player.play()
                self.video_map[video_id].set_playing_state(True)
        else:
            self.stop_current_video()
            self.current_video_id = video_id
            self.video_map[video_id].set_playing_state(True)
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
            return 
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

# Removed DownloadsView (Imported from downloads.py)

class SettingsView(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("YouTubeFetcher", "Config")
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setContentsMargins(40, 40, 40, 40)
        
        label = QLabel("Settings")
        label.setStyleSheet("font-size: 24px; font-weight: bold; color: #fff; margin-bottom: 20px;")
        layout.addWidget(label)
        
        form_layout = QVBoxLayout()
        form_layout.setSpacing(15)
        
        # Download Path
        path_label = QLabel("Download Path:")
        path_label.setStyleSheet("color: #aaa; font-size: 14px;")
        form_layout.addWidget(path_label)
        
        path_row = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setReadOnly(True)
        self.path_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                background-color: #252526;
                border: 1px solid #333;
                border-radius: 5px;
                color: #fff;
            }
        """)
        path_row.addWidget(self.path_input)
        
        browse_btn = QPushButton("Browse")
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.clicked.connect(self.browse_path)
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #333;
                color: white;
                border: none;
                padding: 10px 15px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #444;
            }
        """)
        path_row.addWidget(browse_btn)
        form_layout.addLayout(path_row)
        
        # API Key (Optional placeholder for now)
        api_label = QLabel("API Key (Restart Required):")
        api_label.setStyleSheet("color: #aaa; font-size: 14px; margin-top: 10px;")
        form_layout.addWidget(api_label)
        
        self.api_input = QLineEdit()
        self.api_input.setPlaceholderText("Enter YouTube API Key")
        self.api_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                background-color: #252526;
                border: 1px solid #333;
                border-radius: 5px;
                color: #fff;
            }
        """)
        form_layout.addWidget(self.api_input)
        
        # Save Button
        save_btn = QPushButton("Save Settings")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self.save_settings)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #3ea6ff;
                color: white;
                border: none;
                padding: 12px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
                margin-top: 20px;
            }
            QPushButton:hover {
                background-color: #358cd6;
            }
        """)
        form_layout.addWidget(save_btn)
        
        layout.addLayout(form_layout)
        
        self.load_settings()

    def browse_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if path:
            self.path_input.setText(path)

    def load_settings(self):
        # Default path
        default_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        saved_path = self.settings.value("download_path", default_path)
        self.path_input.setText(saved_path)
        
        # API Key
        api_key = self.settings.value("api_key", "")
        self.api_input.setText(api_key)

    def save_settings(self):
        self.settings.setValue("download_path", self.path_input.text())
        self.settings.setValue("api_key", self.api_input.text())
        QMessageBox.information(self, "Settings", "Settings saved successfully!")

class Sidebar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(200)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 20, 0, 20)
        layout.setSpacing(5)
        
        # Title
        title = QLabel("YT Fetcher")
        title.setStyleSheet("color: #fff; font-size: 18px; font-weight: bold; padding-left: 20px; margin-bottom: 20px;")
        layout.addWidget(title)
        
        # Buttons
        self.btn_home = self.create_nav_btn("Home", "home")
        self.btn_downloads = self.create_nav_btn("Downloads", "download")
        self.btn_settings = self.create_nav_btn("Settings", "settings")
        
        layout.addWidget(self.btn_home)
        layout.addWidget(self.btn_downloads)
        layout.addWidget(self.btn_settings)
        layout.addStretch()

    def create_nav_btn(self, text, icon_name):
        btn = QPushButton(text)
        btn.setProperty("class", "nav-btn")
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # We could add icons here if we had resources
        return btn

# --- Main Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Channel Fetcher")
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet(STYLESHEET)

        # Central Widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar()
        main_layout.addWidget(self.sidebar)

        # Stacked Content
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack)

        # Views
        self.home_view = HomeView()
        self.downloads_view = DownloadsView()
        self.settings_view = SettingsView()

        self.stack.addWidget(self.home_view)
        self.stack.addWidget(self.downloads_view)
        self.stack.addWidget(self.settings_view)

        # Connect Download Signal
        self.home_view.requestDownload.connect(self.downloads_view.add_download)
        self.home_view.requestDownload.connect(lambda: self.switch_view(1)) # Auto switch to downloads

        # Connect Navigation
        self.sidebar.btn_home.clicked.connect(lambda: self.switch_view(0))
        self.sidebar.btn_downloads.clicked.connect(lambda: self.switch_view(1))
        self.sidebar.btn_settings.clicked.connect(lambda: self.switch_view(2))

        # Set default
        self.sidebar.btn_home.setChecked(True)
        self.switch_view(0)

    def switch_view(self, index):
        self.stack.setCurrentIndex(index)
        # Update button states
        self.sidebar.btn_home.setChecked(index == 0)
        self.sidebar.btn_downloads.setChecked(index == 1)
        self.sidebar.btn_settings.setChecked(index == 2)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    qdarktheme.setup_theme(additional_qss=STYLESHEET) 
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
