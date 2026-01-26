# Setup Instructions

## GitHub Actions Setup

To enable the automated weekly README updates:

1. **Get a YouTube Data API Key:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Enable the YouTube Data API v3
   - Create credentials (API Key)
   - Copy the API key

2. **Add the API Key to GitHub Secrets:**
   - Go to your repository on GitHub
   - Navigate to Settings > Secrets and variables > Actions
   - Click "New repository secret"
   - Name: `YOUTUBE_API_KEY`
   - Value: Paste your YouTube API key
   - Click "Add secret"

3. **Manual Trigger (Optional):**
   - Go to Actions tab in your repository
   - Select "Update README with DUST Episodes"
   - Click "Run workflow"

## Local Development

To test the script locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Set your API key
export YOUTUBE_API_KEY="your-api-key-here"

# Run the script
python scripts/generate_readme.py
```

## How It Works

- The workflow runs automatically every Sunday at 00:00 UTC
- It fetches the latest videos from the DUST YouTube channel
- Filters out reruns, compilations, and duplicate uploads
- Generates a README with unique episodes in reverse chronological order
- Commits and pushes the updated README if there are changes
