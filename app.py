import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
import json
import queue
import threading
import os
from datetime import datetime
from config import Config
from downloader import TikTokDownloader
import time
import sys
import subprocess

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
        
        # Check ffmpeg availability
        self.check_ffmpeg()
        
        # Redirect stdout to our console
        sys.stdout = self
        sys.stderr = self
        
        # Create main frame
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # File selection
        file_frame = ttk.LabelFrame(main_frame, text="Data File", padding="5")
        file_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.file_path = tk.StringVar()
        self.file_path.trace_add("write", self.on_file_path_change)
        ttk.Entry(file_frame, textvariable=self.file_path).grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5)
        ttk.Button(file_frame, text="Browse", command=self.browse_file).grid(row=0, column=1, padx=5)
        
        # Configuration
        config_frame = ttk.LabelFrame(main_frame, text="Configuration", padding="5")
        config_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Concurrent downloads
        ttk.Label(config_frame, text="Concurrent Downloads:").grid(row=0, column=0, padx=5, pady=2)
        self.concurrent_downloads = tk.StringVar(value=str(self.config.concurrent_downloads))
        self.concurrent_downloads.trace_add("write", lambda *args: self.validate_rate_limits())
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
        # Convert bytes/s to MB/s for display
        initial_rate = float(self.config.total_rate_limit) / (1024 * 1024) if self.config.total_rate_limit.isdigit() else float(self.config.total_rate_limit.rstrip('M'))
        self.total_rate_limit = tk.StringVar(value=str(initial_rate))
        self.total_rate_limit.trace_add("write", lambda *args: self.validate_rate_limits())
        ttk.Entry(rate_frame, textvariable=self.total_rate_limit, width=10).grid(row=0, column=1, padx=5, pady=2)
        
        # Rate warning label
        self.rate_warning = ttk.Label(rate_frame, text="", wraplength=300, justify=tk.LEFT)
        self.rate_warning.grid(row=1, column=0, columnspan=2, padx=5, pady=2, sticky=(tk.W, tk.E))
        
        # Data Summary
        self.summary_frame = ttk.LabelFrame(main_frame, text="Data Summary", padding="5")
        self.summary_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Create summary labels with good spacing and alignment
        summary_grid = ttk.Frame(self.summary_frame)
        summary_grid.grid(row=0, column=0, sticky=(tk.W, tk.E))
        summary_grid.columnconfigure(1, weight=1)  # Make value column expand
        
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
            self.summary_labels[key] = ttk.Label(summary_grid, text="-")
            self.summary_labels[key].grid(row=i, column=1, sticky=tk.W, padx=5, pady=2)
        
        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=5)
        
        self.start_button = ttk.Button(button_frame, text="Start", command=self.start_download)
        self.start_button.grid(row=0, column=0, padx=5)
        
        self.pause_button = ttk.Button(button_frame, text="Pause", command=self.toggle_pause, state=tk.DISABLED)
        self.pause_button.grid(row=0, column=1, padx=5)
        
        self.stop_button = ttk.Button(button_frame, text="Stop", command=self.stop_download, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=2, padx=5)
        
        # Console output
        console_frame = ttk.LabelFrame(main_frame, text="Console", padding="5")
        console_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.console = scrolledtext.ScrolledText(console_frame, height=20, width=80)
        self.console.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(main_frame, length=300, mode='determinate', variable=self.progress_var)
        self.progress.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Start console update
        self.update_console()
    
    def write(self, text):
        """Handle stdout/stderr redirection"""
        self.log(text.strip())
    
    def flush(self):
        """Required for stdout/stderr redirection"""
        pass
    
    def browse_file(self):
        filename = filedialog.askopenfilename(
            title="Select TikTok Data Export",
            filetypes=[("JSON files", "*.json")]
        )
        if filename:
            self.file_path.set(filename)
    
    def update_config(self):
        """Update config with GUI values"""
        concurrent = int(self.concurrent_downloads.get())
        total_rate = float(self.total_rate_limit.get())
        
        self.config.concurrent_downloads = concurrent
        self.config.total_rate_limit = str(int(total_rate * 1024 * 1024))  # Convert MB/s to bytes/s
        self.config.download_batch_size = int(self.batch_size.get())
        self.config.save_metadata = self.save_metadata.get()
        
        # Save updated config to file
        self.config.save_config()

    def log(self, message):
        """Add message to log queue"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_queue.put(f"[{timestamp}] {message}\n")
    
    def update_console(self):
        """Update console from log queue"""
        while not self.log_queue.empty():
            message = self.log_queue.get()
            self.console.insert(tk.END, message)
            self.console.see(tk.END)
        self.root.after(100, self.update_console)
    
    def toggle_pause(self):
        """Pause/Resume download"""
        if not self.download_thread or not self.is_running:
            return
            
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.pause_button.configure(text="Resume")
            self.log("Downloads paused")
        else:
            self.pause_button.configure(text="Pause")
            self.log("Downloads resumed")

    def stop_download(self):
        """Stop the download process"""
        self.is_running = False
        self.is_paused = False
        if self.download_thread:
            self.download_thread.join(timeout=1.0)  # Wait for thread to finish
            self.download_thread = None
        self.start_button.configure(state=tk.NORMAL)
        self.pause_button.configure(state=tk.DISABLED)
        self.pause_button.configure(text="Pause")
        self.stop_button.configure(state=tk.DISABLED)
        self.log("Download stopped")

    def process_chat_videos(self, chat_history, chat_base_path):
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

    def process_download(self):
        """Process downloads in background thread"""
        try:
            # Load TikTok data
            with open(self.file_path.get(), 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Initialize downloader
            downloader = TikTokDownloader(self.config)
            
            # Process each category
            categories = [
                ("Like List", "ItemFavoriteList", "Likes"),
                ("Favorite Videos", "FavoriteVideoList", "Favorites"),
                ("Video Browsing History", "VideoList", "Browsed"),
                ("Share History", "ShareHistoryList", "Shared")
            ]
            
            total_videos = 0
            processed_videos = 0
            
            # Count total videos
            for category, list_key, folder_name in categories:
                if "Activity" in data and category in data["Activity"]:
                    videos = data["Activity"][category].get(list_key, [])
                    total_videos += len(videos)
            
            # Count chat videos
            chat_history = {}
            if "Direct Messages" in data and "Chat History" in data["Direct Messages"]:
                chat_history = data["Direct Messages"]["Chat History"].get("ChatHistory", {})
            
            chat_videos = self.process_chat_videos(chat_history, "Direct Messages > Chat History > ChatHistory")
            total_videos += len(chat_videos)
            
            self.log(f"Found {total_videos} videos to download")
            
            # Process regular categories
            for category, list_key, folder_name in categories:
                if not self.is_running:
                    return
                    
                while self.is_paused and self.is_running:
                    time.sleep(0.1)  # Wait while paused
                
                if "Activity" in data and category in data["Activity"]:
                    videos = data["Activity"][category].get(list_key, [])
                    if videos:
                        self.log(f"Processing {len(videos)} videos from {category}")
                        # Extract URLs from the video data
                        video_urls = []
                        for video in videos:
                            if isinstance(video, dict) and "Link" in video:
                                video_urls.append({"url": video["Link"]})
                        
                        if video_urls:
                            self.log(f"Found {len(video_urls)} valid URLs in {category}")
                            self.log(f"Sample URL: {video_urls[0]['url'] if video_urls else 'None'}")
                            
                            # Process videos in smaller batches
                            batch_size = self.config.download_batch_size
                            for i in range(0, len(video_urls), batch_size):
                                if not self.is_running:
                                    return
                                    
                                while self.is_paused and self.is_running:
                                    time.sleep(0.1)  # Wait while paused
                                
                                batch = video_urls[i:i + batch_size]
                                downloader.process_videos(
                                    batch,
                                    folder_name,
                                    link_key="url",
                                    category_path=f"Activity > {category} > {list_key}"
                                )
                                processed_videos += len(batch)
                                self.progress_var.set((processed_videos / total_videos) * 100)
                        else:
                            self.log(f"No valid video links found in {category}")
            
            # Process chat videos
            if chat_videos:
                self.log(f"Found {len(chat_videos)} chat videos")
                if chat_videos:
                    self.log(f"Sample chat URL: {chat_videos[0][1]['url'] if chat_videos else 'None'}")
                
                # Process chat videos in batches
                batch_size = self.config.download_batch_size
                for i in range(0, len(chat_videos), batch_size):
                    if not self.is_running:
                        return
                        
                    while self.is_paused and self.is_running:
                        time.sleep(0.1)  # Wait while paused
                    
                    batch = chat_videos[i:i + batch_size]
                    for username, video in batch:
                        folder_name = os.path.join("ChatHistory", username)
                        category_path = f"Direct Messages > Chat History > ChatHistory > Chat History with {username}"
                        
                        self.log(f"Processing video from chat with {username}")
                        downloader.process_videos(
                            [video],
                            folder_name,
                            link_key="url",
                            category_path=category_path
                        )
                        processed_videos += 1
                        self.progress_var.set((processed_videos / total_videos) * 100)
            
            self.log("Download completed successfully!")
            
        except Exception as e:
            self.log(f"Error: {str(e)}")
            import traceback
            self.log(traceback.format_exc())
        finally:
            self.download_thread = None
            self.is_running = False
            self.is_paused = False
            self.start_button.configure(state=tk.NORMAL)
            self.pause_button.configure(state=tk.DISABLED)
            self.pause_button.configure(text="Pause")
            self.stop_button.configure(state=tk.DISABLED)

    def start_download(self):
        """Start download process"""
        if not self.file_path.get():
            self.log("Please select a data file first")
            return
        
        try:
            self.update_config()
            self.progress_var.set(0)
            self.is_running = True
            self.is_paused = False
            self.start_button.configure(state=tk.DISABLED)
            self.pause_button.configure(state=tk.NORMAL)
            self.stop_button.configure(state=tk.NORMAL)
            
            self.download_thread = threading.Thread(target=self.process_download)
            self.download_thread.daemon = True
            self.download_thread.start()
            
        except Exception as e:
            self.log(f"Error starting download: {str(e)}")
            self.start_button.configure(state=tk.NORMAL)
            self.pause_button.configure(state=tk.DISABLED)
            self.stop_button.configure(state=tk.DISABLED)

    def on_file_path_change(self, *args):
        if self.file_path.get():
            try:
                with open(self.file_path.get(), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Update summary labels
                total_videos = 0
                likes = 0
                favorites = 0
                history = 0
                shared = 0
                chat = 0
                
                categories = [
                    ("Like List", "ItemFavoriteList", "Likes"),
                    ("Favorite Videos", "FavoriteVideoList", "Favorites"),
                    ("Video Browsing History", "VideoList", "Browsed"),
                    ("Share History", "ShareHistoryList", "Shared")
                ]
                
                for category, list_key, folder_name in categories:
                    if "Activity" in data and category in data["Activity"]:
                        videos = data["Activity"][category].get(list_key, [])
                        total_videos += len(videos)
                        if folder_name == "Likes":
                            likes = len(videos)
                        elif folder_name == "Favorites":
                            favorites = len(videos)
                        elif folder_name == "Browsed":
                            history = len(videos)
                        elif folder_name == "Shared":
                            shared = len(videos)
                
                # Process chat videos
                chat_history = {}
                if "Direct Messages" in data and "Chat History" in data["Direct Messages"]:
                    chat_history = data["Direct Messages"]["Chat History"].get("ChatHistory", {})
                
                chat_videos = self.process_chat_videos(chat_history, "Direct Messages > Chat History > ChatHistory")
                chat = len(chat_videos)
                total_videos += chat
                
                file_size = os.path.getsize(self.file_path.get())
                
                self.summary_labels["total_videos"].config(text=str(total_videos))
                self.summary_labels["likes"].config(text=str(likes))
                self.summary_labels["favorites"].config(text=str(favorites))
                self.summary_labels["history"].config(text=str(history))
                self.summary_labels["shared"].config(text=str(shared))
                self.summary_labels["chat"].config(text=str(chat))
                self.summary_labels["size"].config(text=f"{file_size / (1024 * 1024):.2f} MB")
            
            except Exception as e:
                self.log(f"Error loading data file: {str(e)}")
                for label in self.summary_labels.values():
                    label.config(text="-")

    def validate_rate_limits(self):
        """Validate rate limits and concurrent downloads"""
        try:
            concurrent = int(self.concurrent_downloads.get())
            total = float(self.total_rate_limit.get())
            
            warning_messages = []
            
            # Check if average rate per download is too low
            avg_rate = total / concurrent if concurrent > 0 else 0
            if avg_rate < 0.5:
                warning_messages.append(
                    f"{concurrent} downloads and {total}MB/s total rate limit will result in "
                    f"each download only getting ~{avg_rate:.1f}MB/s. "
                    "This may cause timeouts."
                )
            
            # Suggest better values
            if warning_messages:
                suggested_total = max(concurrent * 0.5, total)  # At least 0.5MB/s per download
                warning_messages.append(
                    f"Either reduce concurrent downloads to {max(1, int(total / 0.5))} "
                    f"or increase total rate limit to ~{suggested_total:.1f}MB/s"
                )
            
            # Update warning label
            if warning_messages:
                self.rate_warning.config(
                    text="\n".join(warning_messages),
                    foreground="red"
                )
            else:
                self.rate_warning.config(text="", foreground="black")
            
        except (ValueError, ZeroDivisionError):
            self.rate_warning.config(
                text="Please enter valid numbers for rate limit and concurrent downloads",
                foreground="red"
            )

    def check_ffmpeg(self):
        """Check ffmpeg availability and warn if not found"""
        # Create a temporary downloader to check ffmpeg
        downloader = TikTokDownloader(self.config)
        if not downloader.ffmpeg_path:
            self.log("WARNING: ffmpeg not found in PATH or tools directory!")
            self.log("Videos will fail to download until ffmpeg is available.")
            self.log("Please run Setup.bat to install ffmpeg or add it to your system PATH.")
        else:
            self.log(f"Found ffmpeg: {downloader.ffmpeg_path}")
            
        # Also try direct command to help debug
        try:
            result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
            self.log(f"Direct ffmpeg check succeeded: {result.stdout.splitlines()[0] if result.stdout else ''}")
        except Exception as e:
            self.log(f"Direct ffmpeg check failed: {str(e)}")

def main():
    root = tk.Tk()
    app = TikTokArchiverGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
