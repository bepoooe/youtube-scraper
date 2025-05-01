import requests
import json
import os
import time
import argparse
from datetime import datetime
import csv
import re

def run_youtube_scraper(api_token, url_or_query):
    """Run the YouTube scraper using Apify API."""
    # Look for YouTube scraper actors in the user's account
    print(f"Looking for YouTube scraper actors in your Apify account...")
    search_url = f"https://api.apify.com/v2/acts?token={api_token}"
    search_response = requests.get(search_url)
    
    if search_response.status_code != 200:
        print(f"❌ Failed to search actors: {search_response.status_code}, {search_response.text}")
        return None
    
    # Find YouTube scraper actors
    actors_data = search_response.json()
    available_actors = actors_data.get('data', {}).get('items', [])
    
    youtube_actors = []
    for actor in available_actors:
        name = actor.get('name', '').lower()
        if 'youtube' in name and ('scraper' in name or 'crawler' in name or 'extractor' in name):
            youtube_actors.append(actor)
    
    if not youtube_actors:
        print("❌ No YouTube scraper actors found. Please add one to your Apify account.")
        print("Recommended: YouTube Scraper (https://apify.com/apify/youtube-scraper)")
        return None
    
    # Use the first YouTube scraper found
    actor = youtube_actors[0]
    actor_id = actor.get('id')
    actor_name = actor.get('name')
    
    print(f"Found YouTube scraper: {actor_name} (ID: {actor_id})")
    
    # Create input configuration based on provided URL or search query
    input_config = {}
    if "youtube.com" in url_or_query or "youtu.be" in url_or_query:
        # For video URL
        if "watch?v=" in url_or_query or "youtu.be" in url_or_query:
            input_config = {
                "startUrls": [{"url": url_or_query}],
                "maxResults": 1,
                "proxy": {"useApifyProxy": True}
            }
        # For channel URL
        else:
            input_config = {
                "startUrls": [{"url": url_or_query}],
                "maxResults": 50,
                "proxy": {"useApifyProxy": True}
            }
    else:
        # For search query
        input_config = {
            "search": url_or_query,
            "maxResults": 50,
            "proxy": {"useApifyProxy": True}
        }
    
    print(f"Starting YouTube scraper for: {url_or_query}")
    print(f"Using actor ID: {actor_id}")
    
    # Start the actor run
    start_url = f"https://api.apify.com/v2/acts/{actor_id}/runs?token={api_token}"
    start_response = requests.post(start_url, json=input_config)
    
    if start_response.status_code != 201:
        print(f"❌ Failed to start actor: {start_response.status_code}, {start_response.text}")
        return None
    
    run_data = start_response.json()
    
    # Extract run ID from the response
    run_id = None
    
    # First attempt - direct access to id
    if 'data' in run_data and 'id' in run_data['data']:
        run_id = run_data['data']['id']
    
    # Second attempt - check for actorRunId 
    elif 'data' in run_data and 'actorRunId' in run_data['data']:
        run_id = run_data['data']['actorRunId']
    
    # Third attempt - check for id in the root
    elif 'id' in run_data:
        run_id = run_data['id']
    
    # Final attempt - parse from resource URL if available
    elif 'data' in run_data and 'resource' in run_data['data']:
        resource_url = run_data['data']['resource']
        if resource_url:
            run_id_match = resource_url.split('/')[-1]
            if run_id_match:
                run_id = run_id_match
    
    if not run_id:
        print("❌ No run ID returned")
        print("Response:", json.dumps(run_data, indent=2))
        return None
    
    print(f"✅ Actor started, run ID: {run_id}")
    
    # Poll for run status
    status_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={api_token}"
    max_attempts = 60  # 10 minutes with 10-second intervals
    
    for attempt in range(max_attempts):
        time.sleep(10)  # Wait 10 seconds between checks
        
        status_response = requests.get(status_url)
        if status_response.status_code != 200:
            print(f"❌ Failed to get run status: {status_response.status_code}")
            continue
        
        status_data = status_response.json()
        status = status_data.get('data', {}).get('status')
        
        print(f"Run status: {status} (attempt {attempt+1}/{max_attempts})")
        
        if status in ['SUCCEEDED', 'FAILED', 'TIMED-OUT', 'ABORTED']:
            break
    
    if status != 'SUCCEEDED':
        print(f"❌ Run did not succeed, final status: {status}")
        return None
    
    # Get the run results
    dataset_id = status_data.get('data', {}).get('defaultDatasetId')
    if not dataset_id:
        print("❌ No dataset ID found")
        return None
    
    items_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={api_token}"
    items_response = requests.get(items_url)
    
    if items_response.status_code != 200:
        print(f"❌ Failed to get dataset items: {items_response.status_code}")
        return None
    
    data = items_response.json()
    print(f"✅ Retrieved {len(data)} items from the dataset")
    
    return data

