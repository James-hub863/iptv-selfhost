import asyncio, aiohttp, re, os, time

# ========== 配置区 ==========
SOURCES_FILE = "sources.txt"
OUTPUT_M3U = "live.m3u"
TIMEOUT = 8                     # 单链接测活超时（秒）
MAX_CHANNELS = 400              # 最多保留 400 个频道
MAX_PER_CHANNEL = 2             # 每个频道最多保留 2 条备线

# 频道白名单（只保留这些频道，其余丢弃）
CHANNEL_WHITELIST = [
    # 央视全系列
    'CCTV1','CCTV2','CCTV3','CCTV4','CCTV5','CCTV5+','CCTV6','CCTV7',
    'CCTV8','CCTV9','CCTV10','CCTV11','CCTV12','CCTV13','CCTV14','CCTV15',
    'CCTV16','CCTV17',
    # 卫视
    '东方卫视','江苏卫视','浙江卫视','湖南卫视','北京卫视','广东卫视',
    '深圳卫视','山东卫视','安徽卫视','东南卫视','海峡卫视','厦门卫视',
    '上海第一财经',
    # 本地
    '苏州4K','苏州新闻综合','苏州文化生活',
    # 少儿
    '金鹰卡通','卡酷少儿','优漫卡通','浙江少儿',
]

# 苏州联通优选网段（正则匹配 IP 前缀）
PREFER_IPS = re.compile(
    r'^(?:221\.226\.51\.220|218\.1\.138\.153|112\.123\.243\.37|112\.30\.73\.119|'
    r'119\.166\.53\.110|113\.90\.154\.189|111\.59\.24\.227|112\.234\.22\.76|'
    r'218\.13\.138\.139|123\.175\.209\.118|223\.78\.65\.165|221\.7\.175\.154|'
    r'120\.237\.39\.10|120\.198\.95\.220|120\.196\.235\.42|120\.238\.84\.45|'
    r'120\.40\.39\.246|113\.57\.140\.161|219\.147\.245\.238|58\.56\.162\.102|'
    r'118\.122\.144\.115|171\.38\.148\.188|171\.8\.86\.73|222\.240\.44\.42|'
    r'183\.142\.200\.28|118\.193\.115\.2|111\.8\.242\.127|27\.39\.122\.2|'
    r'139\.214\.181\.174|222\.71\.55\.147|119\.39\.9\.8|221\.7\.175\.154|'
    r'61\.161\.61\.119|218\.13\.170\.98|112\.99\.195\.122|110\.53\.218\.182|'
    r'222\.169\.85\.8|111\.8\.242\.104|61\.178\.227\.57|182\.150\.23\.74|'
    r'36\.136\.38\.87|222\.128\.55\.152|61\.136\.172\.236|112\.27\.235\.94|'
    r'38\.64\.72\.148|74\.91\.26\.218|1\.190\.240\.47|121\.57\.88\.206|'
    r'47\.100\.209\.208|39\.164\.143\.66|175\.155\.106\.72|113\.57\.140\.161)'
)

# ========== 工具函数 ==========

async def fetch_text(session, url):
    """从远程 URL 拉取 M3U 文本内容"""
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
            if r.status == 200:
                return await r.text(encoding="utf-8", errors="ignore")
    except Exception:
        pass
    return ""


def parse_m3u(text):
    """解析 M3U 文本，返回 [(extinf行, url)]"""
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


def get_channel_name(extinf_line):
    """从 EXTINF 行提取频道名称"""
    # 尝试提取 tvg-name 属性
    m = re.search(r'tvg-name="([^"]+)"', extinf_line)
    if m:
        return m.group(1).strip()
    # 否则取逗号后面的部分
    return extinf_line.split(',', 1)[-1].strip()


def score_url(url):
    """对 URL 进行优先级打分，分数越高越优先"""
    score = 0
    if PREFER_IPS.match(url):
        score += 10          # 优选网段（江苏联通/电信）
    if url.startswith('https'):
        score += 2           # HTTPS 优先
    if 'txiptv' in url:
        score += 1           # 运营商源特征
    if 'newlive' in url or 'hls/' in url:
        score += 1           # 常见稳定路径
    if url.startswith('udp/'):
        score -= 20          # UDP 组播强烈降权
    if len(url) > 500:
        score -= 5           # 超长 URL 降权（可能带过期 token）
    return score


