"""TikTok video downloader core functionality"""
import os
import time
import shutil
import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import Dict, Any, Set, List, Tuple, Optional
from yt_dlp import YoutubeDL
from ..utils.file_utils import create_folder, log_message, sanitize_filename
from .config import Config
from src.utils.data_parser import TikTokDataParser

class YTDLLogger:
    def __init__(self, logger):
        self.logger = logger

    def debug(self, msg):
        # Only log important debug messages
        if msg.startswith('[debug] '):
            self.logger.debug(msg)

    def info(self, msg):
        # Filter out progress messages
        if not msg.startswith('[download]') or 'has already been downloaded' in msg:
            self.logger.info(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def error(self, msg):
        self.logger.error(msg)

class TikTokDownloader:
    TIKTOK_URL_PATTERN = "https://www.tiktokv.com/share/video/"

    def __init__(self, config: Config, gui=None):
        self.config = config
        self.gui = gui
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        
        # Check ffmpeg first
        self.ffmpeg_path = self._find_ffmpeg()
        if not self.ffmpeg_path:
            raise RuntimeError("ffmpeg not found. Please install ffmpeg and make sure it's in your PATH.")
        
        # Create necessary directories
        create_folder(self.config.base_folder)
        create_folder(os.path.join(self.config.base_folder, "Likes"))
        create_folder(os.path.join(self.config.base_folder, "metadata"))
        create_folder(os.path.join(self.config.base_folder, "logs"))
        
        # Set up log files
        self.error_log = os.path.join(self.config.base_folder, "logs", "error.log")
        self.success_log = os.path.join(self.config.base_folder, "logs", "success.log")
        
        # Thread safety
        self._active_downloads: Set[str] = set()
        self._downloads_lock = Lock()
        
        # Load previously downloaded videos
        self._downloaded_videos: Set[str] = self._load_downloaded_videos()

    def _find_ffmpeg(self) -> Optional[str]:
        """Find ffmpeg executable, checking both PATH and tools directory"""
        try:
            self.logger.info("Checking for ffmpeg in PATH...")
            result = subprocess.run(["where", "ffmpeg"], capture_output=True, text=True, check=True)
            ffmpeg_path = result.stdout.splitlines()[0].strip()
            
            # Verify it works
            result = subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True)
            version = result.stdout.splitlines()[0] if result.stdout else ''
            if version:
                self.logger.info(f"ffmpeg found in PATH: {ffmpeg_path}")
                self.logger.info(f"ffmpeg version: {version}")
                return ffmpeg_path
            
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            self.logger.warning(f"ffmpeg not found in PATH: {str(e)}")
            
            # Check tools directory
            tools_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools")
            ffmpeg_path = os.path.join(tools_dir, "ffmpeg.exe")
            if os.path.exists(ffmpeg_path):
                try:
                    # Verify the ffmpeg in tools works
                    result = subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True)
                    version = result.stdout.splitlines()[0] if result.stdout else ''
                    if version:
                        self.logger.info(f"ffmpeg found in tools: {ffmpeg_path}")
                        self.logger.info(f"ffmpeg version: {version}")
                        return ffmpeg_path
                except subprocess.CalledProcessError as e:
                    self.logger.error(f"tools ffmpeg failed verification: {str(e)}")
            else:
                self.logger.error(f"ffmpeg not found in tools directory: {tools_dir}")
        
        return None

    def _load_downloaded_videos(self) -> Set[str]:
        """Load list of previously downloaded videos from success log"""
        downloaded = set()
        if os.path.exists(self.success_log):
            try:
                with open(self.success_log, 'r', encoding='utf-8') as f:
                    for line in f:
                        if "URL:" in line:
                            downloaded.add(line.split("URL:")[1].strip())
            except UnicodeDecodeError:
                # If UTF-8 fails, try reading with errors='replace'
                with open(self.success_log, 'r', encoding='utf-8', errors='replace') as f:
                    for line in f:
                        if "URL:" in line:
                            downloaded.add(line.split("URL:")[1].strip())
                # Rewrite the file with proper UTF-8 encoding
                with open(self.success_log, 'w', encoding='utf-8') as f:
                    for url in downloaded:
                        log_message(self.success_log, f"URL: {url}")
        return downloaded

    def get_ydl_opts(self, folder: str) -> Dict[str, Any]:
        """Get yt-dlp options based on current configuration"""
        metadata_folder = os.path.join(folder, "metadata") if self.config.save_metadata else None
        if metadata_folder:
            create_folder(metadata_folder)

        # Calculate per-download rate limit by dividing total rate by concurrent downloads
        total_rate = float(self.config.total_rate_limit)  # Already in bytes/s
        per_download_rate = total_rate / self.config.concurrent_downloads  # Share of total limit

        return {
            'outtmpl': os.path.join(folder, self.config.output_template),
            'writeinfojson': self.config.save_metadata,
            'writethumbnail': self.config.save_metadata,
            'format': 'best',  
            'ratelimit': per_download_rate,  # Pass as number, not string
            'socket_timeout': self.config.timeout,
            'retries': self.config.max_retries,
            'ffmpeg_location': self.ffmpeg_path,
            'quiet': False,  # Enable output
            'no_warnings': False,  # Show warnings
            'progress': True,  # Show progress
            'logger': YTDLLogger(self.logger),  # Use our custom logger
            'progress_hooks': [self._progress_hook],  # Add progress hook
            'extractor_args': {'TikTok': {'download_timeout': self.config.timeout}},
        }

    def _progress_hook(self, d):
        """Progress hook for yt-dlp"""
        if d['status'] == 'downloading':
            if 'total_bytes' in d:
                total = d['total_bytes']
                downloaded = d['downloaded_bytes']
                percent = (downloaded / total) * 100
                speed = d.get('speed', 0)
                if speed:
                    self.logger.info(f"[download] {percent:.1f}% of {total/1024/1024:.2f}MiB at {speed/1024/1024:.2f}MiB/s")
            elif 'downloaded_bytes' in d:
                self.logger.info(f"[download] {d['downloaded_bytes']/1024/1024:.2f}MiB downloaded")
        elif d['status'] == 'finished':
            self.logger.info(f"[download] Download completed: {os.path.basename(d['filename'])}")
        elif d['status'] == 'error':
            self.logger.error(f"[download] Error: {d.get('error', 'Unknown error')}")

    def download_video(self, url: str, folder: str, category_path: str) -> bool:
        """Download a single video with duplicate download prevention"""
        # Check if already downloaded or in progress
        with self._downloads_lock:
            if url in self._downloaded_videos:
                self.logger.info(f"Skipping already downloaded video: {url}")
                return True
            if url in self._active_downloads:
                self.logger.info(f"Skipping video already being downloaded: {url}")
                return True
            self._active_downloads.add(url)
        
        try:
            # Configure yt-dlp options
            ydl_opts = self.get_ydl_opts(folder)
            
            # Download video
            with YoutubeDL(ydl_opts) as ydl:
                # Extract video info and download in one step
                info = ydl.extract_info(url, download=True)
                if not info:
                    raise Exception("Failed to extract video info")
                
                # Get filename after download
                final_filename = ydl.prepare_filename(info)
                
                # Move metadata files if download was successful
                if os.path.exists(final_filename):
                    self._move_metadata_files(final_filename, os.path.join(folder, "metadata"))
                    
                    # Log success
                    title = info.get('title', 'Unknown Title')
                    video_id = info.get('id', 'Unknown ID')
                    log_message(self.success_log, 
                              f"URL: {url} | TITLE: {title} | ID: {video_id} | CATEGORY: {category_path} | FILE: {final_filename}")
                    
                    if self.gui:
                        self.gui.add_success(title, video_id)
                    
                    # Mark as downloaded
                    with self._downloads_lock:
                        self._downloaded_videos.add(url)
                    return True
                else:
                    raise Exception("Video file not created after download")
        
        except Exception as e:
            error_msg = str(e)
            title = "Unknown Title"
            video_id = url.split('/')[-1] if '/' in url else 'Unknown ID'
            
            log_message(self.error_log, 
                       f"ERROR: {url} | TITLE: {title} | ID: {video_id} | CATEGORY: {category_path} - {error_msg}")
            
            if self.gui:
                self.gui.add_error(title, video_id, error_msg)
            
            self.logger.error(f"Failed to download {url}: {error_msg}")
            return False
        
        finally:
            # Always remove from active downloads
            with self._downloads_lock:
                self._active_downloads.remove(url)

    def _move_metadata_files(self, video_filename: str, metadata_folder: str) -> None:
        """Move metadata files to the metadata folder"""
        base_name = os.path.splitext(video_filename)[0]
        metadata_files = [
            f"{base_name}.info.json",
            f"{base_name}.jpg"  # Thumbnail
        ]
        
        for metadata_file in metadata_files:
            if os.path.exists(metadata_file):
                shutil.move(metadata_file, os.path.join(metadata_folder, os.path.basename(metadata_file)))

    def extract_videos(self, data: Dict[str, Any]) -> List[Tuple[str, str, str]]:
        """Extract all video URLs from the data file"""
        _, videos = TikTokDataParser.parse_data_file(data)
        
        # Convert relative paths to absolute
        videos = [(url, os.path.join(self.config.base_folder, folder), category) 
                 for url, folder, category in videos]
        
        if videos:
            self.logger.info(f"Total videos found: {len(videos)}")
        else:
            self.logger.warning("No videos found in data file")
        
        return videos

    def process_videos(self, videos: list, folder_name: str, 
                      link_key: str = "url", category_path: str = "Unknown Category") -> None:
        """Process a list of videos with concurrent downloads"""
        folder_path = os.path.join(self.config.base_folder, sanitize_filename(folder_name))
        create_folder(folder_path)
        create_folder(os.path.join(folder_path, "metadata"))
        
        # Process videos in batches
        for i in range(0, len(videos), self.config.download_batch_size):
            batch = videos[i:i + self.config.download_batch_size]
            self.logger.info(f"Processing batch {i//self.config.download_batch_size + 1} "
                           f"({len(batch)} videos)")
            
            with ThreadPoolExecutor(max_workers=self.config.concurrent_downloads) as executor:
                futures = []
                for video in batch:
                    if isinstance(video, dict) and link_key in video:
                        url = video[link_key]
                        future = executor.submit(self.download_video, url, folder_path, category_path)
                        futures.append(future)
                        self.logger.debug(f"Scheduled download for {url}")
                
                # Wait for all downloads to complete and collect results
                results = []
                for future in as_completed(futures):
                    try:
                        results.append(future.result())
                    except Exception as e:
                        self.logger.error(f"Unexpected error in download thread: {str(e)}")
                        results.append(False)
                
                # Log batch summary
                total = len(futures)
                successful = sum(1 for r in results if r)
                self.logger.info(f"Completed batch: {successful}/{total} videos downloaded successfully")
            
            # Small delay between batches to prevent rate limiting
            if i + self.config.download_batch_size < len(videos):
                time.sleep(1)
