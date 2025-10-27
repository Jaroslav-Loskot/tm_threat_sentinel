from src.services.slack_manager import client

resp = client.conversations_history(channel="C07USTR5ZAQ", limit=3)
for m in resp["messages"]: # type: ignore
    print(m.get("text"))
