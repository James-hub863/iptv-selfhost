#!/usr/bin/env python3
"""
IPTV 一体化入口
- 从 sources.txt 读取直播源 & EPG 源
- 并发探测 + 去重 + 排序
- 自动下载 & 合并 EPG
- 历史留存 + 对比报告
"""
import asyncio
import sys
import time
from pathlib import Path
from typing import List, Tuple

# ===== 各模块（前面几轮产出的） =====
from parser import parse_m3u, deduplicate, group_and_sort, write_m3u, Channel
from probe import probe_channel, Config as ProbeConfig
from epg_downloader import download_and_parse, EpgDownloader
from epg import match_epg_to_channels, write_epg_xml
from history import HistoryManager, make_history_entry


# ==================== sources.txt 解析 ====================

@dataclass
class SourceEntry:
    url: str
    kind: str = "m3u"      # m3u / epg


def parse_sources_file(path: str = "sources.txt") -> Tuple[List[str], List[str]]:
    """
    解析 sources.txt
    返回 (m3u_urls, epg_urls)
    支持：
      - # 注释行
      - 空行
      - 行尾 #epg 标记
      - 自动去重
    """
    p = Path(path)
    if not p.exists():
        print(f"❌ {path} 不存在", file=sys.stderr)
        return [], []

    m3u_urls: List[str] = []
    epg_urls: List[str] = []
    seen = set()

    for raw in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        kind = "m3u"
        if "#epg" in line:
            kind = "epg"
            line = line.replace("#epg", "").strip()

        if not (line.startswith("http://") or line.startswith("https://")):
            print(f"  ⚠️ 跳过非 HTTP 行: {line[:60]}")
            continue

        if line in seen:
            continue
        seen.add(line)

        if kind == "epg":
            epg_urls.append(line)
        else:
            m3u_urls.append(line)

    return m3u_urls, epg_urls


# ==================== 下载 M3U 源 ====================

async def download_m3u_urls(urls: List[str]) -> List[Channel]:
    """下载 sources.txt 里的直播源直链，返回合并后的频道列表"""
    if not urls:
        return []

    import aiohttp
    all_channels: List[Channel] = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    timeout = aiohttp.ClientTimeout(total=60)
    connector = aiohttp.TCPConnector(limit=20, ssl=False)

    async with aiohttp.ClientSession(timeout=timeout, connector=connector, headers=headers) as session:
        for url in urls:
            try:
                async with session.get(url, allow_redirects=True) as resp:
                    if resp.status != 200:
                        print(f"  ⚠️ {url}: HTTP {resp.status}")
                        continue
                    text = await resp.text(errors="ignore")
            except Exception as e:
                print(f"  ⚠️ 下载失败 {url}: {str(e)[:50]}")
                continue

            chs = parse_m3u(text, source=_short_name(url))
            print(f"  📄 {_short_name(url)}: {len(chs)} 条")
            all_channels.extend(chs)

    return all_channels


def _short_name(url: str) -> str:
    from urllib.parse import urlparse
    p = urlparse(url)
    return f"{p.netloc}{p.path}"


# ==================== 主流程 ====================

async def main_async():
    start = time.time()

    # 1. 读取 sources.txt
    print("📋 读取 sources.txt ...")
    m3u_urls, epg_urls = parse_sources_file("sources.txt")
    print(f"   M3U 源: {len(m3u_urls)} 个 | EPG 源: {len(epg_urls)} 个\n")

    if not m3u_urls:
        print("❌ 没有可用的 M3U 源，请检查 sources.txt")
        sys.exit(1)

    # 2. 下载直播源
    print("⬇️  下载直播源...")
    all_channels = await download_m3u_urls(m3u_urls)
    print(f"   原始合计: {len(all_channels)} 条\n")

    # 3. 去重
    deduped = deduplicate(all_channels, strategy="best")
    print(f"🔀 去重: {len(all_channels)} → {len(deduped)} 条\n")

    # 4. 并发探测
    cfg = ProbeConfig(
        concurrency=50,
        verify_with_ffmpeg=True,
    )
    print(f"🚀 开始探测 (并发 {cfg.concurrency})...\n")

    # ---- 这里粘贴 probe.py 的探测逻辑 ----
    # TODO: 把你 probe.py 里 "并发探测 + 进度条 + 统计" 那段代码贴进来
    # 期望产出：alive (存活列表), all_channels (全量), by_source (源分布)
    alive, all_channels, by_source = await run_probe(deduped, cfg)
    # ---- END TODO ----

    elapsed = time.time() - start

    # 5. 排序 + 写出 M3U
    alive = group_and_sort(alive)
    write_m3u(alive, "live.m3u")

    # 6. 历史留存
    from collections import Counter
    history = HistoryManager(history_dir="history", keep_days=7)
    by_group = Counter(c.group or "未分类" for c in alive)
    top_errors = Counter(c.error.split(":")[0] for c in all_channels if c.status != "ok" and c.error)

    entry = make_history_entry(
        total=len(all_channels),
        alive=len(alive),
        dead=len(all_channels) - len(alive),
        elapsed=elapsed,
        by_source=dict(Counter(c.source for c in alive)),
        by_group=dict(by_group),
        top_errors=dict(top_errors.most_common(10)),
    )
    history.save(entry)

    cmp_report = history.compare_with_previous(entry)
    if cmp_report.get("has_previous"):
        arrow = {"up": "📈", "down": "📉", "flat": "➡️"}[cmp_report["trend"]]
        print(f"\n{arrow} 对比上次 ({cmp_report['prev_date']}): "
              f"存活 {cmp_report['diff_alive']:+d}, 有效率 {cmp_report['diff_rate']:+.1f}%")

    # 7. EPG 下载 & 合并
    if epg_urls:
        print("\n" + "=" * 60)
        print("📡 下载并合并 EPG...")
        epg_data = await download_and_parse(
            urls=epg_urls,
            cache_dir="epg_cache",
            max_age_hours=12,
        )
        if epg_data and epg_data.channels:
            matched = match_epg_to_channels(epg_data, alive, time_window_hours=24)
            if matched:
                write_epg_xml(matched, "epg.xml")

    # 8. 历史报告
    print("\n" + history.generate_report())


# ==================== TODO 占位 ====================
# 把你 probe.py 的探测主循环完整搬进这里
async def run_probe(channels, cfg) -> Tuple[list, list, dict]:
    """
    并发探测
    返回 (alive, all_channels, by_source)
    >>> 把 probe.py 里 `async def main_async` 的探测循环搬到这里 <<<
    """
    raise NotImplementedError("请把 probe.py 的探测逻辑粘贴到这里")


# ==================== 入口 ====================
if __name__ == "__main__":
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n⛔ 中断", file=sys.stderr)
        sys.exit(130)