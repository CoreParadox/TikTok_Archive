# TikTok Archive Downloader

A Python tool I made to bulk download videos from TikTok data exports. Handles liked videos, favorites, history, shared videos, chat history, and your own profile videos.

I rarely use python, and whipped this together in a few hours. I promise this code is ugly.

# Support
If this helped and you'd like to give me some thanks you can do so on 
* [ko-fi](coreparadox.com/☕)
* Following/subscribing to me on [twitch.tv](coreparadox.com/twitch)
* Follow me on [Bluesky](https://bsky.app/profile/coreparadox.com)


## Features

- Downloads all video types from your TikTok data export:
  - Profile videos (your own posted/reposted content)
  - Liked videos
  - Favorites
  - Watch history
  - Shared videos
  - Videos from chat history
- Videos are saved into different folders based on category
- Saves metadata and thumbnails (optional)
- Multi-threaded downloads so it's not slow af
- Gui Based
- Detailed logging, ideally meant to be reentrant based off of success/error logs.

## Requirements

- Python 3.8+
- FFmpeg

## Setup

1. Clone/download this repo somewhere

Windows users can run `Setup.bat` to install everything and then `Run.bat` to run the app

Mac and Linux users can just make sure they have Python and FFmpeg installed and run the following:

```
# Install dependencies
pip install -r requirements.txt

# Install FFmpeg if you don't have it
# Linux: sudo apt-get install ffmpeg
# Mac: brew install ffmpeg

# Run the app
python main.py
```

## How to Use
1. Download your TikTok data
   1. Login to TikTok
   2. Go to settings and privacy
   3. Account
   4. Download your data
   5. Request Data => All Data
   6. File Format => JSON (important!!!!!)
   7. It may take a while depending on how much data you have, mine was only a few minutes
   8. Go back to the same path (Settings and Privacy => Account => Download your data)
   9. Download your Data => Download
   10. Unzip the file, it should be called user_data_tiktok.json

2. Run the app:
   - Double click `Run.bat` (Windows)
   - Or run `python main.py` from terminal

3. In the app:
   - Pick your data file (the user_data.json from step 1)
   - Choose what to download (profile, likes, etc)
   - Set your download folder
   - Hit Start and let it run

## Config Options

- Output folder: Where to save everything
- Concurrent downloads: How many videos to download at once (default: 10)
- Rate limit: Max download speed in MB/s (default: 10MB/s)
- Save metadata: Keep the video info (on by default)
- Categories: Toggle which types of videos to download


## Contributing

Contributions welcome, but I don't imagine this will be useful for too long lol
