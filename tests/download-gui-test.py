from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                             QPushButton, QListWidget, QLabel, QListWidgetItem, QWidget)
from PyQt6.QtCore import Qt
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.download_manager import DownloadManager, DownloadStatus

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Aura Download Manager")
        self.resize(800, 600)
        
        self.layout = QVBoxLayout()
        self.status_list = QListWidget()
        self.layout.addWidget(self.status_list)
        
        container = QWidget()
        container.setLayout(self.layout)
        self.setCentralWidget(container)
        
        # Initialize Manager
        self.manager = DownloadManager(max_concurrent=2)
        
        # Connect signals
        self.manager.task_added.connect(self.on_task_added)
        self.manager.task_updated.connect(self.on_task_updated)
        self.manager.task_finished.connect(self.on_task_finished)
        
        # Add a test button
        btn = QPushButton("Download Test File")
        btn.clicked.connect(self.test_download)
        self.layout.addWidget(btn)

    def test_download(self):
        # Test URL (Ubuntu ISO for size test)
        url = "https://ct.animeheaven.me/video.mp4?8b710918bd9a9dd4a37cc061238f46f4&d"
        dest = Path.home() / "Downloads"
        
        self.manager.add_download(url, dest)

    def on_task_added(self, data):
        item_id = data['task_id']
        item = QListWidgetItem(f"[{data['status']}] {data['filename']}")
        item.setData(Qt.ItemDataRole.UserRole, item_id)
        self.status_list.addItem(item)

    def on_task_updated(self, data):
        task_id = data['task_id']
        # Find item by ID
        items = self.status_list.findItems("*", Qt.MatchFlag.MatchWildcard)
        for item in items:
            if item.data(Qt.ItemDataRole.UserRole) == task_id:
                # Update text
                size_mb = data['downloaded'] / (1024*1024)
                total_mb = data['total'] / (1024*1024)
                speed_mbs = data['speed'] / (1024*1024)
                
                text = (f"[{data['status']}] {data['filename']}\n"
                         f"Progress: {data['progress']:.1f}% "
                         f"({size_mb:.1f}MB / {total_mb:.1f}MB) @ {speed_mbs:.2f} MB/s")
                item.setText(text)
                break

    def on_task_finished(self, stats, success, message):
        task_id = stats['task_id']
        items = self.status_list.findItems("*", Qt.MatchFlag.MatchWildcard)
        for item in items:
            if item.data(Qt.ItemDataRole.UserRole) == task_id:
                status = "COMPLETED" if success else "ERROR"
                text = (f"[{status}] {item.text().split(chr(10))[0]}\n"
                         f"Msg: {message}")
                item.setText(text)
                break

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())