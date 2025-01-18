import os
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
        self.logger.debug(msg)

    def info(self, msg):
        self.logger.info(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def error(self, msg):
        self.logger.error(msg)

class TikTokDownloader:
    TIKTOK_URL_PATTERN = "https://www.tiktokv.com/share/video/"

    def __init__(self, config: Config, callback=None):
        self.config = config
        self.callback = callback
        self.logger = logging.getLogger(__name__)
        self.is_running = True
        
        self.ffmpeg_path = self._find_ffmpeg()
        if not self.ffmpeg_path:
            raise RuntimeError("ffmpeg not found. Please install ffmpeg and make sure it's in your PATH.")
        
        create_folder(self.config.output_folder)
        create_folder(os.path.join(self.config.output_folder, "Likes"))
        create_folder(os.path.join(self.config.output_folder, "metadata"))
        create_folder(os.path.join(self.config.output_folder, "logs"))
        
        self.error_log = os.path.join(self.config.output_folder, "logs", "error.log")
        self.success_log = os.path.join(self.config.output_folder, "logs", "success.log")
        
        self._active_downloads: Set[str] = set()
        self._downloads_lock = Lock()
        
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
            
            # Check tools directory in root
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            tools_dir = os.path.join(root_dir, "tools")
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
        downloaded = set()
        if os.path.exists(self.success_log):
            try:
                with open(self.success_log, 'r', encoding='utf-8') as f:
                    for line in f:
                        if "URL:" in line:
                            downloaded.add(line.split("URL:")[1].strip())
            except UnicodeDecodeError:
                with open(self.success_log, 'r', encoding='utf-8', errors='replace') as f:
                    for line in f:
                        if "URL:" in line:
                            downloaded.add(line.split("URL:")[1].strip())
                with open(self.success_log, 'w', encoding='utf-8') as f:
                    for url in downloaded:
                        log_message(self.success_log, f"URL: {url}")
        return downloaded

    def get_ydl_opts(self, folder: str) -> Dict[str, Any]:
        metadata_folder = os.path.join(folder, "metadata") if self.config.save_metadata else None
        if metadata_folder:
            create_folder(metadata_folder)

        total_rate = float(self.config.total_rate_limit)  
        per_download_rate = total_rate / self.config.concurrent_downloads  

        return {
            'outtmpl': os.path.join(folder, self.config.output_template),
            'writeinfojson': self.config.save_metadata,
            'writethumbnail': self.config.save_metadata,
            'format': 'best',  
            'ratelimit': per_download_rate,  
            'socket_timeout': self.config.timeout,
            'retries': self.config.max_retries,
            'ffmpeg_location': self.ffmpeg_path,
            'quiet': False,  
            'no_warnings': False,  
            'progress': True,  
            'logger': YTDLLogger(self.logger),  
            'progress_hooks': [self._progress_hook],  
            'extractor_args': {'TikTok': {'download_timeout': self.config.timeout}},
        }

    def _progress_hook(self, d: dict):
        try:
            if d['status'] == 'downloading':
                pass
            elif d['status'] == 'finished':
                self.logger.info(f"Download complete: {d['filename']}")
            elif d['status'] == 'error':
                self.logger.error(f"Download error: {d.get('error')}")
                
            if self.callback and hasattr(self.callback, 'update_progress'):
                self.callback.update_progress(d)
                
        except Exception as e:
            self.logger.error(f"Error in progress hook: {str(e)}")

    def extract_videos(self, data: Dict[str, Any]) -> List[Tuple[str, str, str]]:
        counts, videos, username = TikTokDataParser.parse_data_file(data)
        
        filtered_videos = []
        
        # Add profile URL if username found and profile download enabled
        if username and self.config.download_profile:
            profile_url = f"https://www.tiktok.com/@{username}"
            profile_folder = os.path.join(self.config.output_folder, f"Profile_{username}")
            filtered_videos.append((profile_url, profile_folder, "profile"))
            self.logger.info(f"Will download profile videos for @{username}")
        
        # Add other videos based on category preferences
        for url, folder, category_id in videos:
            if (
                (category_id == "likes" and self.config.download_likes) or
                (category_id == "favorites" and self.config.download_favorites) or
                (category_id == "history" and self.config.download_history) or
                (category_id == "shared" and self.config.download_shared) or
                (category_id == "chat" and self.config.download_chat)
            ):
                filtered_videos.append((url, os.path.join(self.config.output_folder, folder), category_id))
        
        # Log what we're going to download
        categories_to_download = []
        if username and self.config.download_profile:
            categories_to_download.append("profile")
        if self.config.download_likes and counts["likes"] > 0:
            categories_to_download.append(f"likes ({counts['likes']} videos)")
        if self.config.download_favorites and counts["favorites"] > 0:
            categories_to_download.append(f"favorites ({counts['favorites']} videos)")
        if self.config.download_history and counts["history"] > 0:
            categories_to_download.append(f"history ({counts['history']} videos)")
        if self.config.download_shared and counts["shared"] > 0:
            categories_to_download.append(f"shared ({counts['shared']} videos)")
        if self.config.download_chat and counts["chat"] > 0:
            categories_to_download.append(f"chat ({counts['chat']} videos)")
            
        if categories_to_download:
            self.logger.info(f"Will download from categories: {', '.join(categories_to_download)}")
        else:
            self.logger.warning("No videos found in selected categories")
        
        return filtered_videos

    def download_video(self, url: str, folder: str, category_path: str) -> bool:
        with self._downloads_lock:
            if url in self._downloaded_videos:
                self.logger.info(f"Skipping already downloaded video: {url}")
                return True
            if url in self._active_downloads:
                self.logger.info(f"Skipping video already being downloaded: {url}")
                return True
            self._active_downloads.add(url)
        
        try:
            ydl_opts = self.get_ydl_opts(folder)
            
            # Handle profile URLs differently
            if category_path == "profile":
                ydl_opts['extract_flat'] = True  # Only extract video URLs first
                with YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    if info and 'entries' in info:
                        success = True
                        for entry in info['entries']:
                            video_url = entry.get('url') or entry.get('webpage_url')
                            if video_url:
                                # Download each video
                                ydl_opts['extract_flat'] = False
                                with YoutubeDL(ydl_opts) as video_ydl:
                                    try:
                                        video_info = video_ydl.extract_info(video_url, download=True)
                                        if video_info:
                                            final_filename = video_ydl.prepare_filename(video_info)
                                            if os.path.exists(final_filename):
                                                self._move_metadata_files(final_filename, os.path.join(folder, "metadata"))
                                                title = video_info.get('title', 'Unknown Title')
                                                video_id = video_info.get('id', 'Unknown ID')
                                                log_message(self.success_log, 
                                                        f"URL: {video_url} | TITLE: {title} | ID: {video_id} | CATEGORY: {category_path} | FILE: {final_filename}")
                                                if self.callback:
                                                    self.callback.add_success(title, video_id)
                                            else:
                                                success = False
                                    except Exception as e:
                                        self.logger.error(f"Error downloading profile video {video_url}: {str(e)}")
                                        success = False
                        return success
                return False
            else:
                # Regular video download
                with YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if not info:
                        raise Exception("Failed to extract video info")
                    
                    final_filename = ydl.prepare_filename(info)
                    
                    if os.path.exists(final_filename):
                        self._move_metadata_files(final_filename, os.path.join(folder, "metadata"))
                        
                        title = info.get('title', 'Unknown Title')
                        video_id = info.get('id', 'Unknown ID')
                        log_message(self.success_log, 
                                  f"URL: {url} | TITLE: {title} | ID: {video_id} | CATEGORY: {category_path} | FILE: {final_filename}")
                        
                        if self.callback:
                            self.callback.add_success(title, video_id)
                        
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
            
            if self.callback:
                self.callback.add_error(title, video_id, error_msg)
            
            self.logger.error(f"Failed to download {url}: {error_msg}")
            return False
        
        finally:
            with self._downloads_lock:
                self._active_downloads.remove(url)

    def _move_metadata_files(self, video_filename: str, metadata_folder: str) -> None:
        base_name = os.path.splitext(video_filename)[0]
        metadata_files = [
            f"{base_name}.info.json",
            f"{base_name}.jpg"  
        ]
        
        for metadata_file in metadata_files:
            if os.path.exists(metadata_file):
                shutil.move(metadata_file, os.path.join(metadata_folder, os.path.basename(metadata_file)))

    def download_videos(self, videos: List[Tuple[str, str, str]]) -> None:
        if not videos:
            return
            
        if self.callback and hasattr(self.callback, 'update_batch_size'):
            self.callback.update_batch_size(len(videos))
            
        with ThreadPoolExecutor(max_workers=self.config.concurrent_downloads) as executor:
            futures = []
            for url, folder, category in videos:
                if not self.is_running:
                    break
                futures.append(executor.submit(self.download_video, url, folder, category))
                
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    self.logger.error(f"Error in download thread: {str(e)}")

    def process_videos(self, videos: list, folder_name: str, 
                      link_key: str = "url", category_path: str = "Unknown Category"):
        if not videos:
            self.logger.warning("No videos to process")
            return
            
        folder_path = os.path.join(self.config.output_folder, folder_name)
        create_folder(folder_path)
        create_folder(os.path.join(folder_path, "metadata"))
        
        self.logger.info(f"Processing {len(videos)} videos with {self.config.concurrent_downloads} concurrent downloads")
        
        with ThreadPoolExecutor(max_workers=self.config.concurrent_downloads) as executor:
            futures = []
            for video in videos:
                if isinstance(video, dict) and link_key in video:
                    url = video[link_key]
                    future = executor.submit(self.download_video, url, folder_path, category_path)
                    futures.append(future)
                    self.logger.debug(f"Scheduled download for {url}")
            
            results = []
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as e:
                    self.logger.error(f"Unexpected error in download thread: {str(e)}")
                    results.append(False)
            
            total = len(futures)
            successful = sum(1 for r in results if r)
            self.logger.info(f"Download complete: {successful}/{total} videos downloaded successfully")
