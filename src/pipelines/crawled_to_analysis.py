import json
from pathlib import Path
from tqdm import tqdm

from src.core.analyzer_manager import analyze_article
from src.utils.file_utils import load_json, save_json
from src.utils.path_utils import get_data_path


def run_crawled_to_analysis(input_path: str | Path, model_name: str = "claude") -> Path:
    """
    Read crawled article data and analyze each entry using Claude/Nova.
    Displays a progress bar and saves structured results.
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"❌ Input file not found: {input_path}")

    # Load crawled articles
    articles = load_json(input_path)
    print(f"🧩 Loaded {len(articles)} crawled articles for LLM analysis")

    analyses = []
    errors = 0

    # Progress bar
    for article in tqdm(articles, desc="🧠 Analyzing with LLM", unit="doc"):
        url = article.get("url")
        text = article.get("content", "")

        if not text.strip():
            tqdm.write(f"⚠️ Skipping empty content: {url}")
            continue

        try:
            result = analyze_article(url, text, model_name)
            analyses.append(result)
            tqdm.write(f"✅ {url[:80]}")
        except Exception as e:
            errors += 1
            tqdm.write(f"❌ {url[:80]} → {e}")
            analyses.append({"url": url, "error": str(e)})

    # Save results
    out_path = get_data_path("threat-intelligence_analysis.json")
    save_json(analyses, out_path)

    print(f"\n💾 Saved {len(analyses)} analyses → {out_path}")
    if errors:
        print(f"⚠️ {errors} analyses failed (check log for details)")

    return out_path
