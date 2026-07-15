import os
import re
import time
import json
import requests
import concurrent.futures
from datetime import datetime, timezone, timedelta
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15',
    'VLC/3.0.18 LibVLC/3.0.18',
    'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36'
]

MASTER_FILE = "master.m3u8"
DEATH_FILE = "death.m3u8"
TRACKER_FILE = "dead_tracker.json"

def test_stream_speed(channel):
    url = channel['url']
    
    # সাজেশন ১: ইউটিউব/গুগল ভিডিও লিঙ্ক ডিটেকশন
    if "googlevideo.com" in url or "youtube.com" in url or "youtu.be" in url:
        channel['latency'] = 0.1
        return channel, True

    headers = {
        'User-Agent': USER_AGENTS[int(time.time()) % len(USER_AGENTS)],
        'Accept': '*/*',
        'Referer': 'https://www.google.com/'
    }
    
    start_time = time.time()
    try:
        response = requests.get(url, headers=headers, stream=True, timeout=(2.0, 3.5), verify=False)
        if response.status_code in [200, 206]:
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' not in content_type:
                for _ in response.iter_content(chunk_size=512):
                    break
                channel['latency'] = time.time() - start_time
                response.close()
                return channel, True
        if response: response.close()
    except Exception:
        pass
    return channel, False

def parse_m3u_content(content):
    lines = content.replace('\r\n', '\n').split('\n')
    channels = []
    current = {}
    
    for line in lines:
        line = line.strip()
        if not line: continue
        if line.startswith('#EXTINF:'):
            current['tvg-id'] = (re.search(r'tvg-id="([^"]+)"', line) or [None, ""])[1]
            current['logo'] = (re.search(r'tvg-logo="([^"]+)"', line) or [None, ""])[1]
            current['group'] = (re.search(r'group-title="([^"]+)"', line) or [None, "Live TV"])[1]
            current['name'] = line[line.find(',')+1:].strip() if ',' in line else "Unknown"
        elif line.startswith('http') and 'name' in current:
            current['url'] = line.split('|')[0]
            channels.append(current)
            current = {}
    return channels

def load_local_m3u(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return parse_m3u_content(f.read())
    return []

def load_tracker():
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_tracker(tracker):
    with open(TRACKER_FILE, 'w', encoding='utf-8') as f:
        json.dump(tracker, f, ensure_ascii=False, indent=4)

def main():
    print("🚀 RAMIM IPTV Engine Started...")
    
    bd_tz = timezone(timedelta(hours=6))
    now = datetime.now(bd_tz)
    
    secret_sources = os.getenv("IPTV_SOURCES", "")
    sources = [s.strip() for s in secret_sources.split(",") if s.strip()]
    
    raw_channels = []
    for src in sources:
        try:
            # 🛡️ ফিক্স: সোর্স ফাইল ডাউন বা স্লো থাকলে যেন স্ক্রিপ্ট হ্যাং না হয় (Connect 3s, Read 5s Timeout)
            res = requests.get(src, timeout=(3.0, 5.0), verify=False, headers={'User-Agent': USER_AGENTS[0]})
            if res.status_code == 200:
                raw_channels.extend(parse_m3u_content(res.text))
        except Exception as e:
            print(f"⚠️ Error fetching source: {e}")

    death_channels = load_local_m3u(DEATH_FILE)
    total_pool = raw_channels + death_channels
    
    live_list = []
    dead_list = []
    
    print(f"⏳ মোট {len(total_pool)}টি লিঙ্ক টেস্ট করা হচ্ছে...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=150) as executor:
        results = executor.map(test_stream_speed, total_pool)
        for channel, is_live in results:
            if is_live:
                live_list.append(channel)
            else:
                dead_list.append(channel)

    best_channels = {}
    for ch in live_list:
        name_clean = ch['name'].upper().replace('| RAMIM', '').strip()
        if name_clean not in best_channels or ch['latency'] < best_channels[name_clean]['latency']:
            best_channels[name_clean] = ch

    # সাজেশন ২: ৭২ ঘণ্টা ট্র্যাশ ক্লিনিং
    tracker = load_tracker()
    updated_tracker = {}
    final_dead_list = []
    seen_dead_urls = set()

    for ch in dead_list:
        url = ch['url']
        if url in seen_dead_urls:
            continue
        seen_dead_urls.add(url)
        
        if url not in tracker:
            first_dead_time = now.timestamp()
        else:
            first_dead_time = tracker[url]
            
        hours_dead = (now.timestamp() - first_dead_time) / 3600
        
        if hours_dead <= 72:
            updated_tracker[url] = first_dead_time
            final_dead_list.append(ch)
        else:
            print(f"🗑️ 72 Hours Exceeded! Permanently Removed: {ch['name']}")

    save_tracker(updated_tracker)

    next_update = now + timedelta(hours=1)
    
    time_header = (
        f"# Owner: Ramim Talukder\n"
        f"# Branding: Powered by RAMIM\n"
        f"# Total Links Found: {len(total_pool)}\n"
        f"# Total Live Channels: {len(best_channels)}\n"
        f"# Total Dead Links: {len(final_dead_list)}\n"
        f"# Last Updated On: {now.strftime('%Y-%m-%d %H:%M:%S')} (BD Time)\n"
        f"# Next Update Scheduled: {next_update.strftime('%Y-%m-%d %H:%M:%S')} (BD Time)\n\n"
    )

    with open(MASTER_FILE, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n" + time_header)
        for ch in best_channels.values():
            f.write(f'#EXTINF:-1 tvg-id="{ch.get("tvg-id", "")}" tvg-logo="{ch["logo"]}" group-title="{ch["group"]}",{ch["name"]} | RAMIM\n')
            f.write(f"{ch['url']}\n")

    with open(DEATH_FILE, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n# TRASH CAN - DEAD CHANNELS FOR RE-CHECKING\n\n")
        for ch in final_dead_list:
            f.write(f'#EXTINF:-1 tvg-id="{ch.get("tvg-id", "")}" tvg-logo="{ch["logo"]}" group-title="{ch["group"]}",{ch["name"]}\n')
            f.write(f"{ch['url']}\n")

    print(f"✅ সম্পন্ন! সচল: {len(best_channels)} | ডেড: {len(final_dead_list)}")

if __name__ == "__main__":
    main()
