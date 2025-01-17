import os
import logging
import re
from typing import Optional
from pathlib import Path

def setup_logging(log_dir: str = "logs") -> None:
    """Setup logging configuration"""
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, "app.log")),
            logging.StreamHandler()
        ]
    )

def create_folder(path: str) -> None:
    """Create a folder if it doesn't exist, handling long paths on Windows"""
    try:
        if not os.path.exists(path):
            if os.name == 'nt':
                # Convert to absolute path and normalize
                abs_path = os.path.abspath(path)
                if len(abs_path) >= 260 and not abs_path.startswith('\\\\?\\'):
                    # Add Windows long path prefix for paths >= 260 chars
                    path = '\\\\?\\' + abs_path
                    if not os.path.exists(path):
                        os.makedirs(path)
                else:
                    # For shorter paths, use normal makedirs
                    os.makedirs(path)
            else:
                # Non-Windows systems
                os.makedirs(path)
    except OSError as e:
        if os.name == 'nt' and len(os.path.abspath(path)) >= 260:
            # If path is too long on Windows and doesn't have the prefix
            if not path.startswith('\\\\?\\'):
                raise OSError(f"Path too long: {path}")
        raise e

def sanitize_filename(name: str, max_length: int = 100) -> str:
    """Sanitize filename and limit its length while preserving extension"""
    # Split filename and extension
    base, ext = os.path.splitext(name)
    
    # Remove invalid characters from base name
    sanitized_base = "".join(c for c in base if c.isalnum() or c in (" ", "-", "_")).rstrip()
    
    # Calculate maximum length for base name (accounting for extension)
    max_base_length = max_length - len(ext)
    sanitized_base = sanitized_base[:max_base_length]
    
    # Combine base name and extension
    return sanitized_base + ext

def log_message(file_path: str, message: str) -> None:
    """Log a message to a file"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'a', encoding='utf-8') as log_file:
        log_file.write(f"{message}\n")

def get_video_id_from_url(url: str) -> Optional[str]:
    """Extract video ID from TikTok URL"""
    # Regular expressions for different TikTok URL formats
    patterns = [
        r'tiktok\.com/(?:@[\w.-]+/video/|v/)(\d+)',  # Standard URL format
        r'vm\.tiktok\.com/(\d+)',  # Short URL format
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None
