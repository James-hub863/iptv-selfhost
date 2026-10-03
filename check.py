#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check.py —— 直播源三级测活 + 按频道择优
L1 连通性探测（HEAD，失败降级 GET）
L2 读取 m3u8 正文，识别 #EXTM3U 特征、是否为点播（含 #EXT-X-ENDLIST）
L3 多次采样 #EXT-X-MEDIA-SEQUENCE，递增则确认为直播流
评分：国内/已知中转优先，延迟低优先，直播确认额外加分。
按频道取 score 最高的一条写入 live_ok.m3u。
"""
import json
import sys
import time
import re
import os
import concurrent.futures
import requests

RAW_FILE = "raw_channels.json"
OK_FILE = "live_ok.m3u"
DEAD_FILE = "dead_urls.txt"
REPORT_FILE = "report.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
    ),
    "Referer": "https://www.kan0512.com/",
}
# 进程级 Session：连接池复用，每次请求独立，避免 urllib 并发响应错位
_SESSION = requests.Session()
_SESSION.headers.update(HEADERS)

# 已知防盗链/CDN 会拦截云出口的域名，云端 L1/L2 必败，但用户本地可能可播 -> 降级保留
PROTECTED_DOMAINS = (
    "zbds.top", "fanmingming.cn", "live.fanmingming.cn", "vbskycn",
    "epg.pw", "51kandianshi.com", "kan0512.com",
)
# 国内中转/教育网/运营商内网 IP，命中则评分加权，且云出口不可达时降级为 protected
PREFER_PATTERNS = (
    "221.226.51.220", "58.56.162.102", "113.57.140.161", "113.120.243.10",
    "61.136.172.236", "223.112.114.228", "120.76.248.139", "221.7.175.154",
    "120.198.86.186", "120.238.84.45", "120.198.95.220", "118.122.144.115",
    "61.143.43.2", "61.161.61.119", "183.11.239.36", "183.94.146.79",
    "123.138.216.44", "219.147.245.238", "223.247.25.219", "182.61.15.73",
    "117.63.79.182", "116.52.173.172", "42.94.210.16", "27.12.12.174",
    "107.150.60.122", "69.30.245.50", "74.91.26.218", "198.204.228.26",
    "204.12.221.218", "198.204.240.250",
)


def is_protected(url):
    return any(d in url for d in PROTECTED_DOMAINS)


def ip_score(url):
    return 10 if any(p in url for p in PREFER_PATTERNS) else 0


def l1_probe(url, timeout):
    """L1 连通性：先 HEAD，失败降级 GET（stream 模式不读 body，省带宽）。"""
    t0 = time.time()
    for meth in ("head", "get"):
        try:
            r = getattr(_SESSION, meth)(url, timeout=timeout, allow_redirects=True, stream=True)
            r.close()
            return True, r.headers.get("Content-Type", ""), time.time() - t0
        except Exception:
            continue
    return False, "", time.time() - t0


def fetch_m3u8(url, timeout):
    """拉取 m3u8 正文，返回 (正文, 耗时秒, 错误描述)。"""
    t0 = time.time()
    try:
        r = _SESSION.get(url, timeout=timeout, stream=False)
        r.raise_for_status()
        return r.text, time.time() - t0, None
    except Exception as e:
        return None, time.time() - t0, f"err:{type(e).__name__}"


def parse_playlist(text):
    """解析 m3u8 清单，返回 (是否像直播清单, 元信息)。"""
    if not text or not text.lstrip().startswith("#EXTM3U"):
        return False, {"reason": "not_m3u8"}
    if "#EXT-X-ENDLIST" in text:
        return False, {"reason": "vod_has_endlist"}
    seq = None
    m = re.search(r"#EXT-X-MEDIA-SEQUENCE:(\d+)", text)
    if m:
        seq = int(m.group(1))
    td = None
    m = re.search(r"#EXT-X-TARGETDURATION:(\d+)", text)
    if m:
        td = int(m.group(1))
    segs = len([l for l in text.splitlines() if l.strip() and not l.startswith("#")])
    return True, {"sequence": seq, "target_duration": td, "segments": segs}


def sample_sequences(url, timeout, times=3, interval=1.0):
    """多次采样 SEQUENCE；取不到则返回空列表。"""
    seqs = []
    for _ in range(times):
        text, _, err = fetch_m3u8(url, timeout)
        if text is not None:
            ok, info = parse_playlist(text)
            if ok and info.get("sequence") is not None:
                seqs.append(info["sequence"])
        time.sleep(interval)
    return seqs


def is_live_stream(seqs):
    return len(seqs) >= 2 and len(set(seqs)) > 1


def check_one(item):
    url = item["url"]
    name = item.get("name") or "unknown"
    result = {
        "name": name, "url": url, "group": item.get("group", "其他"),
        "logo": item.get("logo", ""),
        "status": "unknown", "latency": None, "score": 0, "reason": "",
    }
    if is_protected(url):
        result["status"] = "protected"
        result["reason"] = "防盗链源，需本地验证"
        return result

    # L1
    ok, ct, el = l1_probe(url, 6)
    result["latency"] = round(el, 3)
    if not ok:
        if ip_score(url) > 0:
            result["status"] = "protected"
            result["reason"] = "云出口不可达，本地可能可播"
            return result
        result["status"] = "dead"
        result["reason"] = "L1 连通失败"
        return result

    # L2
    text, el2, err = fetch_m3u8(url, 8)
    result["latency"] = round(result["latency"] + el2, 3)
    if text is None:
        result["status"] = "dead"
        result["reason"] = f"L2 拉取失败 {err}"
        return result
    looks_live, info = parse_playlist(text)
    if not looks_live:
        result["status"] = "dead"
        result["reason"] = f"L2 {info.get('reason', '无效清单')}"
        return result

    # L3
    seqs = sample_sequences(url, 6, times=3, interval=1.0)
    live = is_live_stream(seqs)

    ips = ip_score(url)
    result["score"] = round(ips * 1.0 - (result["latency"] or 0) * 6 + (2 if live else 0), 3)
    result["sequences"] = seqs
    result["status"] = "live" if live else "stale"
    if not live:
        result["reason"] = "SEQUENCE 未变化，疑似点播或静态列表"
    return result


def pick_best(results_by_url):
    """每个频道取 score 最高的一条；全频道不可判定时保留 protected 供本地验证。"""
    by_name = {}
    for r in results_by_url.values():
        by_name.setdefault(r["name"], []).append(r)
    best = {}
    for name, items in by_name.items():
        alive = [it for it in items if it["status"] in ("live", "stale")]
        pool = alive if alive else items
        best[name] = max(pool, key=lambda x: (x["score"], -(x["latency"] or 999)))
    return best


def main():
    if not os.path.exists(RAW_FILE):
        print(f"缺少 {RAW_FILE}，请先运行 collect.py", file=sys.stderr)
        sys.exit(1)
    with open(RAW_FILE, encoding="utf-8") as f:
        items = json.load(f)

    print(f"[测活] 共 {len(items)} 条源，并发 12 线程…", flush=True)
    t0 = time.time()
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        futs = [ex.submit(check_one, it) for it in items]
        done = 0
        for fut in concurrent.futures.as_completed(futs):
            done += 1
            try:
                results.append(fut.result())
            except Exception as e:
                results.append({"name": "?", "url": "", "status": "dead",
                                "reason": f"crash:{e}"})
            if done % 50 == 0 or done == len(items):
                print(f"[测活] {done}/{len(items)}", flush=True)

    stats = {"live": 0, "stale": 0, "dead": 0, "protected": 0}
    for r in results:
        stats[r["status"]] = stats.get(r["status"], 0) + 1
    print(f"[测活] 结果 {stats}，耗时 {time.time()-t0:.1f}s", flush=True)

    results_by_url = {r["url"]: r for r in results if r.get("url")}
    best = pick_best(results_by_url)

    kept, dead = [], []
    for r in results:
        if r["status"] == "dead":
            if r.get("url"):
                dead.append(r["url"])
        else:
            kept.append(r)

    groups_order = {}
    for name, r in best.items():
        groups_order.setdefault(r.get("group", "其他"), []).append(name)

    lines = ['#EXTM3U url-tvg="https://epg.pw/api/guide.php?channel={channel}&format=json"']
    for grp in sorted(groups_order):
        for name in sorted(groups_order[grp]):
            r = results_by_url[best[name]["url"]]
            url = r["url"]
            logo = r.get("logo") or f"https://live.fanmingming.cn/tv/{name.replace(' ', '')}.png"
            lines.append(
                f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo}" '
                f'group-title="{grp}",{name}'
            )
            lines.append(url)
    with open(OK_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    with open(DEAD_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(set(dead))) + "\n")
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "stats": stats, "total": len(results),
            "kept": len(kept), "dead": len(dead), "results": results,
        }, f, ensure_ascii=False, indent=1)

    print(f"[输出] {OK_FILE}: {len(best)} 频道 | {DEAD_FILE}: {len(dead)} 条死链", flush=True)
    print(f"[输出] {REPORT_FILE} 供归档/对比", flush=True)


if __name__ == "__main__":
    main()
