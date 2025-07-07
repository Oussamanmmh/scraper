from flask import Flask, request, jsonify, send_file
import instaloader
import re
import os
import requests
import time
from bs4 import BeautifulSoup
import logging
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create downloads directory if not exists
if not os.path.exists('downloads'):
    os.makedirs('downloads')

def download_instagram_video(url):
    # Extract shortcode from URL
    match = re.search(r'instagram\.com/(?:reel|p|tv)/([^/?#]+)', url)
    if not match:
        return None, "❌ Invalid Instagram URL. Please provide a reel, post, or IGTV URL."
    
    shortcode = match.group(1)
    loader = instaloader.Instaloader(
        quiet=True,
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
            return None, "❌ This post does not contain a video."
        
        logger.info(f"📥 Downloading: {post.title or 'Instagram Video'}")
        
        # Create target directory
        target_dir = f"downloads/{shortcode}"
        os.makedirs(target_dir, exist_ok=True)
        
        # Download the post
        loader.download_post(post, target=target_dir)
        
        # Wait a moment for files to be written
        time.sleep(1)
        
        # Find the downloaded video file
        for file in os.listdir(target_dir):
            if file.endswith(".mp4"):
                file_path = os.path.join(target_dir, file)
                return file_path, f"✅ Success! Video saved as: {file}"
        
        # If no MP4 found, try manual download
        logger.warning("⚠️ Instaloader download failed, attempting manual download...")
        return manual_download(url, target_dir)
        
    except instaloader.exceptions.InstaloaderException as e:
        logger.error(f"⚠️ Instaloader error: {str(e)}")
        logger.info("Attempting manual download...")
        return manual_download(url, f"downloads/{shortcode}")

def manual_download(url, target_dir):
    """Improved manual download using BeautifulSoup to parse meta tags"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }
    
    try:
        logger.info("🌐 Fetching page content...")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        logger.info("🔍 Parsing video URL...")
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
            return None, "❌ Video URL not found in page source"
        
        logger.info(f"🔗 Found video URL: {video_url[:60]}...")
        
        # Clean video URL
        video_url = video_url.replace('\\u0026', '&').replace('\\u0025', '%')
        filename = f"{os.path.basename(target_dir)}.mp4"
        file_path = os.path.join(target_dir, filename)
        
        # Download video
        logger.info("📥 Downloading video...")
        os.makedirs(target_dir, exist_ok=True)
        with requests.get(video_url, stream=True, headers=headers) as r:
            r.raise_for_status()
            with open(file_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        
        return file_path, f"✅ Success! Video saved as: {filename}"
    
    except Exception as e:
        return None, f"❌ Manual download failed: {str(e)}"

@app.route('/download', methods=['POST'])
def download():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "URL is required"}), 400
    
    url = data['url']
    logger.info(f"Received download request for: {url}")
    
    file_path, message = download_instagram_video(url)
    
    if file_path:
        try:
            # Return the video file
            return send_file(file_path, as_attachment=True)
        except Exception as e:
            return jsonify({"error": f"Failed to send file: {str(e)}"}), 500
    else:
        return jsonify({"error": message}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)