import os
import json
import time
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
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
        self.root.geometry("1200x1000")
        
        # State
        self.is_running = False
        self.is_paused = False
        self.config = Config(config_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config.json"))
        self.log_queue = queue.Queue()
        self.download_thread = None
        self.downloader = None
        
        # Initialize variables
        self.file_path = tk.StringVar()
        self.output_folder = tk.StringVar(value=self.config.output_folder)
        self.concurrent_downloads = tk.StringVar(value=str(self.config.concurrent_downloads))
        initial_rate = float(self.config.total_rate_limit) / (1024 * 1024)
        self.total_rate_limit = tk.StringVar(value=str(initial_rate))
        self.save_metadata = tk.BooleanVar(value=self.config.save_metadata)
        
        # Add variable traces
        self.output_folder.trace_add("write", self.on_setting_change)
        self.concurrent_downloads.trace_add("write", self.on_setting_change)
        self.total_rate_limit.trace_add("write", self.on_setting_change)
        self.save_metadata.trace_add("write", self.on_setting_change)
        
        # Set up logging
        setup_logging(os.path.join(self.config.output_folder, "logs"))
        self.logger = logging.getLogger(__name__)
        
        # Build UI
        self._create_main_frame()
        
        # Set up window close handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Add console handler
        console_handler = ConsoleHandler(None, self.log_queue)
        logging.getLogger().addHandler(console_handler)
        
        self._init_ui()
        console_handler.console = self.console  # Set console after UI init
        
    def _init_ui(self):
        """Initialize the user interface"""
        self._create_file_section()
        self._create_config_section()
        self._create_summary_section()
        self._create_control_section()
        self._create_console_section()
        self._create_progress_bar()
        
        # Start console update
        self.update_console()
    
    def _create_main_frame(self):
        """Create and configure the main frame"""
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.N, tk.W, tk.E, tk.S))
        self.main_frame.columnconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

    def _create_file_section(self):
        """Create file selection section"""
        file_frame = ttk.Frame(self.main_frame)
        file_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        file_frame.columnconfigure(1, weight=1)
        
        self.file_path.trace_add("write", self.on_file_path_change)
        
        self.file_entry = ttk.Entry(file_frame, textvariable=self.file_path, width=50)
        self.file_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
        ttk.Label(file_frame, text="Data File:").grid(row=0, column=0, sticky=tk.W)
        ttk.Button(file_frame, text="Browse", command=self.browse_file).grid(row=0, column=2)

    def _create_config_section(self):
        """Create configuration section"""
        config_frame = ttk.LabelFrame(self.main_frame, text="Configuration", padding="5")
        config_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Output folder selection
        folder_frame = ttk.Frame(config_frame)
        folder_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=2)
        
        ttk.Label(folder_frame, text="Output Folder:").grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Entry(folder_frame, textvariable=self.output_folder).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        ttk.Button(folder_frame, text="Browse", command=self.browse_folder).grid(row=0, column=2, padx=5)
        
        # Download settings
        settings_frame = ttk.Frame(config_frame)
        settings_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=2)
        
        # Concurrent downloads
        ttk.Label(settings_frame, text="Concurrent Downloads:").grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Entry(settings_frame, textvariable=self.concurrent_downloads, width=10).grid(row=0, column=1, padx=5, pady=2)
        
        # Rate limit (convert bytes/s to MB/s for display)
        ttk.Label(settings_frame, text="Total Rate Limit (MB/s):").grid(row=0, column=2, sticky=tk.W, padx=5)
        ttk.Entry(settings_frame, textvariable=self.total_rate_limit, width=10).grid(row=0, column=3, padx=5, pady=2)
        
        # Save metadata
        ttk.Checkbutton(settings_frame, text="Save Metadata", variable=self.save_metadata).grid(row=0, column=4, padx=5, pady=2)
        
        # Category selection
        category_frame = ttk.LabelFrame(config_frame, text="Categories to Download", padding="5")
        category_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Initialize category variables
        self.download_likes = tk.BooleanVar(value=self.config.download_likes)
        self.download_favorites = tk.BooleanVar(value=self.config.download_favorites)
        self.download_history = tk.BooleanVar(value=self.config.download_history)
        self.download_shared = tk.BooleanVar(value=self.config.download_shared)
        self.download_chat = tk.BooleanVar(value=self.config.download_chat)
        
        # Add traces
        self.download_likes.trace_add("write", self.on_setting_change)
        self.download_favorites.trace_add("write", self.on_setting_change)
        self.download_history.trace_add("write", self.on_setting_change)
        self.download_shared.trace_add("write", self.on_setting_change)
        self.download_chat.trace_add("write", self.on_setting_change)
        
        # Create checkboxes
        ttk.Checkbutton(category_frame, text="Likes", variable=self.download_likes).grid(row=0, column=0, padx=10, pady=2)
        ttk.Checkbutton(category_frame, text="Favorites", variable=self.download_favorites).grid(row=0, column=1, padx=10, pady=2)
        ttk.Checkbutton(category_frame, text="History", variable=self.download_history).grid(row=0, column=2, padx=10, pady=2)
        ttk.Checkbutton(category_frame, text="Shared", variable=self.download_shared).grid(row=0, column=3, padx=10, pady=2)
        ttk.Checkbutton(category_frame, text="Chat", variable=self.download_chat).grid(row=0, column=4, padx=10, pady=2)

    def browse_folder(self):
        """Open folder browser dialog"""
        folder = filedialog.askdirectory(initialdir=self.output_folder.get())
        if folder:
            self.output_folder.set(folder)

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

    def _create_control_section(self):
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
        """Create progress bars"""
        progress_frame = ttk.LabelFrame(self.main_frame, text="Download Progress", padding="5")
        progress_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5, padx=5)
        progress_frame.columnconfigure(0, weight=1)  # Make column expandable
        
        # Overall batch progress
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, mode='determinate', length=400)
        self.progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5, pady=2)
        self.progress_label = ttk.Label(progress_frame, text="0/0 files completed")
        self.progress_label.grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        
        # Initialize batch tracking
        self.total_files = 0
        self.completed_files = 0
        
    def update_batch_size(self, total_files: int):
        """Update the total number of files in the batch"""
        self.total_files = total_files
        self.completed_files = 0
        self.progress_var.set(0)
        self.progress_label.config(text=f"0/{total_files} files completed")
        
    def update_progress(self, status: dict):
        """Update progress when a file completes"""
        try:
            if status.get('status') == 'finished':
                self.completed_files += 1
                if self.total_files > 0:
                    percent = (self.completed_files / self.total_files) * 100
                    self.progress_var.set(percent)
                    self.progress_label.config(text=f"{self.completed_files}/{self.total_files} files completed")
                    
            elif status.get('status') == 'error':
                self.completed_files += 1
                if self.total_files > 0:
                    percent = (self.completed_files / self.total_files) * 100
                    self.progress_var.set(percent)
                    self.progress_label.config(text=f"{self.completed_files}/{self.total_files} files completed")
                
        except Exception as e:
            self.logger.error(f"Error updating progress: {str(e)}")

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
        """Update config from UI values"""
        self.config.output_folder = self.output_folder.get()
        try:
            concurrent = int(self.concurrent_downloads.get())
            if concurrent < 1:
                self.log("Warning: Concurrent downloads must be at least 1")
                concurrent = 1
            self.config.concurrent_downloads = concurrent
        except ValueError:
            self.log("Warning: Invalid concurrent downloads value, using 1")
            self.config.concurrent_downloads = 1
            
        try:
            total_rate = float(self.total_rate_limit.get())
            if total_rate < 1:
                self.log("Warning: Rate limit must be at least 1 MB/s")
                total_rate = 1
            self.config.total_rate_limit = int(total_rate * 1024 * 1024)  # Convert MB/s to bytes/s
        except ValueError:
            self.log("Warning: Invalid rate limit value, using 1 MB/s")
            self.config.total_rate_limit = 1024 * 1024
            
        self.config.save_metadata = self.save_metadata.get()
        self.config.save_config("config.json")

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
            
        # Check if output folder is set
        output_folder = self.config.output_folder
        if not output_folder:
            self.log("Error: Output folder not set")
            return False
            
        # Create output folder if it doesn't exist
        try:
            os.makedirs(output_folder, exist_ok=True)
        except Exception as e:
            self.log(f"Error creating output folder: {str(e)}")
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
        """Process the download"""
        if not self.file_path.get():
            self.log("Please select a data file first")
            return
            
        if not os.path.exists(self.file_path.get()):
            self.log(f"File not found: {self.file_path.get()}")
            return

        self.is_running = True
        self.update_buttons()
        self.update_batch_size(0)
        
        try:
            # Initialize downloader with GUI reference
            self.downloader = TikTokDownloader(self.config, self)
            
            # Parse data file
            data = None
            with open(self.file_path.get(), 'r', encoding='utf-8') as f:
                data = json.loads(f.read())
                
            if not data:
                self.log("Error: Empty data file")
                return
                
            # Extract video URLs
            videos = self.downloader.extract_videos(data)
            
            if not videos:
                self.log("No videos found in data file")
                return
                
            total_videos = len(videos)
            self.log(f"Found {total_videos} videos to download")
            
            # Update batch size
            self.update_batch_size(total_videos)
            downloaded = 0  # Initialize counter
            
            # Process videos in batches
            batch_size = self.config.concurrent_downloads
            for i in range(0, len(videos), batch_size):
                if not self.is_running:
                    break
                    
                batch = videos[i:i + batch_size]
                futures = []
                
                with ThreadPoolExecutor(max_workers=batch_size) as executor:
                    for url, folder, category in batch:
                        if not self.is_running:
                            break
                        futures.append(executor.submit(self.downloader.download_video, url, folder, category))
                        
                    for future in futures:
                        if not self.is_running:
                            break
                            
                        if future.result():
                            downloaded += 1
                            
                        # Update progress percentage
                        percentage = (downloaded / total_videos) * 100
                        self.progress_label.config(text=f"Progress: {percentage:.1f}% ({downloaded}/{total_videos})")
                
                if not self.is_running:
                    self.log("Download stopped by user")
                    break
                    
            if self.is_running:
                self.log("All downloads completed")
                
        except Exception as e:
            self.log(f"Error processing download: {str(e)}")
            import traceback
            traceback.print_exc()
            
        finally:
            self.is_running = False
            self.update_buttons()

    def start_download(self):
        """Start download process"""
        if self.download_thread and self.download_thread.is_alive():
            return
            
        self.is_running = True
        self.is_paused = False
        
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

    def on_setting_change(self, *args):
        """Update config when settings change"""
        try:
            # Update output folder
            new_folder = self.output_folder.get()
            if new_folder != self.config.output_folder:
                self.config.output_folder = new_folder
                
            # Update concurrent downloads
            try:
                concurrent = int(self.concurrent_downloads.get())
                if concurrent < 1:
                    self.log("Warning: Concurrent downloads must be at least 1")
                    concurrent = 1
                    self.concurrent_downloads.set(str(concurrent))
                self.config.concurrent_downloads = concurrent
            except ValueError:
                self.log("Warning: Invalid concurrent downloads value, using 1")
                self.config.concurrent_downloads = 1
                self.concurrent_downloads.set("1")
            
            # Update rate limit
            try:
                total_rate = float(self.total_rate_limit.get())
                if total_rate < 1:
                    self.log("Warning: Rate limit must be at least 1 MB/s")
                    total_rate = 1
                    self.total_rate_limit.set(str(total_rate))
                self.config.total_rate_limit = int(total_rate * 1024 * 1024)  # Convert MB/s to bytes/s
            except ValueError:
                self.log("Warning: Invalid rate limit value, using 1 MB/s")
                self.config.total_rate_limit = 1024 * 1024
                self.total_rate_limit.set("1")
            
            # Update save metadata
            self.config.save_metadata = self.save_metadata.get()
            
            # Update category selection
            self.config.download_likes = self.download_likes.get()
            self.config.download_favorites = self.download_favorites.get()
            self.config.download_history = self.download_history.get()
            self.config.download_shared = self.download_shared.get()
            self.config.download_chat = self.download_chat.get()
            
            # Save config
            self.config.save_config("config.json")
            
        except Exception as e:
            self.log(f"Error updating settings: {str(e)}")

    def on_closing(self):
        """Handle window close event"""
        if self.is_running:
            if messagebox.askokcancel("Quit", "Downloads are in progress. Stop downloads and quit?"):
                self.stop_download()
                self.root.after(100, self._check_and_close)  # Give time for threads to clean up
            return
        self.root.destroy()
        
    def _check_and_close(self):
        """Check if downloads have stopped before closing"""
        if self.download_thread and self.download_thread.is_alive():
            self.root.after(100, self._check_and_close)  # Check again in 100ms
        else:
            self.root.destroy()
            
    def stop_download(self):
        """Stop the download process"""
        self.is_running = False
        if self.downloader:
            self.downloader.is_running = False  # Signal downloader to stop
        if self.download_thread:
            self.download_thread.join(timeout=0.1)  # Give thread a chance to finish
