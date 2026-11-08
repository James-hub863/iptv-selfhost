#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
live_ok.m3u 测活 + CDN 镜像源生成器
------------------------------------------------------------
1. 拉取 GitHub raw 上的原始 m3u（用 jsDelivr / ghproxy 等 CDN 镜像拉，绕开直连 raw 域名不稳定）
2. 解析 #EXTINF 与 url，逐个做 HTTP HEAD/GET 探活（超时可控）
3. 输出：
   - output/live_ok_tested.m3u        : 仅保留存活源的 m3u（可直接导入播放器）
   - output/live_ok_mirror.txt        : 镜像 URL 对照表（便于排障）
   - output/report.json               : 结构化报告（含耗时、状态码）
"""

import os
import re
import sys
import json
import time
import socket
import argparse
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------- 配置区（可按需修改） ----------
# 原始 m3u 地址（保留 raw 作为「基准源」）
RAW_URL = ("https://raw.githubusercontent.com/"
           "James-hub863/iptv-selfhost/refs/heads/main/live_ok.m3u")

# CDN 镜像规则：把 raw.githubusercontent.com/USER/REPO/... 转成国内可直连的 CDN
# 建议至少保留两个，脚本会自动挑选首个返回 200 的镜像
CDN_MIRRORS = [
    # jsDelivr：对 github.com/USER/REPO@BRANCH/FILE 格式，国内直连友好
    lambda u: re.sub(
        r"https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/refs/heads/([^/]+)/(.*)",
        r"https://cdn.jsdelivr.net/gh/\1/\2@\3/\4", u),
    # ghproxy（备用）
    lambda u: "https://ghproxy.net/" + u,
]

TIMEOUT = 8                 # 单源探测超时（秒）
MAX_WORKERS = 20            # 并发探测数
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")
# -----------------------------------------


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def fetch_m3u(url: str) -> str:
    """尝试多个镜像拉取 m3u 文本，返回首个成功的文本。"""
    tried = [url] + [m(url) for m in CDN_MIRRORS]
    last_err = None
    for i, u in enumerate(tried):
        try:
            log(f"拉取 m3u（第 {i+1}/{len(tried)}）: {u}")
            req = urllib.request.Request(u, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = r.read()
                for enc in ("utf-8", "gbk", "latin-1"):
                    try:
                        text = data.decode(enc)
                        log(f"  成功，编码={enc}，长度={len(text)}")
                        return text
                    except UnicodeDecodeError:
                        continue
        except Exception as e:
            last_err = e
            log(f"  失败：{e}")
    raise RuntimeError(f"所有镜像均拉取失败，最后错误：{last_err}")


def parse_m3u(text: str):
    """解析 m3u，返回 [(extinf_line, url), ...]"""
    lines = [ln.rstrip("\r") for ln in text.split("\n")]
    entries = []
    cur_extinf = None
    for ln in lines:
        if ln.startswith("#EXTINF"):
            cur_extinf = ln
        elif ln.startswith("#"):
            continue
        elif ln.strip() == "":
            continue
        else:
            if cur_extinf is not None:
                entries.append((cur_extinf, ln.strip()))
                cur_extinf = None
    return entries


def probe(entry):
    """探测单条直播源，返回 dict。"""
    extinf, url = entry
    name = ""
    m = re.search(r',([^,]+)$', extinf)
    if m:
        name = m.group(1).strip()
    result = {
        "name": name,
        "url": url,
        "ok": False,
        "status": None,
        "time_ms": None,
        "error": None,
    }
    # 只探 http(s) 源；组播/rtp 等无法 HTTP 探测，直接保留
    if not (url.startswith("http://") or url.startswith("https://")):
        result["ok"] = True
        result["status"] = "non-http(skip)"
        return result
    t0 = time.time()
    try:
        req = urllib.request.Request(
            url, method="HEAD", headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            result["status"] = r.status
            result["ok"] = 200 <= r.status < 400
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        result["ok"] = False
    result["time_ms"] = round((time.time() - t0) * 1000, 1)
    return result


def build_m3u(entries):
    """用存活结果重建 m3u 文本。"""
    out = ["#EXTM3U"]
    for extinf, url in entries:
        out.append(extinf)
        out.append(url)
    return "\n".join(out) + "\n"


def main():
    global TIMEOUT
    parser = argparse.ArgumentParser(description="m3u 测活 + CDN 镜像生成")
    parser.add_argument("--raw", default=RAW_URL, help="原始 m3u 地址")
    parser.add_argument("--outdir", default="output", help="输出目录")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS)
    parser.add_argument("--timeout", type=int, default=TIMEOUT)
    parser.add_argument("--no-test", action="store_true",
                        help="只生成镜像源，不逐条探活")
    args = parser.parse_args()

    TIMEOUT = args.timeout

    os.makedirs(args.outdir, exist_ok=True)

    # 1. 拉取
    text = fetch_m3u(args.raw)
    entries = parse_m3u(text)
    log(f"共解析到 {len(entries)} 条直播源")

    # 2. 生成「镜像源对照表」（把每个 url 走 CDN 镜像，解决 raw 直连问题）
    mirror_lines = []
    for extinf, url in entries:
        name = ""
        m = re.search(r',([^,]+)$', extinf)
        if m:
            name = m.group(1).strip()
        mirrors = [mfunc(url) for mfunc in CDN_MIRRORS]
        mirror_lines.append({
            "name": name,
            "original": url,
            "mirrors": mirrors,
        })
    mirror_txt = []
    for item in mirror_lines:
        mirror_txt.append(f"# {item['name']}")
        mirror_txt.append(f"  原始 : {item['original']}")
        for mm in item["mirrors"]:
            mirror_txt.append(f"  镜像 : {mm}")
        mirror_txt.append("")
    with open(os.path.join(args.outdir, "live_ok_mirror.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(mirror_txt))

    # 3. 探活
    if args.no_test:
        log("已跳过探活（--no-test），直接输出全量 m3u")
        tested = entries
        report = []
    else:
        log(f"开始并发探活（workers={args.workers}）…")
        report = []
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = [pool.submit(probe, e) for e in entries]
            for fut in as_completed(futs):
                report.append(fut.result())
        ok_cnt = sum(1 for r in report if r["ok"])
        log(f"探活完成：{ok_cnt}/{len(report)} 存活")
        # 按原始顺序保留存活源
        ok_urls = {r["url"] for r in report if r["ok"]}
        tested = [(e, u) for e, u in entries if u in ok_urls]

    # 4. 写出
    m3u_out = build_m3u(tested)
    with open(os.path.join(args.outdir, "live_ok_tested.m3u"), "w", encoding="utf-8") as f:
        f.write(m3u_out)
    with open(os.path.join(args.outdir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    log(f"输出目录 {args.outdir}/ :")
    log(f"  - live_ok_tested.m3u  ({len(tested)} 条存活源，可直接导入播放器)")
    log(f"  - live_ok_mirror.txt  (原始/镜像 URL 对照)")
    log(f"  - report.json         (逐条探活报告)")


if __name__ == "__main__":
    main()
