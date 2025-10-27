from pathlib import Path
from tqdm import tqdm
from src.services.analyzer_manager import analyze_article
from src.utils.file_utils import load_json, save_json
from src.utils.path_utils import get_data_path
from src.pipelines.base_pipeline import BasePipeline


class CrawledToAnalysisPipeline(BasePipeline):
    name = "Crawled → Analysis"

    def __init__(self, input_path: str | Path, model_name: str = "claude"):
        super().__init__(input_path=input_path, model_name=model_name)
        self.input_path = Path(input_path)
        self.model_name = model_name

    async def execute(self) -> Path:
        if not self.input_path.exists():
            raise FileNotFoundError(f"❌ Input file not found: {self.input_path}")

        articles = load_json(self.input_path)
        print(f"🧩 Loaded {len(articles)} crawled articles for LLM analysis")

        analyses = []
        errors = 0
        for article in tqdm(articles, desc="🧠 Analyzing with LLM", unit="doc"):
            url = article.get("url")
            text = article.get("content", "")
            if not text.strip():
                continue
            try:
                result = analyze_article(url, text)
                analyses.append(result)
            except Exception as e:
                errors += 1
                analyses.append({"url": url, "error": str(e)})

        out_path = get_data_path("threat-intelligence_analysis.json")
        save_json(analyses, out_path)
        return out_path
