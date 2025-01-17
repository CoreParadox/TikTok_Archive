# TikTok Archive Downloader

A Python-based tool for downloading and organizing videos from your TikTok data export.

## Features

- Downloads videos from your TikTok data export including:
  - Liked videos
  - Favorite videos
  - Browsing history
  - Shared videos
  - Chat history videos
  - Your own posted/reposted videos
- Organizes downloads into categorized folders
- Saves video metadata and thumbnails
- Concurrent downloads for better performance
- Configurable download settings
- Detailed logging and error tracking

## Requirements

- Python 3.8 or higher
- FFmpeg (for metadata embedding and thumbnail processing)

## Installation

1. Clone this repository:
   ```bash
   git clone <repository-url>
   cd tiktok-archive
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Install FFmpeg:
   - Windows: Download from [FFmpeg website](https://ffmpeg.org/download.html)
   - Linux: `sudo apt-get install ffmpeg`
   - macOS: `brew install ffmpeg`

## Usage

1. Export your TikTok data:
   - Go to TikTok Settings > Privacy > Download Your Data
   - Request data in JSON format
   - Wait for the export to be ready and download it
   - Extract the downloaded archive

2. Run the script:
   ```bash
   python tiktok_archive.py --data path/to/data.json
   ```

### Command Line Arguments

- `--config`: Path to config file (default: config.json)
- `--data`: Path to TikTok data export JSON file (default: data.json)
- `--log-dir`: Directory for log files (default: logs)

### Configuration

You can customize the download behavior by editing `config.json`:

```json
{
    "base_folder": "Downloaded_Videos",
    "output_template": "%(uploader)s - %(title).50s - %(id)s.%(ext)s",
    "save_metadata": true,
    "max_retries": 3,
    "timeout": 300,
    "concurrent_downloads": 3,
    "min_video_quality": "720p",
    "skip_existing": true,
    "rate_limit": "1M"
}
```

## Project Structure

- `tiktok_archive.py`: Main script
- `config.py`: Configuration management
- `downloader.py`: Video download functionality
- `utils.py`: Utility functions
- `config.json`: User configuration
- `requirements.txt`: Python dependencies

## Logs and Output

- Success and error logs are stored in the download folder
- Detailed application logs are stored in the logs directory
- Downloaded videos are organized in folders by category
- Metadata and thumbnails are stored in a separate metadata folder within each category

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
