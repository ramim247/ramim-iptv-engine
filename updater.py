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
TIMEOUT_CONNECT = 1.5  # দ্রুত কানেকশনের জন্য টাইমআউট কমানো হলো
TIMEOUT_READ = 2.0
MAX_WORKERS = 150      # স্পিড বাড়াতে থ্রেড সংখ্যা বাড়ানো হলো

CLEANUP_PATTERNS = [
    r'(?i)\.tv', r'(?i)\.hd', r'(?i)\.sd', r'(?i)\.fhd', r'(?i)\.4k',
    r'(?i)\[live\]', r'(?i)live', r'(?i)fhd', r'(?i)shd', r'[\s_.-]+hd\b', 
    r'[\s_.-]+sd\b', r'[\s_.-]+fhd\b', r'[_\.-]', r'\s+'
]

CATEGORY_MAP = {
    'Sports': ['sports', 'sport', 'cricket', 'football', 't20', 'sony', 'star sports', 'ten', 'bein', 'willow', 'supersport', 'wwe', 'ufc', 'racing'],
    'News': ['news', 'khabor', 'somoy', 'jamuna', 'ekattor', 'independent', '24', 'atn', 'bbc', 'cnn', 'al jazeera'],
    'Movies': ['movies', 'movie', 'cinema', 'bioscope', 'hbo', 'action', 'star gold', 'zee cinema', 'sony max'],
    'Entertainment': ['entertainment', 'zee', 'star', 'colors', 'sony sab', 'tv', 'bangla', 'channel', 'gazi', 'gtv', 'maasranga', 'ntv', 'deepto'],
    'Music': ['music', 'gaan', 'sangeet', 'mtv', 'b4u', 'channel i'],
    'Kids': ['kids', 'cartoon', 'disney', 'nick', 'pogo']
}

def clean_channel_name(name):
    cleaned = name.strip()
    for pattern in CLEANUP_PATTERNS:
        cleaned = re.sub(pattern, ' ' if pattern == r'\s+' else '', cleaned)
    return cleaned.strip().title()

def auto_assign_category(name):
    name_lower = name.lower()
    for category, keywords in CATEGORY_MAP.items():
        if any(keyword in name_lower for keyword in keywords):
            return category
    return "Other"

def test_single_url(channel_info):
    name, url = channel_info
    session = requests.Session()
    retries = Retry(total=0)  # কোনো রিট্রাই ট্রাই করা হবে না, ফাস্ট রেসপন্স দরকার
    session.mount('http://', HTTPAdapter(max_retries=retries))
    session.mount('https://', HTTPAdapter(max_retries=retries))
    
    start_time = time.time()
    try:
        response = session.head(url, timeout=(TIMEOUT_CONNECT, TIMEOUT_READ), allow_redirects=True)
        if response.status_code == 200:
            return {"name": name, "url": url, "status": "alive", "latency": time.time() - start_time}
    except:
        try:
            response = session.get(url, timeout=(TIMEOUT_CONNECT, TIMEOUT_READ), stream=True, allow_redirects=True)
            if response.status_code == 200:
                latency = time.time() - start_time
                response.close()
                return {"name": name, "url": url, "status": "alive", "latency": latency}
        except:
            pass
    return {"name": name, "url": url, "status": "dead", "latency": float('inf')}

