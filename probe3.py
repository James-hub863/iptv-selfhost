import asyncio, aiohttp

# 再加几个在 iptv-org 里被标注为稳定的"英语/教育"源
URLS = [
    ("VOA http",  "http://voa-ingest.akamaized.net/hls/live/2035200/161_352R/playlist.m3u8"),
    ("SABC News","http://185.59.221.131:8081/live/sabcnews/playlist.m3u8"),
    ("RTI Audio", "https://streamak0138.akamaized.net/live0138lh-mbm9/_definst_/rti3/playlist.m3u8"),
    ("PowerFM",  "https://crystalout.surfernetwork.com:8001/KVSP_MP3"),
    ("CapFM",    "https://19183.live.streamtheworld.com/CAPITAL958FM_PREM.aac"),
    ("AJE audio","http://tunein.ord.streamguys1.com/secure-aljazeera-english"),
    ("TV360alt", "http://turkmedya-live.ercdn.net/tv360/tv360.m3u8"),
]

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

async def main():
    async with aiohttp.ClientSession(headers={"User-Agent":UA}) as s:
        for name,url in URLS:
            try:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=8),
                                 ssl=False) as r:
                    t = await r.read()
                    hls = b"#EXTM3U" in t
                    print(f"{name:<12} {r.status}  {len(t):>6}B  HLS={hls}  {t[:100]}")
            except Exception as e:
                print(f"{name:<12} ERR  {str(e)[:70]}")

asyncio.run(main())
