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
TIMEOUT_CONNECT = 1.5
TIMEOUT_READ = 2.0
MAX_WORKERS = 150

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

BD_INDIA_KEYWORDS = [
    'bangla', 'bangladesh', 'bd', 'india', 'indian', 'somoy', 'jamuna', 'ekattor',
    'independent', 'atn', 'channel i', 'ntv', 'gtv', 'gazi', 'deepto', 'maasranga',
    'desh', 'boishakhi', 'rtv', 'my tv', 'asian tv', 'bangla vision', 'saatv',
    'star jalsha', 'zee bangla', 'colors bangla', 'sony aath', 'sun bangla',
    'star plus', 'star gold', 'zee tv', 'zee cinema', 'sony tv', 'sony max',
    'sony sab', 'colors tv', 'colors', 'aaj tak', 'ndtv', 'republic', 'news18'
]

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
    name, url, logo, tvg_id = channel_info
    session = requests.Session()
    retries = Retry(total=0)
    session.mount('http://', HTTPAdapter(max_retries=retries))
    session.mount('https://', HTTPAdapter(max_retries=retries))
    
    start_time = time.time()
    try:
        response = session.head(url, timeout=(TIMEOUT_CONNECT, TIMEOUT_READ), allow_redirects=True)
        if response.status_code == 200:
            return {"name": name, "url": url, "logo": logo, "tvg_id": tvg_id, "status": "alive", "latency": time.time() - start_time}
    except:
        try:
            response = session.get(url, timeout=(TIMEOUT_CONNECT, TIMEOUT_READ), stream=True, allow_redirects=True)
            if response.status_code == 200:
                latency = time.time() - start_time
                response.close()
                return {"name": name, "url": url, "logo": logo, "tvg_id": tvg_id, "status": "alive", "latency": latency}
        except:
            pass
    return {"name": name, "url": url, "logo": logo, "tvg_id": tvg_id, "status": "dead", "latency": float('inf')}

def generate_bd_india_playlist(alive_channels):
    """শুধুমাত্র জ্যান্ত (Alive) ইন্ডিয়ান ও বিডি চ্যানেলগুলোর জন্য নতুন প্লেলিস্ট জেনারেট করে"""
    merged_bd_in = {}
    for ch in alive_channels:
        name = ch["name"]
        name_lower = name.lower()
        if any(keyword in name_lower for keyword in BD_INDIA_KEYWORDS):
            if name not in merged_bd_in:
                merged_bd_in[name] = []
            merged_bd_in[name].append(ch)

    with open("bd_india.m3u8", "w", encoding="utf-8") as f_bdin:
        f_bdin.write("#EXTM3U\n")
        for name, links in merged_bd_in.items():
            links_sorted = sorted(links, key=lambda x: x["latency"])
            category = auto_assign_category(name)
            
            main_item = links_sorted[0]
            logo_str = f' tvg-logo="{main_item["logo"]}"' if main_item["logo"] else ""
            id_str = f' tvg-id="{main_item["tvg_id"]}"' if main_item["tvg_id"] else ""
            
            f_bdin.write(f'#EXTINF:-1 tvg-name="{name}"{id_str}{logo_str} group-title="{category}",{name}\n{main_item["url"]}\n')
            
            if len(links_sorted) > 1:
                for b_idx, backup_item in enumerate(links_sorted[1:], start=1):
                    b_logo_str = f' tvg-logo="{backup_item["logo"]}"' if backup_item["logo"] else ""
                    b_id_str = f' tvg-id="{backup_item["tvg_id"]}"' if backup_item["tvg_id"] else ""
                    f_bdin.write(f'#EXTINF:-1 tvg-name="{name} Backup {b_idx}"{b_id_str}{b_logo_str} group-title="{category} Backup",{name} [Backup {b_idx}]\n{backup_item["url"]}\n')

    bd_in_total_links = sum(len(links) for links in merged_bd_in.values())
    print(f"🎉 New Playlist Created: 'bd_india.m3u8' with {bd_in_total_links} BD & India Links!")
    return bd_in_total_links

