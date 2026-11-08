# -*- coding: utf-8 -*-
"""
group_m3u.py - IPTV 分组重写器（双模式输出）

输出两个文件：
  1. live_ok.m3u    通用版：保留 # cmcc-province 注释、二级分组用 " / " 分隔
  2. live_aptv.m3u  APTV 专用版：去注释、分组用 "·" 连接、字段全部显式占位

用法：
  python group_m3u.py              # 双模式（默认）
  python group_m3u.py --aptv-only  # 只输出 APTV 版
  python group_m3u.py --generic-only  # 只输出通用版
"""

import re
import argparse
from pathlib import Path
from collections import OrderedDict

# ========== 国内频道类型（一级分类） ==========
# 顺序即输出顺序；"中国移动" 插在 "卫视频道" 之后
CN_CATEGORIES = OrderedDict([
    ("央视频道", [
        "CCTV", "CETV", "央视", "风云", "电视指南", "央广", "CGTN"
    ]),
    ("卫视频道", [
        "卫视", "湖南", "浙江", "江苏", "东方", "北京", "广东",
        "湖北", "安徽", "山西", "广西", "CHC", "四川", "云南",
        "江西", "吉林", "黑龙江", "内蒙古", "青海", "深圳",
        "重庆", "陕西", "西藏", "新疆", "厦门", "海南", "河北",
        "辽宁", "河南", "山东", "天津", "宁夏", "甘肃", "贵州",
        "东南", "大湾区", "三沙", "安多", "延边", "QTV", "BTV"
    ]),
    ("中国移动", [
        "chinamobile", "cmcc", "移动", "2409:8087", "2408:",
        "otttv", "dbiptv", "plcm", "miguvideo", "itv.aptv"
    ]),
    ("地方台", [
        "新闻", "综合", "公共", "都市", "生活", "经济", "影视", "少儿",
        "科教", "综艺", "民生", "体育", "国际", "乡村", "农民", "教育",
        "文化旅游", "靖江", "宿州", "荆门", "固镇", "松潘", "旺苍", "汶川",
        "渭源", "张掖", "安顺", "六安", "灌阳", "铜陵", "三明", "金川",
        "新昌", "嵊州", "缙云", "开化", "兰溪", "武义", "庆元", "云和",
        "余姚", "余杭", "洞头", "文成", "遂昌", "松阳", "龙泉", "青田",
        "平湖", "萧山", "上虞", "龙游", "乐至", "易门", "名山", "通海",
        "定襄", "荥经", "泸县", "青川", "嘉峪关", "白银", "永昌", "天祝",
        "衡水", "清河", "昌黎", "任丘", "平泉", "兴隆", "滦平", "太谷",
        "普陀", "象山", "嵊泗", "黄山", "南京", "镇江", "苏州", "无锡",
        "诸暨", "东阳", "广州", "南宁", "之江", "梨园", "海南", "上海",
        "朝阳", "长白", "汾西", "西峰", "邯鄣", "第一财经"
    ]),
    ("电影频道", [
        "电影", "影院", "影视", "经典", "龙祥", "怀旧", "都市剧场", "SiTV"
    ]),
    ("少儿频道", [
        "少儿", "动画", "卡通", "儿童", "TVOKids", "卡酷", "金鹰卡通"
    ]),
])

