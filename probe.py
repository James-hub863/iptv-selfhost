import asyncio
import aiohttp
import re
import os

# 定义输入和输出文件名
INPUT_M3U = "input.m3u"
OUTPUT_M3U = "live.m3u"

# 获取仓库中所有 m3u 文件并合并为一个输入源（排除最终输出的 live.m3u）
def merge_m3u_files():
    all_lines = []
    for file in os.listdir('.'):
        if file.endswith('.m3u') and file != OUTPUT_M3U:
            with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                all_lines.extend(f.readlines())
    with open(INPUT_M3U, 'w', encoding='utf-8') as f:
        f.writelines(all_lines)

async def check_stream(session, name, url):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8), ssl=False) as response:
            if response.status == 200:
                return (name, url)
    except:
        return None

async def main():
    merge_m3u_files()
    
    with open(INPUT_M3U, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    tasks = []
    valid_channels = []
    
    async with aiohttp.ClientSession(headers=headers) as session:
        for i in range(len(lines)):
            if lines[i].startswith('#EXTINF:'):
                name = lines[i].split(',', 1)[-1].strip()
                if i + 1 < len(lines) and not lines[i+1].startswith('#'):
                    url = lines[i+1].strip()
                    tasks.append(check_stream(session, name, url))
        
        results = await asyncio.gather(*tasks)
        valid_channels = [r for r in results if r is not None]

    with open(OUTPUT_M3U, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n')
        for name, url in valid_channels:
            f.write(f'#EXTINF:-1,{name}\n{url}\n')
            
    print(f"测活完成，共筛选出 {len(valid_channels)} 个有效源，已保存至 {OUTPUT_M3U}")

if __name__ == '__main__':
    asyncio.run(main())
