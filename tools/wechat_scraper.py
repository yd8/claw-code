#!/usr/bin/env python3
"""
微信公众号文章抓取工具
用法: python3 wechat_scraper.py <url> [output_file]
依赖: pip install requests beautifulsoup4 lxml
"""

import sys
import re
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin


def fetch_article(url: str) -> BeautifulSoup:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://mp.weixin.qq.com/",
    }
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return BeautifulSoup(resp.text, "lxml")


def extract_meta(soup: BeautifulSoup) -> dict:
    meta = {}

    # 标题
    title_tag = soup.find("h1", id="activity-name") or soup.find(
        "h1", class_=re.compile(r"title")
    )
    meta["title"] = title_tag.get_text(strip=True) if title_tag else "未知标题"

    # 公众号名称
    account_tag = soup.find("a", id="js_name") or soup.find(
        class_=re.compile(r"account_nickname|rich_media_meta_nickname")
    )
    meta["account"] = account_tag.get_text(strip=True) if account_tag else "未知公众号"

    # 发布时间
    time_tag = soup.find("em", id="publish_time") or soup.find(
        id=re.compile(r"publish_time|createTime")
    )
    if time_tag:
        meta["publish_time"] = time_tag.get_text(strip=True)
    else:
        # 从 JS 变量中提取
        script_text = soup.get_text()
        m = re.search(r'"publish_time"\s*:\s*"([^"]+)"', soup.decode())
        meta["publish_time"] = m.group(1) if m else ""

    # 作者
    author_tag = soup.find(id=re.compile(r"js_author_name|author")) or soup.find(
        class_=re.compile(r"rich_media_meta_primary")
    )
    meta["author"] = author_tag.get_text(strip=True) if author_tag else ""

    return meta


def extract_content(soup: BeautifulSoup) -> list[dict]:
    """提取正文，返回段落列表，每段包含 type 和 content"""
    content_div = soup.find(id="js_content") or soup.find(
        class_=re.compile(r"rich_media_content")
    )
    if not content_div:
        return [{"type": "text", "content": "（未找到正文区域）"}]

    blocks = []
    for el in content_div.descendants:
        if el.name == "img":
            src = el.get("data-src") or el.get("src") or ""
            alt = el.get("alt") or el.get("data-desc") or ""
            if src:
                blocks.append({"type": "image", "src": src, "alt": alt})

        elif el.name in ("p", "h1", "h2", "h3", "h4", "section"):
            # 避免重复处理嵌套
            if el.parent and el.parent.name in ("p", "h1", "h2", "h3"):
                continue
            text = el.get_text(separator=" ", strip=True)
            if text:
                tag_type = "heading" if el.name in ("h1", "h2", "h3", "h4") else "text"
                blocks.append({"type": tag_type, "content": text})

    # 去重相邻重复文本
    deduped = []
    seen_last = None
    for b in blocks:
        key = b.get("content") or b.get("src")
        if key and key == seen_last:
            continue
        deduped.append(b)
        seen_last = key

    return deduped


def to_markdown(meta: dict, blocks: list[dict], url: str) -> str:
    lines = []
    lines.append(f"# {meta['title']}\n")
    lines.append(f"> **公众号**: {meta['account']}  ")
    if meta.get("author"):
        lines.append(f"> **作者**: {meta['author']}  ")
    if meta.get("publish_time"):
        lines.append(f"> **发布时间**: {meta['publish_time']}  ")
    lines.append(f"> **原文链接**: {url}  ")
    lines.append(f"> **抓取时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append("---\n")

    img_index = 1
    for b in blocks:
        if b["type"] == "image":
            caption = b["alt"] if b["alt"] else f"图{img_index}"
            lines.append(f"![{caption}]({b['src']})\n")
            img_index += 1
        elif b["type"] == "heading":
            lines.append(f"## {b['content']}\n")
        else:
            lines.append(f"{b['content']}\n")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("用法: python3 wechat_scraper.py <微信文章URL> [输出文件名]")
        sys.exit(1)

    url = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else "wechat_article.md"

    print(f"正在抓取: {url}")
    try:
        soup = fetch_article(url)
    except requests.HTTPError as e:
        print(f"HTTP 错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"请求失败: {e}")
        sys.exit(1)

    print("解析文章元数据...")
    meta = extract_meta(soup)
    print(f"  标题: {meta['title']}")
    print(f"  公众号: {meta['account']}")
    if meta.get("publish_time"):
        print(f"  时间: {meta['publish_time']}")

    print("提取正文内容...")
    blocks = extract_content(soup)
    text_count = sum(1 for b in blocks if b["type"] == "text")
    img_count = sum(1 for b in blocks if b["type"] == "image")
    print(f"  文字段落: {text_count}, 图片: {img_count}")

    md = to_markdown(meta, blocks, url)
    Path(output).write_text(md, encoding="utf-8")
    print(f"\n已保存到: {output}")
    print(f"文件大小: {len(md)} 字符")


if __name__ == "__main__":
    main()
