#!/usr/bin/env python3
"""
微信公众号文章抓取 —— 本地版（调用本机 Chrome）
在你的 Mac 上运行:
  pip install playwright beautifulsoup4 lxml
  python3 -m playwright install chrome
  python3 wechat_scraper_local.py <url> [output.md]
"""

import sys
import re
import asyncio
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


TARGET_URL = sys.argv[1] if len(sys.argv) > 1 else "https://mp.weixin.qq.com/s/XbjL_BZxNkKt41qiuY5Jow"
OUTPUT = sys.argv[2] if len(sys.argv) > 2 else "wechat_article.md"


def parse_article(html: str, url: str) -> str:
    soup = BeautifulSoup(html, "lxml")

    # ── 元数据 ──
    def text(sel_id=None, sel_class=None, tag="*"):
        el = (soup.find(id=sel_id) if sel_id else None) or \
             (soup.find(class_=re.compile(sel_class)) if sel_class else None)
        return el.get_text(strip=True) if el else ""

    title = text("activity-name") or soup.title.string or "未知标题"
    account = text("js_name") or text(sel_class=r"account_nickname")
    author = text("js_author_name") or text(sel_class=r"rich_media_meta_primary")
    pub_time = text("publish_time")

    # ── 正文 ──
    body = soup.find(id="js_content") or soup.find(class_=re.compile(r"rich_media_content"))
    blocks = []
    if body:
        for el in body.descendants:
            if el.name == "img":
                src = el.get("data-src") or el.get("src") or ""
                alt = el.get("alt") or el.get("data-desc") or ""
                if src:
                    blocks.append(("image", src, alt))
            elif el.name in ("p", "h2", "h3", "h4", "section"):
                if el.parent and el.parent.name in ("p",):
                    continue
                t = el.get_text(" ", strip=True)
                if t:
                    kind = "heading" if el.name in ("h2", "h3", "h4") else "text"
                    blocks.append((kind, t, ""))

    # 去相邻重复
    seen, deduped = None, []
    for b in blocks:
        key = b[1]
        if key != seen:
            deduped.append(b)
            seen = key

    # ── 生成 Markdown ──
    lines = [
        f"# {title}\n",
        f"> **公众号**: {account}  ",
    ]
    if author:
        lines.append(f"> **作者**: {author}  ")
    if pub_time:
        lines.append(f"> **发布时间**: {pub_time}  ")
    lines += [
        f"> **原文**: {url}  ",
        f"> **抓取时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
        "---\n",
    ]

    img_n = 1
    for kind, val, extra in deduped:
        if kind == "image":
            caption = extra or f"图{img_n}"
            lines.append(f"![{caption}]({val})\n")
            img_n += 1
        elif kind == "heading":
            lines.append(f"## {val}\n")
        else:
            lines.append(f"{val}\n")

    return "\n".join(lines)


async def scrape():
    async with async_playwright() as p:
        print("启动本地 Chrome...")
        browser = await p.chromium.launch(
            channel="chrome",       # 使用本机已安装的 Google Chrome
            headless=True,          # 改为 False 可看到浏览器窗口
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
        )
        page = await context.new_page()

        print(f"打开: {TARGET_URL}")
        await page.goto(TARGET_URL, wait_until="networkidle", timeout=30000)

        # 等待正文加载
        try:
            await page.wait_for_selector("#js_content", timeout=10000)
        except Exception:
            print("警告: 未检测到 #js_content，继续解析现有内容")

        html = await page.content()
        await browser.close()

    print("解析内容...")
    md = parse_article(html, TARGET_URL)

    out = Path(OUTPUT)
    out.write_text(md, encoding="utf-8")

    lines = md.splitlines()
    imgs = sum(1 for l in lines if l.startswith("!["))
    texts = sum(1 for l in lines if l and not l.startswith(("#", ">", "!", "-", "─")))
    print(f"完成！段落: {texts}  图片: {imgs}")
    print(f"已保存 → {out.resolve()}")

    # 预览前 5 行
    print("\n── 预览 ──")
    print("\n".join(lines[:8]))


if __name__ == "__main__":
    asyncio.run(scrape())
