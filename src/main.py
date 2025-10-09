import asyncio
from src.pipelines.slack_to_urls import run_slack_to_urls
from src.pipelines.urls_to_crawled import run_urls_to_crawled
from src.pipelines.crawled_to_analysis import run_crawled_to_analysis

async def main():
    print("🚀 Starting Threat Intelligence Pipeline")

    # Step 1: Slack → URLs
    urls_path = await run_slack_to_urls("threat-intelligence", limit=5)

    # Step 2: URLs → Crawled HTML/Text
    crawl_path = await run_urls_to_crawled(urls_path, headless=True)

    # Step 3: Crawled → LLM Analysis
    analysis_path = run_crawled_to_analysis(str(crawl_path), model_name="claude")

    print(f"\n✅ Full pipeline complete → {analysis_path}")

if __name__ == "__main__":
    asyncio.run(main())
