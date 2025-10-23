import json
import re
from typing import Dict, List, Tuple

from .bedrock_client import converse_json, converse_agentic, invoke_agent_text


SCHEMA_GUIDE = {
    "issues": [
        {
            "issue_id": "string-unique",
            "category": "e.g., confidentiality, indemnity, IP, non-compete, termination, jurisdiction, payment, liability, dispute-resolution",
            "severity": "one of: low|medium|high|critical",
            "risk_summary": "short explanation of risk in Indian context",
            "recommendation": "practical change for safer position",
            "exact_text_snippet": "exact text copied from the contract that triggers the risk",
            "page_hint": 1,
            "redline_suggestion": "a suggested rewritten clause or minimal edit",
        }
    ],
    "summary": "1-2 sentence summary",
}


def build_prompt(full_text: str) -> str:
    instructions = (
        "You are a contracts attorney specializing in Indian contract law. "
        "Analyze the following contract text and identify risky clauses and concerns. "
        "Return STRICT JSON only, matching the JSON schema. Do not include markdown. "
        "Use exact clause quotes in 'exact_text_snippet' for frontend highlighting. "
        "Keep recommendations pragmatic and concise; include redline_suggestion when applicable. "
        "If multiple similar issues exist, group them logically."
    )
    schema = json.dumps(SCHEMA_GUIDE, ensure_ascii=False)
    prompt = (
        f"{instructions}\n\n"
        f"JSON schema (structure example, not literal):\n{schema}\n\n"
        f"Contract:\n" + full_text[:200000]
    )
    return prompt


def parse_llm_json(text: str) -> Dict:
    # Try to extract JSON block
    s = text.strip()
    # If model added extra text, attempt to find first { ... }
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        s = s[start : end + 1]
    try:
        data = json.loads(s)
        if "issues" not in data:
            data = {"issues": data if isinstance(data, list) else [], "summary": ""}
        return data
    except Exception:
        # last resort minimal structure
        return {"issues": [], "summary": s}


def normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def locate_snippet_pages(pages: List[str], snippet: str) -> List[int]:
    if not snippet:
        return []
    sn = normalize_ws(snippet)
    hits = []
    for i, page_text in enumerate(pages, start=1):
        pt = normalize_ws(page_text)
        if sn and sn in pt:
            hits.append(i)
    return hits


def analyze_with_bedrock(model_id: str, pages: List[str]) -> Dict:
    combined = "\n\n".join([f"[Page {i+1}]\n{t}" for i, t in enumerate(pages)])
    prompt = build_prompt(combined)

    # Agentic tool: policy_library (Indian contract norms)
    tools = [
        {
            "toolSpec": {
                "name": "policy_library",
                "description": "Returns concise Indian contract norms and thresholds for categories like confidentiality, indemnity, IP, non-compete, termination, jurisdiction, payment, liability, dispute-resolution.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string"},
                            "jurisdiction": {"type": "string", "enum": ["India"]}
                        },
                        "required": ["category", "jurisdiction"]
                    }
                }
            }
        }
    ]

    def tool_runner(name: str, inp: Dict) -> str:
        if name != "policy_library":
            return "Unknown tool"
        category = (inp or {}).get("category", "general").lower()
        norms = {
            "confidentiality": [
                "Exclude information already known/independently developed/public domain.",
                "Add mutual obligations if both parties share information.",
                "Limit onward disclosure to need-to-know + written obligations.",
                "Add prompt notice for compelled disclosures.",
            ],
            "indemnity": [
                "Cap indemnity to fees or a defined INR cap.",
                "Exclude indirect/special/consequential/punitive damages.",
                "Define notice, control of defense, and mitigation.",
            ],
            "liability": [
                "Cap total liability; carve-out only wilful misconduct/gross negligence.",
                "Exclude indirect/special/consequential damages; limit to direct losses.",
            ],
            "termination": [
                "Allow convenience termination with notice (e.g., 30 days).",
                "Shorter auto-renew cycles or explicit opt-in renewals.",
            ],
            "jurisdiction": [
                "Prefer Indian law and venue convenient to both parties.",
                "Consider arbitration (Arbitration and Conciliation Act, 1996).",
            ],
            "payment": [
                "Define clear payment terms, GST handling, and late fees.",
                "Set-off rights and dispute procedures.",
            ],
            "ip": [
                "Clarify ownership, license scope, and residuals.",
                "Avoid implied assignment; require written assignment if needed.",
            ],
            "dispute-resolution": [
                "Escalation ladder; mediation; arbitration venue and seat in India.",
                "Costs and language provisions.",
            ],
            "non-compete": [
                "Ensure reasonable scope/duration; tie to protection of legitimate interests.",
                "Avoid restraints that may be void under Section 27 (restraint of trade).",
            ],
            "general": [
                "Ensure compliance with applicable Indian data protection requirements.",
                "Add confidentiality survival term; return/destroy obligations.",
            ],
        }
        tips = norms.get(category, norms["general"])
        return "Policy library (India) for category='{}':\n- " .format(category) + "\n- ".join(tips)

    # Encourage tool usage via instruction prefix
    tool_instruction = (
        "You have access to a tool named policy_library(category, jurisdiction='India'). "
        "Call it when forming the risk analysis to ground recommendations. "
        "Return STRICT JSON matching the schema."
    )

    raw = converse_agentic(model_id, tool_instruction + "\n\n" + prompt, tools, tool_runner)
    data = parse_llm_json(raw)
    return data


def analyze_with_bedrock_agent(agent_id: str, agent_alias_id: str, pages: List[str]) -> Dict:
    """Invoke a Bedrock Agent (no external KB) with instructions to use offline tools.

    The Agent should be configured with Action Group functions matching:
      - policy_library(category: string, jurisdiction: "India") -> text tips
      - severity_rules(clause: string, category: string) -> suggested severity
      - redline_templates(clause: string, category: string) -> template edits
    and instructed to return STRICT JSON per SCHEMA_GUIDE.
    """
    combined = "\n\n".join([f"[Page {i+1}]\n{t}" for i, t in enumerate(pages)])
    base_instructions = (
        "You are a contracts attorney specializing in Indian contract law. "
        "Use available tools (policy_library, severity_rules, redline_templates) to ground your analysis. "
        "Return STRICT JSON only, matching the schema with fields: issues[], summary. "
        "Use exact_text_snippet for precise highlighting and keep recommendations pragmatic."
    )
    schema = json.dumps(SCHEMA_GUIDE, ensure_ascii=False)
    user_text = (
        f"{base_instructions}\n\n"
        f"JSON schema (structure example, not literal):\n{schema}\n\n"
        f"Contract:\n{combined[:200000]}"
    )
    raw = invoke_agent_text(agent_id, agent_alias_id, user_text)
    return parse_llm_json(raw)