async def measure_latency_and_check(session, url):
    """
    测活并测量延迟，同时验证内容是否为真正的 HLS 流
    返回 (延迟秒数, 是否有效)，失败返回 None
    """
    try:
        start = time.time()
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=TIMEOUT),
                               headers={"User-Agent": "Mozilla/5.0"}) as r:
            if r.status not in (200, 206):
                return None
            # 读取前 2KB 检查是否为真正的 HLS 流
            chunk = await r.content.read(2048)
            elapsed = time.time() - start
            if b"#EXTM3U" in chunk:
                return (elapsed, True)
            else:
                # 返回 200 但不是 HLS 流（可能是 HTML 错误页）
                return None
    except Exception:
        return None


# ========== 主流程 ==========

async def main():
    # 1. 读取 sources.txt
    if not os.path.exists(SOURCES_FILE):
        print("❌ sources.txt 不存在"); return
    source_urls = [l.strip() for l in open(SOURCES_FILE, encoding="utf-8")
                   if l.strip() and not l.startswith("#")]
    if not source_urls:
        print("❌ sources.txt 中没有有效的订阅链接"); return
    print(f"📡 将从 {len(source_urls)} 个订阅源拉取数据")

    # 2. 并发拉取所有远程 M3U
    async with aiohttp.ClientSession() as session:
        raws = await asyncio.gather(*[fetch_text(session, u) for u in source_urls])

    # 3. 合并去重（按 URL 去重）
    seen = set()
    merged = []
    for txt in raws:
        for extinf, u in parse_m3u(txt):
            if u not in seen:
                seen.add(u)
                merged.append((extinf, u))
    print(f"📋 合并去重后共 {len(merged)} 条候选")

    # 4. 按白名单过滤频道
    whitelist_set = set(CHANNEL_WHITELIST)
    filtered = []
    for extinf, u in merged:
        name = get_channel_name(extinf)
        if name in whitelist_set:
            filtered.append((extinf, u, name))
    print(f"🔍 白名单过滤后剩余 {len(filtered)} 条")

    if not filtered:
        print("⚠️ 白名单过滤后无剩余频道，请检查 sources.txt 或白名单配置")
        return

    # 5. 并发测活 + 内容校验 + 延迟测量
    async with aiohttp.ClientSession() as session:
        tasks = [measure_latency_and_check(session, u) for _, u, _ in filtered]
        results = await asyncio.gather(*tasks)

    # 6. 组合有效结果并计算综合得分
    valid_items = []
    for i, result in enumerate(results):
        if result is not None:
            latency, is_valid = result
            extinf, url, name = filtered[i]
            ip_score = score_url(url)
            # 综合得分：延迟越低越好，IP 优先级越高越好
            # 归一化：延迟权重 0.6，IP 权重 0.4
            combined_score = ip_score * 0.4 - latency * 10 * 0.6
            valid_items.append({
                'extinf': extinf,
                'url': url,
                'name': name,
                'latency': latency,
                'ip_score': ip_score,
                'combined_score': combined_score
            })

    print(f"✅ 测活存活 {len(valid_items)} 条")

    if not valid_items:
        print("⚠️ 所有链接均失效，请检查网络或 sources.txt")
        return

    # 7. 按综合得分排序（高分优先）
    valid_items.sort(key=lambda x: x['combined_score'], reverse=True)

    # 8. 每个频道最多保留 MAX_PER_CHANNEL 条
    seen_channel = {}
    final_valid = []
    for item in valid_items:
        name = item['name']
        if name not in seen_channel:
            seen_channel[name] = 0
        if seen_channel[name] < MAX_PER_CHANNEL:
            seen_channel[name] += 1
            final_valid.append(item)

    # 9. 总量限制
    final_valid = final_valid[:MAX_CHANNELS]
    print(f"📊 最终保留 {len(final_valid)} 条（{len(set(i['name'] for i in final_valid))} 个频道）")

    # 10. 写入 live.m3u
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write('#EXTM3U url-tvg="https://epg.pw/api/guide.php?channel={channel}&format=json"\n')
        f.write('# 苏州联通优选 · 自动测活生成\n')
        for item in final_valid:
            f.write(item['extinf'] + "\n")
            f.write(item['url'] + "\n")

    print(f"✅ 已写出 {OUTPUT_M3U}")
    
    # 打印前 10 个频道预览
    print("\n📺 前 10 个频道预览：")
    for item in final_valid[:10]:
        print(f"  {item['name']:<12} 延迟:{item['latency']:.2f}s  得分:{item['combined_score']:.1f}")

if __name__ == "__main__":
    asyncio.run(main())
