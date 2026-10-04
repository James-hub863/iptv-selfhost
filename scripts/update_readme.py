#!/usr/bin/env python3
"""更新 README 中的直连地址"""
import os

def main():
    gitee_user = os.getenv("GITEE_USER", "James-hub863")
    gitee_repo = os.getenv("GITEE_REPO", "iptv-selfhost")
    
    github_url = f"https://github.com/{gitee_user}/{gitee_repo}/raw/main/live_ok.m3u"
    gitee_url_ok = f"https://gitee.com/{gitee_user}/{gitee_repo}/raw/master/live_ok.m3u"
    gitee_url_all = f"https://gitee.com/{gitee_user}/{gitee_repo}/raw/master/live_all.m3u"
    
    content = [
        "# 📺 IPTV 直播源自托管",
        "",
        "自动测活与聚合，每日更新。",
        "",
        "## 直连地址（推荐 Gitee 国内极速）",
        f"- GitHub（存活版）：{github_url}",
        f"- Gitee（存活版）：{gitee_url_ok}",
        f"- Gitee（全量版）：{gitee_url_all}",
        "",
        "数据由 GitHub Actions 自动生成，无需人工干预。"
    ]
    
    with open("README.md", "w", encoding="utf-8") as f:
        f.write("\n".join(content))
    print("✅ README 更新完成")

if __name__ == "__main__":
    main()