# 国内省份（用于二级分组）
CN_PROVINCES = [
    ("北京", ["北京", "BTV"]),
    ("上海", ["上海", "东方", "第一财经"]),
    ("广东", ["广东", "广州", "深圳", "珠海", "佛山", "东莞", "大湾区", "珠江", "嘉佳"]),
    ("浙江", ["浙江", "杭州", "宁波", "温州", "嘉兴", "湖州", "绍兴", "金华", "衢州", "舟山", "台州", "丽水", "缙云", "开化", "兰溪", "嵊州", "武义", "余姚", "庆元", "云和", "新昌", "嵊泗", "文成", "遂昌", "松阳", "龙泉", "青田", "平湖", "萧山", "上虞", "龙游", "乐至", "之江", "余杭", "洞头", "东阳", "中国蓝"]),
    ("江苏", ["江苏", "南京", "苏州", "无锡", "常州", "徐州", "南通", "连云港", "淮安", "盐城", "扬州", "镇江", "泰州", "宿迁", "宿州", "靖江", "新沂", "涟水", "灌阳"]),
    ("湖南", ["湖南", "长沙", "梨园"]),
    ("湖北", ["湖北", "武汉", "荆门"]),
    ("四川", ["四川", "成都", "重庆", "泸县", "汶川", "松潘", "金川", "旺苍", "太谷", "渭源", "张掖", "安顺", "乐至", "青川", "易门", "名山", "通海", "嘉峪关", "白银", "永昌", "天祝", "普陀"]),
    ("山东", ["山东", "济南", "青岛", "QTV"]),
    ("福建", ["福建", "福州", "厦门", "东南", "海峡"]),
    ("安徽", ["安徽", "黄山"]),
    ("江西", ["江西"]),
    ("河南", ["河南", "郑州"]),
    ("河北", ["河北", "石家庄", "秦皇岛", "清河", "滦平", "衡水", "昌黎", "任丘", "平泉", "兴隆"]),
    ("山西", ["山西", "太原", "定襄", "汾西"]),
    ("陕西", ["陕西", "西安", "农林", "三沙"]),
    ("辽宁", ["辽宁", "沈阳", "大连"]),
    ("吉林", ["吉林", "延边", "长白"]),
    ("黑龙江", ["黑龙江", "哈尔滨"]),
    ("内蒙古", ["内蒙古", "内蒙"]),
    ("新疆", ["新疆"]),
    ("西藏", ["西藏", "安多"]),
    ("宁夏", ["宁夏"]),
    ("青海", ["青海"]),
    ("甘肃", ["甘肃", "兰州", "西峰"]),
    ("云南", ["云南", "昆明"]),
    ("贵州", ["贵州", "贵阳"]),
    ("广西", ["广西", "南宁", "桂林"]),
    ("海南", ["海南", "三亚"]),
    ("港澳台", ["香港", "澳门", "台湾", "东森", "纬来", "三立", "TVBS", "民视", "台视", "中视", "华视"]),
]

# ========== 国外频道类型（一级分类） ==========
FOREIGN_CATEGORIES = OrderedDict([
    ("新闻频道", [
        "News", "新闻", "Televida", "TV27", "TV 24", "TVCARiB Latino",
        "Televisora de Oriente", "TV Curuca", "TV Estrella", "Tenarenses",
        "Telesur", "Telepacifico", "TVN (Chile)", "Times Now",
        "News 21", "CCTN", "HLAO", "HLDQ", "Dali TV", "UN Web"
    ]),
    ("电影频道", [
        "Movie", "Film", "Cinema", "Cinemalu", "电影", "Whiplash", "龙祥",
        "黑莓", "经典电影", "Zee Cinema", "精品体育", "Movies Now",
        "FILMBOX", "Star Maa Movies", "We TV", "Sony", "WWE"
    ]),
    ("儿童频道", [
        "Kids", "Teens", "儿童", "少儿", "卡通", "TVOKids", "TV2 Kids",
        "Polsat Viasat"
    ]),
    ("娱乐频道", [
        "TV Land", "娱乐", "Sitcom", "Comedy", "Show", "Drama", "Walking Dead",
        "Wild West", "Rifleman", "Hillbillies", "Love Boat", "Twilight Zone",
        "Challenge", "Price Is Right", "Three's Company", "Millers",
        "Tiny House", "Top Gear", "Tosh.0", "Voyages", "Unga Mammor",
        "True Crime", "Vevo", "Wildfire", "Weeds", "Andy Griffith",
        "Beverly Hillbillies", "Wild 'N Out", "That's", "Detectives",
        "Viafree", "Vaya", "Y'a que la verite", "Unifranz", "UMSA",
        "Venevision", "The Daily Show", "Yellow Couch", "Pet Collective",
        "The L Word", "Western TV", "Vav TV", "XITE", "Med Muzik",
        "Music Box", "UA Music", "Visual Radio", "Sorozat", "Prima",
        "TV Paprika", "TV2 (Hungary)", "O!", "Dushevnoe", "Vitebsk",
        "Rang", "Pasand", "Madani", "Radio Fann", "BritBox", "Wedo TV",
        "Vipa TV", "Zoom", "TET", "UDAR", "2M", "A&E", "History 2",
        "Lifetime", "Ve Plus", "A&R Canal", "Vea Canal", "ACC Network",
        "MTV2", "One America", "Fox", "NBC", "ABC", "Sansad", "Star Sports",
        "Asharq", "W9", "France 3", "KBS", "TV Liptov", "Parliament",
        "Dali", "ETV", "Ulzii", "Malchin", "TV 25", "Televize Seznam",
        "Pro Cinema", "SADA", "13 Ulica", "True Crime Network"
    ]),
])

