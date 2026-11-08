# IPTV 测活 + CDN 镜像源自动生成方案

> 目标：解决 `raw.githubusercontent.com` 证书/直连不稳定导致的 iOS 播放器 `-1200` 报错，
> 自动产出一份**国内可直连、仅含存活源**的 m3u，供播放器直接订阅。

---

## 一、整体思路

```
raw.githubusercontent.com (原始 m3u，国内不稳定)
        │
        ▼  GitHub Actions 定时拉取（服务端网络稳定，不受你手机证书影响）
   ┌────────────┐
   │  测活脚本   │  逐条探活 → 只留存活源
   └────────────┘
        │
        ▼  自动 commit 到仓库
   output/live_ok_tested.m3u   ←  这份走 CDN，国内直连
        │
        ▼  播放器订阅这个 CDN 地址
   iOS 播放器（不再直连 raw 域名，不再触发证书错误）
```

**关键点**：把「不稳定的 raw 域名」和「需要证书校验的直连」转移到
GitHub 服务端去完成，你手机只订阅最终那份**走 CDN 的镜像 m3u**。

---

## 二、文件说明

| 文件 | 作用 |
|---|---|
| `check_live.py` | 核心脚本：拉取 m3u → 解析 → CDN 镜像 → 并发探活 → 输出存活源 |
| `.github/workflows/auto-check.yml` | Actions 工作流：定时自动跑脚本并提交结果 |
| `output/live_ok_tested.m3u` | **最终产物**：仅存活源，可直接导入播放器 |
| `output/live_ok_mirror.txt` | 每个源的原始/镜像 URL 对照表（排障用） |
| `output/report.json` | 逐条探活报告（状态码、耗时、错误原因） |

---

## 三、部署步骤（5 分钟）

### 第 1 步：新建你自己的公开仓库
比如叫 `iptv-mirror`。把以下文件放进去：
```
iptv-mirror/
├── check_live.py
├── .github/
│   └── workflows/
│       └── auto-check.yml
└── output/          （空目录，放一个 .gitkeep）
```

### 第 2 步：开启 Actions
仓库 → **Actions** 标签 → 启用 workflow。
若仓库是**私有**的：Settings → Actions → General → Workflow permissions → 选 **Read and write permissions**。

### 第 3 步：手动触发一次验证
Actions → 选 `IPTV 测活 & CDN 镜像生成` → **Run workflow**。
约 1~3 分钟后，`output/` 下会出现 `live_ok_tested.m3u`。

### 第 4 步：拿到「国内可直连」的订阅地址
在你自己的仓库里，用 **jsDelivr CDN** 地址（国内友好）：

```
https://cdn.jsdelivr.net/gh/你的用户名/iptv-mirror@main/output/live_ok_tested.m3u
```

> 例：`https://cdn.jsdelivr.net/gh/Tom/iptv-mirror@main/output/live_ok_tested.m3u`
> jsDelivr 的证书由正规 CA 签发，iOS 完全信任，不会再报 `-1200`。

---

## 四、iOS 播放器里怎么填

1. 打开播放器 → 添加订阅配置
2. **配置链接** 填上面那条 `cdn.jsdelivr.net` 地址
3. 保存 —— 此时连接的是正规 CDN，证书有效，不会弹证书错误

---

## 五、CDN 镜像规则说明（`check_live.py` 里的 `CDN_MIRRORS`）

脚本内置两条镜像，自动选首个返回 200 的：

| 镜像 | 说明 | 国内可达性 |
|---|---|---|
| jsDelivr | `raw.../USER/REPO/refs/heads/BRANCH/FILE` → `cdn.jsdelivr.net/gh/USER/REPO@BRANCH/FILE` | ✅ 优 |
| ghproxy | 前置反代 `https://ghproxy.net/<原地址>` | ⚠️ 备用，偶发限流 |

想加新镜像，在 `CDN_MIRRORS` 里追加一条 lambda 即可。

---

## 六、关键配置项（`check_live.py` 顶部）

```python
TIMEOUT = 8          # 单源探测超时（秒），源多可加大
MAX_WORKERS = 20     # 并发探测数
```

`auto-check.yml` 里的调度时间（`cron`）默认 UTC，可按需改：
```yaml
- cron: "0 6,18 * * *"   # 每天 06:00 & 18:00 UTC
```

---

## 七、排障清单

| 现象 | 排查 |
|---|---|
| Actions 失败：`git push` 无权限 | 私有仓库需开 write 权限（见第 2 步） |
| 拉取 m3u 失败 | 原始仓库/分支是否存在；`live_ok.m3u` 路径是否正确 |
| 存活源为 0 | 源本身是组播/rtp → 脚本会保留（`non-http(skip)`），看 report.json |
| jsDelivr 打不开 | 确认仓库是**公开**的（jsDelivr 不支持私有仓库） |
| 播放器仍报证书错误 | 确认填的是 `cdn.jsdelivr.net` 而不是 `raw.githubusercontent.com` |

---

## 八、安全提醒

- 本方案只解决「**传输层**」的证书/可达性问题，**不验证直播源内容合法性**。
- m3u 里若混有未知中转服务器、http 明文源，仍有隐私与注入风险。
- **不要**为了能播在播放器里关闭 ATS / 忽略证书校验，等于裸奔。
- 脚本运行在服务端，你手机只消费最终 CDN 产物，最小化暴露面。

---

## 九、本地快速验证（可选）

```bash
# 安装依赖（仅需标准库，无第三方依赖）
python check_live.py --raw "https://raw.githubusercontent.com/James-hub863/iptv-selfhost/refs/heads/main/live_ok.m3u" --outdir output
ls output/
# live_ok_tested.m3u  live_ok_mirror.txt  report.json
```
