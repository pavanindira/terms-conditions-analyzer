"""
llm.py — Ollama integration for enhanced T&C analysis.

Talks to a local Ollama instance via its REST API.
Gracefully degrades to None if Ollama is unavailable or times out.

All prompts are designed to be fast on small models (llama3.2, mistral, phi3).
"""

import json
import os
import re
import logging
from typing import Optional
from dataclasses import dataclass, field

import requests

logger = logging.getLogger(__name__)

# ── Config (overridable via environment variables) ────────────────────────────
OLLAMA_BASE_URL  = os.environ.get("OLLAMA_BASE_URL",  "http://ollama:11434")
OLLAMA_MODEL     = os.environ.get("OLLAMA_MODEL",     "llama3.2")
OLLAMA_TIMEOUT   = int(os.environ.get("OLLAMA_TIMEOUT", "120"))   # seconds
OLLAMA_ENABLED   = os.environ.get("OLLAMA_ENABLED", "true").lower() != "false"

# How many characters of the document to send to the LLM
# (keeps prompt short enough for smaller models)
MAX_DOC_CHARS = 6000


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class LLMInsight:
    """Enhanced analysis produced by the local LLM."""
    plain_summary:      str = ""          # One paragraph, plain English
    overall_verdict:    str = ""          # Single sentence bottom line
    negotiation_tips:   list = field(default_factory=list)   # 3–5 tips
    plain_red_flags:    list = field(default_factory=list)   # LLM-spotted concerns
    user_questions:     list = field(default_factory=list)   # Questions to ask before signing
    model_used:         str = ""
    enhanced:           bool = False      # False = fallback / unavailable


# ─────────────────────────────────────────────────────────────────────────────
# Ollama client
# ─────────────────────────────────────────────────────────────────────────────

def _ollama_available() -> bool:
    """Quick ping to see if Ollama is reachable."""
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=4)
        return r.status_code == 200
    except Exception:
        return False


def _ollama_generate(prompt: str, system: str = "") -> Optional[str]:
    """
    Call /api/generate and return the full response text, or None on failure.
    Uses stream=False for simplicity.
    """
    payload = {
        "model":  OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature":  0.2,    # Low temp = more consistent / factual
            "num_predict":  800,    # Token limit per response
            "top_p":        0.9,
        },
    }
    if system:
        payload["system"] = system

    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip()
    except requests.exceptions.Timeout:
        logger.warning("Ollama timed out after %ds", OLLAMA_TIMEOUT)
        return None
    except Exception as e:
        logger.warning("Ollama error: %s", e)
        return None


def _parse_json_response(text: str) -> Optional[dict]:
    """Extract JSON from model output — handles markdown fences and stray text."""
    if not text:
        return None
    # Strip markdown code fences
    text = re.sub(r"```(?:json)?", "", text).strip()
    # Find the first { ... } block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


def _parse_list_response(text: str, max_items: int = 5) -> list:
    """
    Parse a numbered or bulleted list from model output.
    Returns a plain list of strings.
    """
    if not text:
        return []
    lines = text.strip().splitlines()
    items = []
    for line in lines:
        line = re.sub(r"^[\d\-\*\•\·\#]+[\.\):\s]+", "", line).strip()
        if line and len(line) > 10:
            items.append(line)
        if len(items) >= max_items:
            break
    return items


# ─────────────────────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a plain-English legal analyst helping everyday people understand \
Terms & Conditions documents. Be concise, honest, and practical. \
Never use legal jargon without immediately explaining it. \
Respond ONLY with what is asked — no preamble, no sign-off."""


def _prompt_summary(doc_type: str, text: str) -> str:
    return f"""This is a {doc_type} document. In 3–4 sentences, explain in plain English \
what a person is agreeing to if they sign this. Write as if explaining to a friend.

Document (excerpt):
{text[:MAX_DOC_CHARS]}

Plain English summary:"""


def _prompt_verdict(doc_type: str, risk_level: str, risk_score: int, text: str) -> str:
    return f"""This is a {doc_type} with a {risk_level} risk score of {risk_score}/100.

Write ONE sentence that gives an honest bottom-line verdict on whether a typical person \
should sign this, and why. Be direct. No hedging.

Document (excerpt):
{text[:2000]}