def process_iptv():
    raw_sources = os.environ.get("IPTV_SOURCES", "")
    if not raw_sources:
        print("Error: No IPTV sources found!")
        return
        
    urls = [u.strip() for u in raw_sources.split(",") if u.strip()]
    
    # পুরোনো ডেড ট্র্যাকার লোড করা
    known_dead_urls = set()
    if os.path.exists("dead_tracker.json"):
        try:
            with open("dead_tracker.json", "r", encoding="utf-8") as f:
                known_dead_urls = set(json.load(f))
        except:
            pass

    unique_channels = {}
    dead_channels_from_source = {}

    print("Step 1: Extracting URLs from sources...")
    for source_url in urls:
        try:
            res = requests.get(source_url, timeout=7)
            if res.status_code != 200: continue
            lines = res.text.split('\n')
            current_meta = ""
            for line in lines:
                line = line.strip()
                if line.startswith("#EXTINF:"): current_meta = line
                elif line.startswith("http") and current_meta:
                    name_match = re.search(r',([^,]+)$', current_meta)
                    if name_match:
                        raw_name = name_match.group(1).strip()
                        clean_name = clean_channel_name(raw_name)
                        
                        # আপনার লজিক: যদি আগে থেকেই ডেড জানা থাকে, মেইন স্ক্যানে ইগনোর করে ডেড পুলে পাঠাবো
                        if line in known_dead_urls:
                            dead_channels_from_source[line] = clean_name
                        else:
                            if line not in unique_channels:
                                unique_channels[line] = clean_name
                    current_meta = ""
        except:
            pass

    print(f"Main Scan Queue (New/Active): {len(unique_channels)} | Deferred Dead Queue: {len(dead_channels_from_source)}")
    
    alive_channels = []
    new_dead_urls = set()

    # ১. মেইন স্ক্যান (যেগুলো সচল বা নতুন লিঙ্ক)
    print("Step 2: Running Main Fast Scan...")
    main_tasks = [(name, url) for url, name in unique_channels.items()]
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = executor.map(test_single_url, main_tasks)
        for res in results:
            if res["status"] == "alive":
                alive_channels.append(res)
            else:
                new_dead_urls.add(res["url"])

    # ২. আপনার লজিক: মেইন স্ক্যান শেষে ডেড ফাইল থেকে আলাদা একটা কুইক স্ক্যান
    print("Step 3: Running Secondary Quick Scan on known dead links...")
    dead_tasks = [(name, url) for url, name in dead_channels_from_source.items()]
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = executor.map(test_single_url, dead_tasks)
        for res in results:
            if res["status"] == "alive":
                print(f"🔥 Dead channel revived: {res['name']}")
                alive_channels.append(res)  # লাইভ ফিরে আসলে মেইন ফাইলে অ্যাড
            else:
                new_dead_urls.add(res["url"]) # ডেডই থাকলে ট্র্যাকারেই রেখে দেওয়া হলো

    # ডেড ফাইল আপডেট (ডিলিট না করে ফাইলে রেখে দেওয়া হলো)
    with open("dead_tracker.json", "w", encoding="utf-8") as f:
        json.dump(list(new_dead_urls), f, indent=4)

    # মাইন ফাইল ও ডেড ফাইল তৈরি (.m3u8 ফরম্যাট)
    merged_channels = {}
    for ch in alive_channels:
        name = ch["name"]
        if name not in merged_channels: merged_channels[name] = []
        merged_channels[name].append(ch)

    stats_data = {
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "total_live": len(alive_channels),
        "total_dead": len(new_dead_urls),
        "categories": {}
    }

    # master.m3u8 রাইট করা
    with open("master.m3u8", "w", encoding="utf-8") as f_master:
        f_master.write("#EXTM3U\n")
        for name, links in merged_channels.items():
            links_sorted = sorted(links, key=lambda x: x["latency"])
            category = auto_assign_category(name)
            stats_data["categories"][category] = stats_data["categories"].get(category, 0) + 1
            
            main_link = links_sorted[0]["url"]
            f_master.write(f'#EXTINF:-1 tvg-name="{name}" group-title="{category}",{name}\n{main_link}\n')
            if len(links_sorted) > 1:
                for b_idx, backup_link in enumerate(links_sorted[1:], start=1):
                    f_master.write(f'#EXTINF:-1 tvg-name="{name} Backup {b_idx}" group-title="{category} Backup",{name} [Backup {b_idx}]\n{backup_link["url"]}\n')

    # death.m3u8 ফাইলে শুধু ডেড লিঙ্কগুলো জমা রাখা (ডিলিট করা হলো না)
    with open("death.m3u8", "w", encoding="utf-8") as f_death:
        f_death.write("#EXTM3U\n")
        for url, name in dead_channels_from_source.items():
            if url in new_dead_urls:
                f_death.write(f'#EXTINF:-1 group-title="Dead-Archive",{name}\n{url}\n')

    with open("stats.json", "w", encoding="utf-8") as f_stats:
        json.dump(stats_data, f_stats, indent=4)
        
    print(f"Upgrade Completed! Live: {len(alive_channels)} | Tracked Dead: {len(new_dead_urls)}")

if __name__ == "__main__":
    process_iptv()
