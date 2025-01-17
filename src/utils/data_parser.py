"""Utility functions for parsing TikTok data files"""
from typing import Dict, Any, Tuple, List

class TikTokDataParser:
    TIKTOK_URL_PATTERN = "https://www.tiktokv.com/share/video/"
    
    # Category definitions
    CATEGORIES = {
        "likes": {
            "section": "Activity",
            "name": "Like List",
            "list_key": "ItemFavoriteList",
            "folder": "Likes",
            "count_key": "likes"
        },
        "favorites": {
            "section": "Activity",
            "name": "Favorite Videos",
            "list_key": "FavoriteVideoList",
            "folder": "Favorites",
            "count_key": "favorites"
        },
        "history": {
            "section": "Activity",
            "name": "Video Browsing History",
            "list_key": "VideoList",
            "folder": "History",
            "count_key": "history"
        },
        "shared": {
            "section": "Activity",
            "name": "Share History",
            "list_key": "ShareHistoryList",
            "folder": "Shared",
            "count_key": "shared"
        },
        "chat": {
            "section": "Direct Messages",
            "name": "Chat History",
            "folder": "ChatHistory",
            "count_key": "chat"
        }
    }
    
    @staticmethod
    def parse_data_file(data: Dict[str, Any]) -> Tuple[Dict[str, int], List[Tuple[str, str, str]]]:
        """Parse TikTok data file and return counts and video info
        
        Args:
            data: Loaded JSON data from TikTok data file
            
        Returns:
            Tuple containing:
            - Dict with counts for each category (likes, favorites, history, shared, chat)
            - List of tuples (url, folder_name, category_path) for each video
        """
        counts = {
            "total_videos": 0,
            "likes": 0,
            "favorites": 0,
            "history": 0,
            "shared": 0,
            "chat": 0
        }
        
        videos = []
        
        # Process regular categories
        for category_id, category in TikTokDataParser.CATEGORIES.items():
            if category_id == "chat":  # Chat is handled separately
                continue
                
            if category["section"] in data:
                if category["name"] in data[category["section"]]:
                    video_list = data[category["section"]][category["name"]].get(category["list_key"], [])
                    count = 0
                    for video in video_list:
                        if isinstance(video, dict):
                            # Try different possible URL fields
                            url = None
                            for field in ["link", "Link", "shareURL", "ShareURL", "videoURL", "VideoURL"]:
                                if field in video and video[field]:
                                    url = video[field]
                                    break
                            if url:
                                count += 1
                                category_path = f"{category['section']} > {category['name']} > {category['list_key']}"
                                videos.append((url, category["folder"], category_id))
                    
                    counts[category["count_key"]] = count
                    counts["total_videos"] += count
        
        # Process chat videos
        chat = TikTokDataParser.CATEGORIES["chat"]
        if chat["section"] in data and chat["name"] in data[chat["section"]]:
            chat_history = data[chat["section"]][chat["name"]].get("ChatHistory", {})
            chat_count = 0
            
            for username_key, messages in chat_history.items():
                if not username_key.startswith("Chat History with "):
                    continue
                    
                username = username_key.replace("Chat History with ", "").rstrip(":")
                if not isinstance(messages, list):
                    continue
                    
                for message in messages:
                    if not isinstance(message, dict) or "Content" not in message:
                        continue
                        
                    content = message.get("Content", "")
                    if not isinstance(content, str) or TikTokDataParser.TIKTOK_URL_PATTERN not in content:
                        continue
                        
                    # Extract URL from message
                    for word in content.split():
                        if TikTokDataParser.TIKTOK_URL_PATTERN in word:
                            chat_count += 1
                            category_path = f"{chat['section']} > {chat['name']} > {username}"
                            videos.append((word.strip(), f"{chat['folder']}/{username}", "chat"))
                            break
            
            counts["chat"] = chat_count
            counts["total_videos"] += chat_count
        
        return counts, videos
        
    @staticmethod
    def is_category_match(category_id: str, category_from_data: str) -> bool:
        """Check if a category from the data matches a category ID"""
        return category_id == category_from_data
