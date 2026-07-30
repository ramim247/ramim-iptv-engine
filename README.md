# 📺 Automated IPTV Playlist & Stream Checker

![GitHub last commit](https://img.shields.io/github/last-commit/username/repository-name?style=flat-square&color=blue)
![Automated Workflow](https://img.shields.io/badge/Workflow-GitHub%20Actions-orange?style=flat-square)
![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=flat-square)

একটি সম্পূর্ণ স্বয়ংক্রিয় (Fully Automated) IPTV প্লেলিস্ট জেনারেটর এবং স্ট্রিম চেকার। এটি বিভিন্ন উৎস থেকে চ্যানেল সংগ্রহ করে সেগুলোর স্পিড ও সচলতা (Latency & Status) পরীক্ষা করে এবং স্বয়ংক্রিয়ভাবে একটি গোছানো `.m3u8` প্লেলিস্ট তৈরি করে।

---

## ✨ ফিচারসমূহ (Features)

* 🚀 **অটোমেটেড হেলথ চেক:** প্রতিবার আপডেটের সময় সব লিংকের সচলতা টেস্ট করে শুধুমাত্র ওয়ার্কিং (Alive) লিংক প্লেলিস্টে যুক্ত করে।
* ⚡ **মাল্টি-থ্রেডেড স্পিড স্ক্যান:** একসাথে ১৫০+ থ্রেড ব্যবহার করে অত্যন্ত দ্রুত স্ট্রিম চেক করতে পারে।
* 🔄 **স্মার্ট লোগো ও মেটাডেটা সিঙ্ক (Auto-Sync):** সমনামের চ্যানেলগুলোর মধ্যে কোনো একটিতে লোগো বা `tvg-id` থাকলে তা স্বয়ংক্রিয়ভাবে ব্যাকআপ স্ট্রিমগুলোতে যুক্ত হয়ে যায়।
* 📡 **স্মার্ট ব্যাকআপ সিস্টেম:** প্রধান লিংকটি উপরে রেখে বাকি জ্যান্ত লিংকগুলোকে স্পিডের ওপর ভিত্তি করে [Backup 1], [Backup 2] হিসেবে সাজিয়ে দেয়।
* 🇧🇩🇮🇳 **ডেডিকেটেড BD & India প্লেলিস্ট:** সাধারণ প্লেলিস্টের পাশাপাশি বাংলাদেশ ও ভারতের স্পেশাল চ্যানেলগুলো আলাদা `bd_india.m3u8` ফাইলে জেনারেট হয়।
* 📊 **লাইভ ড্যাশবোর্ড ও স্ট্যাটস:** লাইভ ও ডেড চ্যানেলের সংখ্যা এবং ক্যাটাগরি ট্র্যাকিংয়ের জন্য `stats.json` আপডেট করে।
* 🔄 **ডেড লিংক ট্র্যাকিং:** সাময়িকভাবে বন্ধ থাকা লিংকগুলোকে `dead_tracker.json`-এ ট্র্যাক করে পরবর্তীতে আবার চেক করে (Revive Support)।

---

## 🔗 প্লেলিস্ট লিংকসমূহ (Playlist URLs)

আপনার IPTV প্লেয়ার (যেমন: OTT Navigator, IPTV Smarters, VLC, TiviMate) এ নিচের লিংকগুলো ব্যবহার করতে পারেন:

| প্লেলিস্ট টাইপ | M3U8 লিংক URL | বিবরণ |
| :--- | :--- | :--- |
| **🌐 Master Playlist** | `https://raw.githubusercontent.com/ramim247/ramim-iptv-engine/main/master.m3u8` | সমস্ত ফিল্টার করা সচল লাইভ চ্যানেল |
| **🇧🇩🇮🇳 BD & India Special** | `https://raw.githubusercontent.com/ramim247/ramim-iptv-engine/main/bd_india.m3u8` | শুধুমাত্র বাংলাদেশ ও ভারতের চ্যানেল |
| **🏴‍☠️ Dead Archive** | `https://raw.githubusercontent.com/ramim247/ramim-iptv-engine/main/death.m3u8` | বর্তমানে অকার্যকর থাকা চ্যানেলের আর্কাইভ |


---

## 📁 প্রজেক্ট স্ট্রাকচার (Project Structure)

```text
├── .github/workflows/  # GitHub Actions অটোমেশন ফাইল
├── updater.py          # মূল পাইথন স্ক্যানার ও প্লেলিস্ট মেকার স্ক্রিপ্ট
├── master.m3u8         # জেনারেট হওয়া প্রধান প্লেলিস্ট
├── bd_india.m3u8       # বাংলাদেশ ও ভারতের প্লেলিস্ট
├── death.m3u8          # অকার্যকর লিংকসমূহের প্লেলিস্ট
├── dead_tracker.json   # ডেড লিংকের হিস্ট্রি ট্রাক ফাইল
├── stats.json          # চ্যানেল স্ট্যাটাস এবং ক্যাটাগরি তথ্য
└── README.md           # প্রজেক্ট গাইড
