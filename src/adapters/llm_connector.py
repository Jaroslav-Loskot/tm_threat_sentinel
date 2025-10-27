import os
from typing import List, Union, cast
from dotenv import load_dotenv
from litellm import completion, embedding
from litellm.files.main import ModelResponse
import base64
import boto3

load_dotenv(override=True)

AWS_REGION = os.getenv("AWS_REGION", "")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
CLAUDE_MODEL_ID = os.getenv(
    "CLAUDE_MODEL_ID", ""
)  # e.g. "us.anthropic.claude-sonnet-4-20250514-v1:0"
NOVA_LITE_MODEL_ID = os.getenv("NOVA_LITE_MODEL_ID", "")
TITAN_EMBEDDING_MODEL_ID = os.getenv(
    "TITAN_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"
)


def list_available_models():
    client = boto3.client(
        "bedrock",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )

    response = client.list_foundation_models()
    for model in response["modelSummaries"]:
        print(model["modelId"], "-", model["modelName"])


def call_llm(
    model_id: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 500,
    temperature: float = 0.7,
) -> str:
    """
    Unified Bedrock LLM call via LiteLLM Converse API.

    Args:
        model_id: The Claude/Nova model ID from AWS Bedrock (e.g., "us.anthropic.claude-sonnet-4-20250514-v1:0")
        system_prompt: Instructions for the assistant (role=system)
        user_prompt: The user query (role=user)
        max_tokens: Max output tokens
        temperature: Randomness factor

    Returns:
        str: Generated text
    """
    model = f"bedrock/converse/{model_id}"

    resp = completion(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
        stream=False,
    )

    mr = cast(ModelResponse, resp)
    return mr["choices"][0]["message"]["content"]


# --- convenience wrapper for Claude ---
def call_claude(system_prompt: str, user_prompt: str) -> str:
    if not CLAUDE_MODEL_ID:
        raise ValueError("CLAUDE_MODEL_ID not set in environment")
    return call_llm(CLAUDE_MODEL_ID, system_prompt, user_prompt)


def call_nova_lite(system_prompt: str, user_prompt: str) -> str:
    if not NOVA_LITE_MODEL_ID:
        raise ValueError("NOVA_LITE_MODEL_ID not set in environment")
    return call_llm(NOVA_LITE_MODEL_ID, system_prompt, user_prompt)


# --- Multimodal (Image + Text) ---
def analyze_image_with_llm(
    model_id: str,
    image_input: Union[str, bytes],
    user_input: str,
    system_prompt: str = "You are a vision assistant.",
) -> str:
    """
    Analyze an image with Claude/Nova multimodal models via LiteLLM.

    Args:
        model_id: Bedrock model ID (e.g. "us.anthropic.claude-sonnet-4-20250514-v1:0")
        image_input: Either a file path, raw bytes, or a base64 string (PNG/JPEG)
        question: Text prompt/question for the model
        system_prompt: Optional system prompt
    """
    model = f"bedrock/converse/{model_id}"

    # Handle file path
    if isinstance(image_input, str) and os.path.exists(image_input):
        with open(image_input, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")
    # Handle raw bytes
    elif isinstance(image_input, (bytes, bytearray)):
        image_b64 = base64.b64encode(image_input).decode("utf-8")
    # Assume already base64 string
    elif isinstance(image_input, str):
        image_b64 = image_input
    else:
        raise ValueError("image_input must be a file path, base64 string, or bytes")

    resp = completion(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_input},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                    },
                ],
            },
        ],
        max_tokens=500,
        stream=False,
    )

    mr = cast(ModelResponse, resp)
    return mr["choices"][0]["message"]["content"]


# --- Embeddings Wrapper ---
def get_embedding(text: str, model_id: str = TITAN_EMBEDDING_MODEL_ID) -> List[float]:
    """Fetch an embedding vector using Titan on Bedrock via LiteLLM."""
    model = f"bedrock/{model_id}"  # embeddings don’t use 'converse'

    resp = embedding(
        model=model,
        input=text,
    )

    return resp["data"][0]["embedding"]


if __name__ == "__main__":
    # print(call_claude(system_prompt="You are a helpful assistant.", user_prompt="Hi, who are you?"))
    # print(call_nova_lite(system_prompt="You are a helpful assistant.", user_prompt="Hi, who are you?"))
    # vec = get_embedding("Artificial intelligence is transforming industries.")
    # print("Embedding length:", len(vec))
    # print("First 5 values:", vec[:5])

    # with open("cat.png", "rb") as f:
    #     img_b64 = base64.b64encode(f.read()).decode("utf-8")

    # resp = analyze_image_with_llm(
    #     # model_id=CLAUDE_MODEL_ID,
    #     model_id=NOVA_LITE_MODEL_ID,
    #     image_b64=img_b64,
    #     question="What do you see in this picture?"
    # )

    # print("Vision:", resp)
    pass
