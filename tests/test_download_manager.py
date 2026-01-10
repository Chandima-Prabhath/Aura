
import pytest
import shutil
import time
from pathlib import Path
from core.download_manager import DownloadManager
from core.models import DownloadStatus

TEST_DL_DIR = Path("tests/downloads_tmp")

@pytest.fixture
def dm():
    if TEST_DL_DIR.exists():
        shutil.rmtree(TEST_DL_DIR)
    TEST_DL_DIR.mkdir(parents=True, exist_ok=True)
    
    # Use a separate persistence file for tests
    manager = DownloadManager(persistence_file="tests/test_downloads.json")
    # Reset state
    manager.tasks = {}
    manager.queue = []
    
    yield manager
    
    # Cleanup
    # manager.shutdown() # Not implemented/needed for daemon thread
    if TEST_DL_DIR.exists():
        shutil.rmtree(TEST_DL_DIR)
    if Path("tests/test_downloads.json").exists():
        Path("tests/test_downloads.json").unlink()

def test_add_and_queue_download(dm):
    url = "http://speedtest.tele2.net/1MB.zip"
    task_id = dm.add_download(url, TEST_DL_DIR, "test_1MB.zip")
    
    assert task_id is not None
    task = dm.get_task(task_id)
    assert task is not None
    assert task.url == url
    assert task.status in [DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING]

def test_download_execution(dm):
    # This might take time, so we use a small file
    url = "http://speedtest.tele2.net/1MB.zip"
    task_id = dm.add_download(url, TEST_DL_DIR, "test_exec.zip")
    
    # Wait for completion (timeout 30s)
    start = time.time()
    completed = False
    
    while time.time() - start < 30:
        task = dm.get_task(task_id)
        if task.status == DownloadStatus.COMPLETED:
            completed = True
            break
        elif task.status == DownloadStatus.ERROR:
            pytest.fail(f"Download failed: {task.error_message}")
        time.sleep(1)
        
    assert completed, "Download did not complete in time"
    assert (TEST_DL_DIR / "test_exec.zip").exists()

def test_pause_resume(dm):
    url = "http://speedtest.tele2.net/10MB.zip" # Larger file to allow pause
    task_id = dm.add_download(url, TEST_DL_DIR, "test_pause.zip")
    
    # Wait for start
    time.sleep(2) 
    
    dm.pause_download(task_id)
    time.sleep(1)
    task = dm.get_task(task_id)
    # Depending on speed, it might have finished, but likely paused.
    # Note: SmartDL might not pause instantly if file is too small. 10MB should be fine.
    
    if task.status != DownloadStatus.COMPLETED:
        assert task.status == DownloadStatus.PAUSED
        
        dm.resume_download(task_id)
        time.sleep(1)
        task = dm.get_task(task_id)
        assert task.status in [DownloadStatus.DOWNLOADING, DownloadStatus.COMPLETED]
