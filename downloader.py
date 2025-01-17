import os
import shutil
import logging
from typing import Dict, Any, Optional, Set, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from yt_dlp import YoutubeDL
from utils import create_folder, sanitize_filename, log_message
from config import Config
import time
import subprocess

class TikTokDownloader:
    def __init__(self, config: Config):
        self.config = config
        # Create necessary directories
        create_folder(self.config.base_folder)
        create_folder(os.path.join(self.config.base_folder, "Likes"))
        create_folder(os.path.join(self.config.base_folder, "metadata"))
        create_folder(os.path.join(self.config.base_folder, "logs"))
        
        # Set up logging
        self.error_log = os.path.join(self.config.base_folder, "logs", "error.log")
        self.success_log = os.path.join(self.config.base_folder, "logs", "success.log")
        self.logger = logging.getLogger(__name__)
        
        # Thread safety
        self._active_downloads: Set[str] = set()
        self._downloads_lock = Lock()
        
        # Load previously downloaded videos
        self._downloaded_videos: Set[str] = self._load_downloaded_videos()
        
        # Check ffmpeg availability
        self.ffmpeg_path = self._find_ffmpeg()

    def _find_ffmpeg(self) -> str:
        """Find ffmpeg executable, checking both PATH and tools directory"""
        # First check if ffmpeg is in PATH
        try:
            self.logger.info("Checking for ffmpeg in PATH...")
            result = subprocess.run(["where", "ffmpeg"], capture_output=True, text=True, check=True)
            ffmpeg_path = result.stdout.splitlines()[0].strip()  # Get first found path
            self.logger.info(f"ffmpeg found in PATH: {ffmpeg_path}")
            
            # Verify it works
            result = subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True)
            self.logger.info(f"PATH ffmpeg verified: {result.stdout.splitlines()[0] if result.stdout else ''}")
            return ffmpeg_path
            
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            self.logger.warning(f"ffmpeg not found in PATH: {str(e)}")
            # Check tools directory
            tools_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools")
            ffmpeg_path = os.path.join(tools_dir, "ffmpeg.exe")
            if os.path.exists(ffmpeg_path):
                self.logger.info(f"ffmpeg found in tools directory: {ffmpeg_path}")
                try:
                    # Verify the ffmpeg in tools works
                    result = subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True)
                    self.logger.info(f"tools ffmpeg verified: {result.stdout.splitlines()[0] if result.stdout else ''}")
                    return ffmpeg_path
                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    self.logger.warning(f"tools ffmpeg failed: {str(e)}")
            else:
                self.logger.warning(f"ffmpeg not found in tools directory: {ffmpeg_path}")
        
        self.logger.error("No working ffmpeg found!")
        return None

    def _load_downloaded_videos(self) -> Set[str]:
        """Load list of previously downloaded videos from success log"""
        downloaded = set()
        if os.path.exists(self.success_log):
            with open(self.success_log, 'r') as f:
                for line in f:
                    if "SUCCESS:" in line:
                        url = line.split("|")[0].split("SUCCESS:")[1].strip()
                        downloaded.add(url)
        return downloaded

    def get_ydl_opts(self, folder: str) -> Dict[str, Any]:
        """Get yt-dlp options based on current configuration"""
        metadata_folder = os.path.join(folder, "metadata") if self.config.save_metadata else None
        if metadata_folder:
            create_folder(metadata_folder)

        # Calculate per-download rate limit by dividing total rate by concurrent downloads
        total_rate = float(self.config.total_rate_limit)  # Already in bytes/s
        per_download_rate = total_rate / self.config.concurrent_downloads  # Share of total limit

        # Check for ffmpeg in tools directory
        tools_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools")
        ffmpeg_path = os.path.join(tools_dir, "ffmpeg.exe")

        return {
            'outtmpl': os.path.join(folder, self.config.output_template),
            'noprogress': True,
            'restrictfilenames': True,
            'writeinfojson': self.config.save_metadata,
            'writethumbnail': self.config.save_metadata,
            'format': 'best',  
            'ratelimit': per_download_rate,  # Pass as number, not string
            'socket_timeout': self.config.timeout,
            'retries': self.config.max_retries,
            'ffmpeg_location': self.ffmpeg_path,
            'postprocessors': [
                {'key': 'FFmpegMetadata'},
                {'key': 'EmbedThumbnail', 'already_have_thumbnail': False} if self.config.save_metadata else {}
            ]
        }

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
            # Create metadata folder
            metadata_folder = os.path.join(folder, "metadata")
            create_folder(metadata_folder)
            
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
                    self._move_metadata_files(final_filename, metadata_folder)
                    log_message(self.success_log, 
                              f"SUCCESS: {url} | CATEGORY_PATH: {category_path} | FILENAME: {final_filename}")
                    self.logger.info(f"Downloaded: {final_filename}")
                    
                    # Mark as downloaded
                    with self._downloads_lock:
                        self._downloaded_videos.add(url)
                    return True
                else:
                    raise Exception("Video file not created after download")
        
        except Exception as e:
            log_message(self.error_log, 
                       f"ERROR: {url} | CATEGORY_PATH: {category_path} - {str(e)}")
            self.logger.error(f"Failed to download {url}: {str(e)}")
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
                dest_file = os.path.join(metadata_folder, os.path.basename(metadata_file))
                try:
                    shutil.move(metadata_file, dest_file)
                    self.logger.debug(f"Moved metadata file: {metadata_file} -> {dest_file}")
                except Exception as e:
                    self.logger.error(f"Failed to move metadata file {metadata_file}: {str(e)}")

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
                    url = video.get(link_key)
                    if url:
                        future = executor.submit(self.download_video, url, folder_path, category_path)
                        futures.append(future)
                        self.logger.debug(f"Scheduled download for {url}")
                
                # Wait for all downloads to complete and collect results
                results = []
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        results.append(result)
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

    def process_chat_videos(self, chat_videos: list) -> None:
        """Process videos from chat history"""
        if not chat_videos:
            return
            
        # Process sent messages
        if "SentTo" in chat_videos:
            for friend, messages in chat_videos["SentTo"].items():
                folder_name = os.path.join("ChatHistory", "SentTo", sanitize_filename(friend))
                category_path = f"Activity > ChatHistory > SentTo > {friend}"
                self.process_videos(messages, folder_name, link_key="url", category_path=category_path)
        
        # Process received messages
        if "ReceivedFrom" in chat_videos:
            for friend, messages in chat_videos["ReceivedFrom"].items():
                folder_name = os.path.join("ChatHistory", "ReceivedFrom", sanitize_filename(friend))
                category_path = f"Activity > ChatHistory > ReceivedFrom > {friend}"
                self.process_videos(messages, folder_name, link_key="url", category_path=category_path)
