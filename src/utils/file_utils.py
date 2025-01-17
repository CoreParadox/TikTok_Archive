import os
import re
import sys
import logging
from datetime import datetime

def create_folder(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path)

def sanitize_filename(filename: str) -> str:
    # Remove invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Remove control characters
    filename = "".join(char for char in filename if ord(char) >= 32)
    return filename.strip()

def log_message(log_file: str, message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}\n"
    
    try:
        with open(log_file, 'a', encoding='utf-8', errors='replace') as f:
            f.write(log_line)
    except Exception as e:
        logging.error(f"Failed to write to log file {log_file}: {str(e)}")

def setup_logging(log_folder: str) -> None:
    create_folder(log_folder)
    
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_folder, 'app.log'), encoding='utf-8'),
            logging.StreamHandler(sys.stdout)  # Use stdout with UTF-8 encoding
        ]
    )
