"""Configuration management for TikTok Archiver"""
import os
import json
from dataclasses import dataclass, asdict
from typing import Optional

@dataclass
class Config:
    base_folder: str = "Downloaded_Videos"
    concurrent_downloads: int = 3
    download_batch_size: int = 10
    total_rate_limit: str = "10M"  # In bytes/s or with M suffix
    timeout: int = 30
    max_retries: int = 3
    save_metadata: bool = True
    output_template: str = "%(id)s.%(ext)s"
    config_file: str = "config.json"

    def __post_init__(self):
        """Load config from file if it exists"""
        if os.path.exists(self.config_file):
            self.load_config()

    def save_config(self):
        """Save current config to file"""
        with open(self.config_file, 'w') as f:
            json.dump(asdict(self), f, indent=4)

    def load_config(self):
        """Load config from file"""
        try:
            with open(self.config_file, 'r') as f:
                config_data = json.load(f)
                for key, value in config_data.items():
                    if hasattr(self, key):
                        setattr(self, key, value)
        except Exception as e:
            print(f"Error loading config: {str(e)}")
            # If there's an error loading, save current config
            self.save_config()
