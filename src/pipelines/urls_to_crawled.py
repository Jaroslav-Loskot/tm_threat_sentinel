from src.services.crawler_manager import crawl_urls_playwright
from src.utils.file_utils import load_json, save_json
from src.utils.path_utils import get_data_path
from src.pipelines.base_pipeline import BasePipeline


class UrlsToCrawledPipeline(BasePipeline):
    name = "URLs → Crawled"

    def __init__(self, urls_path: str, headless: bool = True):
        super().__init__(urls_path=urls_path, headless=headless)
        self.urls_path = urls_path
        self.headless = headless

    async def execute(self):
        urls = load_json(self.urls_path)
        results = await crawl_urls_playwright(urls, headless=self.headless)
        out_path = get_data_path("threat-intelligence_results.json")
        save_json(results, out_path)
        return str(out_path)
