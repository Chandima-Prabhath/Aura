# core/download_manager.py
import os
import uuid
import json
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Callable
from pysmartdl2 import SmartDL
from core.logger import get_logger

logger = get_logger(__name__)

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
        self.progress = 0.0
        self.error_message = None
        
        # Internal components
        self.smart_dl: Optional[SmartDL] = None
        self.dest_path = None
        self._stop_event = threading.Event()

    def to_dict(self):
        """Serialize task to dictionary."""
        return {
            "id": self.id,
            "url": self.url,
            "dest_folder": str(self.dest_folder),
            "filename": self.filename,
            "status": self.status,
            "downloaded": self.downloaded_bytes,
            "total": self.total_bytes,
            "progress": self.progress,
            "speed": self.speed,
            "error": self.error_message
        }
    
    @classmethod
    def from_dict(cls, data):
        """Deserialize task from dictionary."""
        task = cls(
            data["id"], 
            data["url"], 
            data["dest_folder"], 
            data["filename"]
        )
        task.status = data.get("status", DownloadStatus.QUEUED)
        task.downloaded_bytes = data.get("downloaded", 0)
        task.total_bytes = data.get("total", 0)
        task.progress = data.get("progress", 0.0)
        return task

# ----------------------------------------------------------------------
# Manager
# ----------------------------------------------------------------------
class DownloadManager:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DownloadManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, max_concurrent=3, persistence_file="downloads.json"):
        if hasattr(self, "_initialized"):
            return
            
        self.max_concurrent = max_concurrent
        self.persistence_file = persistence_file
        
        self.tasks: Dict[str, DownloadTask] = {} # id -> DownloadTask
        self.queue: List[str] = [] # List of task_ids
        
        self.lock = threading.RLock()
        self.running_threads: Dict[str, threading.Thread] = {}
        
        # Callbacks: List of functions (task_dict) -> None
        self.progress_callbacks: List[Callable] = [] 
        self.completion_callbacks: List[Callable] = [] # (task_dict, success, message)
        
        self._initialized = True
        self._load_state()
        
        # Start the queue processor
        self.processor_thread = threading.Thread(target=self._queue_processor_loop, daemon=True)
        self.processor_thread.start()
        
    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    
    def add_download(self, url: str, dest_folder: str, filename: str = None) -> str:
        """Add a new download task."""
        task_id = str(uuid.uuid4())
        task = DownloadTask(task_id, url, dest_folder, filename)
        
        with self.lock:
            self.tasks[task_id] = task
            self.queue.append(task_id)
            self._save_state()
            
        logger.info(f"Added download task: {task_id} - {url}")
        self._notify_progress(task)
        return task_id

    def pause_download(self, task_id: str):
        with self.lock:
            task = self.tasks.get(task_id)
            if task and task.status == DownloadStatus.DOWNLOADING:
                if task_id in self.running_threads:
                    # PySmartDL blocking call cannot be easily interrupted nicely without stop()
                    # But stop() is called on the object.
                    if task.smart_dl:
                        task.smart_dl.stop() 
                    task.status = DownloadStatus.PAUSED
                    self._save_state()
                    logger.info(f"Paused task: {task_id}")
                    self._notify_progress(task)

    def resume_download(self, task_id: str):
        with self.lock:
            task = self.tasks.get(task_id)
            if task and task.status == DownloadStatus.PAUSED:
                task.status = DownloadStatus.QUEUED
                if task_id not in self.queue:
                    self.queue.append(task_id)
                self._save_state()
                logger.info(f"Resumed task: {task_id}")
                self._notify_progress(task)

    def cancel_download(self, task_id: str):
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                return

            if task.status == DownloadStatus.DOWNLOADING:
                if task.smart_dl:
                    task.smart_dl.stop()
            
            task.status = DownloadStatus.CANCELLED
            if task_id in self.queue:
                self.queue.remove(task_id)
            
            # Cleanup partial files
            try:
                if task.smart_dl:
                    path = task.smart_dl.get_dest()
                    if path and os.path.exists(path):
                        os.remove(path)
                elif task.filename:
                    path = Path(task.dest_folder) / task.filename
                    if path.exists():
                        path.unlink()
            except Exception as e:
                logger.error(f"Error cleaning up cancelled task {task_id}: {e}")

            self._save_state()
            self._notify_progress(task)

    def get_task(self, task_id: str) -> Optional[Dict]:
        with self.lock:
            task = self.tasks.get(task_id)
            return task.to_dict() if task else None

    def get_all_tasks(self) -> List[Dict]:
        with self.lock:
            return [t.to_dict() for t in self.tasks.values()]

    def add_progress_callback(self, callback: Callable):
        self.progress_callbacks.append(callback)

    def add_completion_callback(self, callback: Callable):
        self.completion_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Internal Logic
    # ------------------------------------------------------------------
    
    def _queue_processor_loop(self):
        """Background thread to monitor and start queued tasks."""
        while True:
            with self.lock:
                # Clean up finished threads
                finished_ids = []
                for tid, thread in self.running_threads.items():
                    if not thread.is_alive():
                        finished_ids.append(tid)
                
                for tid in finished_ids:
                    del self.running_threads[tid]

                # Check slots
                active_count = len(self.running_threads)
                slots = self.max_concurrent - active_count
                
                # Start new tasks
                if slots > 0:
                    # Get next eligible task
                    candidate_id = None
                    for tid in self.queue:
                        task = self.tasks[tid]
                        if task.status == DownloadStatus.QUEUED:
                            candidate_id = tid
                            break
                    
                    if candidate_id:
                        self.queue.remove(candidate_id)
                        self._start_task_thread(candidate_id)
            
            time.sleep(1) # Check every second

    def _start_task_thread(self, task_id):
        task = self.tasks[task_id]
        task.status = DownloadStatus.DOWNLOADING
        
        thread = threading.Thread(
            target=self._download_worker, 
            args=(task,),
            name=f"Download-{task_id}",
            daemon=True
        )
        self.running_threads[task_id] = thread
        thread.start()
        logger.info(f"Started download thread for {task_id}")

    def _download_worker(self, task: DownloadTask):
        try:
            if not task.dest_folder.exists():
                task.dest_folder.mkdir(parents=True, exist_ok=True)

            dest = str(task.dest_folder / task.filename) if task.filename else str(task.dest_folder)
            
            # PySmartDL Setup
            # threads=5 is a good balance
            obj = SmartDL(task.url, dest, progress_bar=False, threads=5)
            task.smart_dl = obj
            
            # Start (Non-blocking)
            obj.start(blocking=False)
            
            while not obj.isFinished():
                # Check for stop request (pause/cancel)
                if task.status != DownloadStatus.DOWNLOADING:
                     if not obj.isFinished():
                        obj.stop()
                     break

                try:
                    # Update stats safely
                    task.speed = obj.get_speed(human=False)
                    task.downloaded_bytes = obj.get_dl_size()
                    total = obj.get_final_filesize()
                    if total:
                        task.total_bytes = total
                        task.progress = (task.downloaded_bytes / total) * 100
                    
                    self._notify_progress(task)
                except Exception:
                    # Ignore errors during stat fetch (e.g. might have finished)
                    pass
                    
                time.sleep(0.2)

            if obj.isSuccessful():
                task.status = DownloadStatus.COMPLETED
                task.progress = 100.0
                # Final safe stat update
                try:
                    task.total_bytes = obj.get_final_filesize() or task.total_bytes
                    task.downloaded_bytes = task.total_bytes
                    task.filename = Path(obj.get_dest()).name
                except:
                    pass
                
                logger.info(f"Task {task.id} completed successfully.")
                self._notify_completion(task, True, "Download Completed")
                
            else:
                # If we stopped manually, it might not be successful, but check status
                if task.status in [DownloadStatus.PAUSED, DownloadStatus.CANCELLED]:
                    return 

                # Genuine error
                err = "Unknown error"
                try:
                   err = str(obj.get_errors())
                except:
                   pass
                   
                task.status = DownloadStatus.ERROR
                task.error_message = err
                logger.error(f"Task {task.id} failed: {err}")
                self._notify_completion(task, False, err)
                
        except Exception as e:
            # Check if this exception was caused by us stopping it
            if task.status in [DownloadStatus.PAUSED, DownloadStatus.CANCELLED]:
                 return

            task.status = DownloadStatus.ERROR
            task.error_message = str(e)
            logger.exception(f"Exception in download worker for {task.id}")
            self._notify_completion(task, False, str(e))
            
        finally:
            self._save_state()

    def _notify_progress(self, task: DownloadTask):
        data = task.to_dict()
        for cb in self.progress_callbacks:
            try:
                cb(data)
            except Exception:
                pass

    def _notify_completion(self, task: DownloadTask, success: bool, message: str):
        data = task.to_dict()
        for cb in self.completion_callbacks:
            try:
                cb(data, success, message)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _save_state(self):
        data = {
            "queue": self.queue,
            "tasks": {tid: t.to_dict() for tid, t in self.tasks.items()}
        }
        try:
            with open(self.persistence_file, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def _load_state(self):
        if not os.path.exists(self.persistence_file):
            return
            
        try:
            with open(self.persistence_file, 'r') as f:
                data = json.load(f)
                
            self.queue = data.get("queue", [])
            tasks_data = data.get("tasks", {})
            
            for tid, tdata in tasks_data.items():
                task = DownloadTask.from_dict(tdata)
                # Reset downloading tasks to queued (or paused) on restart
                if task.status == DownloadStatus.DOWNLOADING:
                    task.status = DownloadStatus.QUEUED
                    if tid not in self.queue:
                        self.queue.append(tid)
                
                self.tasks[tid] = task
                
            logger.info(f"Loaded {len(self.tasks)} tasks from state.")
            
        except Exception as e:
            logger.error(f"Failed to load state: {e}")

# Global instance
manager = DownloadManager()