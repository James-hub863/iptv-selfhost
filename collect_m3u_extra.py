# -*- coding: utf-8 -*-
"""Retry failed sources only, merge into existing sources.txt"""
import urllib.request, re, sys

EXTRA = [
    ("Free-TV", "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"),
    ("fanmingming/live IPv6", "https://live.fanmingming.com/tv/m3u/ipv6.m3u"),
    ("Guovin/iptv-api", "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u"),
    ("vbskycn/iptv IPv4", "https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.m3u"),
]
HDRS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def fetch(url):
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", errors="replace")

def parse_m3u(text):
    items, pending = [], None
    for line in text.splitlines():
        line = line.strip()
        if not line: continue
        if line.startswith("#EXTINF"):
            m = re.search(r",\s*(.+?)\s*$", line)
            pending = m.group(1) if m else "Unknown"
        elif line.startswith("#"):
            continue
        else:
            if line.lower().startswith(("http://", "https://", "rtmp://", "rtsp://")):
                items.append((pending or "Unknown", line))
            pending = None
    return items

path = sys.argv[1]
with open(path, encoding="utf-8") as f:
    existing_lines = f.read().splitlines()

seen = set()
header = []
for ln in existing_lines:
    if not ln.startswith("#EXTINF"):
        if ln.lower().startswith(("http://", "https://", "rtmp://", "rtsp://")):
            seen.add(ln.strip().lower())
        elif ln.startswith("#") and not ln.startswith("#EXTINF"):
            header.append(ln)

new_entries = []
for name, url in EXTRA:
    got = []
    err = None
    for _ in range(3):
        try:
            got = parse_m3u(fetch(url)); err = None; break
        except Exception as e:
            err = str(e)[:80]
    if got:
        print(f"OK  {name}: {len(got)}")
        for n, u in got:
            k = u.strip().lower()
            if k not in seen:
                seen.add(k)
                new_entries.append((name, n, u))
    else:
        print(f"FAIL {name}: {err or 'empty'}")

with open(path, "w", encoding="utf-8") as f:
    f.write("\n".join(header) + "\n")
    for ln in existing_lines:
        if ln.startswith("#EXTINF") or ln.lower().startswith(("http://", "https://", "rtmp://", "rtsp://")):
            f.write(ln + "\n")
    for src, n, u in new_entries:
        safe = (n or "Unknown").replace("\r", " ").replace("\n", " ").strip() or "Unknown"
        f.write(f'#EXTINF:-1 group-title="{src}",{safe}\n{u}\n')

total_urls = len(seen) + len({u for _, _, u in new_entries})
print(f"total unique urls now: {len(seen)}")
