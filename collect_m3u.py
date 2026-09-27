# -*- coding: utf-8 -*-
"""Collect public M3U live TV playlists from GitHub, merge & dedupe into sources.txt"""
import urllib.request
import re
import io
import sys

SOURCES = [
    # (name, url)
    ("iptv-org 全球全量", "https://iptv-org.github.io/iptv/index.m3u"),
    ("iptv-org 中文区", "https://iptv-org.github.io/iptv/countries/cn.m3u"),
    ("iptv-org 新闻类", "https://iptv-org.github.io/iptv/categories/news.m3u"),
    ("iptv-org 音乐类", "https://iptv-org.github.io/iptv/categories/music.m3u"),
    ("iptv-org 体育类", "https://iptv-org.github.io/iptv/categories/sports.m3u"),
    ("iptv-org 纪录片", "https://iptv-org.github.io/iptv/categories/documentary.m3u"),
    ("iptv-org 娱乐类", "https://iptv-org.github.io/iptv/categories/entertainment.m3u"),
    ("iptv-org 儿童类", "https://iptv-org.github.io/iptv/categories/kids.m3u"),
    ("iptv-org 电影类", "https://iptv-org.github.io/iptv/categories/movies.m3u"),
    ("Free-TV", "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"),
    ("fanmingming/live IPv4", "https://live.fanmingming.com/tv/m3u/ipv6.m3u"),
    ("Guovin/iptv-api", "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u"),
    ("vbskycn/iptv IPv4", "https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.m3u"),
    ("vbskycn/iptv IPv6", "https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv6.m3u"),
    ("YanG-1989/m3u", "https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u"),
    ("kimwang1978/collect-tv-txt (m3u)", "https://raw.githubusercontent.com/kimwang1978/collect-tv-txt/main/merged_output.m3u"),
]

HDRS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def fetch(url):
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")

def parse_m3u(text):
    """Return list of (name, url) preserving order."""
    items = []
    lines = text.splitlines()
    pending_name = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            # standard EXTINF: "...attributes,DURATION,NAME" -> name is last comma segment
            m = re.search(r",\s*([^,]+?)\s*$", line)
            pending_name = m.group(1) if m else "Unknown"
        elif line.startswith("#"):
            continue  # other directives
        else:
            url = line
            if url.lower().startswith(("http://", "https://", "rtmp://", "rtsp://")):
                items.append((pending_name or "Unknown", url))
            pending_name = None
    return items

def main():
    all_items = []           # (source_name, channel_name, url)
    ok, fail = [], []
    for name, url in SOURCES:
        items = []
        err = None
        for attempt in range(3):
            try:
                text = fetch(url)
                items = parse_m3u(text)
                err = None
                break
            except Exception as e:
                err = str(e)[:80]
        if items:
            ok.append((name, len(items)))
            all_items.extend((name, n, u) for n, u in items)
        else:
            fail.append((name, err or "no entries parsed"))

    # dedupe by URL (keep first occurrence)
    seen = set()
    merged = []
    for src, name, url in all_items:
        key = url.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append((src, name, url))

    out = io.StringIO()
    out.write("#EXTM3U\n")
    out.write("# Generated: 2026-09-17 | Sources: GitHub public IPTV playlists\n")
    for src, name, url in merged:
        # escape commas issue: EXTINF format "duration, name"
        safe_name = (name or "Unknown").replace("\r", " ").replace("\n", " ").strip() or "Unknown"
        out.write(f'#EXTINF:-1 tvg-logo="" group-title="{src}",{safe_name}\n{url}\n')

    with open(sys.argv[1], "w", encoding="utf-8") as f:
        f.write(out.getvalue())

    print("=== SUCCEEDED ===")
    for n, c in ok:
        print(f"  {n}: {c} entries")
    print("=== FAILED ===")
    for n, e in fail:
        print(f"  {n}: {e}")
    print(f"=== SUMMARY ===")
    print(f"raw total: {len(all_items)}, unique after dedupe: {len(merged)}")

if __name__ == "__main__":
    main()
