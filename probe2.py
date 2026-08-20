import asyncio, aiohttp, ssl

URLS = [
    ("ABC News Live", "https://abc-news-dmd-streams-1.akamaized.net/out/v1/701126012d044971b3fa89406a440133/index.m3u8"),
    ("Al Jazeera EN", "https://live-hls-web-aja.getaj.net/AJA/01.m3u8"),
    ("France 24", "https://static.france24.com/live/F24_EN_LO_HLS/live_web.m3u8"),
    ("TRT World", "https://tv-trtworld.medya.trt.com.tr/master.m3u8"),
    ("BBC News", "https://cdn4.skygo.mn/live/disk1/BBC_News/HLSv3-FTA/BBC_News.m3u8"),
    ("NPR", "https://nprdmcoitunes.akamaized.net/hls/live/2034276/itls/playlist.m3u8"),
    ("VOA", "http://voa-ingest.akamaized.net/hls/live/2035200/161_352R/playlist.m3u8"),
    ("Africa24", "https://africa24.vedge.infomaniak.com/livecast/ik:africa24/manifest.m3u8"),
    ("TV360", "https://turkmedya-live.ercdn.net/tv360/tv360.m3u8"),
    ("99TV", "https://cdn-1.pishow.tv/live/1211/master.m3u8"),
]

# 完整浏览器级请求头，模拟真实客户端
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",  # 不压缩，方便看原文
    "Origin": "https://www.google.com",
    "Referer": "https://www.google.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
}

async def check(session, name, url):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10),
                               allow_redirects=True) as r:
            text = await r.read()
            is_hls = b"#EXTM3U" in text
            snip = text[:160].decode("utf-8","ignore").replace("\n"," ")
            return (name, r.status, len(text), is_hls, snip)
    except Exception as e:
        return (name, "ERR", 0, False, str(e)[:80])

async def main():
    # 关闭 SSL 验证避免某些 CDN 证书问题
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    conn = aiohttp.TCPConnector(ssl=ssl_ctx)
    async with aiohttp.ClientSession(headers=HEADERS, connector=conn) as s:
        results = await asyncio.gather(*[check(s,n,u) for n,u in URLS])
        print(f"{'名称':<16}{'状态':<6}{'字节':<8}HLS?  备注")
        print("-"*100)
        for name,st,bl,hls,sn in results:
            print(f"{name:<16}{str(st):<6}{bl:<8}{str(hls):<6} {sn[:80]}")

asyncio.run(main())
