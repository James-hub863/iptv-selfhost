import asyncio, aiohttp, re, os

SOURCES_FILE = "sources.txt"
OUTPUT_M3U = "live.m3u"
TIMEOUT = 8  # 单链接测活超时（秒）
CONCURRENCY = 40  # 并发数，GitHub runner 别超 50

async def fetch_text(session, url):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
            if r.status == 200:
                return await r.text(encoding="utf-8", errors="ignore")
    except Exception:
        pass
    return ""

def parse_m3u(text):
    """返回 [(extinf行, url)]"""
    out = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        line = line.strip()
        if line.startswith("#EXTINF:"):
            if i + 1 < len(lines) and not lines[i+1].strip().startswith("#"):
                url = lines[i+1].strip()
                if url.startswith("http"):
                    out.append((line, url))
    return out

async def alive(session, url):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=TIMEOUT),
                               headers={"User-Agent": "Mozilla/5.0"}) as r:
            if r.status in (200, 206):
                return True
    except Exception:
        pass
    return False

async def main():
    # 1. 读源池
    if not os.path.exists(SOURCES_FILE):
        print("sources.txt 不存在"); return
    urls = [l.strip() for l in open(SOURCES_FILE, encoding="utf-8")
            if l.strip() and not l.startswith("#")]

    # 2. 并发拉取所有远程 m3u
    async with aiohttp.ClientSession() as session:
        raws = await asyncio.gather(*[fetch_text(session, u) for u in urls])

    # 3. 合并去重（按 stream URL 去重）
    seen = set()
    merged = []
    for txt in raws:
        for extinf, u in parse_m3u(txt):
            if u not in seen:
                seen.add(u)
                merged.append((extinf, u))
    print(f"合并去重后共 {len(merged)} 条候选")

    # 4. 并发测活
    async with aiohttp.ClientSession() as session:
        tasks = [alive(session, u) for _, u in merged]
        results = await asyncio.gather(*tasks)

    valid = [merged[i] for i, ok in enumerate(results) if ok]
    print(f"测活存活 {len(valid)} 条")

    # 5. 写 live.m3u
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for extinf, u in valid:
            f.write(extinf + "\n" + u + "\n")
    print(f"已写出 {OUTPUT_M3U}")

if __name__ == "__main__":
    asyncio.run(main())
