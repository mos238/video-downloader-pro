from flask import Flask, render_template, request, send_file, jsonify
from flask_cors import CORS
import yt_dlp
import subprocess
import os
import uuid
import re
import json
import logging

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DOWNLOAD_FOLDER = 'downloads'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

def clean_youtube_url(url):
    url = url.strip()
    if 'youtu.be' in url:
        match = re.search(r'youtu\.be/([a-zA-Z0-9_-]+)', url)
        if match:
            return f'https://www.youtube.com/watch?v={match.group(1)}'
    if 'youtube.com' in url:
        url = re.sub(r'[?&](si|feature|list|index|pp|is|emb|utm|ab_channel)=[^&]*', '', url)
        url = re.sub(r'[?&]$', '', url)
    return url

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/youtube-info', methods=['POST'])
def youtube_info():
    data = request.json
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    
    url = clean_youtube_url(url)
    logger.info(f"Fetching YouTube info: {url}")
    
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            formats = []
            for f in info.get('formats', []):
                if f.get('height') and f.get('ext') in ['mp4', 'webm']:
                    formats.append({
                        'quality': f"{f['height']}p",
                        'format_id': f['format_id'],
                        'ext': f['ext'],
                        'filesize': f.get('filesize', 0)
                    })
            
            formats.sort(key=lambda x: int(x['quality'].replace('p', '')), reverse=True)
            
            return jsonify({
                'success': True,
                'title': info.get('title', 'Unknown'),
                'thumbnail': info.get('thumbnail', ''),
                'uploader': info.get('uploader', 'Unknown'),
                'duration': info.get('duration', 0),
                'formats': formats[:10]
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/youtube-download', methods=['POST'])
def youtube_download():
    data = request.json
    url = data.get('url')
    format_id = data.get('format_id')
    
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    
    url = clean_youtube_url(url)
    
    filename = f"{uuid.uuid4().hex}.mp4"
    filepath = os.path.join(DOWNLOAD_FOLDER, filename)
    
    try:
        cmd = [
            'yt-dlp',
            '-f', format_id,
            '--merge-output-format', 'mp4',
            '--no-warnings',
            '--quiet',
            '--no-check-certificate',
            '-o', filepath,
            url
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        
        if result.returncode != 0:
            return jsonify({'error': result.stderr[:200]}), 500
        
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            return send_file(
                filepath,
                as_attachment=True,
                download_name=f"video_{uuid.uuid4().hex[:8]}.mp4"
            )
        else:
            return jsonify({'error': 'File not created'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass

@app.route('/m3u8-download', methods=['POST'])
def m3u8_download():
    try:
        data = request.json
        url = data.get('url')
        referer = data.get('referer', '')
        
        if not url:
            return jsonify({'error': 'No M3U8 URL provided'}), 400
        
        # Check if ffmpeg is available
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        except:
            return jsonify({'error': 'ffmpeg not available on server'}), 500
        
        filename = f"{uuid.uuid4().hex}.mp4"
        filepath = os.path.join(DOWNLOAD_FOLDER, filename)
        
        cmd = ['ffmpeg', '-y']
        
        if referer:
            cmd.extend(['-headers', f'Referer: {referer}'])
        
        cmd.extend([
            '-user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            '-i', url,
            '-c', 'copy',
            '-bsf:a', 'aac_adtstoasc',
            filepath
        ])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            error_msg = result.stderr if result.stderr else "Unknown error"
            return jsonify({'error': f'ffmpeg error: {error_msg[:200]}'}), 500
        
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            return send_file(
                filepath,
                as_attachment=True,
                download_name=f"m3u8_video_{uuid.uuid4().hex[:8]}.mp4",
                mimetype='video/mp4'
            )
        else:
            return jsonify({'error': 'File not created'}), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Download timeout (5 minutes)'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
