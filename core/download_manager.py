# core/download_manager.py
import os
import uuid
import shutil
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QMutex, QMutexLocker
from pysmartdl2 import SmartDL

# ----------------------------------------------------------------------
# Data Models
# ----------------------------------------------------------------------
class DownloadStatus:
    QUEUED = "Queued"
    DOWNLOADING = "Downloading"
    PAUSED = "Paused"
    COMPLETED = "Completed"
    ERROR = "Error"
    CANCELLED = "Cancelled"

class DownloadTask:
    def __init__(self, task_id, url, dest_folder, filename=None):
        self.id = task_id
        self.url = url
        self.dest_folder = Path(dest_folder)
        self.filename = filename
        self.status = DownloadStatus.QUEUED
        
        # Runtime stats
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.speed = 0  # Bytes per second
        self.progress_percentage = 0.0
        
        # Internal components
        self.worker = None      # The QThread running this task
        self.smart_dl = None   # The PySmartDL instance
        self.dest_path = None  # Full path once resolved

# ----------------------------------------------------------------------
# Worker Thread (Runs the download in background)
# ----------------------------------------------------------------------
class DownloadWorker(QThread):
    # Signals to notify the GUI/Manager
    progress_signal = pyqtSignal(dict)  # { task_id: str, ...stats }
    finished_signal = pyqtSignal(dict, bool, str) # {task_id}, success_bool, error_msg

    def __init__(self, task):
        super().__init__()
        self.task = task
        self._is_running = True

    def run(self):
        # Determine destination path
        if not self.task.dest_folder.exists():
            self.task.dest_folder.mkdir(parents=True, exist_ok=True)
        
        # PySmartDL logic
        # We set threads=8 for high speed (multi-part)
        # progress_bar=False because we handle it manually
        try:
            self.task.status = DownloadStatus.DOWNLOADING
            dest = self.task.dest_folder / self.task.filename if self.task.filename else self.task.dest_folder
            
            self.task.smart_dl = SmartDL(
                self.task.url, 
                dest=dest,
                progress_bar=False,
                threads=8, # Multi-threaded download
                connections=8
            )
            
            # Hook up pysmartdl's internal progress updates
            self.task.smart_dl.add_hook(self._hook_handler)
            
            # Start blocking download
            self.task.smart_dl.start(blocking=True)
            
            # If we get here, it finished successfully
            self.task.status = DownloadStatus.COMPLETED
            self.task.progress_percentage = 100.0
            self.task.downloaded_bytes = self.task.total_bytes
            
            # Emit final success
            stats = self._get_stats()
            self.finished_signal.emit(stats, True, "Download Completed")

        except Exception as e:
            self.task.status = DownloadStatus.ERROR
            self.task.smart_dl = None # Clean up
            self.finished_signal.emit({"task_id": self.task.id}, False, str(e))

    def _hook_handler(self, obj):
        """
        Callback from pysmartdl2 during download.
        obj contains: dl_size, downloaded, speed, etc.
        """
        # Update task state
        self.task.downloaded_bytes = obj.downloaded
        self.task.total_bytes = obj.filesize if hasattr(obj, 'filesize') else obj.dl_size
        self.task.speed = obj.speed
        
        if self.task.total_bytes > 0:
            self.task.progress_percentage = (self.task.downloaded_bytes / self.task.total_bytes) * 100
            
        # Emit progress update to GUI
        self.progress_signal.emit(self._get_stats())

    def _get_stats(self):
        """Return a dict with current stats."""
        return {
            "task_id": self.task.id,
            "url": self.task.url,
            "filename": self.task.smart_dl.get_dest() if self.task.smart_dl else self.task.filename or "Unknown",
            "downloaded": self.task.downloaded_bytes,
            "total": self.task.total_bytes,
            "speed": self.task.speed,
            "progress": self.task.progress_percentage,
            "status": self.task.status
        }

    def pause(self):
        if self.task.smart_dl:
            self.task.status = DownloadStatus.PAUSED
            self.task.smart_dl.stop()
            self.wait() # Wait for thread to finish blocking
            return True
        return False

    def resume(self):
        # PySmartDL resumes automatically if target file exists and is partial
        if self.task.status == DownloadStatus.PAUSED:
            self.task.status = DownloadStatus.QUEUED # Move back to manager queue
            return True
        return False

