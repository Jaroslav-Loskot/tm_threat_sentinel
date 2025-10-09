import json
from src.core.crawler_manager import crawl_urls_playwright
from src.utils.file_utils import load_json, save_json
from src.utils.path_utils import get_data_path

async def run_urls_to_crawled(urls_path: str, headless=True):
    urls = load_json(urls_path)
    results = await crawl_urls_playwright(urls, headless=headless)
    out_path = get_data_path("threat-intelligence_results.json")
    save_json(results, out_path)
    print(f"💾 Saved {len(results)} crawl results → {out_path}")
    return out_path
