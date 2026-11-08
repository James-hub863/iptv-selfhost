# IPTV 直播源自动收集 · 测活 · 分组流水线

一个 GitHub Actions 驱动的 IPTV 直播源自动化仓库：每日定时从公开聚合源 + 各省直链 + 中国移动各省源收集 M3U，测活选优，再按「国内 5 类 + 移动专属」与「国外 4 类」两级分组，输出可直接导入播放器的 `live_ok.m3u`。

---

## 目录

- [1. 流水线总览](#1-流水线总览)
- [2. 文件清单与职责](#2-文件清单与职责)
- [3. 数据流与产出](#3-数据流与产出)
- [4. 分组规则（核心）](#4-分组规则核心)
- [5. 中国移动源专项说明](#5-中国移动源专项说明)
- [6. 配置项速查](#6-配置项速查)
- [7. 使用方式](#7-使用方式)
- [8. 常见问题排查](#8-常见问题排查)
- [9. 已知现状与待落盘补丁](#9-已知现状与待落盘补丁)
- [10. 在播放器中使用](#10-在播放器中使用)

---

## 1. 流水线总览

```
┌──────────────────────────────────────────────────────────────────────┐
│ 触发：每日 06:00 / 18:00 (北京时间)  ＋  workflow_dispatch 手动触发   │
└──────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────┐    raw_channels.json     ┌──────────────────┐
│ ① collect.py     │ ───────────────────────▶ │ ② check.py      │
│ 双层收集          │   8188 条频道池          │ 测活选优         │
│ L1 iptv-org CDN  │                          │ 并发20线程/限20min│
│ L2 国内直链+移动  │                          └────────┬─────────┘
└───────────────────┘                                   │ live_ok.m3u
                                                         ▼
┌───────────────────┐                            ┌──────────────────┐
│ ④ update.yml     │                            │ ③ group_m3u.py  │
│ 提交 + 上传产物   │ ◀────────────────────────── │ 两级分组重写     │
│ git push + artifact│  分组后 live_ok.m3u         │ 国内5类+国外4类  │
└───────────────────┘                            └──────────────────┘
```

**设计目标**

| 目标 | 实现手段 |
|------|----------|
| 源持续新鲜 | 每日 2 次定时 + 公开源定期采集 |
| 只留能播的 | HEAD/GET 双检测活，两轮实测 |
| 切台快 | 按首包延迟升序，国内/国外各取前 150 |
| 播放器好找台 | 两级分组（类型 → 省份/国家） |
| 防误提交 | 频道池 <50 / 存活 <10 直接中止 |
| 移动源友好 | 独立分组 + IPv6 兼容（见第 5 节） |

---

## 2. 文件清单与职责

| 文件 | 职责 | 关键输入 → 输出 |
|------|------|----------------|
| `collect.py` | 双层收集器：L1 iptv-org（jsDelivr CDN）＋ L2 国内省市直链 + 中国移动各省源 | 网络 → `raw_channels.json` |
| `check.py` | 测活选优：并发探测、BLOCKED 过滤、去重保留最快、写缓存 | `raw_channels.json` → `live_ok.m3u` + `report.json` + `dead_urls.txt` + `cache.json` |
| `group_m3u.py` | 分组重写：按类型 + 省份/国家两级组织，重写 `group-title` | `live_ok.m3u` → 分组后 `live_ok.m3u` |
| `update.yml` | GitHub Actions 工作流：6 阶段编排、分层时限、自检、产物上传 | — |
| `cache.json` | 测活结果缓存（默认 TTL 1 天），避免重复探测同一 URL | 自动读写 |
| `requirements.txt` | Python 依赖（`requests` 等）；无第三方依赖时可省略 | — |

### 脚本之间的契约

```
collect.py                check.py                 group_m3u.py
───────────              ───────────              ─────────────
输出字段：                读取：                    读取：
 name                      name                     name
 url                       url                      group-title（重写）
 tvg_id                    tvg_id（可选）            tvg-name / tvg-logo（保留）
 tvg_logo                  tvg_logo（可选）
 group_title               group_title（可选）
 is_cmcc        ───────▶  is_cmcc                 # cmcc-province 注释
 is_ipv6                   is_ipv6（skip，不判死）
 cmcc_province             cmcc_province（本省优先）
 source                    source（统计）
```

---

## 3. 数据流与产出

### 阶段 ① 收集（`collect.py`）

- **L1 主源**：`cdn.jsdelivr.net/gh/iptv-org/iptv@master/streams/{code}.m3u`
  - 覆盖 100+ 国家/地区（cn / us / ru / de / jp / kr / fr / in …）
  - 实测一次可拉 **8188 条**，tvg-id 覆盖约 90%
  - 用 jsDelivr 是为了穿透 GitHub 原域名的 WAF 403
- **L2 国内直链**：浙江/河北/甘肃/四川/云南/青岛/南京/苏州/湖州/镇江/广州/福州/绍兴/荆门/延边 + 青海/内蒙古/西藏/新疆卫视
- **L2 移动源**：`https://itv.aptv.app/china-iptv/{prov}yd.m3u`（北京/上海/江苏/浙江/广东/四川/河南/湖南/安徽/山东/湖北/福建/辽宁/广西/江西/陕西/贵州/河北/重庆/甘肃/云南/内蒙古/黑龙江/山西）

### 阶段 ② 测活（`check.py`）

- 并发 20 线程，`HEAD` 先探、失败再 `GET` 流式探测
- `BLOCKED` 域名表硬过滤（含高频死链/失效域名）
- 同频道名去重，保留响应最快的一条
- 国内 / 国外各保留 **150 条**（共 300 条）
- 结果写缓存 `cache.json`，TTL 1 天

### 阶段 ③ 分组（`group_m3u.py`）

见第 4 节分组规则。

### 阶段 ④ 提交与产物（`update.yml`）

- `live_ok.m3u` / `live_all.m3u` 提交回仓库
- `cache/` 目录一并提交（跨次复用缓存，加速下次运行）
- Artifact 保留 7 天，含 `live_ok.m3u`、`live_all.m3u`、`report.json`、`dead_urls.txt`

---

## 4. 分组规则（核心）

### 国内频道：一级「类型」＋ 二级「省份」

| 一级分类（顺序即输出顺序） | 命中关键词 | 二级分组 |
|---------------------------|------------|----------|
| **央视频道** | CCTV / CETV / 央视 / 风云 / 电视指南 / 央广 / CGTN | 央视、风云… |
| **卫视频道** | 卫视 / 湖南 / 浙江 / 江苏 / 东方 / 北京 / 广东 / 湖北 / 安徽 / 广西 / 四川 / 青海 / 深圳 / 重庆 / 陕西 / 西藏 / 新疆 / 厦门 / 河北 / 辽宁 / 河南 / 山东 / 吉林 / 黑龙江 / 内蒙古 / 宁夏 / 甘肃 / 贵州 / 海南 / 延边 / QTV / BTV | 北京、上海、广东、浙江、江苏、湖南… |
| **地方台** | 新闻 / 综合 / 公共 / 都市 / 生活 / 经济 / 影视 / 科教 / 综艺 / 民生 / 体育 / 乡村 / 农民 / 教育 / 文化旅游 + 各县级台名（靖江、宿州、荆门、松潘、缙云、开化…） | 浙江、江苏、四川、河北、山东… |
| **电影频道** | 电影 / 影院 / 影视 / 经典 / 龙祥 / 怀旧 / 都市剧场 / SiTV | 省份 |
| **少儿频道** | 少儿 / 动画 / 卡通 / 儿童 / TVOKids / 卡酷 / 金鹰卡通 | 省份 |

### 国外频道：一级「类型」＋ 二级「国家」

| 一级分类 | 命中关键词 | 二级分组 |
|----------|------------|----------|
| **新闻频道** | News / 新闻 / Televida / TV27 / TV 24 / Telesur / TVN / Times Now / CCTN / UN Web | 印度、美国、拉美、其他 |
| **电影频道** | Movie / Film / Cinema / Zee Cinema / Movies Now / FILMBOX / Star Maa Movies / Sony / WWE | 印度、美国 |
| **儿童频道** | Kids / Teens / 儿童 / 卡通 / TVOKids / TV2 Kids / Polsat Viasat | 其他 |
| **娱乐频道** | TV Land / Comedy / Drama / NBC / ABC / Fox / BBC / True Crime / Vevo / 各国综合台 | 美国、英国、印度、匈牙利、波兰、法国/东欧、中东、北欧… |

### group-title 生成规则

```
一级分类 / 二级分类     例：卫视频道 / 浙江
一级分类（二级为"其他"时）  例：电影频道
```

播放器（IPTVX / UHF / iMPlayer / iPlayTV 等）会据此生成侧边分组栏。

### 分类优先级（防误判）

当频道名同时命中多个关键词时，按以下顺序定级，避免 CCTV-1 被误分进"地方台"：

```
央视  →  卫视  →  电影  →  少儿  →  地方台  →  移动（若有 cmcc 标记）
```

---

## 5. 中国移动源专项说明

### 为什么移动源要单独处理

中国移动 IPTV 源有 3 个特殊性：

1. **URL 含 `chinamobile.com` 等特征域名**，靠关键词可识别
2. **多为 IPv6 单播**（如 `2409:8087:…`、`[2409:…]`），GitHub Actions 默认 IPv4 环境直连会超时
3. **跨省基本不可用**，本省源才是有效源

### 收集阶段（`collect.py`）

每条移动源会打上 3 个标签，供下游消费：

| 字段 | 含义 | 示例 |
|------|------|------|
| `is_cmcc` | 是否移动源 | `true` |
| `cmcc_province` | 所属省份 | `"浙江"` |
| `is_ipv6` | 是否 IPv6 地址 | `true` |

### 测活阶段（`check.py`，补丁版）

- **IPv6 源不再 BLOCKED**：旧版把 `2409:8087` 写死在 `BLOCKED` 里会一刀切死所有移动源；补丁版改为 `is_ipv6_url()` 动态识别 → 标记 `skip=True`，跳过测活但**保留到输出**，不误判为死链
- **本省优先**：通过 `ip-api.com` 识别 runner 所在省，本省移动源响应时间 ×0.5（加权），排序时固定排最前
- **分层计时**：国内限额 `CHECK_CN_MAX`、国外限额 `CHECK_FOREIGN_MAX`，各自到限即停，互不影响

### 分组阶段（`group_m3u.py`，补丁版）

- 新增**「中国移动」一级分类**，插在「卫视频道」之后
- 移动源**只归入此分组**，不重复出现在卫视/地方台里
- 按省份细分（浙江/江苏/广东…），本省排最前
- 输出 `# cmcc-province="浙江"` 注释，本省优先带 `(本省优先)` 标记

> **重要提示**：补丁版 `check.py` / `group_m3u.py` 已在对话中交付（见第 9 节），但**尚未落盘到本仓库**。当前仓库内仍是旧版，因此「中国移动」独立分组、IPv6 动态 skip、本省优先加权**目前不会生效**。需要按第 9 节手动覆盖。

---

## 6. 配置项速查

### `check.py` 常量（文件顶部）

| 常量 | 默认值 | 说明 |
|------|--------|------|
| `CONCURRENCY` | `20` | 测活并发线程数 |
| `PER_TIMEOUT` | `(5, 10)` | (连接超时, 读取超时) 秒 |
| `MAX_DURATION` | `1200` | 整体测活上限（秒），新版建议改用分层变量 |
| `MAX_CHANNELS` | `150` | 国内/国外各保留条数 |
| `CACHE_TTL` | `86400` | 缓存有效期（秒，1 天） |
| `CACHE_FILE` | `cache.json` | 缓存文件 |
| `OUTPUT_OK` | `live_ok.m3u` | 输出清单 |

### `update.yml` 环境变量（覆盖 `check.py`）

| 变量 | 默认 | 作用 |
|------|------|------|
| `CHECK_CN_MAX` | `900` | 国内测活时限（秒） |
| `CHECK_FOREIGN_MAX` | `600` | 国外测活时限（秒） |
| `CACHE_TTL` | `86400` | 缓存 TTL |
| `MAX_WORKERS` | `40` | 并发（供 check.py 读取） |

### `update.yml` 触发与手动参数

- **定时**：`0 22,10 * * *`（UTC）＝ 北京时间每天 06:00 / 18:00
- **手动**（`workflow_dispatch`）：
  - `mode`：`full`（全量）／ `fast`（快速，可只跑国内）
  - `custom_url`：自定义 M3U 源 URL，留空用默认

---

## 7. 使用方式

### 一键部署

1. 把本仓库文件放到 `.github/workflows/update.yml` + `collect.py` + `check.py` + `group_m3u.py`
2. 推送至 GitHub 仓库
3. Actions 自动按北京时间 06:00 / 18:00 运行；也可在仓库 **Actions → 每日更新 IPTV 直播源 → Run workflow** 手动触发

### 本地调试

```bash
# 1. 收集
python collect.py

# 2. 测活（可选：设环境变量覆盖时限）
CHECK_CN_MAX=900 CHECK_FOREIGN_MAX=600 python check.py

# 3. 分组
python group_m3u.py

# 4. 校验输出
grep -c "^#EXTINF" live_ok.m3u        # 应有约 300 行
grep "group-title" live_ok.m3u | sort -u   # 查看分组
```

### 提交注意事项（GitHub 网页端）

- **不要**给 `actions/setup-python@v6` 加 `cache: 'no'`（v6 不认这个值，会报 `Caching for 'no' is not supported`）——**直接删掉 `cache` 那行即可**，默认即不缓存
- 若网页端提交报 `File could not be edited`，多半是 **main 分支保护**，请选择 **"Create a new branch for this commit and start a pull request"** 建新分支提 PR 合并
- 或用本地 Git 命令行推送

---

## 8. 常见问题排查

| 现象 | 原因 | 解决 |
|------|------|------|
| Actions 报 `Caching for 'no' is not supported` | `setup-python` 传了非法 cache 值 | 删除 `cache:` 整行 |
| 网页端 `File could not be edited` | main 分支保护 / 并发冲突 | 建新分支提 PR，或本地 CLI 推送 |
| `raw_channels.json` 不存在 / 频道池 <50 | jsDelivr CDN 临时失效 | 流程自动中止，不提交空清单；下一轮重试 |
| `live_ok.m3u` 只有几十条 | 大量源超时（含移动 IPv6 源在纯 IPv4 环境） | 属正常，缓存 TTL 内不重复探测；升级补丁版 check.py 可保留 IPv6 源为 skip |
| 国内源大量被判死 | 本地网络问题 | `check.py` 冒烟测试会暴露，注意日志 |
| 分组全是"其他" | `group-title` 未被重写 / 频道名无关键词命中 | 检查 `group_m3u.py` 的 `CN_CATEGORIES` 关键词是否覆盖该台名 |
| 同一频道重复出现 | 不同 URL 同名 | `check.py` 去重保留最快；`group_m3u.py` 不再二次去重（如需可加） |
| 移动源一条没分到"中国移动"组 | 当前为旧版 group_m3u.py | 按第 9 节覆盖补丁版 |

---

## 9. 已知现状与待落盘补丁

### 当前仓库文件版本（截至 2026-11-08）

| 文件 | 版本 | 状态 |
|------|------|------|
| `collect.py` | **新版** | ✅ 已含 `is_cmcc` / `is_ipv6` / `cmcc_province` 标签 |
| `check.py` | **旧版** | ⚠️ 无 IPv6 动态 skip、无本省优先、无分层计时（仍用 `MAX_DURATION=1200`） |
| `group_m3u.py` | **旧版** | ⚠️ 无「中国移动」独立分组，移动源混在卫视/地方台 |
| `update.yml` | **新版** | ✅ 已引用 `CHECK_CN_MAX` / `CHECK_FOREIGN_MAX`，但 check.py 暂不读取 |

### 待落盘的补丁（已在对话中交付）

以下补丁已在本次对话中生成，可直接下载覆盖仓库对应文件：

| 补丁文件 | 能力 | 交付物 |
|----------|------|--------|
| **`check.py`（补丁版）** | IPv6 动态 skip 兼容 ＋ 本省优先加权 ＋ 国内外分层计时 ＋ 完整 tvg 字段输出 ＋ cmcc 标记 | 对话中已交付，路径见下方说明 |
| **`group_m3u.py`（补丁版）** | 新增「中国移动」独立一级分类 ＋ cmcc-province 解析 ＋ 本省优先标记 ＋ 分类优先级防误判 ＋ 移动源去重 | 对话中已交付 |

> 覆盖方式：将对话中下载的补丁文件，重命名为 `check.py` / `group_m3u.py`，替换仓库内同名文件后提交即可。补丁版 `check.py` 能正确读取 `update.yml` 传入的 `CHECK_CN_MAX` / `CHECK_FOREIGN_MAX` 环境变量，两者需配套使用。

### 升级收益对照

| 能力 | 旧版 | 补丁版 |
|------|------|--------|
| 移动 IPv6 源 | 一刀切死（BLOCKED） | 标记 skip，保留到输出 |
| 本省优先 | 无 | 本省移动源加权 2×，排序最前 |
| 测活时限 | 单一 1200s | 国内 900s / 国外 600s 分层 |
| 移动源分组 | 混在卫视/地方台 | 独立「中国移动 / 省份」 |
| 输出字段 | 简略 | 完整 tvg-id / tvg-logo / cmcc 注释 |

---

## 10. 在播放器中使用

### 推荐播放器（Apple TV / iOS / macOS）

| 播放器 | 特点 | 价格 |
|--------|------|------|
| **IPTVX** | 原生大屏、EPG、M3U/Xtream、分组界面漂亮 | 免费 + 订阅 $28.99/年 |
| **UHF** | 苹果风、iCloud 同步、M3U/Emby/Jellyfin | 免费 + 终身 $49.99 |
| **iMPlayer** | 类 TiviMate 逻辑、EPG/回看 | 免费 + $24.99 高级 |
| **iPlayTV** | 电视网格、换台快、一次性买断 | $5.99 |
| **Smarters Player Lite** | 国区可搜、填 M3U 直用 | 免费 + 去广告 $1.99 |
| **VLC** | 纯测试，无 EPG/分组 | 免费 |

> TiviMate **没有** tvOS 版；"IPTV Smarters Pro" 在 App Store 实际名为 **Smarters Player Lite**，别下错仿冒。

### 导入步骤

1. 把 `live_ok.m3u` 传到 **iCloud 云盘**，或挂到 **GitHub Pages** 出一个直链
2. Apple TV / iOS 安装上述任一播放器
3. 添加来源选 **M3U 文件 / URL** → 粘贴链接
4. 播放器会自动读取 `group-title`，生成：
   ```
   央视频道 / 央视
   卫视频道 / 浙江
   卫视频道 / 广东
   中国移动 / 浙江   ← 补丁版生效后出现
   地方台 / 浙江
   电影频道
   少儿频道
   ─────────────
   新闻频道 / 印度
   电影频道 / 美国
   儿童频道 / 其他
   娱乐频道 / 美国
   ```

### 验证分组是否生效

```bash
# 看分组种类
grep -o 'group-title="[^"]*"' live_ok.m3u | sort -u

# 看国内/国外条数
echo "国内:"; grep -B1 "group-title=\"央视频道\|卫视频道\|地方台\|电影频道\|少儿频道\|中国移动" live_ok.m3u | grep -c "^#EXTINF"
echo "国外:"; grep -A0 "^# ===== 国外频道" -A9999 live_ok.m3u | grep -c "^#EXTINF"

# 看移动源标记
grep "cmcc-province" live_ok.m3u
```

---

## 免责声明

本仓库仅收集**公开可得**的 IPTV 播放地址，用于个人技术研究、播放器兼容性验证与内网合规使用。所有直播内容版权归对应电视台/运营商所有。请勿用于任何商业分发或侵犯版权的行为。因使用本仓库产生的任何法律责任由使用者自行承担。

---

_文档版本：2026-11-08 · 对应流水线 v3（collect 新版 + check/group 旧版 + update 新版；补丁版 check/group 待落盘）_