# ----------------------------------------------------------------------
# Manager: Handles Queue and UI Communication
# ----------------------------------------------------------------------
class DownloadManager(QObject):
    # Signals for the Main Window to connect to
    task_added = pyqtSignal(dict)
    task_updated = pyqtSignal(dict)
    task_finished = pyqtSignal(dict, bool, str) # task_dict, success, message
    
    def __init__(self, max_concurrent=3):
        super().__init__()
        self.active_tasks = {} # id -> DownloadTask
        self.queue = []
        self.max_concurrent = max_concurrent
        self.mutex = QMutex()

    def add_download(self, url, dest_folder, filename=None):
        """
        Add a new download to the queue.
        """
        task_id = str(uuid.uuid4())
        
        # If filename is not provided, we guess it or let PySmartDL handle it
        # But for consistent tracking, it's better to know it early if possible.
        # PySmartDL will resolve it on start.
        
        new_task = DownloadTask(task_id, url, dest_folder, filename)
        
        with QMutexLocker(self.mutex):
            self.active_tasks[task_id] = new_task
            self.queue.append(new_task)
        
        # Notify UI
        initial_stats = {
            "task_id": task_id,
            "url": url,
            "filename": filename or "Resolving...",
            "downloaded": 0,
            "total": 0,
            "speed": 0,
            "progress": 0.0,
            "status": DownloadStatus.QUEUED
        }
        self.task_added.emit(initial_stats)
        
        # Trigger processing
        self._process_queue()

    def pause_download(self, task_id):
        with QMutexLocker(self.mutex):
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                if task.worker and task.worker.isRunning():
                    task.worker.pause()
                    task.status = DownloadStatus.PAUSED
                    self.task_updated.emit({"task_id": task_id, "status": task.status})

    def cancel_download(self, task_id):
        with QMutexLocker(self.mutex):
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                if task.worker:
                    if task.worker.isRunning():
                        task.worker.terminate() # Force kill
                        task.worker.wait()
                
                # Cleanup partial file
                if task.smart_dl and task.smart_dl.get_dest() and Path(task.smart_dl.get_dest()).exists():
                    Path(task.smart_dl.get_dest()).unlink()
                
                task.status = DownloadStatus.CANCELLED
                # Remove from active (optional, or keep as 'Cancelled' for history)
                self.task_updated.emit({"task_id": task_id, "status": task.status})

    def resume_download(self, task_id):
        with QMutexLocker(self.mutex):
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                if task.status == DownloadStatus.PAUSED:
                    task.resume() # Logic handled by checking status in run
                    self.queue.append(task) # Re-add to end of queue
                    self._process_queue()

    def _process_queue(self):
        """Start tasks from queue if slots available."""
        with QMutexLocker(self.mutex):
            running = [t for t in self.active_tasks.values() 
                       if t.status == DownloadStatus.DOWNLOADING]
            
            while len(running) < self.max_concurrent and self.queue:
                # Get next queued task
                # Filter out paused/cancelled tasks from queue
                task = self.queue.pop(0)
                if task.status == DownloadStatus.QUEUED:
                    self._start_task(task)
                    running.append(task)

    def _start_task(self, task):
        # Create worker
        worker = DownloadWorker(task)
        task.worker = worker
        
        # Connect signals
        worker.progress_signal.connect(self._on_progress)
        worker.finished_signal.connect(self._on_finished)
        
        worker.start()

    def _on_progress(self, stats):
        # Forward stats to GUI
        self.task_updated.emit(stats)

    def _on_finished(self, stats, success, message):
        # This is called when a thread finishes
        task_id = stats.get("task_id")
        
        with QMutexLocker(self.mutex):
            if task_id in self.active_tasks:
                # Update internal state
                self.active_tasks[task_id].status = DownloadStatus.COMPLETED if success else DownloadStatus.ERROR
                
                # Process next in queue
                self._process_queue()
        
        # Notify GUI
        # Note: stats dict might be partial on error, so we ensure ID is there
        if not success:
            stats = {"task_id": task_id}
            
        self.task_finished.emit(stats, success, message)