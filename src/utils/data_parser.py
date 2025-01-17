"""Utility functions for parsing TikTok data files"""
from typing import Dict, Any, Tuple, List

class TikTokDataParser:
    TIKTOK_URL_PATTERN = "https://www.tiktokv.com/share/video/"
    
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
        categories = [
            ("Like List", "ItemFavoriteList", "Likes", "likes"),
            ("Favorite Videos", "FavoriteVideoList", "Favorites", "favorites"),
            ("Video Browsing History", "VideoList", "History", "history"),
            ("Share History", "ShareHistoryList", "Shared", "shared")
        ]
        
        if "Activity" in data:
            print("Found Activity section")
            for category, list_key, folder_name, count_key in categories:
                if category in data["Activity"]:
                    print(f"Found {category}")
                    if category == "Like List":
                        print("Like List structure:", data["Activity"]["Like List"])
                    video_list = data["Activity"][category].get(list_key, [])
                    print(f"{category} > {list_key} count:", len(video_list))
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
                                category_path = f"Activity > {category} > {list_key}"
                                videos.append((url, folder_name, category_path))
                    
                    counts[count_key] = count
                    counts["total_videos"] += count
        
        # Process chat videos
        if "Direct Messages" in data and "Chat History" in data["Direct Messages"]:
            chat_history = data["Direct Messages"]["Chat History"].get("ChatHistory", {})
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
                            category_path = f"Direct Messages > Chat History > {username}"
                            videos.append((word.strip(), f"ChatHistory/{username}", category_path))
                            break
            
            counts["chat"] = chat_count
            counts["total_videos"] += chat_count
        
        return counts, videos
