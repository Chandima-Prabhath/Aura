import sys
import os
import time
import shutil

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.download_manager import manager, DownloadStatus

def on_progress(data):
    # Minimal output to avoid spamming
    # print(f"Progress: {data['progress']:.1f}% | Speed: {data['speed']}", end='\r')
    pass

def on_complete(data, success, message):
    print(f"\nTask Finished: {data['filename']} | Success: {success} | Msg: {message}")

def test_download():
    print("Initializing manager...")
    manager.add_progress_callback(on_progress)
    manager.add_completion_callback(on_complete)
    
    # Test URL (small file for quick test)
    url = "http://speedtest.tele2.net/1MB.zip"
    dest = "downloads_test"
    
    if os.path.exists(dest):
        shutil.rmtree(dest)
    os.makedirs(dest)
    
    print(f"Adding download: {url}")
    task_id = manager.add_download(url, dest, "1MB.zip")
    
    print("Waiting for download to start...")
    time.sleep(2)
    
    task = manager.get_task(task_id)
    print(f"Current Status: {task['status']}")
    
    # Simulate pause/resume
    print("Pausing...")
    manager.pause_download(task_id)
    time.sleep(2)
    task = manager.get_task(task_id)
    print(f"Paused Status: {task['status']}")
    
    print("Resuming...")
    manager.resume_download(task_id)
    
    # Wait for completion or timeout
    for _ in range(60):
        task = manager.get_task(task_id)
        print(f"Progress: {task['progress']:.2f}% | Status: {task['status']}")
        if task['status'] in [DownloadStatus.COMPLETED, DownloadStatus.ERROR]:
            break
        time.sleep(1)
        
    print("Test Finished.")

if __name__ == "__main__":
    test_download()
