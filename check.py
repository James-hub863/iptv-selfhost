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

CONCURRENCY = 15          # 并发线程数
PER_TIMEOUT = (5, 10)     # (连接超时, 读取超时)
MAX_DURATION = 2100       # 整体测活上限 35 分钟（秒）
CACHE_TTL = 86400 * 3     # 缓存有效 3 天（秒）
MAX_CHANNELS = 150        # 国内外各保留 150 个，共 300 个

# 已知易卡/403 域名可快速跳过（可选）
BLOCKED = ("akamaized", "cdn3.wowza", "cablecast", "streamlock")

# 国内频道关键词（用于区分国内外源）
CN_KEYWORDS = (
    "CCTV", "卫视", "湖南", "浙江", "江苏", "东方", "北京", "广东",
    "深圳", "四川", "山东", "湖北", "安徽", "福建", "江西", "辽宁",
    "河南", "河北", "重庆", "天津", "上海", "黑龙江", "吉林", "山西",
    "陕西", "甘肃", "云南", "贵州", "广西", "内蒙古", "新疆", "西藏",
    "宁夏", "青海", "海南", "厦门", "大连", "青岛", "宁波", "苏州",
    "CHC", "SiTV", "BTV", "HBS", "JSTV", "ZJTV", "SDTV", "HNTV",
    "电影", "电视剧", "少儿", "体育", "新闻", "财经", "综艺"
)

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
    Path(CACHE_FILE).write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def is_blocked(url: str) -> bool:
    return any(b in url.lower() for b in BLOCKED)


def is_cn_source(name: str) -> bool:
    """判断是否为国内源"""
    name_upper = name.upper()
    return any(kw.upper() in name_upper for kw in CN_KEYWORDS)


def check_one(item: dict, cache: dict) -> dict:
    """测活单条源，返回原 item + alive/response_time"""
    url = item.get("url", "")
    now = time.time()
    cached = cache.get(url)

    # 缓存命中且在 TTL 内 → 直接复用
    if cached and (now - cached.get("ts", 0)) < CACHE_TTL:
        if cached.get("alive"):
            item["_alive"] = True
            item["_response_time"] = cached.get("rt", 9999)
        else:
            item["_alive"] = False
            item["_response_time"] = 9999
        return item

    if is_blocked(url):
        cache[url] = {"alive": False, "ts": now, "rt": 9999}
        item["_alive"] = False
        item["_response_time"] = 9999
        return item

    alive = False
    response_time = 9999

    try:
        start_time = time.time()
        # HEAD 快速探活
        r = session.head(url, timeout=PER_TIMEOUT, allow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0"})
        elapsed = time.time() - start_time

        if r.status_code == 200:
            alive = True
            response_time = round(elapsed, 3)
        elif r.status_code in (403, 404):
            alive = False
        else:
            # 回退 GET（部分源仅 GET 可通）
            get_start = time.time()
            r2 = session.get(url, timeout=PER_TIMEOUT, stream=True)
            alive = r2.status_code == 200
            response_time = round(time.time() - get_start, 3)
    except requests.Timeout:
        alive = False
    except Exception:
        alive = False

    # 更新缓存（含响应时间）
    cache[url] = {"alive": alive, "ts": now, "rt": response_time}
    item["_alive"] = alive
    item["_response_time"] = response_time
    return item


def select_top_sources(results: list, max_per_group: int = 150) -> tuple:
    """
    去重保留最快的源，分国内/国外，各保留最快的前 max_per_group 个
    返回 (cn_sorted, foreign_sorted)
    """
    # 按频道名去重，保留响应时间最短的
    cn_by_name = {}
    foreign_by_name = {}

    for it in results:
        if not it.get("_alive"):
            continue
        name = it.get("name", "未知")
        rt = it.get("_response_time", 9999)

        # 选择目标字典
        target_dict = cn_by_name if is_cn_source(name) else foreign_by_name

        # 去重保留最快
        if name not in target_dict or rt < target_dict[name]["_response_time"]:
            target_dict[name] = it

    # 按响应时间排序，取前 N 个
    cn_sorted = sorted(cn_by_name.values(), key=lambda x: x.get("_response_time", 9999))[:max_per_group]
    foreign_sorted = sorted(foreign_by_name.values(), key=lambda x: x.get("_response_time", 9999))[:max_per_group]

    return cn_sorted, foreign_sorted


def write_m3u(cn_sources: list, foreign_sources: list, output_file: str):
    """写入 M3U 文件，国内在前，国外在后"""
    lines = ["#EXTM3U"]

    # 写入国内源
    lines.append("# ===== 国内频道 =====")
    for it in cn_sources:
        name = it.get("name", "未知").replace('"', "'")
        logo = it.get("logo", "").replace('"', "'")
        group = it.get("group", "国内").replace('"', "'")
        lines.append(
            f'#EXTINF:-1 tvg-name="{name}" '
            f'tvg-logo="{logo}" '
            f'group-title="{group}",{name}'
        )
        lines.append(it["url"])

    # 写入国外源
    lines.append("# ===== 国外频道 =====")
    for it in foreign_sources:
        name = it.get("name", "未知").replace('"', "'")
        logo = it.get("logo", "").replace('"', "'")
        group = it.get("group", "国外").replace('"', "'")
        lines.append(
            f'#EXTINF:-1 tvg-name="{name}" '
            f'tvg-logo="{logo}" '
            f'group-title="{group}",{name}'
        )
        lines.append(it["url"])

    Path(output_file).write_text("\n".join(lines) + "\n", encoding="utf-8")


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

    # 去重保留最快的源，分国内/国外，各取前 150 个
    cn_sources, foreign_sources = select_top_sources(results, max_per_group=MAX_CHANNELS)

    # 写主清单 live_ok.m3u（国内在前，国外在后，按响应时间排序）
    write_m3u(cn_sources, foreign_sources, OUTPUT_OK)

    # 报告 & 死链
    report = {
        "total": len(channels),
        "alive": alive_count,
        "cn_channels": len(cn_sources),
        "foreign_channels": len(foreign_sources),
        "total_output": len(cn_sources) + len(foreign_sources),
        "dead": len(dead_urls),
        "duration": round(time.time() - start, 1),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "fastest_cn": min(
            (it.get("name", "N/A") for it in cn_sources),
            default="N/A"
        ),
        "fastest_foreign": min(
            (it.get("name", "N/A") for it in foreign_sources),
            default="N/A"
        )
    }
    Path(REPORT_FILE).write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    Path(DEAD_FILE).write_text("\n".join(dead_urls), encoding="utf-8")

    save_cache(cache)
    print(f"✅ 测活完成: 存活 {alive_count}/{len(channels)}")
    print(f"🇨🇳 国内频道: {len(cn_sources)} 个（最快: {report['fastest_cn']}）")
    print(f"🌍 国外频道: {len(foreign_sources)} 个（最快: {report['fastest_foreign']}）")
    print(f"📊 总计输出: {report['total_output']} 个频道")
    print(f"⏱  耗时 {report['duration']}s")


if __name__ == "__main__":
    main()
