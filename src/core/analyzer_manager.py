from src.connectors.llm_connector import call_claude, call_nova_lite

SYSTEM_PROMPT = (
    "You are a cybersecurity and fraud intelligence analyst at ThreatMark.\n"
    "Analyze the article strictly for its relevance and potential impact on online banking, fraud detection, and identity protection.\n\n"

    "Provide a structured analysis using the following format and criteria:\n\n"
    "Summary: <2–4 sentences summarizing the article>\n"
    "Potential Impact: <bulleted list of the most critical consequences>\n"
    "Relevance: <integer 0–5, where 0 = none and 5 = directly relevant to ThreatMark's mission>\n"
    "Severity: <one of: green, amber, red, critical>\n"
    "Recommended Actions: <numbered list of concrete steps>\n\n"

    "Severity guidance:\n"
    "- green → informational or low risk\n"
    "- amber → moderate risk or limited exposure\n"
    "- red → high risk or active exploitation, serious technical impact\n"
    "- critical → extreme risk, active exploitation + severe technical impact (RCE, auth bypass, financial impact)\n\n"

    "Keep the output concise and well-structured.\n"
)


def analyze_article(url: str, text: str, model: str = "claude") -> dict:
    user_input = f"URL: {url}\n\n{text[:7000]}"
    try:
        if model == "claude":
            result = call_claude(SYSTEM_PROMPT, user_input)
        elif model == "nova":
            result = call_nova_lite(SYSTEM_PROMPT, user_input)
        else:
            raise ValueError(f"Unsupported model: {model}")
        return {"url": url, "analysis": result}
    except Exception as e:
        return {"url": url, "error": str(e)}