# 国外国家（用于二级分组）
FOREIGN_COUNTRIES = [
    ("美国", ["univision", "jmp2.uk", "epg.pw", "USA", "UniMas", "WFUT", "WXTV", "KMEX", "WVVH", "W14DK", "KVVB", "Youtoo", "Pluto", "VICE", "Yes Network", "Universal TV Latin", "The Challenge", "The Millers", "The Price Is Right", "Three's Company", "The Beverly Hillbillies", "The Love Boat", "The Rifleman", "The Andy Griffith", "The New Detectives", "The Walking Dead", "The Yellow Couch", "The Daily Show", "That's", "Tiny House", "Top Gear", "Tosh.0", "True Crime by Pluto", "Tough Jobs", "Turbo", "Turma da Monica", "TV Land", "Tennis Channel", "Unga Mammor", "Unidad de investigacion", "Utsav", "Vevo True School", "Voyages", "Weeds", "Western TV", "Whiplash", "Wild 'N Out", "Wild at Heart", "Wildfire", "Window TV", "XITE", "Y'a que la verite"]),
    ("英国", ["tweedekamer", "klompezaal", "plenaire", "stoelzaal", "thorbeckezaal", "groenewegzaal", "TV Land Drama", "Totally Turtles", "True crime fran Viaplay", "Vaya semanita", "Viafree Movies"]),
    ("荷兰", ["tweedekamer", "klompezaal", "plenairezaal", "maxvanderstoelzaal", "thorbeckezaal", "suzegroenewegzaal"]),
    ("印度", ["Zee", "YuppTV", "ColorsHD", "Utsav", "Venevision", "Sony", "Star", "Colors", "ETV", "News 21"]),
    ("葡萄牙", ["TVI", "V+ TVI", "canaistvpt", "tvi"]),
    ("拉美", ["Univision", "Universal TV Latin America", "UniMas", "TEN Canal", "TVN (Chile)", "Televida", "Telepacifico", "Telesur", "TV Curuca", "TV Estrella", "Tenarenses", "Televisora de Oriente", "Unidad de investigacion", "Venevision Internacional"]),
    ("泰国", ["True4U", "thaimomo", "chtvb", "Umm TV"]),
    ("法国", ["Voyages", "TMC", "Y'a que la verite", "W9", "France 3"]),
    ("德国", ["Tortues Ninja", "The L Word", "Pluto", "DMAX"]),
    ("北欧", ["DK", "NO", "Sweden", "DK)", "NO)", "(Sweden)", "NO (", "DK (", "Viafree Movies NO", "Viafree Movies DK"]),
    ("东欧", ["Dushevnoe", "Vitebsk", "O!", "UA Music", "13 Ulica", "Sorozat+", "Prima", "TV Paprika"]),
    ("中东", ["Asharq", "Madani", "Radio Fann", "Zoom (Israel)", "2M"]),
    ("其他境外源", ["cloudfront", "streamhoster", "enhdtv", "fasttvcdn", "mycloudstream", "whiplash", "xpbroadcasting", "manasat", "smashmalta", "fastchannel", "ultrabase", "enisoras", "hostlagarto", "kylintv", "whats on", "cloudstream"]),
]

