#!/usr/bin/env python3
"""
Generate README with DUST YouTube episodes.

This script fetches videos from the DUST YouTube channel (@watchdust),
filters out reruns/duplicates, and generates a README with unique episodes
in reverse chronological order.
"""

import os
import re
from datetime import datetime
from typing import List, Dict, Set
from googleapiclient.discovery import build
from dateutil import parser as date_parser


YOUTUBE_CHANNEL_ID = "UC7sDT8jZ76VLV1u__krUutA"  # @watchdust channel ID
YOUTUBE_CHANNEL_URL = "https://www.youtube.com/@watchdust"
MAX_RESULTS = 50  # Number of videos to fetch per request
TOTAL_VIDEOS = 200  # Total videos to fetch


def get_youtube_service():
    """Initialize and return YouTube API service."""
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise ValueError("YOUTUBE_API_KEY environment variable not set")
    return build("youtube", "v3", developerKey=api_key)


def normalize_title(title: str) -> str:
    """
    Normalize video title to detect reruns.
    
    Removes common prefixes/suffixes like "DUST Presents:", timestamps,
    and special characters for comparison.
    """
    # Remove common DUST prefixes
    title = re.sub(r'^DUST\s*(Presents?:?|Films?:?)\s*', '', title, flags=re.IGNORECASE)
    
    # Remove timestamps like (2023), [HD], etc.
    title = re.sub(r'\s*[\[\(]\s*\d{4}\s*[\]\)]', '', title)
    title = re.sub(r'\s*[\[\(]\s*HD\s*[\]\)]', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*[\[\(]\s*4K\s*[\]\)]', '', title, flags=re.IGNORECASE)
    
    # Remove "remastered", "reupload", etc.
    title = re.sub(r'\s*[-|]\s*(Remastered|Reupload|Re-upload)', '', title, flags=re.IGNORECASE)
    
    # Normalize whitespace and convert to lowercase
    title = ' '.join(title.split()).lower()
    
    return title


def fetch_videos(youtube) -> List[Dict]:
    """Fetch videos from DUST YouTube channel."""
    videos = []
    next_page_token = None
    
    while len(videos) < TOTAL_VIDEOS:
        # Search for videos in the channel
        request = youtube.search().list(
            part="id,snippet",
            channelId=YOUTUBE_CHANNEL_ID,
            maxResults=min(MAX_RESULTS, TOTAL_VIDEOS - len(videos)),
            order="date",  # Most recent first
            type="video",
            pageToken=next_page_token
        )
        response = request.execute()
        
        for item in response.get("items", []):
            video_id = item["id"]["videoId"]
            snippet = item["snippet"]
            
            videos.append({
                "id": video_id,
                "title": snippet["title"],
                "description": snippet["description"],
                "published_at": snippet["publishedAt"],
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "thumbnail": snippet["thumbnails"]["default"]["url"]
            })
        
        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break
    
    return videos


def filter_unique_episodes(videos: List[Dict]) -> List[Dict]:
    """
    Filter out reruns and duplicate videos.
    
    Returns list of unique episodes based on normalized titles.
    """
    seen_titles: Set[str] = set()
    unique_videos = []
    
    for video in videos:
        normalized = normalize_title(video["title"])
        
        # Skip if we've seen this title before (rerun)
        if normalized in seen_titles:
            continue
        
        # Skip obvious reruns/compilations
        title_lower = video["title"].lower()
        if any(keyword in title_lower for keyword in [
            "compilation", "best of", "top 10", "top 5",
            "trailer", "behind the scenes", "interview"
        ]):
            continue
        
        seen_titles.add(normalized)
        unique_videos.append(video)
    
    return unique_videos


def format_date(date_str: str) -> str:
    """Format ISO date string to readable format."""
    dt = date_parser.parse(date_str)
    return dt.strftime("%B %d, %Y")


def generate_summary(videos: List[Dict]) -> str:
    """Generate summary statistics."""
    if not videos:
        return "No episodes found."
    
    latest = date_parser.parse(videos[0]["published_at"])
    oldest = date_parser.parse(videos[-1]["published_at"])
    
    return f"""**Total Episodes:** {len(videos)}  
**Latest Episode:** {format_date(videos[0]["published_at"])}  
**Oldest Episode (in this list):** {format_date(videos[-1]["published_at"])}"""


def generate_readme(videos: List[Dict]) -> str:
    """Generate README content with episode list."""
    readme = f"""# DUST Episodes

This is an automatically generated list of unique sci-fi short film episodes from the [DUST YouTube channel]({YOUTUBE_CHANNEL_URL}).

> **About DUST:** DUST presents thought-provoking science fiction content, showcasing the visions of the world's most talented sci-fi creators.

## Summary

{generate_summary(videos)}

---

## Episodes

Episodes are listed in reverse chronological order (newest first).

"""
    
    for idx, video in enumerate(videos, 1):
        date = format_date(video["published_at"])
        title = video["title"]
        url = video["url"]
        
        # Get first 150 characters of description
        desc = video["description"]
        if len(desc) > 150:
            desc = desc[:150].rsplit(' ', 1)[0] + "..."
        
        readme += f"### {idx}. [{title}]({url})\n"
        readme += f"**Published:** {date}\n\n"
        if desc.strip():
            readme += f"{desc}\n\n"
        readme += "---\n\n"
    
    readme += f"""
## About This Repository

This README is automatically updated weekly via GitHub Actions.

- **Source:** [DUST YouTube Channel]({YOUTUBE_CHANNEL_URL})
- **Last Updated:** {datetime.utcnow().strftime("%B %d, %Y at %H:%M UTC")}
- **Note:** This list excludes reruns, compilations, and duplicate uploads.

---

*Generated with ❤️ for sci-fi fans*
"""
    
    return readme


def main():
    """Main function to generate README."""
    print("Fetching DUST episodes from YouTube...")
    
    try:
        youtube = get_youtube_service()
        videos = fetch_videos(youtube)
        print(f"Fetched {len(videos)} videos")
        
        unique_videos = filter_unique_episodes(videos)
        print(f"Found {len(unique_videos)} unique episodes")
        
        readme_content = generate_readme(unique_videos)
        
        readme_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "README.md"
        )
        
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        print(f"README.md generated successfully at {readme_path}")
        
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
