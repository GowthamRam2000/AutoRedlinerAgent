import json
import os
from typing import Any, Dict


def _policy_library(category: str, jurisdiction: str = "India") -> str:
    category = (category or "general").lower()
    norms = {
        "confidentiality": [
            "Exclude information already known/independently developed/public domain.",
            "Prefer mutual obligations if both parties share information.",
            "Limit onward disclosure to need-to-know with written obligations.",
            "Add prompt notice for compelled disclosures.",
        ],
        "indemnity": [
            "Cap indemnity (e.g., fees paid or agreed INR cap).",
            "Exclude indirect/special/consequential/punitive damages.",
            "Define notice, defense control, and mitigation duties.",
        ],
        "liability": [
            "Cap total liability; carve-out only wilful misconduct/gross negligence.",
            "Exclude indirect/special/consequential damages; limit to direct losses.",
        ],
        "termination": [
            "Allow convenience termination with reasonable notice (e.g., 30 days).",
            "Avoid auto-renewal or require explicit opt-in renewals.",
        ],
        "jurisdiction": [
            "Prefer Indian law; choose a mutually convenient venue.",
            "Consider arbitration under the Arbitration and Conciliation Act, 1996.",
        ],
        "payment": [
            "Define payment schedule, GST handling, and late fees.",
            "Include set-off rights and dispute procedures.",
        ],
        "ip": [
            "Clarify ownership, license scope, and residuals.",
            "Avoid implied assignments; require written assignment if needed.",
        ],
        "dispute-resolution": [
            "Escalation ladder; mediation; arbitration seat and venue in India.",
            "Specify costs allocation and language.",
        ],
        "non-compete": [
            "Ensure reasonable scope/time; tie to legitimate interests.",
            "Avoid restraints that may be void under Section 27 (restraint of trade).",
        ],
        "general": [
            "Ensure confidentiality survival and return/destroy obligations.",
            "Consider data protection compliance as applicable.",
        ],
    }
    tips = norms.get(category, norms["general"])
    header = f"Policy library for category='{category}', jurisdiction='{jurisdiction}':"
    return header + "\n- " + "\n- ".join(tips)


def _severity_rules(clause: str, category: str) -> str:
    c = (clause or "").lower()
    cat = (category or "").lower()
    score = 0
    # Heuristics (very simple): missing caps and unlimited liability → higher severity
    if "unlimited" in c and "liability" in c:
        score += 3
    if "indemnif" in c and ("all losses" in c or "any and all" in c):
        score += 2
    if "confidential" in c and ("perpetual" in c or "in perpetuity" in c):
        score += 1
    if "non-compete" in c or "non compete" in c:
        score += 2
    if cat in ("indemnity", "liability"):
        score += 1
    if score >= 4:
        return "critical"
    if score >= 3:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


def _redline_templates(clause: str, category: str) -> str:
    cat = (category or "general").lower()
    if cat == "liability":
        return (
            "Cap total liability to fees paid in the 12 months preceding the claim; "
            "exclude indirect, incidental, special, exemplary, and consequential damages."
        )
    if cat == "indemnity":
        return (
            "Indemnity limited to direct losses subject to cap; include notice requirements, "
            "control of defense by indemnifying party, and duty to mitigate."
        )
    if cat == "confidentiality":
        return (
            "Add exclusions (public domain, independently developed, legally obtained), mutual obligations if applicable, "
            "and an obligation to provide prompt notice of compelled disclosure."
        )
    return "Keep edits minimal and clear; prefer caps, exclusions, and clear procedures."


def handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Bedrock Agent Action Group Lambda handler.

    Expects Bedrock Agent to call with fields including:
      - actionGroup, function, parameters: [{ "name": str, "value": str }]

    Returns a JSON-serializable dict with a 'response' string for the agent.
    """
    action = event.get("function") or event.get("actionGroup") or ""
    params_list = event.get("parameters") or []
    params = {p.get("name"): p.get("value") for p in params_list if isinstance(p, dict)}

    name = (event.get("function") or "").strip()
    if name == "policy_library":
        category = params.get("category", "general")
        jurisdiction = params.get("jurisdiction", "India")
        result = _policy_library(category, jurisdiction)
    elif name == "severity_rules":
        clause = params.get("clause", "")
        category = params.get("category", "")
        result = _severity_rules(clause, category)
    elif name == "redline_templates":
        clause = params.get("clause", "")
        category = params.get("category", "")
        result = _redline_templates(clause, category)
    else:
        result = f"Unknown function: {name}"

    return {
        "response": result,
        # Agents often expect string content; keep it simple.
        "contentType": "text/plain",
    }

