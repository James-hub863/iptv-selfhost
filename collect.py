#!/usr/bin/env python3
"""
collect.py — 从 sources.txt 拉取多源 M3U，合并去重后输出 raw_channels.json
修复：超时控制、403 过滤、整体时限 30 分钟
"""

import json
import os
import re
import sys
import time
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── 全局 Session：连接 5s、读取 10s、重试 2 次 ──
session = requests.Session()
retries = Retry(total=2, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=20)
session.mount('http://', adapter)
session.mount('https://', adapter)

# ── 已知无效域名黑名单（GitHub Actions 出口常见 403） ──
BLOCKED_DOMAINS = [
    'cablecast', 'akamaized', 'wowza', 'streamlock',
    'cdn3.', 'edgefcs.net', 'fms.', 'rtmp.',
]

def is_blocked(url: str) -> bool:
    """快速跳过已知无效域名"""
    domain = urlparse(url).netloc.lower()
    return any(b in domain for b in BLOCKED_DOMAINS)

def fetch_text(url: str) -> str | None:
    """带超时和重试的 HTTP GET，返回文本或 None"""
    if is_blocked(url):
        print(f"  [跳过] 已知无效域名: {url}")
        return None
    try:
        resp = session.get(
            url,
            timeout=(5, 10),           # (连接超时, 读取超时)
            headers={'User-Agent': 'Mozilla/5.0 (compatible; IPTVCollector/1.0)'},
        )
        if resp.status_code == 403:
            print(f"  [403] {url}")
            return None
        resp.raise_for_status()
        # 检查是否为 M3U 内容
        text = resp.text.strip()
        if not text.startswith('#EXTM3U'):
            print(f"  [非M3U] {url} (首行: {text[:80]})")
            return None
        return text
    except requests.Timeout:
        print(f"  [超时] {url}")
    except Exception as e:
        print(f"  [错误] {url}: {e}")
    return None

def parse_m3u(text: str, source_label: str = '') -> list[dict]:
    """解析 M3U 文本为频道列表 [{name, url, group, logo}]"""
    channels = []
    current = {}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('#EXTINF:'):
            # 提取 tvg-name / tvg-logo / group-title
            name = ''
            logo = ''
            group = '其他'
            for attr in re.findall(r'(\w+)="([^"]*)"', line):
                k, v = attr
                if k == 'tvg-name':
                    name = v
                elif k == 'tvg-logo':
                    logo = v
                elif k == 'group-title':
                    group = v
            # fallback: 取逗号后面的名字
            if ',' in line and not name:
                name = line.rsplit(',', 1)[-1].strip()
            current = {'name': name, 'logo': logo, 'group': group, '_source': source_label}
        elif line and not line.startswith('#'):
            if current.get('name'):
                current['url'] = line
                channels.append(current.copy())
                current = {}
    return channels

def load_sources(path: str = 'sources.txt') -> list[str]:
    """读取 sources.txt，返回 URL 列表（忽略空行和注释）"""
    urls = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                urls.append(line)
    return urls

def main():
    sources = load_sources()
    print(f"共 {len(sources)} 个源待收集")

    all_channels = []
    seen_urls = set()
    start_time = time.time()
    MAX_DURATION = 1800  # 30 秒（调试用）/ 1800（生产用）

    for idx, url in enumerate(sources, 1):
        elapsed = time.time() - start_time
        if elapsed > MAX_DURATION:
            print(f"\n⏰ 已达总时限 {MAX_DURATION}s，强制结束收集")
            break

        print(f"[{idx}/{len(sources)}] 收集: {url}")
        text = fetch_text(url)
        if not text:
            continue

        channels = parse_m3u(text, source_label=url)
        added = 0
        for ch in channels:
            u = ch['url']
            if u not in seen_urls:
                seen_urls.add(u)
                all_channels.append(ch)
                added += 1
        print(f"  → 新增 {added} 条（累计 {len(all_channels)} 条）")

    # 写出中间结果
    output = 'raw_channels.json'
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(all_channels, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 收集完成，共 {len(all_channels)} 条频道，已写入 {output}")
    print(f"⏱  耗时 {time.time() - start_time:.1f}s")

if __name__ == '__main__':
    main()
