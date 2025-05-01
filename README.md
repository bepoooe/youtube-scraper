# YouTube Channel Scraper

A Python tool to scrape YouTube channels and search results using the Apify platform.

## Features

- Scrape YouTube channels, videos, or search results
- Extract video metadata (title, views, likes, description, etc.)
- Export data to multiple formats (JSON, CSV, HTML)
- Generate interactive HTML dashboards for data visualization
- Track channel statistics and performance metrics

## Requirements

- Python 3.6+
- An Apify account with API token
- YouTube Scraper actor on your Apify account

## Installation

```bash
git clone https://github.com/yourusername/youtube-scraper.git
cd youtube-scraper
pip install -r requirements.txt
```

## Usage

```bash
python youtube_scraper.py "https://www.youtube.com/@ChannelName" --api-token "your_apify_api_token"
```

or for a search query:

```bash
python youtube_scraper.py "your search query" --api-token "your_apify_api_token"
```

### Options

- `--format`: Specify output formats (default: html,json,csv)

## Output

The script creates a folder in `youtube_data/` with:
- JSON file with all video data
- CSV file for spreadsheet analysis
- Interactive HTML dashboard

## License

MIT License 