def create_output_folder(name):
    """Create output folder for the results."""
    # Sanitize name to create a valid folder name
    # Remove any characters that are invalid in file paths
    invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    sanitized_name = name
    for char in invalid_chars:
        sanitized_name = sanitized_name.replace(char, '_')
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    folder_path = f"youtube_data/{sanitized_name}_{timestamp}"
    os.makedirs(folder_path, exist_ok=True)
    return folder_path

def format_date(date_str):
    """Format the date string to a more readable format."""
    if not date_str:
        return ""
    
    try:
        # Parse ISO 8601 date format
        date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        # Format as a more readable date
        return date_obj.strftime("%B %d, %Y - %I:%M %p")
    except:
        return date_str

def save_data(data, folder_path, filename="youtube_data", formats=None):
    """Save data to multiple file formats."""
    if formats is None:
        formats = ["json", "csv", "html"]  # Default formats
    
    print(f"Saving data to {folder_path} in formats: {formats}")
    results = {}
    
    # Save JSON data
    if "json" in formats:
        # Format dates in the JSON data
        formatted_data = []
        for item in data:
            item_copy = item.copy()
            if 'date' in item_copy and item_copy['date']:
                item_copy['date'] = format_date(item_copy['date'])
                # Also save the original ISO date for reference
                item_copy['originalISODate'] = item['date']
            formatted_data.append(item_copy)
            
        json_path = os.path.join(folder_path, f"{filename}.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(formatted_data, f, ensure_ascii=False, indent=2)
        print(f"✅ Saved JSON data to {json_path}")
        results["json"] = json_path
    
    # Save as CSV
    if "csv" in formats:
        csv_path = os.path.join(folder_path, f"{filename}.csv")
        if data:
            # Format dates for CSV
            formatted_data = []
            for item in data:
                item_copy = item.copy()
                if 'date' in item_copy and item_copy['date']:
                    item_copy['date'] = format_date(item_copy['date'])
                formatted_data.append(item_copy)
                
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=formatted_data[0].keys())
                writer.writeheader()
                writer.writerows(formatted_data)
            print(f"✅ Saved CSV data to {csv_path}")
            results["csv"] = csv_path
    
    # Save as HTML
    if "html" in formats:
        try:
            html_path = os.path.join(folder_path, f"{filename}.html")
            
            # Calculate total view count and likes
            total_views = sum(item.get('viewCount', 0) for item in data if isinstance(item.get('viewCount', 0), (int, float)))
            total_likes = sum(item.get('likes', 0) for item in data if isinstance(item.get('likes', 0), (int, float)))
            
            # Get channel info from the first item if available
            channel_name = filename
            subscriber_count = 0
            channel_url = ""
            if data and len(data) > 0:
                channel_name = data[0].get('channelName', filename)
                subscriber_count = data[0].get('numberOfSubscribers', 0)
                channel_url = data[0].get('channelUrl', "")
            
            # Generate HTML content
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>YouTube Data: {channel_name}</title>
    <style>
        :root {{
            --bg-color: #111420;
            --card-bg: #1e2132;
            --text-color: #f5f5f5;
            --primary: #ff0000;
            --secondary: #ff5252;
            --accent: #4285f4;
            --muted-text: #a0a0a0;
            --border-color: #333648;
        }}
        body {{ font-family: 'Segoe UI', Roboto, Arial, sans-serif; margin: 0; padding: 0; background-color: var(--bg-color); color: var(--text-color); }}
        .container {{ max-width: 1200px; margin: 20px auto; background: var(--card-bg); border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.2); padding: 25px; }}
        h1 {{ color: var(--primary); margin-bottom: 10px; text-align: center; }}
        h2 {{ color: var(--accent); margin-top: 0; text-align: center; font-weight: normal; margin-bottom: 30px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid var(--border-color); }}
        th {{ background-color: var(--primary); color: white; }}
        tr:hover {{ background-color: rgba(255, 0, 0, 0.1); }}
        .stats {{ display: flex; margin-bottom: 30px; gap: 20px; flex-wrap: wrap; }}
        .stat-block {{ flex: 1; background: var(--card-bg); padding: 20px; border-radius: 12px; text-align: center; border: 1px solid var(--primary); }}
        .stat-value {{ font-size: 28px; font-weight: bold; color: var(--accent); margin-bottom: 10px; }}
        .stat-label {{ font-size: 16px; color: var(--text-color); }}
        .search-input {{ width: 100%; padding: 12px; font-size: 16px; margin-bottom: 20px; border: 2px solid var(--border-color); background: var(--bg-color); color: var(--text-color); border-radius: 8px; }}
        a {{ color: var(--accent); text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .channel-info {{ display: flex; align-items: center; justify-content: center; margin-bottom: 20px; }}
        .channel-link {{ background-color: var(--primary); color: white; padding: 8px 16px; border-radius: 20px; margin-left: 10px; }}
        .channel-link:hover {{ background-color: var(--secondary); text-decoration: none; }}
        .date-cell {{ white-space: nowrap; }}
    </style>
    <script>
        function searchTable() {{
            let input = document.getElementById("searchInput");
            let filter = input.value.toUpperCase();
            let table = document.getElementById("videoTable");
            let tr = table.getElementsByTagName("tr");
            
            for (let i = 1; i < tr.length; i++) {{
                let found = false;
                let td = tr[i].getElementsByTagName("td");
                for (let j = 0; j < td.length; j++) {{
                    if (td[j]) {{
                        let txtValue = td[j].textContent || td[j].innerText;
                        if (txtValue.toUpperCase().indexOf(filter) > -1) {{
                            found = true;
                            break;
                        }}
                    }}
                }}
                tr[i].style.display = found ? "" : "none";
            }}
        }}
    </script>
</head>
<body>
    <div class="container">
        <h1>{channel_name}</h1>
        <h2>{subscriber_count:,} subscribers</h2>
        
        <div class="channel-info">
            <a href="{channel_url}" target="_blank" class="channel-link">Visit Channel</a>
        </div>
        
        <div class="stats">
            <div class="stat-block">
                <div class="stat-value">{len(data)}</div>
                <div class="stat-label">Videos</div>
            </div>
            <div class="stat-block">
                <div class="stat-value">{total_views:,}</div>
                <div class="stat-label">Total Views</div>
            </div>
            <div class="stat-block">
                <div class="stat-value">{total_likes:,}</div>
                <div class="stat-label">Total Likes</div>
            </div>
        </div>
        
        <input type="text" id="searchInput" class="search-input" onkeyup="searchTable()" placeholder="Search videos...">
        
        <table id="videoTable">
            <thead>
                <tr>
                    <th>Title</th>
                    <th>Views</th>
                    <th>Likes</th>
                    <th>Duration</th>
                    <th>Published Date</th>
                    <th>Link</th>
                </tr>
            </thead>
            <tbody>
"""
            
            # Add table rows for each video
            for item in data:
                title = item.get('title', '')
                views = f"{item.get('viewCount', 0):,}"
                likes = f"{item.get('likes', 0):,}"
                duration = item.get('duration', '')
                date = format_date(item.get('date', ''))
                url = item.get('url', '')
                
                html_content += f"""                <tr>
                    <td>{title}</td>
                    <td>{views}</td>
                    <td>{likes}</td>
                    <td>{duration}</td>
                    <td class="date-cell">{date}</td>
                    <td><a href="{url}" target="_blank">View</a></td>
                </tr>
"""
            
            # Close the HTML
            html_content += """            </tbody>
        </table>
    </div>
</body>
</html>"""
            
            # Write HTML to file
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print(f"✅ Saved HTML report to {html_path}")
            results["html"] = html_path
            
        except Exception as e:
            print(f"❌ Failed to generate HTML: {str(e)}")
    
    return results

def process_youtube_data(data):
    """Process the raw YouTube data into a standardized format."""
    processed_data = []
    
    # Debug: Print all available fields from the first item
    if data and len(data) > 0:
        print("\nDEBUG: Available fields in first YouTube item:")
        for key in data[0].keys():
            print(f"  - {key}: {data[0][key]}")
    
    # Extract channel name for folder creation
    channel_name = "youtube_data"
    if data and len(data) > 0:
        if 'channelName' in data[0] and data[0]['channelName']:
            channel_name = data[0]['channelName']
        elif 'aboutChannelInfo' in data[0] and data[0]['aboutChannelInfo'] and 'channelName' in data[0]['aboutChannelInfo']:
            channel_name = data[0]['aboutChannelInfo']['channelName']
    
    # Sanitize channel name for folder
    invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for char in invalid_chars:
        channel_name = channel_name.replace(char, '_')
    
    for item in data:
        # Handle different response formats
        if 'id' in item and 'title' in item:
            # Try to get the date from multiple possible field names
            date = ""
            for date_field in ["uploadDate", "date", "publishedAt", "publishDate", "datePublished"]:
                if date_field in item and item[date_field]:
                    date = item[date_field]
                    break
            
            # Get subscriber count
            subscribers = 0
            if 'numberOfSubscribers' in item and item['numberOfSubscribers']:
                subscribers = item['numberOfSubscribers']
            elif 'aboutChannelInfo' in item and item['aboutChannelInfo'] and 'numberOfSubscribers' in item['aboutChannelInfo']:
                subscribers = item['aboutChannelInfo']['numberOfSubscribers']
            
            # Create a standardized entry
            entry = {
                "title": item.get("title", ""),
                "id": item.get("id", ""),
                "url": item.get("url", f"https://www.youtube.com/watch?v={item.get('id', '')}"),
                "viewCount": item.get("viewCount", 0),
                "date": date,
                "likes": item.get("likes", 0),
                "channelName": item.get("channelName", ""),
                "channelUrl": item.get("channelUrl", ""),
                "numberOfSubscribers": subscribers,
                "duration": item.get("duration", "")
            }
            processed_data.append(entry)
    
    return processed_data, channel_name

def main():
    parser = argparse.ArgumentParser(description="YouTube Scraper using Apify")
    parser.add_argument("url_or_query", help="YouTube URL or search query")
    parser.add_argument("--api-token", required=True, help="Your Apify API token")
    parser.add_argument("--format", default="html,json,csv", help="Output format(s), comma-separated: html,json,csv")
    args = parser.parse_args()
    
    url_or_query = args.url_or_query
    api_token = args.api_token
    
    # Parse formats
    formats = [fmt.strip().lower() for fmt in args.format.split(",")]
    
    # Run the scraper to get raw data first
    raw_data = run_youtube_scraper(api_token, url_or_query)
    
    if not raw_data or len(raw_data) == 0:
        print(f"\n❌ Failed to retrieve any YouTube data")
        return
    
    # Process data into standardized format and get channel name
    processed_data, channel_name = process_youtube_data(raw_data)
    
    # Use the channel name for output folder
    output_folder = create_output_folder(channel_name)
    print(f"Created output folder: {output_folder}")
    
    # Save the processed data in requested formats
    saved_files = save_data(processed_data, output_folder, channel_name, formats)
    
    print(f"\n✅ Successfully retrieved YouTube data for {channel_name}")
    print(f"Found {len(processed_data)} videos")
    print(f"Output saved to {output_folder}")
    
    # Print summary of saved files
    print("\n📁 Saved in the following formats:")
    for fmt, path in saved_files.items():
        print(f"  - {fmt.upper()}: {os.path.basename(path)}")

if __name__ == "__main__":
    main() 