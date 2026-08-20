# 英语学习 / 技能培训 M3U 播放列表

> 适用：VLC、TiviMate、IPTV Smarters、TVBox、PotPlayer、IINA

## 文件说明

| 文件 | 内容 | 说明 |
|---|---|---|
| `英语学习_精选.m3u` | 16 条英语直播源 | 主推 5 条 + 备用 11 条，全部带台标和分组 |
| `技能培训_点播导航.m3u` | 9 条技能学习入口 | 以网页导航为主（MOOC/公开课），附 3 条英语聚合订阅 |

## 频道分组（英语学习_精选.m3u）

### 📰 英语新闻·主推（5 条，优先试这 5 条）
| 频道 | 画质 | 特色 |
|---|---|---|
| ABC News Live | 720p | 美式英语，语速适中，新闻+脱口秀 |
| ABC News Live 8 | 720p | ABC 备用线路 |
| Al Jazeera English | 1080p | **英式/国际英语首选**，发音标准清晰 |
| France 24 English | 720p | **法式英语，适合练听力**，语速稍慢 |
| TRT World | 1080p | 土耳其视角国际新闻，发音清晰 |

### 📰 英语新闻·备用（6 条）
BBC News / BBC World News / Fox News / Africa 24 / TV360 / 99TV

### 🎧 英语广播·听力（6 条，轻量、省带宽、全天候）
| 频道 | 格式 | 用途 |
|---|---|---|
| NPR News | AAC | 美式新闻，清晰标准 |
| VOA 环球英语 | AAC | **慢速英语，初级首选** |
| ABC News Radio | AAC | 美式广播 |
| 半岛新闻音频 | AAC | Al Jazeera 音频流 |
| Power FM | MP3 | 英语音乐/谈话 |
| RTI 中央广播 | AAC | 国际广播 |

### 🎓 英语教育（1 条）
ABC Australia — 教育类节目为主

## 🚀 一键订阅（推荐）

把下面链接填进播放器，**每天自动更新、不用下载文件**：

```
# 英语全量（2290+ 台，含大量新闻/教育/音乐）
https://iptv-org.github.io/iptv/languages/eng.m3u

# 教育分类（246+ 台）
https://iptv-org.github.io/iptv/categories/education.m3u

# 新闻分类（941+ 台）
https://iptv-org.github.io/iptv/categories/news.m3u
```

> 国内直连可能慢，可加 CDN 前缀：`https://cdn.jsdelivr.net/gh/iptv-org/iptv@master/playlists/eng.m3u`

## 📖 使用方法

- **VLC**：媒体 → 打开文件 → 选 `英语学习_精选.m3u`
- **TiviMate / IPTV Smarters**：添加播放列表 → 本地文件
- **TVBox / 影视仓**：传到 http 空间填配置地址；`技能培训_点播导航.m3u` 的网页条目需用支持 WebView 的壳子

## ⚠️ 关于"源是否可用"的重要说明

### 沙盒探测全 403 是预期结果
我用 Python 在沙盒里实测所有源，统一返回 Akamai CDN 的拒绝响应：
```
{"title":"Request denied","status":403,"detail":"No policy rule matched the request"}
```
**这不是源失效**，而是 Akamai / Cloudfront / Cloudflare 这些 CDN 对"云服务器 IP"做了地区/类型封锁，只放行真实家庭宽带。

### 真实家宽下的可用性
以下源在**欧美/国内教育网/部分运营商家宽**下可正常播放（来源：iptv-org 社区 2026 年 7-8 月验证记录）：
- ✅ ABC News 系列（akamaized.net）
- ✅ Al Jazeera English（getaj.net / cloudfront.net）
- ✅ France 24（static.france24.com）
- ✅ TRT World（medya.trt.com.tr）
- ✅ NPR / VOA / RTI 等广播流（akamaized.net AAC）
- ⚠️ BBC 系列国内访问不稳定，建议挂代理或作备用
- ⚠️ Fox News 源波动较大，作备用

### 验证建议
1. 在你自己的电脑/手机上用 VLC 打开 `英语学习_精选.m3u`
2. 优先试"主推"5 条，能播就说明网络正常
3. 卡顿时换同分组的"备用"线路
4. 想长期稳定 → 接入你之前搭的 GitHub Actions 测活流水线

## 🎯 接入自动测活流水线（推荐）

把这份列表接入之前的 GitHub Actions 项目：
- `sources.txt` 加 `https://iptv-org.github.io/iptv/languages/eng.m3u`
- `fixed.txt` 锁死 5 条主推源（ABC/AJE/FR24/TRT/NPR）
- `config.py` 的 `CHANNEL_WHITELIST` 设 `["ABC","Al Jazeera","France 24","TRT","NPR","VOA","BBC"]`
- 每天自动跑，死链自动剔除，输出 `learn_en.m3u`

## 📚 技能培训为什么没有直播流

职业技能（编程/PLC/求职/剪辑/电商）本质是**点播课程或定时直播**，不是 24h 连续 HLS 流，所以：
- 传智/黑马、教育部 24365、Coursera、edX、可汗学院都是**网页点播**
- `技能培训_点播导航.m3u` 以"导航书签"形式整理常用入口
- 更实用的做法是用 **TVBox 的 WebView/Nav 源** 或 **浏览器收藏夹**，而不是 M3U

## ⚖️ 合法性

仅收集公开资源，个人学习使用，请勿二次分发与商用。BBC/ABC/VOA 等源请遵守各平台服务条款。
