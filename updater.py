import os
import re
import time
import concurrent.futures
import requests
import json
from urllib3.util import Retry
from requests.adapters import HTTPAdapter

# ==========================================
# CONFIGURATION & CONSTANTS
# ==========================================
TIMEOUT_CONNECT = 3
TIMEOUT_READ = 5
MAX_WORKERS = 100

# ফিচার ২: নাম ক্লিনআপের জন্য রেগুলার এক্সপ্রেশন রুলস
CLEANUP_PATTERNS = [
    r'(?i)\.tv', r'(?i)\.hd', r'(?i)\.sd', r'(?i)\.fhd', r'(?i)\.4k',
    r'(?i)\[live\]', r'(?i)live', r'(?i)fhd', r'(?i)shd', r'(?i)fhd',
    r'[\s_.-]+hd\b', r'[\s_.-]+sd\b', r'[\s_.-]+fhd\b',
    r'[_\.-]', r'\s+'
]

# ফিচার ১: স্মার্ট ক্যাটাগরি ম্যাপিং কী-ওয়ার্ড
CATEGORY_MAP = {
    'Sports': ['sports', 'sport', 'cricket', 'football', 't20', 'sony', 'star sports', 'ten', 'bein', 'willow', 'supersport', 'wwe', 'ufc', 'eurovision', 'racing', 'golf'],
    'News': ['news', 'khabor', 'somoy', 'jamuna', 'ekattor', 'independent', '24', 'atn', 'bbc', 'cnn', 'al jazeera', 'reuters', 'sky news'],
    'Movies': ['movies', 'movie', 'cinema', 'bioscope', 'hbo', 'action', 'star gold', 'zee cinema', 'sony max', 'cine', 'wb', 'pixels'],
    'Entertainment': ['entertainment', 'zee', 'star', 'colors', 'sony sab', 'tv', 'baber', 'bangla', 'chittagong', 'dhaka', 'itv', 'channel', 'gazi', 'gtv', 'maasranga', 'ntv', 'rttv', 'deepto'],
    'Music': ['music', 'gaan', 'sangeet', 'mtv', 'b4u', 'zoom', 'v h1', 'channel i', 't-series'],
    'Kids': ['kids', 'cartoon', 'disney', 'nick', 'pogo', 'hungama', 'sonic']
}

def clean_channel_name(name):
    """ফিচার ২: চ্যানেলের নাম থেকে ডট, ইমোজি ও অপ্রয়োজনীয় ট্যাগ পরিষ্কার করে ফ্রেশ নাম তৈরি করে।"""
    cleaned = name.strip()
    for pattern in CLEANUP_PATTERNS:
        if pattern == r'\s+':
            cleaned = re.sub(pattern, ' ', cleaned)
        else:
            cleaned = re.sub(pattern, '', cleaned)
    return cleaned.strip().title()

def auto_assign_category(name):
    """ফিচার ১: নাম স্ক্যান করে স্বয়ংক্রিয়ভাবে সঠিক ক্যাটাগরি সিলেক্ট করে।"""
    name_lower = name.lower()
    for category, keywords in CATEGORY_MAP.items():
        if any(keyword in name_lower for keyword in keywords):
            return category
    return "Other"

