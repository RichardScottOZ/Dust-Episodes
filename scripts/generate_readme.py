#!/usr/bin/env python3
"""
Generate README with DUST YouTube episodes.

This script fetches ALL videos from the DUST YouTube channel (@watchdust),
filters out reruns/duplicates, and generates a README with unique episodes
in reverse chronological order.

The script uses YouTube's playlistItems API to reliably paginate through
all videos in the channel's uploads playlist until no more episodes are available.

An optional MAX_VIDEOS environment variable can be set to limit the number of
videos fetched for testing purposes (default: unlimited).
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Set
from googleapiclient.discovery import build
from dateutil import parser as date_parser


YOUTUBE_CHANNEL_ID = "UC7sDT8jZ76VLV1u__krUutA"  # @watchdust channel ID
YOUTUBE_CHANNEL_URL = "https://www.youtube.com/@watchdust"
MAX_RESULTS = 50  # Number of videos to fetch per request

# Optional limit for testing purposes. Set to None to fetch all episodes (default).
# Can be overridden with MAX_VIDEOS environment variable (e.g., MAX_VIDEOS=100)
MAX_VIDEOS_ENV = os.environ.get("MAX_VIDEOS")
TOTAL_VIDEOS = int(MAX_VIDEOS_ENV) if MAX_VIDEOS_ENV else None


def get_youtube_service():
    """Initialize and return YouTube API service."""
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise ValueError(
            "YOUTUBE_API_KEY environment variable not set.\n"
            "Please follow the setup instructions in SETUP.md to:\n"
            "1. Get a YouTube Data API key from Google Cloud Console\n"
            "2. Add it as a GitHub repository secret named 'YOUTUBE_API_KEY'\n"
            "For local testing: export YOUTUBE_API_KEY='your-api-key-here'"
        )
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


def get_uploads_playlist_id(youtube, channel_id: str) -> str:
    """Get the uploads playlist ID for a channel."""
    request = youtube.channels().list(
        part="contentDetails",
        id=channel_id
    )
    response = request.execute()
    
    if not response.get("items"):
        raise ValueError(f"Channel {channel_id} not found")
    
    try:
        uploads_playlist_id = response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    except (KeyError, IndexError) as e:
        raise ValueError(f"Unable to get uploads playlist ID for channel {channel_id}: {e}")
    
    return uploads_playlist_id


def fetch_videos(youtube) -> List[Dict]:
    """Fetch videos from DUST YouTube channel using uploads playlist.
    
    Fetches all available videos unless TOTAL_VIDEOS is set to limit for testing.
    """
    videos = []
    next_page_token = None
    
    # Get the channel's uploads playlist ID
    uploads_playlist_id = get_uploads_playlist_id(youtube, YOUTUBE_CHANNEL_ID)
    print(f"Uploads playlist ID: {uploads_playlist_id}")
    
    if TOTAL_VIDEOS:
        print(f"Fetching up to {TOTAL_VIDEOS} videos (limited by MAX_VIDEOS env var)")
    else:
        print("Fetching all available videos")
    
    while True:
        # Stop if we've reached the optional limit
        if TOTAL_VIDEOS and len(videos) >= TOTAL_VIDEOS:
            print(f"Reached limit of {TOTAL_VIDEOS} videos")
            break
        
        # Calculate how many results to request
        if TOTAL_VIDEOS:
            max_results_this_request = min(MAX_RESULTS, TOTAL_VIDEOS - len(videos))
        else:
            max_results_this_request = MAX_RESULTS
        
        # Fetch videos from the uploads playlist
        request = youtube.playlistItems().list(
            part="snippet",
            playlistId=uploads_playlist_id,
            maxResults=max_results_this_request,
            pageToken=next_page_token
        )
        response = request.execute()
        
        items_in_response = response.get("items", [])
        if not items_in_response:
            print("No more items in response")
            break
        
        videos_before = len(videos)
        
        for item in items_in_response:
            snippet = item.get("snippet", {})
            
            # Skip items with missing required fields
            resource_id = snippet.get("resourceId", {})
            video_id = resource_id.get("videoId")
            if not video_id:
                print(f"Warning: Skipping item with missing video ID")
                continue
            
            # Skip items with missing published date (required for sorting and display)
            published_at = snippet.get("publishedAt")
            if not published_at:
                print(f"Warning: Skipping video {video_id} with missing published date")
                continue
            
            # Get thumbnail URL with fallback
            thumbnails = snippet.get("thumbnails", {})
            default_thumb = thumbnails.get("default", {})
            thumbnail_url = default_thumb.get("url", "")
            
            videos.append({
                "id": video_id,
                "title": snippet.get("title", "Untitled"),
                "description": snippet.get("description", ""),
                "published_at": published_at,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "thumbnail": thumbnail_url
            })
        
        videos_added = len(videos) - videos_before
        print(f"Fetched {len(items_in_response)} items, added {videos_added} valid videos (total so far: {len(videos)})")
        
        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            print("No more pages available")
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
            parts = desc[:150].rsplit(' ', 1)
            desc = (parts[0] if len(parts) > 1 else desc[:150]) + "..."
        
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
        
        # Get project root directory (parent of scripts directory)
        project_root = Path(__file__).parent.parent
        readme_path = project_root / "README.md"
        
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        print(f"README.md generated successfully at {readme_path}")
        
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
