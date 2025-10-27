# 🧠 ThreatMark Threat Intelligence Pipeline

> **Automated Slack → Crawl → LLM Analysis → Slack Intelligence System**

This project continuously monitors Slack intelligence channels, extracts URLs, crawls and analyzes their content using LLMs (Claude/Nova on Amazon Bedrock), and posts summarized threat insights back to Slack — complete with emoji indicators, relevance scores, and DM alerts for critical events.

---

## ⚙️ Features

✅ **Slack Integration**

* Fetches URLs from Slack channels and threads
* Posts AI-generated analysis blocks back to Slack
* Auto-reactions for severity (🟢🟠🔴)
* Optional DM alerts for high-severity incidents

🧩 **Three Modular Pipelines**

1. **Slack → URLs**: Extract new URLs from Slack messages
2. **URLs → Crawled**: Fetch article content via Playwright or Crawl4AI
3. **Crawled → Analysis**: Analyze with Claude/Nova + infrastructure context

🤖 **LLM Analysis via Bedrock + LiteLLM**

* Uses AWS Bedrock models (`Claude`, `Nova Lite`, `Titan Embedding`)
* Unified adapters for both LiteLLM and Bedrock-native calls

📊 **Infrastructure-Aware Threat Reasoning**

* Auto-includes ThreatMark’s infrastructure inventory for context
* Categorizes SaaS, databases, containers, etc. for accurate severity

🧠 **Composable Orchestration**

* Run entire end-to-end pipeline or individual stages
* Logs structured results in `/data/slack_channel_export`
* Safe async orchestration with consistent timing & error handling

---

## 🏧 Project Structure

```bash
src/
├── adapters/
│   ├── litellm_connector.py         # Local LiteLLM proxy client
│   ├── llm_connector.py             # Bedrock + Titan unified interface
│
├── converters/
│   ├── infrastructure_converter.py  # CSV/XLSX → categorized JSON + text context
│
├── pipelines/
│   ├── base_pipeline.py             # Abstract async pipeline base class
│   ├── slack_to_urls.py             # Stage 1 – extract URLs from Slack
│   ├── urls_to_crawled.py           # Stage 2 – crawl URLs
│   ├── crawled_to_analysis.py       # Stage 3 – analyze with LLM
│   ├── channel_monitor.py           # Live Slack watcher (continuous)
│   ├── threat_intel_pipeline.py     # Unified orchestrator
│
├── services/
│   ├── slack_manager.py             # Slack API access, message fetcher
│   ├── crawler_manager.py           # Playwright/Crawl4AI fetcher
│   ├── analyzer_manager.py          # Claude-based analyzer w/ infra context
│
├── utils/
│   ├── file_utils.py                # JSON load/save helpers
│   ├── path_utils.py                # Base/data path resolution
│   ├── slack_helpers.py             # Slack posting + block-kit helpers
│
├── scripts/
│   └── convert_infrastructure.py    # CLI to convert infra inventories
│
├── main_threatintel.py              # Entrypoint – run orchestrator
└── dev_autoreload.py                # Watch + hot reload (for dev)
```

---

## 🚀 Quick Start

### 1. Clone & Setup

```bash
git clone https://github.com/your-org/threat-intel-pipeline.git
cd threat-intel-pipeline
uv sync
```

### 2. Environment Variables (`.env`)

```bash
# Slack
SLACK_BOT_TOKEN=xoxb-your-token
MAX_MESSAGE_AGE=7d

# AWS Bedrock
AWS_REGION=eu-central-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...

# Bedrock Models
CLAUDE_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0
NOVA_LITE_MODEL_ID=us.amazon.nova-lite-v1:0
TITAN_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0

# LiteLLM (optional proxy)
LITELLM_MODEL=claude-3.5-sonnet
LITELLM_BASE_URL=http://localhost:4000
LITELLM_API_KEY=sk-your-key
```

---

## 🦯 Running the Pipeline

### 🔹 Full Orchestration (Slack → Crawl → Analysis)

```bash
uv run python src/main_threatintel.py
```

This executes:
1️⃣ `SlackToUrlsPipeline`
2️⃣ `UrlsToCrawledPipeline`
3️⃣ `CrawledToAnalysisPipeline`

Results are saved to:

```
data/slack_channel_export/
 ├── threat-intelligence_urls.json
 ├── threat-intelligence_results.json
 └── threat-intelligence_analysis.json
```

---

### 🔹 Run Individual Stages

```python
from src.pipelines.threat_intel_pipeline import ThreatIntelPipeline
import asyncio

async def main():
    pipeline = ThreatIntelPipeline(channel_name="threat-intelligence", limit=10)
    await pipeline.run_stage("slack_to_urls")
    await pipeline.run_stage("urls_to_crawled")
    await pipeline.run_stage("crawled_to_analysis")

asyncio.run(main())
```

---

### 🔹 Continuous Channel Monitor (Realtime Slack Bot)

```bash
uv run python -m src.pipelines.channel_monitor
```

This keeps watching your Slack channel for new URLs and posts LLM-generated analysis replies automatically.

---

## 🧰 Infrastructure Inventory Context

Before first analysis, convert your internal inventory sheet:

```bash
uv run python src/scripts/convert_infrastructure.py data/infrastructure/inventory.xlsx
```

Generates:

* `data/infrastructure/processed/infrastructure_context.json`
* `data/infrastructure/processed/infrastructure_condensed.txt`

Used automatically by `analyzer_manager.py` to guide threat relevance.

---

## 📊 Slack Integration Highlights

| Function                  | Description                                 |
| ------------------------- | ------------------------------------------- |
| `post_thread_reply()`     | Posts analysis as a threaded reply          |
| `add_reaction()`          | Adds severity emoji reactions (🟢🟠🔴)      |
| `send_alert_dm()`         | Sends direct DM alerts for critical threats |
| `build_analysis_blocks()` | Renders LLM output into Block Kit UI        |

---

## 🧪 Testing the LLM Adapters

```bash
uv run python tests/test_bedrock_llm.py
```

✅ Lists Bedrock models
✅ Tests Claude & Nova text generation
✅ Tests Titan embedding

---

## 🛱️ Design Principles

| Principle                          | Description                                         |
| ---------------------------------- | --------------------------------------------------- |
| **Server-authoritative pipelines** | Async-safe orchestration controlled by backend      |
| **Composable building blocks**     | Each stage reusable individually                    |
| **Separation of concerns**         | Slack, crawl, and LLM handled by dedicated managers |
| **Minimal config**                 | Pure `.env` + explicit parameters                   |
| **Infrastructure-aware reasoning** | LLM context enriched by real infra data             |

---

## 🥉 Example Output in Slack

```
🧠 ThreatMark Intelligence Analysis
-----------------------------------
URL: https://example.com/zero-day

🖍 Summary:
Zero-day exploit in HAProxy allows remote code execution.

⚠️ Impact:
Externally facing proxy systems may be vulnerable.

🔢 Relevance:
5

🧭 Actions:
Immediate patching required, network segmentation.
```

---

## 🔍 Developer Tips

* Auto-reload while developing:

  ```bash
  uv run python src/dev_autoreload.py
  ```
* Data location:

  ```
  data/slack_channel_export/
  ```
* Enable debug logging in Loguru:

  ```python
  logger.remove()
  logger.add(sys.stderr, level="DEBUG")
  ```

---

## 🪿 License

© ThreatMark Internal R&D Team
Confidential and proprietary for internal research purposes only.
