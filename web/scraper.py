import sys
import os
import re
import json
import urllib.request
import urllib.parse

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from yt_dlp import YoutubeDL

def detect_platform(url):
    u = url.lower()
    if 'tiktok.com' in u:
        return 'tiktok'
    elif 'instagram.com' in u:
        return 'instagram'
    elif 'twitter.com' in u or 'x.com' in u:
        return 'twitter'
    elif 'youtube.com' in u or 'youtu.be' in u:
        return 'youtube'
    elif 'facebook.com' in u or 'fb.watch' in u:
        return 'facebook'
    elif 'twitch.tv' in u:
        return 'twitch'
    elif 'bilibili.com' in u:
        return 'bilibili'
    return 'other'

def compute_engagement(views, likes, comments, shares):
    if not views or views <= 0:
        return 0.0
    rate = ((likes + comments + shares) / views) * 100
    return round(rate, 3)

def scrape_tiktok_direct(url):
    req_url = f"https://www.tikwm.com/api/?url={urllib.parse.quote(url, safe='')}"
    req = urllib.request.Request(
        req_url,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        payload = json.loads(r.read().decode('utf-8'))
        if payload.get('code') == 0 and 'data' in payload:
            d = payload['data']
            views = int(d.get('play_count') or 0)
            likes = int(d.get('digg_count') or 0)
            comments = int(d.get('comment_count') or 0)
            shares = int(d.get('share_count') or 0)
            return {
                'status': 'success',
                'platform': 'tiktok',
                'url': url,
                'title': d.get('title') or 'TikTok Video',
                'author': d.get('author', {}).get('nickname') or d.get('author', {}).get('unique_id') or 'TikTok Creator',
                'thumbnail_url': d.get('cover') or '',
                'views': views,
                'likes': likes,
                'comments': comments,
                'shares': shares,
                'engagement_rate': compute_engagement(views, likes, comments, shares)
            }
        raise Exception(payload.get('msg') or 'Failed to parse TikTok payload')

def extract_metrics(url):
    clean_url = (url or '').strip()
    if not clean_url or not clean_url.startswith(('http://', 'https://')):
        return {
            'status': 'error',
            'error': 'Invalid URL format (must begin with http:// or https://)',
            'url': clean_url
        }

    platform = detect_platform(clean_url)

    # TikTok WAF bypass: try fast direct API first
    if platform == 'tiktok':
        try:
            return scrape_tiktok_direct(clean_url)
        except Exception:
            pass

    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'ignoreerrors': False,
        'socket_timeout': 15,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=False)
            
            if not info:
                return {
                    'status': 'error',
                    'error': 'No metadata returned from source',
                    'platform': platform,
                    'url': clean_url
                }
            
            views = int(info.get('view_count') or 0)
            likes = int(info.get('like_count') or 0)
            comments = int(info.get('comment_count') or 0)
            reposts = int(info.get('repost_count') or 0)
            
            return {
                'status': 'success',
                'platform': platform,
                'url': clean_url,
                'title': info.get('title') or 'Untitled',
                'author': info.get('uploader') or info.get('channel') or info.get('creator') or 'Unknown',
                'thumbnail_url': info.get('thumbnail') or '',
                'views': views,
                'likes': likes,
                'comments': comments,
                'shares': reposts,
                'engagement_rate': compute_engagement(views, likes, comments, reposts)
            }
    except Exception as e:
        if platform == 'tiktok':
            try:
                return scrape_tiktok_direct(clean_url)
            except Exception as e2:
                return {
                    'status': 'error',
                    'error': f"{e} | fallback: {e2}",
                    'platform': platform,
                    'url': clean_url
                }
        return {
            'status': 'error',
            'error': str(e),
            'platform': platform,
            'url': clean_url
        }
