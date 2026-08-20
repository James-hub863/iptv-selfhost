import asyncio, aiohttp, re, sys, time

URLS = [
    ("ABC News Live", "https://abc-news-dmd-streams-1.akamaized.net/out/v1/701126012d044971b3fa89406a440133/index.m3u8"),
    ("ABC News Live 8", "https://abcnews-streams.akamaized.net/hls/live/2023567/abcnewshudson8/master.m3u8"),
    ("Al Jazeera EN", "https://live-hls-web-aja.getaj.net/AJA/01.m3u8"),
    ("AJE CDN", "https://d1cy85syyhvqz5.cloudfront.net/v1/master/7b67fbda7ab859400a821e9aa0deda20ab7ca3d2/aljazeeraLive/AJE/index.m3u8"),
    ("France 24", "https://static.france24.com/live/F24_EN_LO_HLS/live_web.m3u8"),
    ("FR24 Klowd", "https://cdn.klowdtv.net/803B48A/n1.klowdtv.net/live2/france24_720p/playlist.m3u8"),
    ("TRT World", "https://tv-trtworld.medya.trt.com.tr/master.m3u8"),
    ("BBC News", "https://cdn4.skygo.mn/live/disk1/BBC_News/HLSv3-FTA/BBC_News.m3u8"),
    ("BBC World", "https://fl2.moveonjoy.com/BBC_WORLD_NEWS/index.m3u8"),
    ("Fox News", "http://138.121.15.230:9002/FOX-NEWS/index.m3u8"),
    ("NPR", "https://nprdmcoitunes.akamaized.net/hls/live/2034276/itls/playlist.m3u8"),
    ("VOA", "http://voa-ingest.akamaized.net/hls/live/2035200/161_352R/playlist.m3u8"),
    ("ABC Aus", "https://abc-news-dmd-streams-1.akamaized.net/out/v1/abc83881886746b0802dc3e7ca2bc792/index.m3u8"),
    ("Africa24", "https://africa24.vedge.infomaniak.com/livecast/ik:africa24/manifest.m3u8"),
    ("TV360", "https://turkmedya-live.ercdn.net/tv360/tv360.m3u8"),
    ("99TV", "https://cdn-1.pishow.tv/live/1211/master.m3u8"),
]

async def check(session, name, url):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
            text = await r.read()
            is_hls = b"#EXTM3U" in text or b"#EXTINF" in text
            snippet = text[:200].decode("utf-8", "ignore").replace("\n"," ")
            return (name, url, r.status, len(text), is_hls, snippet)
    except Exception as e:
        return (name, url, "ERR", 0, False, str(e)[:80])

async def main():
    headers = {"User-Agent":"VLC/3.0.20 LibVLC/3.0.20"}
    async with aiohttp.ClientSession(headers=headers) as s:
        t0 = time.time()
        results = await asyncio.gather(*[check(s,n,u) for n,u in URLS])
        print(f"耗时 {time.time()-t0:.1f}s\n")
        print(f"{'名称':<18}{'状态':<6}{'字节':<8}{'HLS?':<6} 备注")
        print("-"*90)
        for name,url,st,bl,hls,sn in results:
            print(f"{name:<18}{str(st):<6}{bl:<8}{str(hls):<6}  {sn[:70]}")

asyncio.run(main())