# 需要转义的 #EXTINF 属性字符（值一律用双引号包裹）
_ESCAPE_RE = re.compile(r'(?<!\\)"')


def _esc(val):
    """转义属性值里的双引号（补一个反斜杠），避免破坏双引号包裹。"""
    return _ESCAPE_RE.sub(r'\\"', val)


def get_extinf_name(extinf):
    m = re.search(r',([^,]*)$', extinf)
    return m.group(1).strip() if m else "未知"


def get_attr(extinf, attr):
    """提取 #EXTINF 中某个属性值，如 tvg-id"""
    m = re.search(r'%s="([^"\\]*(?:\\.[^"\\]*)*)"' % re.escape(attr), extinf)
    if not m:
        return ""
    # 去掉转义
    return m.group(1).replace('\\"', '"').replace("\\\\", "\\")


def get_cmcc_province(comment):
    """从注释行提取 cmcc-province"""
    m = re.search(r'cmcc-province="([^"]*)"', comment)
    return m.group(1) if m else ""


def is_local_priority(comment):
    """判断是否为本省优先标记"""
    return "(本省优先)" in comment


def classify_cn_category(name, is_cmcc, cmcc_province):
    """
    国内一级分类。
    优先级：移动源 → 央视 → 卫视 → 电影 → 少儿 → 地方台
    """
    if is_cmcc and cmcc_province:
        return "中国移动"

    name_l = name.lower()
    # 先检查央视（避免 CCTV-1 被误分到地方台）
    for kw in CN_CATEGORIES["央视频道"]:
        if kw.lower() in name_l:
            return "央视频道"

    # 再检查卫视
    for kw in CN_CATEGORIES["卫视频道"]:
        if kw.lower() in name_l:
            return "卫视频道"

    # 电影
    for kw in CN_CATEGORIES["电影频道"]:
        if kw.lower() in name_l:
            return "电影频道"

    # 少儿
    for kw in CN_CATEGORIES["少儿频道"]:
        if kw.lower() in name_l:
            return "少儿频道"

    return "地方台"


def classify_cn_province(name, category, cmcc_province=""):
    """国内二级分组（省份）"""
    # 移动源直接用 cmcc-province
    if category == "中国移动" and cmcc_province:
        return cmcc_province

    name_l = name.lower()
    for prov, keywords in CN_PROVINCES:
        for kw in keywords:
            if kw.lower() in name_l:
                return prov
    return "其他"


def classify_foreign_category(name):
    name_l = name.lower()
    for cat, keywords in FOREIGN_CATEGORIES.items():
        for kw in keywords:
            if kw.lower() in name_l:
                return cat
    return "娱乐频道"


def classify_foreign_country(name):
    name_l = name.lower()
    for country, keywords in FOREIGN_COUNTRIES:
        for kw in keywords:
            if kw.lower() in name_l:
                return country
    return "其他境外源"


