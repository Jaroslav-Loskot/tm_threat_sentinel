import os
from dotenv import load_dotenv
from connectors.llm_connector import (
    call_claude,
    call_nova_lite,
    get_embedding,
    list_available_models,
)

load_dotenv(override=True)

def run_tests():
    print("🔍 AWS Region:", os.getenv("AWS_REGION"))
    print("🔍 CLAUDE_MODEL_ID:", os.getenv("CLAUDE_MODEL_ID"))
    print("🔍 NOVA_LITE_MODEL_ID:", os.getenv("NOVA_LITE_MODEL_ID"))

    print("\n🧠 Listing available models:")
    list_available_models()

    print("\n🚀 Testing Claude call:")
    resp = call_claude(
        system_prompt="You are a cybersecurity analyst.",
        user_prompt="Explain in one sentence what a zero-day vulnerability is.",
    )
    print("Claude response:", resp)

    print("\n🚀 Testing Nova Lite call:")
    resp2 = call_nova_lite(
        system_prompt="You are a helpful assistant.",
        user_prompt="Summarize the purpose of Amazon Bedrock.",
    )
    print("Nova Lite response:", resp2)

    print("\n🚀 Testing Titan embedding:")
    vec = get_embedding("Artificial intelligence is transforming industries.")
    print(f"Embedding length: {len(vec)}")
    print("First 5 dims:", vec[:5])


if __name__ == "__main__":
    run_tests()
