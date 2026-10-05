import re
from pathlib import Path
from collections import OrderedDict

# ========== 国内频道类型（一级分类） ==========
CN_CATEGORIES = OrderedDict([
    ("央视频道", [
        "CCTV", "央视", "风云", "电视指南", "央广", "央视台球"
    ]),
    ("卫视频道", [
        "卫视", "湖南", "浙江", "江苏", "东方", "北京", "广东", "湖北", "安徽",
        "山西", "广西", "CHC", "CETV", "四川", "云南", "江西", "吉林", "黑龙江",
        "内蒙古", "青海", "深圳", "重庆", "陕西", "西藏", "新疆", "厦门", "海南",
        "河北", "辽宁", "河南", "山东", "天津", "宁夏", "甘肃", "贵州", "东南",
        "大湾区", "三沙", "安多"
    ]),
    ("地方台", [
        "新闻", "综合", "都市", "生活", "经济", "公共", "影视", "少儿", "科教",
        "综艺", "民生", "体育", "国际", "乡村", "农民", "教育", "文化旅游",
        "靖江", "宿州", "荆门", "固镇", "松潘", "旺苍", "汶川", "渭源", "张掖",
        "安顺", "六安", "灌阳", "铜陵", "三明", "金川", "新沂", "滨州", "涟水",
        "余姚", "缙云", "开化", "兰溪", "嵊州", "武义", "庆元", "云和", "滦平",
        "太谷", "清河", "黄山", "苏州", "湖州", "海宁", "泸县", "朝阳"
    ]),
    ("电影频道", [
        "电影", "影院", "影视", "经典电影", "龙祥", "黑莓", "怀旧剧场", "都市剧场"
    ]),
    ("少儿频道", [
        "少儿", "动画", "卡通", "儿童"
    ]),
])

# 国内省份（二级分组）
CN_PROVINCES = [
    ("北京", ["北京", "BTV"]),
    ("上海", ["上海", "东方"]),
    ("广东", ["广东", "广州", "深圳", "珠海", "佛山", "东莞", "大湾区", "珠江", "嘉佳"]),
    ("浙江", ["浙江", "杭州", "宁波", "温州", "嘉兴", "湖州", "绍兴", "金华", "衢州", "舟山", "台州", "丽水", "缙云", "开化", "兰溪", "嵊州", "武义", "余姚", "庆元", "云和", "中国蓝"]),
    ("江苏", ["江苏", "南京", "苏州", "无锡", "常州", "徐州", "南通", "连云港", "淮安", "盐城", "扬州", "镇江", "泰州", "宿迁", "宿州", "靖江", "新沂", "涟水", "灌阳", "沭阳"]),
    ("湖南", ["湖南", "长沙"]),
    ("湖北", ["湖北", "武汉", "荆门"]),
    ("四川", ["四川", "成都", "重庆", "泸县", "汶川", "松潘", "金川", "旺苍", "太谷", "渭源", "张掖", "安顺", "六安"]),
    ("山东", ["山东", "济南", "青岛"]),
    ("福建", ["福建", "福州", "厦门", "东南", "海峡"]),
    ("安徽", ["安徽"]),
    ("江西", ["江西"]),
    ("河南", ["河南", "郑州"]),
    ("河北", ["河北", "石家庄", "秦皇岛", "清河", "滦平", "固镇", "滨海"]),
    ("山西", ["山西", "太原"]),
    ("陕西", ["陕西", "西安", "农林", "三沙"]),
    ("辽宁", ["辽宁", "沈阳", "大连"]),
    ("吉林", ["吉林"]),
    ("黑龙江", ["黑龙江", "哈尔滨"]),
    ("内蒙古", ["内蒙古", "内蒙"]),
    ("新疆", ["新疆"]),
    ("西藏", ["西藏"]),
    ("宁夏", ["宁夏"]),
    ("青海", ["青海"]),
    ("甘肃", ["甘肃", "兰州"]),
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
        "第一财经", "无线新闻", "三立新闻", "海峡", "TV24"
    ]),
    ("电影频道", [
        "Movie", "Film", "Cinema", "Cinemalu", "电影", "Whiplash", "龙祥",
        "黑莓", "经典电影", "Zee Cinema", "精品体育"
    ]),
    ("儿童频道", [
        "Kids", "Teens", "儿童", "少儿", "Cartoon", "Turtles", "Turma da Monica",
        "Totally Turtles", "尼克", "Nickelodeon"
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
        "The L Word", "Western TV", "Vav TV", "XITE"
    ]),
])

