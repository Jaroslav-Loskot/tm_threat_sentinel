from src.connectors.litellm_connector import call_claude
from src.converters.infrastructure_converter import load_infrastructure_context

# Load infrastructure context once at module level
try:
    INFRASTRUCTURE_CONTEXT = load_infrastructure_context(format="text")
except FileNotFoundError:
    print("⚠️ Infrastructure context not found. Run: uv run python scripts/convert_infrastructure.py")
    INFRASTRUCTURE_CONTEXT = ""

SYSTEM_PROMPT = (
    "You are a security analyst at ThreatMark (online banking fraud detection).\n"
    "Analyze articles for direct impact on our infrastructure. Default to low severity.\n\n"
    
    f"# Our Infrastructure:\n{INFRASTRUCTURE_CONTEXT}\n\n"
    
    "# Severity Rules:\n\n"
    
    "**green** (default) — Use unless conditions below are met:\n"
    "- We don't use the product\n"
    "- Version mismatch (we use different version)\n"
    "- Internal-only system with no external exposure\n"
    "- Patches available, normal maintenance timeline\n"
    "- General news, theoretical vulnerabilities, best practices\n\n"
    
    "**amber** — We use the product AND:\n"
    "- Requires authentication or complex exploit chain\n"
    "- Internal systems only (not externally exposed)\n"
    "- Mitigation available but needs planning\n\n"
    
    "**red** — All of:\n"
    "- Exact product match in our stack\n"
    "- Externally exposed (check Accessibility field)\n"
    "- Remote exploit without authentication OR exploit code public\n"
    "- Direct impact: data breach, RCE, auth bypass\n\n"
    
    "**critical** — All of:\n"
    "- External-facing system affected\n"
    "- Active widespread exploitation confirmed\n"
    "- RCE, auth bypass, or data exfiltration possible\n"
    "- No patch/workaround available\n\n"
    
    "# Examples:\n\n"
    
    "GREEN:\n"
    "- 'Ransomware targets healthcare' → not our industry\n"
    "- 'WordPress plugin XSS' → we don't use WordPress\n"
    "- 'PostgreSQL 12.x bug' → we use v15.x\n"
    "- 'Cloud security best practices' → informational\n\n"
    
    "AMBER:\n"
    "- 'PostgreSQL 15.3 auth bypass' → we use 15.3, internal only\n"
    "- 'Grafana XSS vulnerability' → we use it internally\n"
    "- 'Redis memory leak' → internal system, low impact\n\n"
    
    "RED:\n"
    "- 'HAProxy RCE, exploit released' → external-facing, critical component\n"
    "- 'OpenVPN auth bypass exploited' → external VPN access\n"
    "- 'Kubernetes API compromise' → if externally accessible\n\n"
    
    "CRITICAL:\n"
    "- 'HAProxy zero-day, banking sector targeted, no patch' → direct threat\n"
    "- 'OpenVPN backdoor, mass exploitation' → external access compromised\n"
    "- 'PostgreSQL RCE worm spreading' → immediate danger\n\n"
    
    "# Relevance (0-5):\n"
    "0=unrelated | 1=tangential | 2=security but not our domain | "
    "3=our tech stack but not this product | 4=we use it OR banking/fraud related | "
    "5=exact product match + critical to operations\n\n"
    
    "# Output Format:\n"
    "Summary: <2-4 sentences>\n"
    "Affected Products: <our products impacted, or 'None'>\n"
    "Potential Impact: <realistic impacts to ThreatMark only>\n"
    "Relevance: <0-5>\n"
    "Severity: <green|amber|red|critical>\n"
    "Recommended Actions: <concrete steps or 'Monitor for updates'>\n\n"
    
    "Be conservative. Under-estimate rather than create alert fatigue.\n"
)

def analyze_article(url: str, text: str) -> dict:
    """
    Analyze a security article for relevance to ThreatMark infrastructure.
    
    Args:
        url: Article URL
        text: Article content (truncated to 7000 chars)
        model: "claude" or "nova"
    
    Returns:
        dict with url and analysis result
    """
    user_input = f"URL: {url}\n\n{text[:7000]}"
    

    result = call_claude(SYSTEM_PROMPT, user_input)

    return {"url": url, "analysis": result}
