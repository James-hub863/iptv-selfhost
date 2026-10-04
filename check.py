import json
import time
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# ========== 配置 ==========
INPUT_FILE = "raw_channels.json"
CACHE_FILE = "cache.json"
OUTPUT_OK = "live_ok.m3u"
REPORT_FILE = "report.json"
DEAD_FILE = "dead_urls.txt"

CONCURRENCY = 12          # 并发线程数（GitHub Actions 可适度提高）
PER_TIMEOUT = (5, 10)     # (连接超时, 读取超时)
MAX_DURATION = 2400       # 整体测活上限 40 分钟（秒）
CACHE_TTL = 86400 * 3     # 缓存有效 3 天（秒）

# 已知易卡/403 域名可快速跳过（可选）
BLOCKED = ("akamaized", "cdn3.wowza", "cablecast", "streamlock")

session = requests.Session()
retries = Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
session.mount("http://", HTTPAdapter(max_retries=retries, pool_connections=20, pool_maxsize=50))
session.mount("https://", HTTPAdapter(max_retries=retries, pool_connections=20, pool_maxsize=50))


def load_cache() -> dict:
    if Path(CACHE_FILE).exists():
        try:
            return json.loads(Path(CACHE_FILE).read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_cache(cache: dict):
    Path(CACHE_FILE).write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def is_blocked(url: str) -> bool:
    return any(b in url.lower() for b in BLOCKED)


def check_one(item: dict, cache: dict) -> dict:
    """测活单条源，返回原 item + alive/scores"""
    url = item.get("url", "")
    now = time.time()
    cached = cache.get(url)

    # 缓存命中且在 TTL 内 → 直接复用
    if cached and (now - cached.get("ts", 0)) < CACHE_TTL and cached.get("alive"):
        item["_alive"] = True
        item["_score"] = cached.get("score", 100)
        return item

    if is_blocked(url):
        cache[url] = {"alive": False, "ts": now, "score": 0}
        item["_alive"] = False
        item["_score"] = 0
        return item

    alive = False
    score = 0
    try:
        # HEAD 快速探活
        r = session.head(url, timeout=PER_TIMEOUT, allow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            alive = True
            score = 100
        elif r.status_code in (403, 404):
            alive = False
        else:
            # 回退 GET（部分源仅 GET 可通）
            r2 = session.get(url, timeout=PER_TIMEOUT, stream=True)
            alive = r2.status_code == 200
            score = 80 if alive else 0
    except requests.Timeout:
        alive = False
    except Exception:
        alive = False

    cache[url] = {"alive": alive, "ts": now, "score": score}
    item["_alive"] = alive
    item["_score"] = score
    return item


def main():
    start = time.time()
    channels = json.loads(Path(INPUT_FILE).read_text(encoding="utf-8"))
    cache = load_cache()
    print(f"[测活] 共 {len(channels)} 条源，并发 {CONCURRENCY} 线程，限时 {MAX_DURATION}s")

    done = 0
    alive_count = 0
    dead_urls = []
    results = []

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futures = {ex.submit(check_one, it, cache): it for it in channels}
        for fut in as_completed(futures):
            done += 1
            it = fut.result()
            results.append(it)
            if it.get("_alive"):
                alive_count += 1
            else:
                dead_urls.append(it.get("url", ""))
            if done % 50 == 0 or done == len(channels):
                print(f"[测活] {done}/{len(channels)} (存活 {alive_count})")

            # 整体超时兜底
            if time.time() - start > MAX_DURATION:
                print("⏰ 达整体时限，强制结束测活")
                ex.shutdown(wait=False, cancel_futures=True)
                break

    # 择优：按频道名分组，每组保留最高分源
    by_name = {}
    for it in results:
        if not it.get("_alive"):
            continue
        name = it.get("name", "未知")
        if name not in by_name or it["_score"] > by_name[name]["_score"]:
            by_name[name] = it

    # 写主清单 live_ok.m3u
    lines = ["#EXTM3U"]
    for name, it in sorted(by_name.items()):
        # 清洗名称，避免引号干扰
        clean_name = name.replace('"', "'")
        logo = it.get("logo", "").replace('"', "'")
        group = it.get("group", "其他").replace('"', "'")
        # 标准 m3u_plus 格式，强制保留 tvg-logo 属性
        lines.append(f'#EXTINF:-1 tvg-name="{clean_name}" tvg-logo="{logo}" group-title="{group}",{clean_name}')
        lines.append(it["url"])
    Path(OUTPUT_OK).write_text("\n".join(lines) + "\n", encoding="utf-8")

    # 报告 & 死链
    report = {
        "total": len(channels),
        "alive": alive_count,
        "ok_channels": len(by_name),
        "dead": len(dead_urls),
        "duration": round(time.time() - start, 1),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    Path(REPORT_FILE).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(DEAD_FILE).write_text("\n".join(dead_urls), encoding="utf-8")

    save_cache(cache)
    print(f"✅ 测活完成: 存活 {alive_count}/{len(channels)}，择优 {len(by_name)} 频道")
    print(f"⏱  耗时 {report['duration']}s")

if __name__ == "__main__":
    main()
