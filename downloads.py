import os
import re
import yt_dlp
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, 
                             QScrollArea, QFrame, QPushButton, QMessageBox, QTabWidget)
from PyQt6.QtCore import Qt, pyqtSignal, QRunnable, QThreadPool, QObject, QSettings, QStandardPaths

# --- Worker Signals ---
class DownloadSignals(QObject):
    progress = pyqtSignal(dict) # percent, speed, eta, total_bytes
    finished = pyqtSignal(str) # filename
    error = pyqtSignal(str)

# --- Logger ---
class MyLogger:
    def debug(self, msg):
        pass
    def warning(self, msg):
        pass
    def error(self, msg):
        print(msg)

# --- Download Worker ---
class DownloadWorker(QRunnable):
    def __init__(self, video_id, title, download_path="downloads"):
        super().__init__()
        self.video_id = video_id
        self.title = title
        self.download_path = download_path
        self.signals = DownloadSignals()
        
        if not os.path.exists(self.download_path):
            os.makedirs(self.download_path)

    def run(self):
        def progress_hook(d):
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)
                
                if total > 0:
                    percent = (downloaded / total) * 100
                else:
                    percent = 0
                
                def strip_ansi(text):
                    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                    return ansi_escape.sub('', text)

                speed = strip_ansi(d.get('_speed_str', 'N/A'))
                eta = strip_ansi(d.get('_eta_str', 'N/A'))
                total_str = strip_ansi(d.get('_total_bytes_str', 'N/A'))
                
                self.signals.progress.emit({
                    'percent': percent,
                    'speed': speed,
                    'eta': eta,
                    'total': total_str,
                    'status': 'Downloading'
                })
            elif d['status'] == 'finished':
                self.signals.progress.emit({
                    'percent': 100,
                    'speed': '-',
                    'eta': '0s',
                    'total': d.get('_total_bytes_str', 'N/A'),
                    'status': 'Converting'
                })

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(self.download_path, '%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
            }],
            'progress_hooks': [progress_hook],
            'logger': MyLogger(),
            'quiet': True,
            'no_warnings': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"https://www.youtube.com/watch?v={self.video_id}"])
            self.signals.finished.emit(self.title)
        except Exception as e:
            self.signals.error.emit(str(e))

# --- Download Item Widget ---
class DownloadItemWidget(QFrame):
    def __init__(self, title):
        super().__init__()
        self.setFixedHeight(100)
        self.setStyleSheet("""
            QFrame#downloadCard {
                background-color: #252526;
                border-radius: 12px;
                border: 1px solid #333;
            }
            QLabel {
                background: transparent;
                border: none;
                font-family: "Segoe UI", sans-serif;
            }
            QProgressBar {
                border: none;
                background-color: #333;
                height: 4px;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #3ea6ff;
                border-radius: 2px;
            }
        """)
        self.setObjectName("downloadCard")
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # 1. Icon (Blue Square with WAV)
        self.icon_label = QLabel("WAV")
        self.icon_label.setFixedSize(50, 50)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet("""
            background-color: #3ea6ff;
            color: white;
            font-weight: bold;
            font-size: 14px;
            border-radius: 8px;
        """)
        main_layout.addWidget(self.icon_label)
        
        # 2. Content Area
        content_layout = QVBoxLayout()
        content_layout.setSpacing(4)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #fff; font-weight: bold; font-size: 14px;")
        content_layout.addWidget(self.title_label)
        
        # "Size" Label (Small header)
        self.size_header = QLabel("Size")
        self.size_header.setStyleSheet("color: #888; font-size: 11px;")
        content_layout.addWidget(self.size_header)
        
        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        content_layout.addWidget(self.progress_bar)
        
        # Bottom Row: Size Value | ETA
        bottom_row = QHBoxLayout()
        
        self.size_value = QLabel("Calculating...")
        self.size_value.setStyleSheet("color: #aaa; font-size: 12px;")
        bottom_row.addWidget(self.size_value)
        
        bottom_row.addStretch()
        
        self.eta_label = QLabel("")
        self.eta_label.setStyleSheet("color: #aaa; font-size: 12px;")
        bottom_row.addWidget(self.eta_label)
        
        content_layout.addLayout(bottom_row)
        main_layout.addLayout(content_layout)

        self.current_size = "0 B" # Store size

    def update_progress(self, data):
        self.progress_bar.setValue(int(data['percent']))
        
        # Update Size Value
        if 'total' in data and data['total'] != 'N/A':
            self.size_value.setText(data['total'])
            self.current_size = data['total']
        
        # Update ETA / Status
        if data['status'] == 'Downloading':
             self.eta_label.setText(f"{data['eta']} left")
        else:
             self.eta_label.setText(data['status'])

    def set_finished(self):
        self.progress_bar.setValue(100)
        self.eta_label.setText("Completed")
        self.eta_label.setStyleSheet("color: #4caf50; font-weight: bold; font-size: 12px;")
        self.size_value.setText(self.current_size) # Show final size

    def set_error(self, error):
        self.eta_label.setText("Error")
        self.eta_label.setStyleSheet("color: #f44336; font-weight: bold; font-size: 12px;")
        self.size_value.setText("Failed")

# --- Downloads View ---
class DownloadsView(QWidget):
    def __init__(self):
        super().__init__()
        self.threadpool = QThreadPool()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        header = QLabel("Downloads")
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #fff; margin-bottom: 20px;")
        layout.addWidget(header)
        
        # Tabs
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Active Tab
        self.active_widget = QWidget()
        self.active_widget.setStyleSheet("background: transparent;")
        self.active_layout = QVBoxLayout(self.active_widget)
        self.active_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.active_layout.setSpacing(10)
        
        active_scroll = QScrollArea()
        active_scroll.setWidgetResizable(True)
        active_scroll.setWidget(self.active_widget)
        active_scroll.setStyleSheet("background: transparent; border: none;")
        self.tabs.addTab(active_scroll, "Active")
        
        # Completed Tab
        self.completed_widget = QWidget()
        self.completed_widget.setStyleSheet("background: transparent;")
        self.completed_layout = QVBoxLayout(self.completed_widget)
        self.completed_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.completed_layout.setSpacing(10)
        
        completed_scroll = QScrollArea()
        completed_scroll.setWidgetResizable(True)
        completed_scroll.setWidget(self.completed_widget)
        completed_scroll.setStyleSheet("background: transparent; border: none;")
        self.tabs.addTab(completed_scroll, "Completed")

    def add_download(self, video_id, title):
        # Get Path from Settings
        settings = QSettings("YouTubeFetcher", "Config")
        default_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        download_path = settings.value("download_path", default_path)

        # Create Widget
        item = DownloadItemWidget(title)
        self.active_layout.insertWidget(0, item) # Add to top
        
        # Create Worker
        worker = DownloadWorker(video_id, title, download_path)
        worker.signals.progress.connect(item.update_progress)
        worker.signals.finished.connect(lambda: self.on_download_finished(item))
        worker.signals.error.connect(item.set_error)
        
        self.threadpool.start(worker)
        self.tabs.setCurrentIndex(0)

    def on_download_finished(self, item):
        item.set_finished()
        # Move to completed
        self.active_layout.removeWidget(item)
        self.completed_layout.insertWidget(0, item)
        item.setParent(self.completed_widget) # Reparent explicitly just in case
