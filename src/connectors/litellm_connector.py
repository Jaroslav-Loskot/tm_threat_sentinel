from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage

from dotenv import load_dotenv
import os

_ = load_dotenv()

LITELLM_MODEL = os.getenv("LITELLM_MODEL", "")
LITELLM_BASE_URL = os.getenv("LITELLM_BASE_URL", "")
LITELLM_API_KEY = os.getenv("LITELLM_API_KEY", "")


def call_claude(system_prompt: str, user_prompt: str) -> str:

    chat = init_chat_model(
        model=LITELLM_MODEL,
        base_url=LITELLM_BASE_URL,
        api_key=LITELLM_API_KEY,
        temperature=0,
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    return str(chat.invoke(messages).content)


# ============================================================
# 🚀 Example usage
# ============================================================
def main():
    system_prompt = "You are a concise, helpful assistant."
    user_prompt = "Explain in one sentence why LiteLLM is great for proxying LLMs."

    print("🔹 Sending request to model...")
    response = call_claude(system_prompt, user_prompt)
    print("\n🧠 Model response:\n")
    print(response)


if __name__ == "__main__":
    main()
