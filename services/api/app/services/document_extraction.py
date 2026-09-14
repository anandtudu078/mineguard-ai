"""Provider-neutral extraction for uploaded compliance documents."""

from __future__ import annotations

import base64
import json
from datetime import date
from typing import Any

import httpx

from app.core.config import Settings

_EXTRACTION_PROMPT = """Extract compliance document metadata from the text below.
Return only valid JSON with these keys:
- summary: short plain-language summary
- expiry_date: ISO date YYYY-MM-DD or null
- reference_number: string or null
- authority: string or null
If a value is not present, use null.

DOCUMENT TEXT:
"""


def extract_metadata(text: str, settings: Settings) -> dict[str, Any] | None:
    """Ask the configured provider for metadata, returning None on failure."""
    if not text.strip():
        return None

    if settings.groq_api_key:
        result = _call_groq(text, settings.groq_api_key)
    elif settings.gemini_api_key:
        result = _call_gemini(text, settings.gemini_api_key)
    else:
        return None

    if not result:
        return None
    return _normalise(result)


def extract_document_metadata(
    raw_bytes: bytes,
    content_type: str,
    settings: Settings,
) -> dict[str, Any] | None:
    """Extract metadata from text, images, or PDFs using configured providers."""
    if settings.is_test:
        return None
    if content_type.startswith("text/"):
        return extract_metadata(raw_bytes.decode("utf-8", errors="ignore"), settings)
    if settings.gemini_api_key and content_type in {
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/webp",
    }:
        return _call_gemini_document(raw_bytes, content_type, settings.gemini_api_key)
    return None


def _call_groq(text: str, api_key: str) -> dict[str, Any] | None:
    response = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": "llama-3.1-8b-instant",
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "You extract structured compliance metadata."},
                {"role": "user", "content": _EXTRACTION_PROMPT + text[:12000]},
            ],
        },
        timeout=20,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return json.loads(content)


def _call_gemini(text: str, api_key: str) -> dict[str, Any] | None:
    response = httpx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
        params={"key": api_key},
        json={
            "contents": [{"parts": [{"text": _EXTRACTION_PROMPT + text[:12000]}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        },
        timeout=20,
    )
    response.raise_for_status()
    content = response.json()["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(content)


def _call_gemini_document(
    raw_bytes: bytes, content_type: str, api_key: str
) -> dict[str, Any] | None:
    response = httpx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
        params={"key": api_key},
        json={
            "contents": [
                {
                    "parts": [
                        {"text": _EXTRACTION_PROMPT},
                        {
                            "inline_data": {
                                "mime_type": content_type,
                                "data": base64.b64encode(raw_bytes).decode("ascii"),
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        },
        timeout=45,
    )
    response.raise_for_status()
    content = response.json()["candidates"][0]["content"]["parts"][0]["text"]
    return _normalise(json.loads(content))


def _normalise(result: dict[str, Any]) -> dict[str, Any]:
    expiry_date = result.get("expiry_date")
    if expiry_date:
        try:
            expiry_date = date.fromisoformat(str(expiry_date)).isoformat()
        except ValueError:
            expiry_date = None
    return {
        "summary": str(result.get("summary") or "").strip() or None,
        "expiry_date": expiry_date,
        "reference_number": result.get("reference_number"),
        "authority": result.get("authority"),
    }
