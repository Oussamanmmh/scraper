import instaloader
import re
import sys
import os
import requests
import time
from bs4 import BeautifulSoup

def download_instagram_video(url):
    # Extract shortcode from URL
    match = re.search(r'instagram\.com/(?:reel|p|tv)/([^/?#]+)', url)
    if not match:
        return "❌ Invalid Instagram URL. Please provide a reel, post, or IGTV URL."
    
    shortcode = match.group(1)
    loader = instaloader.Instaloader(
        quiet=False,
        download_pictures=False,
        download_videos=True,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False
    )

    try:
        # Try to load post
        post = instaloader.Post.from_shortcode(loader.context, shortcode)
        
        if not post.is_video:
            return "❌ This post does not contain a video."
        
        print(f"📥 Downloading: {post.title or 'Instagram Video'}")
        
        # Create target directory
        target_dir = f"./{shortcode}"
        os.makedirs(target_dir, exist_ok=True)
        
        # Download the post
        loader.download_post(post, target=target_dir)
        
        # Wait a moment for files to be written
        time.sleep(1)
        
        # Find the downloaded video file
        for file in os.listdir(target_dir):
            if file.endswith(".mp4"):
                file_path = os.path.join(target_dir, file)
                return f"✅ Success! Video saved as: {file_path}"
        
        # If no MP4 found, try manual download
        print("⚠️ Instaloader download failed, attempting manual download...")
        return manual_download(url, target_dir)
        
    except instaloader.exceptions.InstaloaderException as e:
        print(f"⚠️ Instaloader error: {str(e)}")
        print("Attempting manual download...")
        return manual_download(url, f"./{shortcode}")

def manual_download(url, target_dir):
    """Improved manual download using BeautifulSoup to parse meta tags"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }
    
    try:
        print("🌐 Fetching page content...")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        print("🔍 Parsing video URL...")
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try to find video URL in meta tags
        video_url = None
        for meta in soup.find_all('meta'):
            if meta.get('property') in ['og:video', 'og:video:secure_url']:
                video_url = meta.get('content')
                break
        
        if not video_url:
            # Fallback to JSON search
            script_tags = soup.find_all('script', type='application/ld+json')
            for script in script_tags:
                if '"video"' in script.text:
                    json_match = re.search(r'"contentUrl":\s*"([^"]+)"', script.text)
                    if json_match:
                        video_url = json_match.group(1)
                        break
        
        if not video_url:
            return "❌ Video URL not found in page source"
        
        print(f"🔗 Found video URL: {video_url[:60]}...")
        
        # Clean video URL
        video_url = video_url.replace('\\u0026', '&').replace('\\u0025', '%')
        filename = f"{os.path.basename(target_dir)}.mp4"
        file_path = os.path.join(target_dir, filename)
        
        # Download video
        print("📥 Downloading video...")
        with requests.get(video_url, stream=True, headers=headers) as r:
            r.raise_for_status()
            with open(file_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        
        return f"✅ Success! Video saved as: {file_path}"
    
    except Exception as e:
        return f"❌ Manual download failed: {str(e)}"

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python insta.py <instagram_url>")
        sys.exit(1)
    
    result = download_instagram_video(sys.argv[1])
    print(result)