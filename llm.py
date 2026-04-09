"""
LLM interface uses Ollama (free, local) via its REST API
falls back to rule-based stubs if Ollama is unreachable
set OLLAMA_MODEL in .env to override the default model
"""

import os
import json
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
logger = logging.getLogger(__name__)

def _call_ollama(system: str, user: str) -> str | None:
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": 0.2},
        }
        resp = requests.post(f"{OLLAMA_BASE}/api/chat", json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"Ollama unavailable ({e}). Using rule-based fallback.")
        return None


def llm_query(system: str, user: str, fallback_fn=None) -> str:
    # query Ollama if unavailable call fallback_fn() or return a default string

    result = _call_ollama(system, user)
    if result:
        return result
    if fallback_fn:
        return fallback_fn()
    return "LLM unavailable - rule-based analysis applied."
