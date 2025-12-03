import sys
import os
import requests
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QScrollArea, QGridLayout, 
                             QFrame, QSizePolicy, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal, QRunnable, QThreadPool, QObject, QSize
from PyQt6.QtGui import QPixmap, QFont, QIcon, QColor, QPainter, QPainterPath
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
"""

# --- Worker Signals ---
class WorkerSignals(QObject):
    finished = pyqtSignal(list, str) # videos, next_page_token
    error = pyqtSignal(str)
    image_loaded = pyqtSignal(int, bytes) # index, data

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

# --- Video Card Widget ---
class VideoCard(QFrame):
    def __init__(self, video_data):
        super().__init__()
        self.setStyleSheet(CARD_STYLE)
        self.setFixedHeight(90) # Compact height
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QHBoxLayout(self) # Horizontal layout
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # Thumbnail
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(120, 68) # Smaller thumbnail (16:9 approx)
        self.thumb_label.setStyleSheet("background-color: #1a1a1a; border-radius: 5px;")
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setText("Loading...")
        layout.addWidget(self.thumb_label)

        # Info Area
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        # Title
        self.title_label = QLabel(video_data['title'])
        self.title_label.setObjectName("titleLabel")
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        # Adjust font size via stylesheet if needed, or here
        info_layout.addWidget(self.title_label)

        # Date
        date_str = video_data['published_at'].split('T')[0]
        self.date_label = QLabel(date_str)
        self.date_label.setObjectName("dateLabel")
        info_layout.addWidget(self.date_label)
        
        info_layout.addStretch()
        layout.addLayout(info_layout)

    def set_thumbnail(self, data):
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        
        # Scale and crop to fill 120x68
        scaled = pixmap.scaled(QSize(120, 68), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        
        # Center crop
        x = (scaled.width() - 120) // 2
        y = (scaled.height() - 68) // 2
        cropped = scaled.copy(x, y, 120, 68)
        
        # Apply rounded corners
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

# --- Main Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Channel Fetcher")
        self.setGeometry(100, 100, 1000, 800)
        self.setStyleSheet(STYLESHEET)

        self.threadpool = QThreadPool()
        self.current_channel = None
        self.video_widgets = [] # Keep track to update images

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
        self.list_layout = QVBoxLayout(self.scroll_content) # Vertical Layout
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

        self.current_channel = channel
        self.video_widgets.clear()
        
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
        
        # Add cards to list
        for i, video in enumerate(videos):
            card = VideoCard(video)
            self.list_layout.addWidget(card)
            self.video_widgets.append(card)

            # Load thumbnail
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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Apply dark theme base, but we override with our stylesheet
    qdarktheme.setup_theme(additional_qss=STYLESHEET) 
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
