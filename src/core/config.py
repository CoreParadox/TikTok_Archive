"""Configuration management for TikTok Archiver"""
import os
import json
from typing import Optional, Dict, Any

class Config:
    def __init__(self, output_folder: str = None, config_file: str = "config.json"):
        # Initialize default values
        self.output_folder = output_folder or os.path.join(os.path.expanduser("~"), "Downloads", "TikTok_Archive")
        self._concurrent_downloads = 10  # Default to 10 concurrent downloads
        self._total_rate_limit = 10 * 1024 * 1024  # Default to 10MB/s
        self.timeout: int = 30
        self.max_retries: int = 3
        self.save_metadata: bool = True
        self.output_template: str = "%(id)s.%(ext)s"
        
        # Category selection defaults
        self.download_likes = True
        self.download_favorites = True
        self.download_history = True
        self.download_shared = True
        self.download_chat = True
        
        # Load or create config file
        if os.path.exists(config_file):
            self.load_config(config_file)
        else:
            self.save_config(config_file)
            
    @property
    def concurrent_downloads(self) -> int:
        return max(1, self._concurrent_downloads)  # Never allow less than 1
        
    @concurrent_downloads.setter
    def concurrent_downloads(self, value: int):
        self._concurrent_downloads = max(1, value)  # Never allow less than 1

    @property
    def total_rate_limit(self) -> int:
        return max(1024 * 1024, self._total_rate_limit)  # Never allow less than 1MB/s
        
    @total_rate_limit.setter 
    def total_rate_limit(self, value: int):
        self._total_rate_limit = max(1024 * 1024, value)  # Never allow less than 1MB/s

    def save_config(self, config_file: str):
        """Save current config to file"""
        # Ensure the directory exists
        os.makedirs(os.path.dirname(os.path.abspath(config_file)), exist_ok=True)
        
        with open(config_file, 'w') as f:
            json.dump(self.to_dict(), f, indent=4)

    def load_config(self, config_file: str):
        """Load config from file"""
        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
                for key, value in config_data.items():
                    if hasattr(self, key):
                        setattr(self, key, value)
        except Exception as e:
            print(f"Error loading config: {str(e)}")
            # If there's an error loading, save current config
            self.save_config(config_file)

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary"""
        return {
            "output_folder": self.output_folder,
            "concurrent_downloads": self.concurrent_downloads,
            "total_rate_limit": self.total_rate_limit,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "save_metadata": self.save_metadata,
            "output_template": self.output_template,
            "download_likes": self.download_likes,
            "download_favorites": self.download_favorites,
            "download_history": self.download_history,
            "download_shared": self.download_shared,
            "download_chat": self.download_chat
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Config':
        """Create config from dictionary"""
        config = cls()
        config.output_folder = data.get("output_folder", config.output_folder)
        config.concurrent_downloads = data.get("concurrent_downloads", config.concurrent_downloads)
        config.total_rate_limit = data.get("total_rate_limit", config.total_rate_limit)
        config.timeout = data.get("timeout", config.timeout)
        config.max_retries = data.get("max_retries", config.max_retries)
        config.save_metadata = data.get("save_metadata", config.save_metadata)
        config.output_template = data.get("output_template", config.output_template)
        config.download_likes = data.get("download_likes", config.download_likes)
        config.download_favorites = data.get("download_favorites", config.download_favorites)
        config.download_history = data.get("download_history", config.download_history)
        config.download_shared = data.get("download_shared", config.download_shared)
        config.download_chat = data.get("download_chat", config.download_chat)
        return config
