from typing import Dict, Any
import os
import json
from dataclasses import dataclass, asdict
from pathlib import Path

@dataclass
class Config:
    base_folder: str = "Downloaded_Videos"
    output_template: str = "%(uploader)s - %(title).50s - %(id)s.%(ext)s"
    save_metadata: bool = True
    max_retries: int = 3
    timeout: int = 300  # 5 minutes
    concurrent_downloads: int = 3
    min_video_quality: str = "720p"
    skip_existing: bool = True
    total_rate_limit: str = "5M"  # 5 MB/s total across all downloads
    max_failed_retries: int = 3  # Number of times to retry failed downloads
    download_batch_size: int = 10  # Number of videos to process in each batch

    def __init__(self):
        self.config_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(self.config_dir, 'config.json')
        self.load_config()

    def load_config(self):
        """Load config from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                for key, value in config.items():
                    if hasattr(self, key):
                        setattr(self, key, value)
        except FileNotFoundError:
            self.save_config()  # Create default config file

    def save_config(self):
        """Save config to JSON file"""
        config = asdict(self)
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=4)

    @property
    def success_log(self) -> str:
        return os.path.join(self.base_folder, "logs", "success.log")

    @property
    def error_log(self) -> str:
        return os.path.join(self.base_folder, "logs", "error.log")

    @classmethod
    def from_file(cls, config_path: str) -> 'Config':
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config_dict = json.load(f)
                return cls(**config_dict)
        return cls()

# Create default config if it doesn't exist
default_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
if not os.path.exists(default_config_path):
    Config().save_config()