def is_cn(name):
    """判断国内外"""
    if any('\u4e00' <= c <= '\u9fff' for c in name):
        return True
    cn_domains = ["cztvcloud", "qtv.com.cn", "qingting.fm", "kankanlive",
                  "qnmty.com", "gztv.com", "sxmty.com", "yunxya.com",
                  "ganzitv.com", "juyun.tv", "51kandianshi", "live-auth",
                  "nbs.cn", "hugd.com", "shaoxing.com", "zohi.tv",
                  "nntv.cn", "livehwc", "jmtv.com", "spccmc.com",
                  "jincuanrmt", "qcfile", "xntv.tv", "nmtv.cn",
                  "jlntv.cn", "sdetv.com", "cnr.cn", "hntv.tv",
                  "iyb983.cn", "hebyun.com", "hebtv.com", "lanzhousobey",
                  "hsnewsnet.com", "chinacert", "kwimgs.com",
                  "txmov2", "play.kankanlive", "120.76.248",
                  "chinamobile.com", "itv.aptv.app", "miguvideo.com"]
    name_l = name.lower()
    return any(d in name_l for d in cn_domains)


def make_group_title(cat, sub, separator=" / "):
    """生成 group-title。separator 决定二级连接方式。"""
    if sub in ("其他", "其他境外源"):
        return cat
    return f"{cat}{separator}{sub}"


def parse_entries():
    """
    解析 live_ok.m3u，提取：
    - extinf
    - url
    - name
    - tvg_id / tvg_logo / tvg_name（从 #EXTINF 属性里读，兜底到名字）
    - cmcc_province（从注释）
    - is_local（是否本省优先）
    - is_cmcc
    """
    if not Path("live_ok.m3u").exists():
        print("❌ live_ok.m3u 不存在")
        return []

    lines = Path("live_ok.m3u").read_text(encoding="utf-8").splitlines()
    entries = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            extinf = line
            url = lines[i + 1].strip() if i + 1 < len(lines) else ""
            name = get_extinf_name(extinf)

            # 向前查找注释行（cmcc-province）
            comment = ""
            j = i - 1
            while j >= 0 and lines[j].strip().startswith("#"):
                if "cmcc-province" in lines[j]:
                    comment = lines[j].strip()
                    break
                j -= 1

            cmcc_province = get_cmcc_province(comment)
            is_local = is_local_priority(comment)

            entries.append({
                "extinf": extinf,
                "url": url,
                "name": name,
                "tvg_id": get_attr(extinf, "tvg-id") or "",
                "tvg_logo": get_attr(extinf, "tvg-logo") or "",
                "tvg_name": get_attr(extinf, "tvg-name") or name,
                "cmcc_province": cmcc_province,
                "is_local": is_local,
                "is_cmcc": bool(cmcc_province),
            })
            i += 2
        else:
            i += 1

    return entries


def build_grouped(entries):
    """按分类把 entries 装桶，返回 (cn_buckets, foreign_buckets)"""
    cn_buckets = {}
    foreign_buckets = {}

    for e in entries:
        name = e["name"]
        is_cmcc = e["is_cmcc"]
        cmcc_province = e["cmcc_province"]

        if is_cn(name) or is_cmcc:
            cat = classify_cn_category(name, is_cmcc, cmcc_province)
            sub = classify_cn_province(name, cat, cmcc_province)
            key = (cat, sub)
            cn_buckets.setdefault(key, []).append(e)
        else:
            cat = classify_foreign_category(name)
            sub = classify_foreign_country(name)
            key = (cat, sub)
            foreign_buckets.setdefault(key, []).append(e)

    return cn_buckets, foreign_buckets


def _cn_sorted_entries(cat, cat_entries):
    """国内桶内排序：中国移动按本省优先，其他按省份"""
    if cat == "中国移动":
        def cmcc_sort_key(item):
            return (0 if item["is_local"] else 1, item["name"])
        cat_entries.sort(key=lambda kv: kv[0][1])  # 先按省份
        sorted_items = []
        for (c, sub), items in cat_entries:
            items_sorted = sorted(items, key=cmcc_sort_key)
            sorted_items.append(((c, sub), items_sorted))
        return sorted_items
    else:
        return sorted(cat_entries, key=lambda x: x[0][1])


def _foreign_sorted_entries(cat_entries):
    return sorted(cat_entries, key=lambda x: x[0][1])