# 国外国家（二级分组）
FOREIGN_COUNTRIES = [
    ("美国", [
        "univision", "jmp2.uk", "epg.pw", "USA", "UniMas", "WFUT", "WXTV", "KMEX",
        "WVVH", "W14DK", "KVVB", "Youtoo", "Pluto", "VICE", "Yes Network",
        "Universal TV Latin", "The Challenge", "The Millers", "The Price Is Right",
        "Three's Company", "The Beverly Hillbillies", "The Love Boat",
        "The Rifleman", "The Andy Griffith", "The New Detectives",
        "The Walking Dead", "The Yellow Couch", "The Daily Show", "That's",
        "Tiny House", "Top Gear", "Tosh.0", "True Crime by Pluto", "Tough Jobs",
        "Turbo", "Turma da Monica", "TV Land", "Tennis Channel", "Unga Mammor",
        "Unidad de investigacion", "Utsav", "Vevo True School", "Voyages",
        "Weeds", "Western TV", "Whiplash", "Wild 'N Out", "Wild at Heart",
        "Wildfire", "Window TV", "XITE", "Y'a que la verite"
    ]),
    ("英国", [
        "tweedekamer", "klompezaal", "plenaire", "stoelzaal", "thorbeckezaal",
        "groenewegzaal", "TV Land Drama", "Totally Turtles", "True crime fran Viaplay",
        "Vaya semanita", "Viafree Movies"
    ]),
    ("荷兰", [
        "tweedekamer", "klompezaal", "plenairezaal", "maxvanderstoelzaal",
        "thorbeckezaal", "suzegroenewegzaal"
    ]),
    ("印度", ["Zee", "YuppTV", "ColorsHD", "Utsav", "Venevision"]),
    ("葡萄牙", ["TVI", "V+ TVI", "canaistvpt", "tvi"]),
    ("拉美", [
        "Univision", "Universal TV Latin America", "UniMas", "TEN Canal",
        "TVN (Chile)", "Televida", "Telepacifico", "Telesur", "TV Curuca",
        "TV Estrella", "Tenarenses", "Televisora de Oriente",
        "Unidad de investigacion", "Venevision Internacional"
    ]),
    ("泰国", ["True4U", "thaimomo", "chtvb", "Umm TV"]),
    ("法国", ["Voyages", "TMC", "Y'a que la verite"]),
    ("德国", ["Tortues Ninja", "The L Word"]),
    ("北欧", [
        "DK", "NO", "Sweden", "DK)", "NO)", "(Sweden)", "NO (", "DK (",
        "Viafree Movies NO", "Viafree Movies DK"
    ]),
    ("其他境外源", [
        "cloudfront", "streamhoster", "enhdtv", "fasttvcdn", "mycloudstream",
        "whiplash", "xpbroadcasting", "manasat", "smashmalta", "fastchannel",
        "ultrabase", "enisoras", "hostlagarto", "kylintv", "whats on",
        "cloudstream"
    ]),
]


def get_extinf_name(extinf: str) -> str:
    m = re.search(r',(.+)$', extinf)
    return m.group(1).strip() if m else "未知"


def classify_cn_category(name: str) -> str:
    name_l = name.lower()
    for cat, keywords in CN_CATEGORIES.items():
        for kw in keywords:
            if kw.lower() in name_l:
                return cat
    return "地方台"


def classify_cn_province(name: str) -> str:
    name_l = name.lower()
    for prov, keywords in CN_PROVINCES:
        for kw in keywords:
            if kw.lower() in name_l:
                return prov
    return "其他"


def classify_foreign_category(name: str) -> str:
    name_l = name.lower()
    for cat, keywords in FOREIGN_CATEGORIES.items():
        for kw in keywords:
            if kw.lower() in name_l:
                return cat
    return "娱乐频道"