Verdict:"""


def _prompt_negotiation(doc_type: str, text: str) -> str:
    return f"""This is a {doc_type} document.

List 3 to 5 specific, practical things a person could ask to change or negotiate \
before signing. Be concrete — name the actual clause or term. \
Format as a numbered list, one tip per line.

Document (excerpt):
{text[:MAX_DOC_CHARS]}

Negotiation tips:"""


def _prompt_concerns(doc_type: str, text: str) -> str:
    return f"""Read this {doc_type} carefully and identify up to 4 things that are \
unusual, one-sided, or potentially harmful to the person signing.

Only flag things that actually appear in the text. If it is a fair document, say so.
Format as a numbered list, one concern per line.

Document (excerpt):
{text[:MAX_DOC_CHARS]}

Concerns:"""


def _prompt_questions(doc_type: str, text: str) -> str:
    return f"""This is a {doc_type}. What are 3 to 4 specific questions a person \
should ask the other party before signing?

These should be questions whose answers would genuinely change whether they sign.
Format as a numbered list, one question per line.

Document (excerpt):
{text[:MAX_DOC_CHARS]}

Questions to ask:"""


# ─────────────────────────────────────────────────────────────────────────────
# Main public function
# ─────────────────────────────────────────────────────────────────────────────

def enhance_with_llm(
    text: str,
    doc_type: str,
    risk_level: str,
    risk_score: int,
) -> LLMInsight:
    """
    Run the document through the local Ollama LLM for enhanced insights.

    Returns an LLMInsight. If Ollama is unavailable or disabled,
    returns an empty LLMInsight with enhanced=False.
    """
    if not OLLAMA_ENABLED:
        logger.info("Ollama disabled via OLLAMA_ENABLED=false")
        return LLMInsight()

    if not _ollama_available():
        logger.info("Ollama not reachable at %s", OLLAMA_BASE_URL)
        return LLMInsight()

    insight = LLMInsight(model_used=OLLAMA_MODEL, enhanced=True)

    # ── Plain summary ───────────────────────────────────────────────────────
    resp = _ollama_generate(_prompt_summary(doc_type, text), SYSTEM_PROMPT)
    if resp:
        insight.plain_summary = resp.strip()

    # ── Bottom-line verdict ─────────────────────────────────────────────────
    resp = _ollama_generate(_prompt_verdict(doc_type, risk_level, risk_score, text), SYSTEM_PROMPT)
    if resp:
        insight.overall_verdict = resp.strip()

    # ── Negotiation tips ────────────────────────────────────────────────────
    resp = _ollama_generate(_prompt_negotiation(doc_type, text), SYSTEM_PROMPT)
    if resp:
        insight.negotiation_tips = _parse_list_response(resp, max_items=5)

    # ── LLM-spotted concerns ────────────────────────────────────────────────
    resp = _ollama_generate(_prompt_concerns(doc_type, text), SYSTEM_PROMPT)
    if resp:
        insight.plain_red_flags = _parse_list_response(resp, max_items=4)

    # ── Questions to ask ────────────────────────────────────────────────────
    resp = _ollama_generate(_prompt_questions(doc_type, text), SYSTEM_PROMPT)
    if resp:
        insight.user_questions = _parse_list_response(resp, max_items=4)

    return insight


# ─────────────────────────────────────────────────────────────────────────────
# Status helper  (used by the UI health badge)
# ─────────────────────────────────────────────────────────────────────────────

def ollama_status() -> dict:
    """Return Ollama connectivity info for the UI."""
    if not OLLAMA_ENABLED:
        return {"available": False, "reason": "Disabled via OLLAMA_ENABLED=false", "model": OLLAMA_MODEL}

    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=4)
        if r.status_code != 200:
            return {"available": False, "reason": f"HTTP {r.status_code}", "model": OLLAMA_MODEL}

        tags = r.json().get("models", [])
        model_names = [m.get("name", "") for m in tags]
        model_loaded = any(OLLAMA_MODEL in n for n in model_names)

        return {
            "available":    True,
            "model":        OLLAMA_MODEL,
            "model_loaded": model_loaded,
            "all_models":   model_names,
            "base_url":     OLLAMA_BASE_URL,
        }
    except Exception as e:
        return {"available": False, "reason": str(e), "model": OLLAMA_MODEL}
