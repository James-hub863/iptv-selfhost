import asyncio, aiohttp, re, os, time

SOURCES_FILE = "sources.txt"
OUTPUT_M3U = "live.m3u"
TIMEOUT = 8
MAX_CHANNELS = 600  # 最多保留 600 个频道
MAX_PER_CHANNEL = 2  # 每个频道最多保留 2 条备线

async def fetch_text(session, url):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
            if r.status == 200:
                return await r.text(encoding="utf-8", errors="ignore")
    except Exception:
        pass
    return ""

def parse_m3u(text):
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

async def measure_latency(session, url):
    try:
        start = time.time()
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=TIMEOUT),
                               headers={"User-Agent": "Mozilla/5.0"}) as r:
            if r.status in (200, 206):
                elapsed = time.time() - start
                await r.content.read(1024)
                return elapsed
    except Exception:
        pass
    return None

async def main():
    if not os.path.exists(SOURCES_FILE):
        print("sources.txt 不存在"); return
    urls = [l.strip() for l in open(SOURCES_FILE, encoding="utf-8")
            if l.strip() and not l.startswith("#")]

    async with aiohttp.ClientSession() as session:
        raws = await asyncio.gather(*[fetch_text(session, u) for u in urls])

    seen = set()
    merged = []
    for txt in raws:
        for extinf, u in parse_m3u(txt):
            if u not in seen:
                seen.add(u)
                merged.append((extinf, u))
    print(f"合并去重后共 {len(merged)} 条候选")

    async with aiohttp.ClientSession() as session:
        tasks = [measure_latency(session, u) for _, u in merged]
        results = await asyncio.gather(*tasks)

    valid_with_latency = [(merged[i], results[i]) for i, lat in enumerate(results) if lat is not None]
    valid_with_latency.sort(key=lambda x: x[1])

    seen_channel = {}
    final_valid = []
    for (extinf, url), lat in valid_with_latency:
        channel_name = extinf.split(',', 1)[-1].strip()
        if channel_name not in seen_channel:
            seen_channel[channel_name] = 0
        if seen_channel[channel_name] < MAX_PER_CHANNEL:
            seen_channel[channel_name] += 1
            final_valid.append((extinf, url))

    final_valid = final_valid[:MAX_CHANNELS]
    print(f"测活存活 {len(valid_with_latency)} 条，最终保留 {len(final_valid)} 条")

    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for extinf, url in final_valid:
            f.write(extinf + "\n" + url + "\n")
    print(f"已写出 {OUTPUT_M3U}")

if __name__ == "__main__":
    asyncio.run(main())
