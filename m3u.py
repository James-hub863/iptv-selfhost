#!/usr/bin/env python3
"""从 raw_channels.json 生成全量聚合清单 live_all.m3u"""
import json
from pathlib import Path

RAW_FILE = "raw_channels.json"
OUTPUT_FILE = "live_all.m3u"

def generate_all():
    if not Path(RAW_FILE).exists():
        print(f"⚠️  {RAW_FILE} 不存在，跳过生成")
        return
    with open(RAW_FILE, encoding="utf-8") as f:
        channels = json.load(f)
    
    lines = ["#EXTM3U"]
    seen_urls = set()
    for ch in channels:
        url = ch.get("url", "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        name = ch.get("name", "未知").replace('"', "'")
        logo = ch.get("logo", "").replace('"', "'")
        group = ch.get("group", "其他").replace('"', "'")
        lines.append(f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo}" group-title="{group}",{name}')
        lines.append(url)
    
    Path(OUTPUT_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"✅ 全量清单已生成：{OUTPUT_FILE}（{len(seen_urls)} 条唯一 URL）")

if __name__ == "__main__":
    generate_all()
