#!/usr/bin/env python3
"""
从两个公开源里，为「苏州联通」环境筛选一份最小可用 M3U。
优先级：江苏/联通/电信网段 > 其他；每个频道保留 1-2 条。
"""
import re, os

# ---------- 1. 读取两份源 ----------
def load_txt(path):
    """返回 {频道名: [url, ...]}"""
    out = {}
    cur = None
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            if line.endswith('#genre#'):
                cur = None; continue
            if ',' in line:
                name, url = line.split(',', 1)
                name, url = name.strip(), url.strip()
                if not name or not url: continue
                out.setdefault(name, []).append(url)
    return out

a = load_txt('/data/workspace/.tool_output/30e7f373-cc0e-42c5-be55-0f60f64c4dcd.txt')
b = load_txt('/data/workspace/.tool_output/8b2543bd-acdf-4ac1-b6c7-4cf1b0acc4dc.txt')

# 合并
all_ch = {}
for d in (a, b):
    for k, v in d.items():
        all_ch.setdefault(k, []).extend(v)

# 去重保序
def dedupe(seq):
    s, out = set(), []
    for x in seq:
        if x not in s:
            s.add(x); out.append(x)
    return out
for k in all_ch:
    all_ch[k] = dedupe(all_ch[k])

# ---------- 2. 频道挑选 ----------
# 央视全系列（按序号排）
cctv_order = ['CCTV1','CCTV2','CCTV3','CCTV4','CCTV5','CCTV5+','CCTV6','CCTV7',
              'CCTV8','CCTV9','CCTV10','CCTV11','CCTV12','CCTV13','CCTV14','CCTV15',
              'CCTV16','CCTV17']
# 江浙沪 + 主流卫视
weishi = ['东方卫视','江苏卫视','浙江卫视','上海第一财经','深圳卫视','北京卫视',
          '湖南卫视','广东卫视','山东卫视','安徽卫视','东南卫视','海峡卫视','厦门卫视']
# 苏州/江苏本地
local = ['苏州4K']

# ---------- 3. 源优先级打分 ----------
# 苏州联通宽带：联通/电信网段 + 江苏本省 IP 通常最稳
prefer_ips = re.compile(
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
    r'47\.100\.209\.208|39\.164\.143\.66|175\.155\.106\.72|'
    r'113\.57\.140\.161)'  # 大量电信/联通网段
)

def pick(urls, n=2):
    urls = list(urls)
    # 过滤掉明显无效的（udp组播、带中文、过长token的先保留但降权）
    scored = []
    for u in urls:
        s = 0
        if prefer_ips.match(u): s += 10          # 优选网段
        if u.startswith('https'): s += 2         # https 优先
        if 'txiptv' in u: s += 1                 # 带key的一般是运营商源
        if 'newlive' in u or 'hls/' in u: s += 1 # 常见稳定路径
        if u.startswith('http://'): s += 0
        # 降权：超长带token的、udp组播
        if u.startswith('udp/'): s -= 20
        if len(u) > 500: s -= 5
        scored.append((s, u))
    scored.sort(key=lambda x: -x[0])
    seen, out = set(), []
    for s, u in scored:
        if u not in seen:
            seen.add(u); out.append(u)
        if len(out) >= n: break
    return out

# ---------- 4. 组装 M3U ----------
def m3u_line(name, url):
    return f'#EXTINF:-1 tvg-name="{name}" group-title="精选",{name}\n{url}'

lines = ['#EXTM3U url-tvg="https://epg.pw/api/guide.php?channel={channel}&format=json"',
         '#EXTINF:-1 tvg-name="EPG" group-title="说明",本列表为苏州联通优选最小源']
lines.append('# 苏州联通宽带 · 央视+江浙沪卫视+苏州本地 · 自动生成')

# 央视
lines.append('')
lines.append('# === 央视频道 ===')
for c in cctv_order:
    if c in all_ch:
        for u in pick(all_ch[c], 2):
            lines.append(m3u_line(c, u))

# 卫视
lines.append('')
lines.append('# === 江浙沪及主流卫视 ===')
for c in weishi:
    if c in all_ch:
        for u in pick(all_ch[c], 2):
            lines.append(m3u_line(c, u))

# 苏州本地
lines.append('')
lines.append('# === 苏州本地 ===')
for c in local:
    if c in all_ch:
        for u in pick(all_ch[c], 2):
            lines.append(m3u_line(c, u))

# 额外：卡通/少儿（有娃家庭常用）
kids = ['金鹰卡通','卡酷少儿','优漫卡通','浙江少儿']
lines.append('')
lines.append('# === 少儿频道 ===')
for c in kids:
    if c in all_ch:
        for u in pick(all_ch[c], 1):
            lines.append(m3u_line(c, u))

content = '\n'.join(lines) + '\n'
out_path = '/data/workspace/苏州联通_精选IPTV.m3u'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(content)

# 统计
ch_count = sum(1 for l in content.splitlines() if l.startswith('#EXTINF'))
print(f'已生成: {out_path}')
print(f'频道数(含备用线路): {ch_count}')
print(f'文件大小: {os.path.getsize(out_path)/1024:.1f} KB')
print('--- 前 25 行预览 ---')
print('\n'.join(content.splitlines()[:25]))