def process_iptv():
    raw_sources = os.environ.get("IPTV_SOURCES", "")
    if not raw_sources:
        print("Error: No IPTV sources found!")
        return
        
    urls = [u.strip() for u in raw_sources.split(",") if u.strip()]
    
    known_dead_urls = set()
    if os.path.exists("dead_tracker.json"):
        try:
            with open("dead_tracker.json", "r", encoding="utf-8") as f:
                known_dead_urls = set(json.load(f))
        except:
            pass

    unique_channels = {}
    dead_channels_from_source = {}

    print("Step 1: Extracting URLs and Metadata from sources...")
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
                        
                        logo_match = re.search(r'tvg-logo="([^"]+)"', current_meta)
                        id_match = re.search(r'tvg-id="([^"]+)"', current_meta)
                        
                        logo_url = logo_match.group(1).strip() if logo_match else ""
                        tvg_id = id_match.group(1).strip() if id_match else ""
                        
                        meta_data = {"name": clean_name, "logo": logo_url, "tvg_id": tvg_id}
                        
                        if line in known_dead_urls:
                            dead_channels_from_source[line] = meta_data
                        else:
                            if line not in unique_channels:
                                unique_channels[line] = meta_data
                    current_meta = ""
        except:
            pass

    print(f"Main Scan Queue: {len(unique_channels)} | Deferred Dead Queue: {len(dead_channels_from_source)}")
    
    alive_channels = []
    new_dead_urls = set()

    # ১. মেইন স্ক্যান
    print("Step 2: Running Main Fast Scan...")
    main_tasks = [(m["name"], url, m["logo"], m["tvg_id"]) for url, m in unique_channels.items()]
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = executor.map(test_single_url, main_tasks)
        for res in results:
            if res["status"] == "alive":
                alive_channels.append(res)
            else:
                new_dead_urls.add(res["url"])

    # ২. ডেড লিঙ্কগুলোর ওপর সেকেন্ডারি কুইক স্ক্যান
    print("Step 3: Running Secondary Quick Scan on known dead links...")
    dead_tasks = [(m["name"], url, m["logo"], m["tvg_id"]) for url, m in dead_channels_from_source.items()]
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = executor.map(test_single_url, dead_tasks)
        for res in results:
            if res["status"] == "alive":
                print(f"🔥 Dead channel revived: {res['name']}")
                alive_channels.append(res)
            else:
                new_dead_urls.add(res["url"])

    with open("dead_tracker.json", "w", encoding="utf-8") as f:
        json.dump(list(new_dead_urls), f, indent=4)

    merged_channels = {}
    for ch in alive_channels:
        name = ch["name"]
        if name not in merged_channels: merged_channels[name] = []
        merged_channels[name].append(ch)

    # BD & India প্লেলিস্ট জেনারেট এবং কাউন্ট নেওয়া
    total_bd_india_count = generate_bd_india_playlist(alive_channels)

    stats_data = {
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "total_live": len(alive_channels),
        "total_bd_india": total_bd_india_count,
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
            
            main_item = links_sorted[0]
            logo_str = f' tvg-logo="{main_item["logo"]}"' if main_item["logo"] else ""
            id_str = f' tvg-id="{main_item["tvg_id"]}"' if main_item["tvg_id"] else ""
            
            f_master.write(f'#EXTINF:-1 tvg-name="{name}"{id_str}{logo_str} group-title="{category}",{name}\n{main_item["url"]}\n')
            
            if len(links_sorted) > 1:
                for b_idx, backup_item in enumerate(links_sorted[1:], start=1):
                    b_logo_str = f' tvg-logo="{backup_item["logo"]}"' if backup_item["logo"] else ""
                    b_id_str = f' tvg-id="{backup_item["tvg_id"]}"' if backup_item["tvg_id"] else ""
                    f_master.write(f'#EXTINF:-1 tvg-name="{name} Backup {b_idx}"{b_id_str}{b_logo_str} group-title="{category} Backup",{name} [Backup {b_idx}]\n{backup_item["url"]}\n')

    # death.m3u8 রাইট করা
    with open("death.m3u8", "w", encoding="utf-8") as f_death:
        f_death.write("#EXTM3U\n")
        for url, m in dead_channels_from_source.items():
            if url in new_dead_urls:
                b_logo_str = f' tvg-logo="{m["logo"]}"' if m["logo"] else ""
                f_death.write(f'#EXTINF:-1{b_logo_str} group-title="Dead-Archive",{m["name"]}\n{url}\n')

    with open("stats.json", "w", encoding="utf-8") as f_stats:
        json.dump(stats_data, f_stats, indent=4)
        
    print(f"Upgrade Completed with Logos! Live: {len(alive_channels)} | BD/India Live: {total_bd_india_count} | Tracked Dead: {len(new_dead_urls)}")

if __name__ == "__main__":
    process_iptv()
