# gui.py
import sys
import os
import asyncio
import logging
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLineEdit, QPushButton, QListWidget, 
                             QTextEdit, QMessageBox, QLabel)
from PyQt6.QtCore import QThread, pyqtSignal, Qt

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.engine import AnimeHeavenEngine

# ---------------------------------------------------------
# LOGGING BRIDGE: Sends logger messages to the GUI
# ---------------------------------------------------------
class QtLogHandler(logging.Handler):
    def __init__(self, signal):
        super().__init__()
        self.signal = signal

    def emit(self, record):
        msg = self.format(record)
        self.signal.emit(msg)

# ---------------------------------------------------------
# WORKER THREAD: Runs Async Engine in a separate thread
# ---------------------------------------------------------
class EngineWorker(QThread):
    log_signal = pyqtSignal(str)
    result_signal = pyqtSignal(list)
    error_signal = pyqtSignal(str)

    def __init__(self, query):
        super().__init__()
        self.query = query

    def run(self):
        # This function runs in the worker thread
        # We use asyncio.run() to execute the async code
        async def async_job():
            engine = AnimeHeavenEngine(headless=True)
            try:
                await engine.start()
                results = await engine.search_anime(self.query)
                return results
            except Exception as e:
                raise e
            finally:
                await engine.close()

        try:
            # Redirect python logging to our Qt signal handler
            handler = QtLogHandler(self.log_signal)
            handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            
            # Attach to root logger so we see engine logs
            logging.getLogger().addHandler(handler)
            # Set level to INFO so we see the "Detected Chrome" messages
            logging.getLogger().setLevel(logging.INFO)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = loop.run_until_complete(async_job())
            self.result_signal.emit(results)
            
        except Exception as e:
            self.error_signal.emit(str(e))

# ---------------------------------------------------------
# MAIN WINDOW
# ---------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Aura - Anime Searcher")
        self.resize(800, 600)

        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Search Area
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter anime name...")
        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self.start_search)
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_btn)
        layout.addLayout(search_layout)

        # Log Area (To see browser status)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(150)
        self.log_output.setStyleSheet("background-color: #2b2b2b; color: #00ff00; font-family: Consolas;")
        layout.addWidget(QLabel("Engine Log:"))
        layout.addWidget(self.log_output)

        # Results Area
        self.results_list = QListWidget()
        layout.addWidget(QLabel("Search Results:"))
        layout.addWidget(self.results_list)

        self.worker = None

    def append_log(self, message):
        self.log_output.append(message)
        # Auto scroll
        sb = self.log_output.verticalScrollBar()
        sb.setValue(sb.maximum())

    def start_search(self):
        query = self.search_input.text().strip()
        if not query:
            return

        self.search_btn.setEnabled(False)
        self.results_list.clear()
        self.append_log(f"GUI: Starting search for '{query}'...")

        self.worker = EngineWorker(query)
        self.worker.log_signal.connect(self.append_log)
        self.worker.result_signal.connect(self.on_results)
        self.worker.error_signal.connect(self.on_error)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def on_results(self, results):
        self.append_log(f"GUI: Received {len(results)} results.")
        for res in results:
            self.results_list.addItem(f"{res['title']} - {res['url']}")
        self.search_btn.setEnabled(True)

    def on_error(self, error_msg):
        self.append_log(f"GUI: Error occurred - {error_msg}")
        QMessageBox.critical(self, "Error", error_msg)
        self.search_btn.setEnabled(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())