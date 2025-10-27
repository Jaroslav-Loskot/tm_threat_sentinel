import asyncio
from typing import List, Dict
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from tqdm.asyncio import tqdm_asyncio


async def crawl_urls_playwright(urls: List[str], headless: bool = True) -> List[Dict]:
    """
    Crawl URLs using Playwright (headless or headful).
    Displays an async progress bar and returns a list of crawl results.
    """
    results: List[Dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, slow_mo=100)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        async for url in tqdm_asyncio(urls, desc="🌐 Crawling pages", unit="url"):
            try:
                await page.goto(url, timeout=25000)
                await page.wait_for_load_state("domcontentloaded")

                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")

                # Pick the most relevant main content
                main = soup.find("main") or soup.find("article") or soup.body
                text = main.get_text("\n", strip=True) if main else ""
                text = "\n".join(line for line in text.splitlines() if line.strip())

                results.append({"url": url, "content": text, "length": len(text)})
                tqdm_asyncio.write(f"✅ {url[:80]} ({len(text)} chars)")

            except Exception as e:
                tqdm_asyncio.write(f"❌ Failed {url[:80]} → {e}")
                results.append({"url": url, "error": str(e)})

        await browser.close()

    tqdm_asyncio.write(f"\n💾 Finished crawling {len(results)} pages")
    return results