def classify_foreign_country(name: str) -> str:
    name_l = name.lower()
    for country, keywords in FOREIGN_COUNTRIES:
        for kw in keywords:
            if kw.lower() in name_l:
                return country
    return "其他境外源"


def parse_entries():
    lines = Path("live_ok.m3u").read_text(encoding="utf-8").splitlines()
    entries = []
    for i, line in enumerate(lines):
        if line.startswith("#EXTINF"):
            url = lines[i + 1] if i + 1 < len(lines) else ""
            name = get_extinf_name(line)
            entries.append({"extinf": line, "url": url, "name": name})
    return entries


def is_cn(name: str) -> bool:
    try:
        import check
        return check.is_cn_source(name)
    except Exception:
        return any('\u4e00' <= c <= '\u9fff' for c in name)


def make_group_title(cat: str, sub: str) -> str:
    if sub in ("其他", "其他境外源"):
        return cat
    return f"{cat} / {sub}"


def rewrite(entries):
    cn_buckets = {}
    foreign_buckets = {}

    for e in entries:
        name = e["name"]
        if is_cn(name):
            cat = classify_cn_category(name)
            sub = classify_cn_province(name)
            key = (cat, sub)
            cn_buckets.setdefault(key, []).append(e)
        else:
            cat = classify_foreign_category(name)
            sub = classify_foreign_country(name)
            key = (cat, sub)
            foreign_buckets.setdefault(key, []).append(e)

    lines = ["#EXTM3U"]

    # 国内
    lines.append("# ===== 国内频道 =====")
    cn_total = 0
    for cat in CN_CATEGORIES.keys():
        cat_entries = [(k, v) for k, v in cn_buckets.items() if k[0] == cat]
        if not cat_entries:
            continue
        lines.append(f"# --- {cat} ---")
        for (c, sub), items in sorted(cat_entries, key=lambda x: x[0][1]):
            group_title = make_group_title(c, sub)
            lines.append(f"# ---- {sub} ({len(items)}) ----")
            for e in items:
                new_extinf = re.sub(
                    r'group-title="[^"]*"',
                    f'group-title="{group_title}"',
                    e["extinf"]
                )
                lines.append(new_extinf)
                lines.append(e["url"])
            cn_total += len(items)

    # 国外
    lines.append("# ===== 国外频道 =====")
    foreign_total = 0
    for cat in FOREIGN_CATEGORIES.keys():
        cat_entries = [(k, v) for k, v in foreign_buckets.items() if k[0] == cat]
        if not cat_entries:
            continue
        lines.append(f"# --- {cat} ---")
        for (c, sub), items in sorted(cat_entries, key=lambda x: x[0][1]):
            group_title = make_group_title(c, sub)
            lines.append(f"# ---- {sub} ({len(items)}) ----")
            for e in items:
                new_extinf = re.sub(
                    r'group-title="[^"]*"',
                    f'group-title="{group_title}"',
                    e["extinf"]
                )
                lines.append(new_extinf)
                lines.append(e["url"])
            foreign_total += len(items)

    Path("live_ok.m3u").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # 统计输出
    print(f"✅ 分组完成")
    print(f"🇨🇳 国内频道: {cn_total}")
    for cat in CN_CATEGORIES.keys():
        cat_items = [(k, v) for k, v in cn_buckets.items() if k[0] == cat]
        if cat_items:
            parts = []
            for (c, sub), items in sorted(cat_items, key=lambda x: (-len(x[1]))):
                parts.append(f"{sub}×{len(items)}")
            print(f"   {cat}: {sum(len(v) for k, v in cat_items)} | {' | '.join(parts)}")

    print(f"🌍 国外频道: {foreign_total}")
    for cat in FOREIGN_CATEGORIES.keys():
        cat_items = [(k, v) for k, v in foreign_buckets.items() if k[0] == cat]
        if cat_items:
            parts = []
            for (c, sub), items in sorted(cat_items, key=lambda x: (-len(x[1]))):
                parts.append(f"{sub}×{len(items)}")
            print(f"   {cat}: {sum(len(v) for k, v in cat_items)} | {' | '.join(parts)}")


if __name__ == "__main__":
    entries = parse_entries()
    rewrite(entries)