def test_single_url(channel_info):
    """ফিচার ৭: লিঙ্কের রেসপন্স স্পিড (ল্যাটেন্সি) নিখুঁতভাবে পরিমাপ করে।"""
    name, url = channel_info
    session = requests.Session()
    retries = Retry(total=1, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
    session.mount('http://', HTTPAdapter(max_retries=retries))
    session.mount('https://', HTTPAdapter(max_retries=retries))
    
    start_time = time.time()
    try:
        response = session.head(url, timeout=(TIMEOUT_CONNECT, TIMEOUT_READ), allow_redirects=True)
        if response.status_code == 200:
            latency = time.time() - start_time
            return {"name": name, "url": url, "status": "alive", "latency": latency}
    except Exception:
        try:
            response = session.get(url, timeout=(TIMEOUT_CONNECT, TIMEOUT_READ), stream=True, allow_redirects=True)
            if response.status_code == 200:
                latency = time.time() - start_time
                response.close()
                return {"name": name, "url": url, "status": "alive", "latency": latency}
        except Exception:
            pass
    return {"name": name, "url": url, "status": "dead", "latency": float('inf')}

def process_iptv():
    raw_sources = os.environ.get("IPTV_SOURCES", "")
    if not raw_sources:
        print("Error: No IPTV sources found in Environment Variables!")
        return
        
    urls = [u.strip() for u in raw_sources.split(",") if u.strip()]
    print(f"Total Sources Loaded: {len(urls)}")
    
    # ইউনিক লিঙ্ক এবং নাম এক্সট্রাক্ট করা (ফিচার ৮ এর প্রাথমিক ধাপ)
    unique_channels = {}
    
    for idx, source_url in enumerate(urls):
        try:
            res = requests.get(source_url, timeout=10)
            if res.status_code != 200:
                continue
            
            lines = res.text.split('\n')
            current_meta = ""
            for line in lines:
                line = line.strip()
                if line.startswith("#EXTINF:"):
                    current_meta = line
                elif line.startswith("http") and current_meta:
                    # নাম খুঁজে বের করা
                    name_match = re.search(r',([^,]+)$', current_meta)
                    if name_match:
                        raw_name = name_match.group(1).strip()
                        clean_name = clean_channel_name(raw_name)
                        
                        # ডুপ্লিকেট লিঙ্ক এড়ানো
                        if line not in unique_channels:
                            unique_channels[line] = clean_name
                    current_meta = ""
        except Exception as e:
            print(f"Skipping source {idx+1} due to error: {e}")

    print(f"Total Unfiltered Extracted Links: {len(unique_channels)}")
    
    # মাল্টিথ্রেডিং স্পিড টেস্ট
    channel_tasks = [(name, url) for url, name in unique_channels.items()]
    alive_channels = []
    dead_channels_count = 0
    
    print("Testing channels responsiveness and sorting by speed...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = executor.map(test_single_url, channel_tasks)
        for res in results:
            if res["status"] == "alive":
                alive_channels.append(res)
            else:
                dead_channels_count += 1
                
    print(f"Status Summary -> Live: {len(alive_channels)} | Dead: {dead_channels_count}")
    
    # ফিচার ৩, ৭, ৮: ডুপ্লিকেট নাম মার্জার, স্পিড অনুযায়ী সর্টিং এবং ব্যাকআপ লিঙ্ক সেটআপ
    merged_channels = {}
    for ch in alive_channels:
        name = ch["name"]
        if name not in merged_channels:
            merged_channels[name] = []
        merged_channels[name].append(ch)
    
    # ড্যাশবোর্ডের জন্য স্ট্যাটাস ডেটা ট্র্যাকিং (ফিচার ১০)
    stats_data = {
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "total_checked": len(unique_channels),
        "total_live": len(alive_channels),
        "total_dead": dead_channels_count,
        "categories": {}
    }
    
    # রাইট ফাইলে ডেটা সাজানো
    with open("master.m3u8", "w", encoding="utf-8") as f_master:
        f_master.write("#EXTM3U\n")
        
        for name, links in merged_channels.items():
            # ফিচার ৭: স্পিড (কম ল্যাটেন্সি) অনুযায়ী লিঙ্কগুলো সাজানো, প্রথমটি হবে মেইন
            links_sorted = sorted(links, key=lambda x: x["latency"])
            
            category = auto_assign_category(name)
            stats_data["categories"][category] = stats_data["categories"].get(category, 0) + 1
            
            # প্রধান লিঙ্কের জন্য এন্ট্রি
            main_link = links_sorted[0]["url"]
            f_master.write(f'#EXTINF:-1 tvg-name="{name}" group-title="{category}",{name}\n')
            f_master.write(f'{main_link}\n')
            
            # ফিচার ৩: যদি অতিরিক্ত সচল লিঙ্ক থাকে, তবে সেগুলোকে ব্যাকআপ বা অল্টারনেটিভ হিসেবে যোগ করা
            if len(links_sorted) > 1:
                for b_idx, backup_link in enumerate(links_sorted[1:], start=1):
                    f_master.write(f'#EXTINF:-1 tvg-name="{name} Backup {b_idx}" group-title="{category} Backup",{name} [Backup {b_idx}]\n')
                    f_master.write(f'{backup_link["url"]}\n')

    # ড্যাশবোর্ডের জন্য স্ট্যাটাস এক্সপোর্ট (ফিচার ১০ এর প্রিপারেশন)
    with open("stats.json", "w", encoding="utf-8") as f_stats:
        json.dump(stats_data, f_stats, indent=4)
        
    print("Step 1: Core Engine Upgrade Completed Successfully!")

if __name__ == "__main__":
    process_iptv()
