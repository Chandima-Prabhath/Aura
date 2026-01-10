# core/models.py
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict

@dataclass
class AnimeSearchResult:
    title: str
    url: str
    image: str

@dataclass
class Episode:
    name: str
    raw_name: str
    url: str
    episode_number: int
    gate_id: Optional[str] = None
    
from enum import Enum

class DownloadStatus(str, Enum):
    QUEUED = "Queued"
    DOWNLOADING = "Downloading"
    PAUSED = "Paused"
    COMPLETED = "Completed"
    ERROR = "Error"
    CANCELLED = "Cancelled"
    EXPIRED = "Expired"

@dataclass
class DownloadTask:
    id: str
    url: str
    dest_folder: Path
    filename: Optional[str] = None
    episode_url: Optional[str] = None # Added for refreshing links
    anime_title: Optional[str] = None # For folder structure context
    
    status: str = DownloadStatus.QUEUED
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed: float = 0.0
    progress: float = 0.0
    error_message: Optional[str] = None
    
    def __post_init__(self):
        # Ensure dest_folder is Path
        if isinstance(self.dest_folder, str):
            self.dest_folder = Path(self.dest_folder)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "url": self.url,
            "dest_folder": str(self.dest_folder),
            "filename": self.filename,
            "episode_url": self.episode_url,
            "anime_title": self.anime_title,
            "anime_title": self.anime_title,
            "status": self.status.value if isinstance(self.status, DownloadStatus) else str(self.status),
            "downloaded": self.downloaded_bytes,
            "total": self.total_bytes,
            "progress": self.progress,
            "speed": self.speed,
            "error": self.error_message
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'DownloadTask':
        task = cls(
            id=data["id"],
            url=data["url"],
            dest_folder=data["dest_folder"],
            filename=data.get("filename"),
            episode_url=data.get("episode_url"),
            anime_title=data.get("anime_title")
        )
        # Convert string back to Enum
        status_str = data.get("status", "Queued")
        try:
            task.status = DownloadStatus(status_str)
        except ValueError:
            # Fallback for mismatched case or legacy data
            # Try matching by name or case-insensitive value
            found = False
            for s in DownloadStatus:
                if s.value.lower() == status_str.lower():
                    task.status = s
                    found = True
                    break
            if not found:
                task.status = DownloadStatus.QUEUED
                
        task.downloaded_bytes = data.get("downloaded", 0)
        task.total_bytes = data.get("total", 0)
        task.progress = data.get("progress", 0.0)
        task.speed = data.get("speed", 0.0)
        task.error_message = data.get("error")
        return task
