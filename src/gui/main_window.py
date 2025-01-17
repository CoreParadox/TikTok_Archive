"""Main GUI window for TikTok Archiver"""
import os
import json
import time
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
from datetime import datetime
from typing import Dict, Any, List, Tuple
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..core.config import Config
from ..core.downloader import TikTokDownloader
from ..utils.file_utils import setup_logging
from src.utils.data_parser import TikTokDataParser

class ConsoleHandler(logging.Handler):
    def __init__(self, console_widget, log_queue):
        super().__init__()
        self.console = console_widget
        self.log_queue = log_queue
        self.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))

    def emit(self, record):
        msg = self.format(record)
        self.log_queue.put(msg + '\n')

class TikTokArchiverGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("TikTok Archiver")
        self.root.geometry("1200x800")
        
        # State
        self.is_running = False
        self.is_paused = False
        self.config = Config()
        self.log_queue = queue.Queue()
        self.download_thread = None
        
        # Set up logging
        setup_logging(os.path.join(self.config.base_folder, "logs"))
        
        # Add console handler
        console_handler = ConsoleHandler(None, self.log_queue)
        logging.getLogger().addHandler(console_handler)
        
        self._init_ui()
        console_handler.console = self.console  # Set console after UI init
        
    def _init_ui(self):
        """Initialize the user interface"""
        self._create_main_frame()
        self._create_file_section()
        self._create_config_section()
        self._create_summary_section()
        self._create_control_buttons()
        self._create_console_section()
        self._create_progress_bar()
        
        # Start console update
        self.update_console()
    
    def _create_main_frame(self):
        """Create and configure the main frame"""
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)

    def _create_file_section(self):
        """Create file selection section"""
        file_frame = ttk.LabelFrame(self.main_frame, text="Data File", padding="5")
        file_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        file_frame.columnconfigure(1, weight=1)
        
        self.file_path = tk.StringVar()
        self.file_path.trace_add("write", self.on_file_path_change)
        
        self.file_entry = ttk.Entry(file_frame, textvariable=self.file_path, width=50)
        self.file_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
        browse_button = ttk.Button(file_frame, text="Browse", command=self.browse_file)
        browse_button.grid(row=0, column=2, padx=5)

    def _create_config_section(self):
        """Create configuration section"""
        config_frame = ttk.LabelFrame(self.main_frame, text="Configuration", padding="5")
        config_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Concurrent downloads
        ttk.Label(config_frame, text="Concurrent Downloads:").grid(row=0, column=0, padx=5, pady=2)
        self.concurrent_downloads = tk.StringVar(value=str(self.config.concurrent_downloads))
        ttk.Entry(config_frame, textvariable=self.concurrent_downloads, width=10).grid(row=0, column=1, padx=5, pady=2)
        
        # Batch size
        ttk.Label(config_frame, text="Batch Size:").grid(row=1, column=0, padx=5, pady=2)
        self.batch_size = tk.StringVar(value=str(self.config.download_batch_size))
        ttk.Entry(config_frame, textvariable=self.batch_size, width=10).grid(row=1, column=1, padx=5, pady=2)
        
        # Save metadata
        self.save_metadata = tk.BooleanVar(value=self.config.save_metadata)
        ttk.Checkbutton(config_frame, text="Save Metadata", variable=self.save_metadata).grid(row=0, column=3, padx=5, pady=2)
        
        # Rate limits
        rate_frame = ttk.LabelFrame(config_frame, text="Rate Limits", padding="5")
        rate_frame.grid(row=0, column=2, rowspan=2, sticky=(tk.W, tk.E), padx=5)
        
        ttk.Label(rate_frame, text="Total Rate Limit (MB/s):").grid(row=0, column=0, padx=5, pady=2)
        initial_rate = float(self.config.total_rate_limit) / (1024 * 1024) if self.config.total_rate_limit.isdigit() else float(self.config.total_rate_limit.rstrip('M'))
        self.total_rate_limit = tk.StringVar(value=str(initial_rate))
        ttk.Entry(rate_frame, textvariable=self.total_rate_limit, width=10).grid(row=0, column=1, padx=5, pady=2)

    def _create_summary_section(self):
        """Create data summary section"""
        self.summary_frame = ttk.LabelFrame(self.main_frame, text="Data Summary", padding="5")
        self.summary_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        summary_grid = ttk.Frame(self.summary_frame)
        summary_grid.grid(row=0, column=0, sticky=(tk.W, tk.E))
        summary_grid.columnconfigure(1, weight=1)
        
        self.summary_labels = {}
        summary_items = [
            ("total_videos", "Total Videos:"),
            ("likes", "Liked Videos:"),
            ("favorites", "Favorite Videos:"),
            ("history", "Watch History:"),
            ("shared", "Shared Videos:"),
            ("chat", "Chat Videos:"),
            ("size", "File Size:")
        ]
        
        for i, (key, text) in enumerate(summary_items):
            ttk.Label(summary_grid, text=text).grid(row=i, column=0, sticky=tk.W, padx=(5, 10), pady=2)
            self.summary_labels[key] = ttk.Label(summary_grid, text="0")
            self.summary_labels[key].grid(row=i, column=1, sticky=tk.W, padx=5, pady=2)

    def _create_control_buttons(self):
        """Create control buttons"""
        button_frame = ttk.Frame(self.main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=5)
        
        self.start_button = ttk.Button(button_frame, text="Start", command=self.start_download)
        self.start_button.grid(row=0, column=0, padx=5)
        
        self.pause_button = ttk.Button(button_frame, text="Pause", command=self.toggle_pause, state=tk.DISABLED)
        self.pause_button.grid(row=0, column=1, padx=5)
        
        self.stop_button = ttk.Button(button_frame, text="Stop", command=self.stop_download, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=2, padx=5)

    def _create_console_section(self):
        """Create console output and status sections"""
        # Create frame for console and status boxes
        console_frame = ttk.LabelFrame(self.main_frame, text="Status", padding="5")
        console_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        console_frame.columnconfigure(0, weight=1)
        console_frame.columnconfigure(1, weight=1)
        console_frame.rowconfigure(1, weight=1)
        
        # Main console
        console_label = ttk.Label(console_frame, text="Console Output:")
        console_label.grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(0,5))
        
        self.console = scrolledtext.ScrolledText(console_frame, height=10, width=80)
        self.console.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        # Success box
        success_label = ttk.Label(console_frame, text="Successful Downloads:")
        success_label.grid(row=2, column=0, sticky=tk.W, padx=5, pady=(5,0))
        
        self.success_box = scrolledtext.ScrolledText(console_frame, height=8, width=40)
        self.success_box.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        # Error box
        error_label = ttk.Label(console_frame, text="Failed Downloads:")
        error_label.grid(row=2, column=1, sticky=tk.W, padx=5, pady=(5,0))
        
        self.error_box = scrolledtext.ScrolledText(console_frame, height=8, width=40)
        self.error_box.grid(row=3, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

    def _create_progress_bar(self):
        """Create progress bar"""
        progress_frame = ttk.Frame(self.main_frame)
        progress_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.progress_label = ttk.Label(progress_frame, text="Progress: 0% (0/0)")
        self.progress_label.pack(side=tk.LEFT, padx=5)
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate', length=400)
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

    def browse_file(self):
        """Open file dialog to select data file"""
        file_path = filedialog.askopenfilename(
            title="Select TikTok Data File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            self.file_path.set(file_path)
            self.log(f"Selected data file: {file_path}")

    def update_config(self):
        """Update config with GUI values"""
        self.config.concurrent_downloads = int(self.concurrent_downloads.get())
        total_rate = float(self.total_rate_limit.get())
        self.config.total_rate_limit = str(int(total_rate * 1024 * 1024))  # Convert MB/s to bytes/s
        self.config.download_batch_size = int(self.batch_size.get())
        self.config.save_metadata = self.save_metadata.get()
        self.config.save_config()

    def log(self, message: str):
        """Add message to log queue"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_queue.put(f"[{timestamp}] {message}\n")

    def update_console(self):
        """Update console from log queue"""
        while not self.log_queue.empty():
            try:
                message = self.log_queue.get_nowait()
                self.console.insert(tk.END, message)
                self.console.see(tk.END)
                self.console.update_idletasks()
            except queue.Empty:
                break
        self.root.after(100, self.update_console)

    def toggle_pause(self):
        """Toggle pause state"""
        if not self.is_running:
            return
            
        self.is_paused = not self.is_paused
        self.pause_button.configure(text="Resume" if self.is_paused else "Pause")
        
        if self.is_paused:
            self.log("Download paused")
        else:
            self.log("Download resumed")

    def stop_download(self):
        """Stop the download process"""
        self.is_running = False
        self.is_paused = False
        self.pause_button.configure(text="Pause")
        self.update_buttons()
        self.log("Download stopped")

    def validate_inputs(self) -> bool:
        """Validate user inputs before starting download"""
        # Check if data file is selected
        data_file = self.file_path.get()
        if not data_file:
            self.log("Error: Please select a data file")
            return False
            
        if not os.path.exists(data_file):
            self.log("Error: Selected data file does not exist")
            return False
            
        # Check if base folder is set
        base_folder = self.config.base_folder
        if not base_folder:
            self.log("Error: Base folder not set")
            return False
            
        # Create base folder if it doesn't exist
        try:
            os.makedirs(base_folder, exist_ok=True)
        except Exception as e:
            self.log(f"Error creating base folder: {str(e)}")
            return False
            
        return True

    def load_data_file(self, file_path: str) -> Dict[str, Any]:
        """Load and validate the data file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Validate basic data structure
            if not isinstance(data, dict):
                raise ValueError("Invalid data format: root must be a dictionary")
                
            if "Activity" not in data:
                raise ValueError("Invalid data format: missing 'Activity' section")
                
            return data
            
        except json.JSONDecodeError as e:
            self.log(f"Error: Invalid JSON format in data file - {str(e)}")
            return None
        except Exception as e:
            self.log(f"Error reading data file: {str(e)}")
            return None

    def process_download(self):
        """Process the download of videos"""
        if not self.validate_inputs():
            return

        self.is_running = True
        self.update_buttons()
        self.progress_bar["value"] = 0
        self.progress_label.config(text="Progress: 0% (0/0)")
        
        try:
            # Initialize downloader with GUI reference
            downloader = TikTokDownloader(self.config, self)
            
            # Get data file path
            data_file = self.file_path.get()
            
            # Load and process data
            data = self.load_data_file(data_file)
            if not data:
                return
            
            # Extract video URLs
            videos = downloader.extract_videos(data)
            if not videos:
                self.log("No videos found to download")
                return
            
            total_videos = len(videos)
            self.log(f"Found {total_videos} videos to download")
            
            # Update progress bar
            self.progress_bar["maximum"] = total_videos
            downloaded = 0
            
            # Process videos in batches
            batch_size = self.config.concurrent_downloads
            for i in range(0, len(videos), batch_size):
                if not self.is_running:
                    break
                    
                batch = videos[i:i + batch_size]
                self.log(f"Processing batch {(i//batch_size)+1} ({len(batch)} videos)")
                
                with ThreadPoolExecutor(max_workers=batch_size) as executor:
                    futures = []
                    for url, folder, category in batch:
                        if not self.is_running:
                            break
                        futures.append(executor.submit(downloader.download_video, url, folder, category))
                    
                    for future in as_completed(futures):
                        if not self.is_running:
                            break
                        if future.result():
                            downloaded += 1
                        # Update progress
                        self.progress_bar["value"] = downloaded
                        self.root.update_idletasks()
                        
                        # Update progress percentage
                        percentage = (downloaded / total_videos) * 100
                        self.progress_label.config(text=f"Progress: {percentage:.1f}% ({downloaded}/{total_videos})")
                
                if not self.is_running:
                    self.log("Download stopped by user")
                    break
            
            if self.is_running:
                self.log(f"Download complete. Successfully downloaded {downloaded} out of {total_videos} videos")
        
        except Exception as e:
            self.log(f"Error processing data file: {str(e)}")
            import traceback
            self.log(traceback.format_exc())
        
        finally:
            self.is_running = False
            self.update_buttons()

    def start_download(self):
        """Start download process"""
        if self.download_thread and self.download_thread.is_alive():
            return
            
        self.is_running = True
        self.is_paused = False
        self.progress_bar["value"] = 0
        self.progress_label.config(text="Progress: 0% (0/0)")
        
        # Clear success and error boxes
        self.success_box.delete(1.0, tk.END)
        self.error_box.delete(1.0, tk.END)
        
        # Update button states
        self.start_button.configure(state=tk.DISABLED)
        self.pause_button.configure(state=tk.NORMAL)
        self.stop_button.configure(state=tk.NORMAL)
        
        # Start download thread
        self.download_thread = threading.Thread(target=self.process_download)
        self.download_thread.start()

    def update_buttons(self):
        """Update button states based on current status"""
        if self.is_running:
            self.start_button.configure(state=tk.DISABLED)
            self.pause_button.configure(state=tk.NORMAL)
            self.stop_button.configure(state=tk.NORMAL)
        else:
            self.start_button.configure(state=tk.NORMAL)
            self.pause_button.configure(state=tk.DISABLED)
            self.stop_button.configure(state=tk.DISABLED)
            # Reset pause button text
            self.pause_button.configure(text="Pause")

    def on_file_path_change(self, *args):
        """Update summary when file path changes"""
        if not os.path.exists(self.file_path.get()):
            return
        
        try:
            with open(self.file_path.get(), 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            counts, _ = TikTokDataParser.parse_data_file(data)
            
            # Update summary labels
            for key, count in counts.items():
                if key == "size":
                    continue
                self.summary_labels[key].configure(text=str(count))
            
            # Calculate file size
            size = os.path.getsize(self.file_path.get())
            size_str = f"{size / (1024*1024):.2f} MB"
            self.summary_labels["size"].configure(text=size_str)
            
            # Log summary
            self.log("\n=== Data File Summary ===")
            self.log(f"Likes: {counts['likes']} videos")
            self.log(f"Favorites: {counts['favorites']} videos")
            self.log(f"History: {counts['history']} videos")
            self.log(f"Shared: {counts['shared']} videos")
            self.log(f"Chat: {counts['chat']} videos")
            self.log(f"Total Videos: {counts['total_videos']}")
            self.log(f"File Size: {size_str}")
            self.log("========================\n")
            
        except Exception as e:
            self.log(f"Error reading data file: {str(e)}")
            import traceback
            self.log(traceback.format_exc())

    def add_success(self, title: str, video_id: str):
        """Add a successful download to the success box"""
        self.success_box.insert(tk.END, f"{title} ({video_id})\n")
        self.success_box.see(tk.END)
        self.success_box.update_idletasks()

    def add_error(self, title: str, video_id: str, error: str):
        """Add a failed download to the error box"""
        self.error_box.insert(tk.END, f"{title} ({video_id}): {error}\n")
        self.error_box.see(tk.END)
        self.error_box.update_idletasks()

    def process_chat_videos(self, chat_history: Dict[str, Any], chat_base_path: str) -> List[Tuple[str, Dict[str, str]]]:
        """Process videos from chat history"""
        chat_videos = []
        video_string = "https://www.tiktokv.com/share/video/"
        for chat_key, messages in chat_history.items():
            if chat_key.startswith("Chat History with "):
                # Extract username from the chat key
                username = chat_key.replace("Chat History with ", "")
                for message in messages:
                    if isinstance(message, dict) and "Content" in message and isinstance(message["Content"], str):
                        content = message["Content"]
                        if video_string in content:
                            # Extract the URL - it might be part of a longer message
                            for word in content.split():
                                if word.startswith(video_string):
                                    chat_videos.append((username, {"url": word.strip()}))
                                    break
        return chat_videos
