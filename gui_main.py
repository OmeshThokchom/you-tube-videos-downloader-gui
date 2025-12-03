import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QMessageBox, QAbstractItemView)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRunnable, QThreadPool, QObject
from PyQt6.QtGui import QPixmap
import qdarktheme
import requests
from youtube_api import YouTubeManager

# --- Worker Signals ---
class WorkerSignals(QObject):
    finished = pyqtSignal(list) # list of video dicts
    error = pyqtSignal(str)

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
            self.signals.finished.emit(videos)
        except Exception as e:
            self.signals.error.emit(str(e))

# --- Image Loader Worker ---
class ImageLoader(QRunnable):
    def __init__(self, url, row, table):
        super().__init__()
        self.url = url
        self.row = row
        self.table = table # Be careful with thread safety here, usually we emit signal
        # For simplicity in this demo, we'll emit a signal to update UI
        self.signals = WorkerSignals() # Reusing signals class for convenience? No, need specific
    
    # Let's do it properly with signals
    pass

class ImageSignals(QObject):
    loaded = pyqtSignal(int, bytes)

class ImageWorker(QRunnable):
    def __init__(self, url, row):
        super().__init__()
        self.url = url
        self.row = row
        self.signals = ImageSignals()

    def run(self):
        try:
            data = requests.get(self.url).content
            self.signals.loaded.emit(self.row, data)
        except:
            pass

# --- Main Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Channel Fetcher")
        self.setGeometry(100, 100, 1000, 700)

        self.threadpool = QThreadPool()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Input Area
        input_layout = QHBoxLayout()
        self.channel_input = QLineEdit()
        self.channel_input.setPlaceholderText("Enter Channel ID or Handle (e.g., @GoogleDevelopers)")
        input_layout.addWidget(self.channel_input)

        self.fetch_btn = QPushButton("Fetch Videos")
        self.fetch_btn.clicked.connect(self.start_fetch)
        input_layout.addWidget(self.fetch_btn)
        self.layout.addLayout(input_layout)

        # Status
        self.status_label = QLabel("Ready")
        self.layout.addWidget(self.status_label)

        # Results Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Thumbnail", "Title", "Published", "Video ID"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(90) # Height for thumbnails
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.layout.addWidget(self.table)

    def start_fetch(self):
        channel = self.channel_input.text().strip()
        if not channel:
            QMessageBox.warning(self, "Error", "Please enter a channel ID")
            return

        self.status_label.setText("Fetching videos... This may take a while for large channels.")
        self.fetch_btn.setEnabled(False)
        self.table.setRowCount(0)

        worker = FetchWorker(channel)
        worker.signals.finished.connect(self.on_fetch_finished)
        worker.signals.error.connect(self.on_fetch_error)
        self.threadpool.start(worker)

    def on_fetch_finished(self, videos):
        self.status_label.setText(f"Found {len(videos)} videos.")
        self.fetch_btn.setEnabled(True)
        
        self.table.setRowCount(len(videos))
        for i, video in enumerate(videos):
            # Thumbnail (Placeholder first)
            self.table.setItem(i, 0, QTableWidgetItem("Loading..."))
            
            # Title
            self.table.setItem(i, 1, QTableWidgetItem(video['title']))
            
            # Published
            self.table.setItem(i, 2, QTableWidgetItem(video['published_at']))
            
            # ID
            self.table.setItem(i, 3, QTableWidgetItem(video['id']))

            # Load Image
            if video['thumbnail']:
                img_worker = ImageWorker(video['thumbnail'], i)
                img_worker.signals.loaded.connect(self.on_image_loaded)
                self.threadpool.start(img_worker)

    def on_fetch_error(self, error):
        self.status_label.setText("Error occurred.")
        self.fetch_btn.setEnabled(True)
        QMessageBox.critical(self, "API Error", str(error))

    def on_image_loaded(self, row, data):
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        pixmap = pixmap.scaledToHeight(80, Qt.TransformationMode.SmoothTransformation)
        
        label = QLabel()
        label.setPixmap(pixmap)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setCellWidget(row, 0, label)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    qdarktheme.setup_theme()
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
