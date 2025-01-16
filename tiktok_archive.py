import os
import json
from yt_dlp import YoutubeDL
from urllib.parse import urlparse
from datetime import datetime
import shutil

# Settings (Don't change these if you're not sure)
base_folder = "Downloaded_Videos"
create_folder(base_folder)
success_log = os.path.join(base_folder, "success.log")
error_log = os.path.join(base_folder, "error.log")
json_file_path = "data.json"
output_template = "%(uploader)s - %(title).50s - %(id)s.%(ext)s"
save_metadata = True

def create_folder(path):
    if not os.path.exists(path):
        os.makedirs(path)

def sanitize_filename(name, max_length=100):
    sanitized = "".join(c for c in name if c.isalnum() or c in (" ", "-", "_")).rstrip()
    return sanitized[:max_length]  # Limit the length to avoid OS limits

def log_message(file_path, message):
    with open(file_path, 'a', encoding='utf-8') as log_file:
        log_file.write(f"{message}\n")

def download_video(url, folder, output_template, success_log, error_log, category_path, save_metadata=True):
    try:
        # Ensure folder exists
        create_folder(folder)

        # Metadata folder
        metadata_folder = os.path.join(folder, "metadata")
        if save_metadata:
            create_folder(metadata_folder)

        # yt-dlp options
        ydl_opts = {
            'outtmpl': os.path.join(folder, output_template),
            'noprogress': True,  # Disable progress bar in logs
            'restrictfilenames': True,  # Use safe filenames
            'writeinfojson': save_metadata,  # Save metadata alongside the video
            'writethumbnail': save_metadata,  # Save thumbnails if metadata is enabled
            'postprocessors': [
                {'key': 'FFmpegMetadata'},
                {'key': 'EmbedThumbnail', 'already_have_thumbnail': False} if save_metadata else {}
            ]
        }

        # Download video
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            # Construct final filename
            final_filename = ydl.prepare_filename(info)

            # Move metadata files to the metadata folder
            if save_metadata:
                metadata_files = [
                    f"{os.path.splitext(final_filename)[0]}.info.json",
                    f"{os.path.splitext(final_filename)[0]}.jpg"  # Thumbnail
                ]
                for metadata_file in metadata_files:
                    if os.path.exists(metadata_file):
                        dest_metadata_file = os.path.join(metadata_folder, os.path.basename(metadata_file))
                        print(f"Moving metadatafile {metadata_file} {dest_metadata_file}")
                        shutil.move(metadata_file, dest_metadata_file)

        log_message(success_log, f"SUCCESS: {url} | CATEGORY_PATH: {category_path} | FILENAME: {final_filename}")
        print(f"Downloaded: {final_filename}")
    except Exception as e:
        log_message(error_log, f"ERROR: {url} | CATEGORY_PATH: {category_path} - {e}")
        print(f"Failed to download {url}: {e}")


# Load data from file
try:
    with open(json_file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)
except json.JSONDecodeError as e:
    print(f"Failed to load JSON file: {e}")
    data = {}

# Function to process videos from a section
def process_videos(videos, folder_name, link_key="link", category_path="Unknown Category"):
    folder_path = os.path.join(base_folder, folder_name)
    create_folder(folder_path)
    for video in videos:
        url = video.get(link_key)
        if url:
            # yt-dlp output template for filenames
            download_video(url, folder_path, output_template, success_log, error_log, category_path, save_metadata)

# Main:

# Process each category
if "Activity" in data:
    activity = data.get("Activity", {})

    if "Like List" in activity:
        process_videos(activity.get("Like List", {}).get("ItemFavoriteList", []), "Likes", category_path="Activity > Like List > ItemFavoriteList")

    if "Favorite Videos" in activity:
        process_videos(activity.get("Favorite Videos", {}).get("FavoriteVideoList", []), "Favorites", link_key="Link", category_path="Activity > Favorite Videos > FavoriteVideoList")

    if "Video Browsing History" in activity:
        process_videos(activity.get("Video Browsing History", {}).get("VideoList", []), "Browsed", link_key="Link", category_path="Activity > Video Browsing History > VideoList")

    if "Share History" in activity:
        process_videos(activity.get("Share History", {}).get("ShareHistoryList", []), "Shared", link_key="Link", category_path="Activity > Share History > ShareHistoryList")

    if "ChatHistory" in activity:
        chat_videos = activity.get("ChatHistory", [])
        for video in chat_videos:
            folder = "SentTo" if video.get("MessageType") == "Sent" else "ReceivedFrom"
            folder_name = os.path.join(folder, sanitize_filename(video.get("UserName", "Unknown")))
            category_path = f"Activity > ChatHistory > {folder} > {video.get('UserName', 'Unknown')}"
            process_videos([video], folder_name, link_key="VideoLink", category_path=category_path)

# Extract username from JSON data
username = data.get("Profile", {}).get("Profile Information", {}).get("ProfileMap", {}).get("userName")

# Process user videos (posted/reposted)
if username:
    print(f"Processing videos for username: {username}")
    folder_name = f"UserProfile_{username}"
    process_videos([{ "link": f"https://www.tiktok.com/@{username}" }], folder_name, category_path="User Profile")
else:
    print("Username not found in the provided JSON file.")