def _build_extinf(e, group_title):
    """通用版：保留原 #EXTINF 的字段，仅改写 group-title。"""
    extinf = e["extinf"]
    if re.search(r'group-title="[^"\\]*(?:\\.[^"\\]*)*"', extinf):
        new_extinf = re.sub(
            r'group-title="[^"\\]*(?:\\.[^"\\]*)*"',
            'group-title="%s"' % _esc(group_title),
            extinf, count=1
        )
    else:
        # 没有 group-title，补一个
        new_extinf = extinf.replace(
            "#EXTINF:-1",
            '#EXTINF:-1 group-title="%s"' % _esc(group_title),
            1
        )
    return new_extinf


def _build_extinf_aptv(e, group_title):
    """
    APTV 版：四个字段全部显式写出（即使为空也要占位），
    值一律双引号包裹、内部双引号转义，符合 APTV 严格解析要求。
    """
    tvg_id = _esc(e["tvg_id"])
    tvg_name = _esc(e["tvg_name"] or e["name"])
    tvg_logo = _esc(e["tvg_logo"])
    gt = _esc(group_title)
    return ('#EXTINF:-1 tvg-id="%s" tvg-name="%s" tvg-logo="%s" group-title="%s",%s'
            % (tvg_id, tvg_name, tvg_logo, gt, tvg_name))


def _emit_generic(lines_out, cn_buckets, foreign_buckets):
    """写通用版内容到 lines_out，返回 (cn_total, foreign_total)"""
    # ===== 国内频道 =====
    lines_out.append("# ===== 国内频道 =====")
    cn_total = 0
    for cat in CN_CATEGORIES.keys():
        cat_entries = [(k, v) for k, v in cn_buckets.items() if k[0] == cat]
        if not cat_entries:
            continue
        lines_out.append("# --- %s ---" % cat)
        for (c, sub), items in _cn_sorted_entries(cat, cat_entries):
            group_title = make_group_title(cat, sub, separator=" / ")
            lines_out.append("# ---- %s (%d) ----" % (sub, len(items)))
            for e in items:
                # 通用版：保留 cmcc 注释
                if e["cmcc_province"]:
                    lines_out.append('# cmcc-province="%s"%s' % (
                        e["cmcc_province"],
                        " (本省优先)" if e["is_local"] else ""
                    ))
                lines_out.append(_build_extinf(e, group_title))
                lines_out.append(e["url"])
            cn_total += len(items)

    # ===== 国外频道 =====
    lines_out.append("# ===== 国外频道 =====")
    foreign_total = 0
    for cat in FOREIGN_CATEGORIES.keys():
        cat_entries = [(k, v) for k, v in foreign_buckets.items() if k[0] == cat]
        if not cat_entries:
            continue
        lines_out.append("# --- %s ---" % cat)
        for (c, sub), items in _foreign_sorted_entries(cat_entries):
            group_title = make_group_title(cat, sub, separator=" / ")
            lines_out.append("# ---- %s (%d) ----" % (sub, len(items)))
            for e in items:
                lines_out.append(_build_extinf(e, group_title))
                lines_out.append(e["url"])
            foreign_total += len(items)

    return cn_total, foreign_total


