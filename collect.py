#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collect.py —— 多源 M3U 收集与解析
从 sources.txt（每行一个 m3u 直链）拉取并解析，输出结构化 JSON，供 check.py 测活。
"""
import json
import sys
import time
import re
import concurrent.futures
import urllib.request
import urllib.error

SOURCES_FILE = "sources.txt"
OUT_FILE = "raw_channels.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
    ),
    "Referer": "https://www.kan0512.com/",
}


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    for enc in ("utf-8", "gbk", "gb2312", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


EXTINF_RE = re.compile(
    r'^#EXTINF[^\n]*tvg-name="([^"]*)"'
    r'(?:[^\n]*group-title="([^"]*)")?[^\n]*'
    r'(?:,[^\n]*)?$'
)
TVG_LOGO_RE = re.compile(r'tvg-logo="([^"]*)"')


def parse_m3u(text, source_url):
    """解析一份 M3U，返回频道条目列表。跳过 CNTV swf 伪链等无法播放项。"""
    entries = []
    lines = [ln.rstrip() for ln in text.splitlines()]
    i = 0
    current = None
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            m = EXTINF_RE.match(line)
            name = m.group(1).strip() if m else ""
            group = m.group(2).strip() if m and m.group(2) else "其他"
            logo_m = TVG_LOGO_RE.search(line)
            current = {
                "name": name,
                "group": group,
                "logo": logo_m.group(1) if logo_m else "",
                "extinf": line,
            }
        elif line and not line.startswith("#") and current:
            url = line.strip()
            # 过滤掉必然不可直接播放的伪链
            low = url.lower()
            if ".swf" in low or "player.cntv.cn" in low:
                current = None
                i += 1
                continue
            entries.append({
                **current,
                "url": url,
                "source": source_url,
            })
            current = None
        i += 1
    return entries


def fetch_one(src):
    try:
        text = fetch(src)
        if not text.lstrip().startswith("#EXTM3U"):
            print(f"[收集] 非 m3u8 忽略 {src}", flush=True)
            return src, []
        items = parse_m3u(text, src)
        print(f"[收集] {src} -> {len(items)} 条", flush=True)
        return src, items
    except Exception as e:
        # 抓取失败（403/超时/连接拒绝）不丢弃该源，记录待 check.py 判定
        print(f"[收集] 失败 {src}: {e}", flush=True)
        return src, [{
            "name": "", "group": "未分类",
            "logo": "", "extinf": "",
            "url": src, "source": src, "fetch_failed": True,
        }]


def main():
    try:
        with open(SOURCES_FILE, encoding="utf-8") as f:
            sources = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    except FileNotFoundError:
        print(f"缺少 {SOURCES_FILE}", file=sys.stderr)
        sys.exit(1)

    print(f"[收集] 共 {len(sources)} 个源，并发拉取中…", flush=True)
    t0 = time.time()
    all_items = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        for src, items in ex.map(fetch_one, sources):
            all_items.extend(items)

    # 把标记为 PROTECTED（云端无法验证）的源降级保留，交给 check.py 判定为 protected
    for src in sources:
        if "# PROTECTED" in src:
            url = src.split("#")[0].strip()
            if url and url not in seen:
                seen.add(url)
                all_items.append({
                    "name": url.rstrip("/").split("/")[-1] or "protected",
                    "group": "待本地验证",
                    "logo": "", "extinf": "",
                    "url": url, "source": url,
                    "fetch_failed": True,
                })

    # 同频道内 URL 去重，保留首次出现的顺序；抓取失败的源同样参与去重
    seen = set()
    deduped = []
    for it in all_items:
        key = it["url"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(it)

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(deduped, f, ensure_ascii=False, indent=1)

    groups = {}
    for it in deduped:
        groups[it["group"]] = groups.get(it["group"], 0) + 1
    print(f"[收集] 完成：{len(sources)} 源 -> {len(deduped)} 条唯一源，"
          f"覆盖 {len(groups)} 个分组，耗时 {time.time()-t0:.1f}s", flush=True)
    top10 = sorted(groups.items(), key=lambda x: -x[1])[:10]
    print("[分组]", dict(top10), flush=True)


if __name__ == "__main__":
    main()
