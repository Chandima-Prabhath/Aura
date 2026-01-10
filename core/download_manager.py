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
from core.models import DownloadTask, DownloadStatus

logger = get_logger(__name__)

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
        
        # Callbacks
        self.progress_callbacks: List[Callable] = [] 
        self.completion_callbacks: List[Callable] = [] 
        self.refresh_callbacks: List[Callable] = [] # New: Notify when link needs refresh
        
        self._initialized = True
        self._load_state()
        
        # Start the queue processor
        self.processor_thread = threading.Thread(target=self._queue_processor_loop, daemon=True)
        self.processor_thread.start()
        
    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    
    def add_download(self, url: str, dest_folder: str, filename: str = None, 
                     episode_url: str = None, anime_title: str = None) -> str:
        """Add a new download task."""
        
        # Use existing task if we are re-adding / resuming a specific file structure?
        # For now, simplistic approach: always new task ID, unless we handle deduplication logic in Interface.
        
        task_id = str(uuid.uuid4())
        task = DownloadTask(
            id=task_id, 
            url=url, 
            dest_folder=dest_folder, 
            filename=filename,
            episode_url=episode_url,
            anime_title=anime_title
        )
        
        with self.lock:
            self.tasks[task_id] = task
            self.queue.append(task_id)
            self._save_state()
            
        logger.info(f"Added download task: {task_id} - {filename or url}")
        self._notify_progress(task)
        return task_id

    def update_download_url(self, task_id: str, new_url: str):
        """Update the direct download URL for a task (e.g. after refresh)."""
        with self.lock:
            task = self.tasks.get(task_id)
            if task:
                logger.info(f"Updating URL for task {task_id}")
                task.url = new_url
                # If it was EXPIRED or ERROR, move to QUEUED to retry
                if task.status in [DownloadStatus.EXPIRED, DownloadStatus.ERROR, DownloadStatus.PAUSED]:
                    task.status = DownloadStatus.QUEUED
                    if task_id not in self.queue:
                        self.queue.append(task_id)
                self._save_state()
                self._notify_progress(task)

    def pause_download(self, task_id: str):
        with self.lock:
            task = self.tasks.get(task_id)
            if task and task.status == DownloadStatus.DOWNLOADING:
                if task_id in self.running_threads:
                    # Thread will see status change and stop
                    pass
                task.status = DownloadStatus.PAUSED
                self._save_state()
                logger.info(f"Paused task: {task_id}")
                self._notify_progress(task)

    def resume_download(self, task_id: str):
        with self.lock:
            task = self.tasks.get(task_id)
            if task and (task.status == DownloadStatus.PAUSED or task.status == DownloadStatus.ERROR):
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

            # Signal stop
            task.status = DownloadStatus.CANCELLED
            if task_id in self.queue:
                self.queue.remove(task_id)
            
            # Cleanup partial files
            try:
                # If running, smart_dl might still be holding file. 
                # The worker thread will see CANCELLED and exit, but we might need to wait or catch error.
                pass 
                
                # We attempt cleanup here, but if file is locked, we might fail.
                # A robust system would cleanup in the worker thread after loop exit.
            except Exception as e:
                logger.error(f"Error cleaning up cancelled task {task_id}: {e}")

            self._save_state()
            self._notify_progress(task)

    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        with self.lock:
            return self.tasks.get(task_id)

    def get_all_tasks(self) -> List[DownloadTask]:
        with self.lock:
            return list(self.tasks.values())
            
    def add_progress_callback(self, callback: Callable):
        self.progress_callbacks.append(callback)

    def add_completion_callback(self, callback: Callable):
        self.completion_callbacks.append(callback)
        
    def add_refresh_callback(self, callback: Callable):
        self.refresh_callbacks.append(callback)

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
                    candidate_id = None
                    for tid in self.queue:
                        task = self.tasks[tid]
                        if task.status == DownloadStatus.QUEUED:
                            candidate_id = tid
                            break
                    
                    if candidate_id:
                        self.queue.remove(candidate_id)
                        self._start_task_thread(candidate_id)
            
            time.sleep(1) 

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
        obj = None
        try:
            if not task.dest_folder.exists():
                task.dest_folder.mkdir(parents=True, exist_ok=True)

            dest = str(task.dest_folder / task.filename) if task.filename else str(task.dest_folder)
            
            # PySmartDL Setup
            # threads=5 is a good balance
            obj = SmartDL(task.url, dest, progress_bar=False, threads=5)
            # task.smart_dl = obj # Avoid storing obj in task as it's not pickleable for deepcopy/logging easily? 
            # Actually we don't pickle the task object itself using stdlib pickle usually, 
            # but for simplicity let's keep it local or attached if needed.
            
            # Start (Non-blocking)
            obj.start(blocking=False)
            
            while not obj.isFinished():
                # Check for external status changes
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
                    pass
                    
                time.sleep(0.5)

            if obj.isSuccessful():
                task.status = DownloadStatus.COMPLETED
                task.progress = 100.0
                try:
                    task.total_bytes = obj.get_final_filesize() or task.total_bytes
                    task.downloaded_bytes = task.total_bytes
                    task.filename = Path(obj.get_dest()).name
                except:
                    pass
                
                logger.info(f"Task {task.id} completed.")
                self._notify_completion(task, True, "Download Completed")
                
            else:
                # If manually stopped
                if task.status in [DownloadStatus.PAUSED, DownloadStatus.CANCELLED]:
                    return 

                # Genuine error
                err = "Unknown error"
                try:
                   errors = obj.get_errors()
                   err = str(errors)
                except:
                   pass
                   
                # Check for Expiration / Forbidden
                # PySmartDL errors are usually strings or Exception objects.
                err_lower = err.lower()
                if "forbidden" in err_lower or "403" in err_lower or "expired" in err_lower:
                    logger.warning(f"Task {task.id} link expired: {err}")
                    task.status = DownloadStatus.EXPIRED
                    task.error_message = "Link Expired"
                    # Notify interface to refresh
                    self._notify_refresh_needed(task)
                else:
                    task.status = DownloadStatus.ERROR
                    task.error_message = err
                    logger.error(f"Task {task.id} failed: {err}")
                    self._notify_completion(task, False, err)
                
        except Exception as e:
            if task.status in [DownloadStatus.PAUSED, DownloadStatus.CANCELLED]:
                 return

            task.status = DownloadStatus.ERROR
            task.error_message = str(e)
            logger.exception(f"Exception in download worker for {task.id}")
            self._notify_completion(task, False, str(e))
            
        finally:
            self._save_state()
            # If cancelled, we might want to delete the file here to be safe
            if task.status == DownloadStatus.CANCELLED and obj:
                try:
                    path = obj.get_dest()
                    if path and os.path.exists(path):
                        os.remove(path)
                except:
                    pass

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

    def _notify_refresh_needed(self, task: DownloadTask):
        data = task.to_dict()
        for cb in self.refresh_callbacks:
            try:
                cb(data)
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
                
            queue_data = data.get("queue", [])
            tasks_data = data.get("tasks", {})
            
            # Reconstruct tasks
            for tid, tdata in tasks_data.items():
                try:
                    task = DownloadTask.from_dict(tdata)
                    # Reset downloading tasks
                    if task.status == DownloadStatus.DOWNLOADING:
                        task.status = DownloadStatus.QUEUED
                        if tid not in queue_data and tid not in self.queue:
                            self.queue.append(tid)
                    
                    self.tasks[tid] = task
                except Exception as e:
                    logger.error(f"Skipping malformed task {tid}: {e}")
            
            # Reconstruct queue order
            for qid in queue_data:
                if qid in self.tasks and qid not in self.queue:
                    self.queue.append(qid)
                
            logger.info(f"Loaded {len(self.tasks)} tasks from state.")
            
        except Exception as e:
            logger.error(f"Failed to load state: {e}")

# Global instance
manager = DownloadManager()