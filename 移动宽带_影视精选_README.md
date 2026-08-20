# 移动宽带 · 影视精选 M3U 使用说明

## 📺 频道分组概览

| 分组 | 频道示例 | 来源 |
|---|---|---|
| 🎬 电影频道 | CCTV-6、CHC动作/家庭/影迷、NewTV精品/明星/惊悚、电影1~3HD、邵氏、欧美影院 | 江苏/浙江/江西移动 |
| 📺 电视剧频道 | CCTV-8、都市剧场、影视剧频道、家庭剧场、City都市、欢笑剧场、欢笑剧场4K | 江苏/湖北/NewTV |
| 🎭 综合卫视 | 重庆、黑龙江、上海纪实、北京冬奥纪实、江苏、浙江、东方、湖南 | 移动OTT |
| 🎪 4K超高清 | CCTV-4K、纯享4K、江西4K | 江西移动 |
| 🎮 游戏直播 | 战旗TV×6、战旗:三国 | 战旗CDN |
| 🌐 聚合订阅 | bjzhou移动源、APTV全国移动 | GitHub/CDN |

> 共 40+ 条条目，每条都带 **tvg-logo 台标 + group-title 分组**，播放器自动归类。

## ⚙️ 使用方法

### VLC（电脑端）
媒体 → 打开文件 → 选 `移动宽带_影视精选.m3u`

### TiviMate / IPTV Smarters（Android TV）
添加播放列表 → 本地文件 → 选本 m3u

### APTV / 天光云影（推荐移动用户）
直接填订阅链接（下面推荐）

### 一键订阅链接（推荐）
- **APTV 全国移动通用**：`https://itv.aptv.app/china-iptv/jsyd.m3u`
- **bjzhou 移动影视聚合**：`https://testingcf.jsdelivr.net/gh/bjzhou/iptv-collector@output/iptv-cm.m3u`
- **江苏移动**：`https://itv.aptv.app/china-iptv/jsyd.m3u`
- **浙江移动**：`https://itv.aptv.app/china-iptv/zjyd.m3u`
- **上海移动**：`https://itv.aptv.app/china-iptv/shyd.m3u`
- **河南移动**：Gitee `https://gitee.com/shadow-s/iptv/raw/main/hnydiptv.m3u8`
- **湖北移动（2026-07 整理版）**：恩山论坛搜索"2026湖北移动百视通"

## ⚠️ 关键提醒

### 1. 仅限移动宽带
这些源做了 **IP 白名单**，只有移动宽带能播。电信/联通打开会卡顿或 403。

### 2. IPv6 源更稳定
带 `[2409:...]` 的 IPv6 地址在移动 IPv6 网络下通常比 IPv4 更快、更少被限速。
**开启方法**：光猫/路由器开启 IPv6 PD 前缀分配，设备拿到 `2409:` 开头的地址即可。

### 3. 影视源域名速查
| 省份/用途 | 域名 |
|---|---|
| 江苏移动 OTT | `ott.js.chinamobile.com` / `ott.mobaibox.com` |
| 浙江移动 | `hwltc.tv.cdn.zj.chinamobile.com` |
| 江西移动 | `hwrr.jx.chinamobile.com` |
| 河南移动 | `iptv.cdn.ha.chinamobile.com` / `charging-rh.ha.chinamobile.com` |
| 湖北移动 | `huaweicdn.hb.chinamobile.com` / `ztecdn.hb.chinamobile.com` |
| 陕西/宁夏移动 | `dbiptv.sn.chinamobile.com` |
| 北京移动(组播) | `iptvrr.bj.chinamobile.com:6060` |
| 上海移动(内网) | `iptvrr.sh.chinamobile.com:6060` |
| 黑龙江移动 | `ottrrs.hl.chinamobile.com` |
| 全国 iTV 平台 | `gslbserv.itv.cmvideo.cn`（302跳转） |

### 4. 组播源需 UDPXY 转换
北京/上海移动内网源格式是 `rtp://239.x.x.x:800x` 或 `http://...:6060/cms001/...`，
其中 `rtp://` 组播需要路由器开 UDPXY 转单播才能播（参考前面会话的组播转单播教程）。

### 5. 自动维护
把这份 m3u 接入之前搭的 GitHub Actions 测活流水线：
- `sources.txt` 填上面"聚合订阅"两条链接
- `fixed.txt` 锁死你本地验证可用的 CHC / NewTV / 欢笑剧场 等高质量源
- 每天自动跑，死链自动剔除

## 📋 EPG 节目单（可选）
播放器里填 EPG 地址可显示节目预告：
- `http://epg.51zmt.top:8000/e.xml.gz`
- `https://epg.112114.xyz/pp.xml`
- `https://epg.pw/xmltv/epg_CN.xml`

## ⚖️ 声明
仅收集公开资源，个人观看使用，请勿二次分发与商用。
移动宽带影视资源来源易变，建议定期更新订阅链接。