def _emit_aptv(lines_out, cn_buckets, foreign_buckets):
    """写 APTV 专用版内容（无注释、分组用 ·、字段全占位）"""
    # ===== 国内频道 =====
    lines_out.append("# ===== 国内频道 =====")
    cn_total = 0
    for cat in CN_CATEGORIES.keys():
        cat_entries = [(k, v) for k, v in cn_buckets.items() if k[0] == cat]
        if not cat_entries:
            continue
        lines_out.append("# --- %s ---" % cat)
        for (c, sub), items in _cn_sorted_entries(cat, cat_entries):
            # APTV 用 "·" 连接，避免 "/" 被当成字面字符串显示
            group_title = make_group_title(cat, sub, separator="·")
            lines_out.append("# ---- %s (%d) ----" % (sub, len(items)))
            for e in items:
                lines_out.append(_build_extinf_aptv(e, group_title))
                lines_out.append(e["url"])
            cn_total += len(items)

    # ===== 国外频道 =====
    lines_out.append("# ===== 国外频道 =====")
    foreign_total = 0
    for cat in FOREIGN_CATEGORIES.keys():
        cat_entries = [(k, v) for k, v in foreign_buckets.items() if k[0] == cat]
        if not cat_entries:
            continue
        lines_out.append("# --- %s ---" % cat)
        for (c, sub), items in _foreign_sorted_entries(cat_entries):
            group_title = make_group_title(cat, sub, separator="·")
            lines_out.append("# ---- %s (%d) ----" % (sub, len(items)))
            for e in items:
                lines_out.append(_build_extinf_aptv(e, group_title))
                lines_out.append(e["url"])
            foreign_total += len(items)

    return cn_total, foreign_total


def _print_stats(cn_total, foreign_total, cn_buckets, foreign_buckets):
    print("🇨🇳 国内频道: %d" % cn_total)
    for cat in CN_CATEGORIES.keys():
        cat_items = [(k, v) for k, v in cn_buckets.items() if k[0] == cat]
        if cat_items:
            if cat == "中国移动":
                details = ", ".join(
                    "%s×%d%s" % (sub, len(items), "🏠" if any(i["is_local"] for i in items) else "")
                    for (c, sub), items in sorted(cat_items, key=lambda x: -len(x[1]))
                )
            else:
                details = ", ".join(
                    "%s×%d" % (sub, len(items))
                    for (c, sub), items in sorted(cat_items, key=lambda x: -len(x[1]))
                )
            print("   %s: %d | %s" % (cat, sum(len(v) for k, v in cat_items), details))

    print("🌍 国外频道: %d" % foreign_total)
    for cat in FOREIGN_CATEGORIES.keys():
        cat_items = [(k, v) for k, v in foreign_buckets.items() if k[0] == cat]
        if cat_items:
            details = ", ".join(
                "%s×%d" % (sub, len(items))
                for (c, sub), items in sorted(cat_items, key=lambda x: -len(x[1]))
            )
            print("   %s: %d | %s" % (cat, sum(len(v) for k, v in cat_items), details))


def rewrite(entries, generic=True, aptv=True):
    cn_buckets, foreign_buckets = build_grouped(entries)

    if generic:
        lines_out = ["#EXTM3U"]
        cn_total, foreign_total = _emit_generic(lines_out, cn_buckets, foreign_buckets)
        Path("live_ok.m3u").write_text("\n".join(lines_out) + "\n", encoding="utf-8")
        print("✅ 通用版 live_ok.m3u 已生成")
        _print_stats(cn_total, foreign_total, cn_buckets, foreign_buckets)

    if aptv:
        lines_out = ["#EXTM3U"]
        cn_total, foreign_total = _emit_aptv(lines_out, cn_buckets, foreign_buckets)
        Path("live_aptv.m3u").write_text("\n".join(lines_out) + "\n", encoding="utf-8")
        print("✅ APTV 版 live_aptv.m3u 已生成 (%d 条)" % (cn_total + foreign_total))


def main():
    parser = argparse.ArgumentParser(description="IPTV 分组重写器（通用版 + APTV 版）")
    parser.add_argument("--aptv-only", action="store_true", help="只输出 APTV 专用版")
    parser.add_argument("--generic-only", action="store_true", help="只输出通用版")
    args = parser.parse_args()

    entries = parse_entries()
    if not entries:
        return

    print("📥 读取 %d 条源" % len(entries))

    generic = not args.aptv_only
    aptv = not args.generic_only
    if args.aptv_only and args.generic_only:
        # 两者都指定时，默认双模式
        generic, aptv = True, True

    rewrite(entries, generic=generic, aptv=aptv)


if __name__ == "__main__":
    main()
