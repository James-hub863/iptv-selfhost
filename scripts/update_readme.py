#!/usr/bin/env python3
"""
update_readme.py — 自动更新 README.md，写入最新直连地址与测活统计
由 GitHub Actions 在测活完成后调用
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

REPO = os.environ.get("GITHUB_REPOSITORY", "James-hub863/iptv-selfhost")
GITEE_USER = os.environ.get("GITEE_USER", "James-hub863")
GITEE_REPO = os.environ.get("GITEE_REPO", "iptv-selfhost")

README_PATH = Path("README.md")

def load_report() -> dict:
    """读取 report.json，若无则返回空"""
    if Path("report.json").exists():
        return json.loads(Path("report.json").read_text(encoding="utf-8"))
    return {}

def build_readme(report: dict) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = report.get("total", 0)
    alive = report.get("alive", 0)
    ok_channels = report.get("ok_channels", 0)
    duration = report.get("duration", 0)

    # 计算存活率
    rate = f"{(alive / total * 100):.1f}%" if total > 0 else "N/A"

    return f"""# 📺 IPTV 直播源自托管 (iptv-selfhost)

> 全自动收集 · 并发测活 · 去重择优 · 多语言 · 国内直连

---

## 🚀 一键订阅（国内极速 · 推荐）

**APTV / PotPlayer / VLC / Kodi 等播放器直接添加以下地址：**
