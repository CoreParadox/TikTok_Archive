import os
import json
import argparse
import logging
from typing import Optional, Dict, Any

from config import Config
from downloader import TikTokDownloader
from utils import setup_logging, sanitize_filename

def parse_args():
    parser = argparse.ArgumentParser(description='TikTok Archive Downloader')
    parser.add_argument('--config', type=str, default='config.json',
                       help='Path to config file')
    parser.add_argument('--data', type=str, default='data.json',
                       help='Path to TikTok data export JSON file')
    parser.add_argument('--log-dir', type=str, default='logs',
                       help='Directory for log files')
    parser.add_argument('--username', type=str,
                       help='TikTok username for downloading user videos')
    return parser.parse_args()

def load_data(json_file_path: str) -> Dict[str, Any]:
    """Load and validate TikTok data export"""
    try:
        with open(json_file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        return data
    except json.JSONDecodeError as e:
        logging.error(f"Failed to load JSON file: {e}")
        return {}
    except FileNotFoundError:
        logging.error(f"Data file not found: {json_file_path}")
        return {}

def process_activity_data(downloader: TikTokDownloader, activity: Dict[str, Any]) -> None:
    """Process all activity data"""
    # Process likes
    if "Like List" in activity:
        downloader.process_videos(
            activity.get("Like List", {}).get("ItemFavoriteList", []),
            "Likes",
            link_key="url",
            category_path="Activity > Like List > ItemFavoriteList"
        )

    # Process favorites
    if "Favorite Videos" in activity:
        downloader.process_videos(
            activity.get("Favorite Videos", {}).get("FavoriteVideoList", []),
            "Favorites",
            link_key="url",
            category_path="Activity > Favorite Videos > FavoriteVideoList"
        )

    # Process browsing history
    if "Video Browsing History" in activity:
        downloader.process_videos(
            activity.get("Video Browsing History", {}).get("VideoList", []),
            "Browsed",
            link_key="url",
            category_path="Activity > Video Browsing History > VideoList"
        )

    # Process share history
    if "Share History" in activity:
        downloader.process_videos(
            activity.get("Share History", {}).get("ShareHistoryList", []),
            "Shared",
            link_key="url",
            category_path="Activity > Share History > ShareHistoryList"
        )

    # Process chat history
    if "ChatHistory" in activity:
        chat_history = activity.get("ChatHistory", {})
        
        # Process sent messages
        if "SentTo" in chat_history:
            for friend, messages in chat_history["SentTo"].items():
                folder_name = os.path.join("ChatHistory", "SentTo", sanitize_filename(friend))
                category_path = f"Activity > ChatHistory > SentTo > {friend}"
                downloader.process_videos(messages, folder_name, link_key="url", category_path=category_path)
        
        # Process received messages
        if "ReceivedFrom" in chat_history:
            for friend, messages in chat_history["ReceivedFrom"].items():
                folder_name = os.path.join("ChatHistory", "ReceivedFrom", sanitize_filename(friend))
                category_path = f"Activity > ChatHistory > ReceivedFrom > {friend}"
                downloader.process_videos(messages, folder_name, link_key="url", category_path=category_path)

def process_user_profile(downloader: TikTokDownloader, data: Dict[str, Any]) -> None:
    """Process user's own videos"""
    username = data.get("Profile", {}).get("Profile Information", {}).get("ProfileMap", {}).get("userName")
    if username:
        logging.info(f"Processing videos for username: {username}")
        folder_name = f"UserProfile_{username}"
        downloader.process_videos(
            [{"url": f"https://www.tiktok.com/@{username}"}],
            folder_name,
            link_key="url",
            category_path="User Profile"
        )
    else:
        logging.warning("Username not found in the provided JSON file.")

def main():
    args = parse_args()
    setup_logging(args.log_dir)
    
    # Load configuration
    config = Config.from_file(args.config)
    
    # Initialize downloader
    downloader = TikTokDownloader(config)
    
    # Load data
    data = load_data(args.data)
    if not data:
        logging.error("No data loaded, exiting.")
        return

    # Process user profile if username provided
    if args.username:
        process_user_profile(downloader, data)

    # Process activity data
    if "Activity" in data:
        process_activity_data(downloader, data["Activity"])
    else:
        logging.warning("No activity data found in the provided JSON file.")

if __name__ == "__main__":
    main()
