from typing import Dict, Any, Tuple, List, Optional

class TikTokDataParser:
    TIKTOK_URL_PATTERN = "https://www.tiktokv.com/share/video/"
    
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
    def extract_username(data: Dict[str, Any]) -> Optional[str]:
        """Extract username from TikTok data export"""
        try:
            if "Profile" in data:
                print(f"Profile data: {data['Profile'].keys()}")
                profile = data["Profile"].get("Profile Information", {})
                print(f"Profile Information: {profile.keys()}")
                if "ProfileMap" in profile:
                    print(f"ProfileMap: {profile['ProfileMap']}")
                    username = profile["ProfileMap"].get("userName")
                    print(f"Found username: {username}")
                    return username
                print("No ProfileMap found")
            print("No Profile section found")
            return None
        except Exception as e:
            print(f"Error extracting username: {e}")
            return None
    
    @staticmethod
    def parse_data_file(data: Dict[str, Any]) -> Tuple[Dict[str, int], List[Tuple[str, str, str]], Optional[str]]:
        """Returns (category_counts, video_list, username) from TikTok data export"""
        print("\n=== Starting parse_data_file ===")
        counts = {
            "total_videos": 0,
            "likes": 0,
            "favorites": 0,
            "history": 0,
            "shared": 0,
            "chat": 0
        }
        
        videos = []
        username = TikTokDataParser.extract_username(data)
        print(f"Username after extraction: {username}")
        
        # Process regular categories
        for category_id, category in TikTokDataParser.CATEGORIES.items():
            if category_id == "chat":  # Chat is handled separately
                continue
                
            if category["section"] in data:
                category_data = data[category["section"]].get(category["name"], {})
                if category_data:
                    video_list = category_data.get(category["list_key"], [])
                    if video_list:
                        count = 0
                        for video in video_list:
                            if isinstance(video, dict):
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
            
            if chat_history:
                for username_key, messages in chat_history.items():
                    if not username_key.startswith("Chat History with "):
                        continue
                        
                    chat_username = username_key.replace("Chat History with ", "").rstrip(":")
                    if not isinstance(messages, list):
                        continue
                        
                    for message in messages:
                        if not isinstance(message, dict) or "Content" not in message:
                            continue
                            
                        content = message.get("Content", "")
                        if not isinstance(content, str) or TikTokDataParser.TIKTOK_URL_PATTERN not in content:
                            continue
                            
                        for word in content.split():
                            if TikTokDataParser.TIKTOK_URL_PATTERN in word:
                                chat_count += 1
                                category_path = f"{chat['section']} > {chat['name']} > {chat_username}"
                                videos.append((word.strip(), f"{chat['folder']}/{chat_username}", "chat"))
                                break
                
                counts["chat"] = chat_count
                counts["total_videos"] += chat_count
        
        print(f"Username before return: {username}")
        print("=== Finished parse_data_file ===\n")
        return counts, videos, username

    @staticmethod
    def is_category_match(category_id: str, category_from_data: str) -> bool:
        return category_id == category_from_data
