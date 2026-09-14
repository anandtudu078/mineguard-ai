"""Gemini vision analysis of mine-site photos.

The demo arc is photo in -> structured findings out. The service is deliberately
thin and fail-closed: if the model errors or returns something unparseable, the
caller records a manual fallback finding instead of silently pretending the
photo was analysed.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import google.genai as genai

from app.core.config import Settings
from app.models.enums import FindingSource, ViolationSeverity

logger = logging.getLogger(__name__)

#: The one prompt driving all photo analysis. Asking for strict JSON with an
#: enum-constrained severity keeps the output loadable without guesswork.
DETECTION_PROMPT = """You are a mine-safety inspector reviewing a photograph from an active \
mining lease. Identify any safety, environmental, or operational compliance violations \
visible in the photo.

Respond ONLY with a JSON object of this exact shape:
{
  "findings": [
    {
      "title": "short violation title, e.g. 'Workers without helmets near pit edge'",
      "description": "what is visible and why it violates standard practice",
      "severity": "critical" | "high" | "medium" | "low",
      "confidence": 0.0-1.0,
      "corrective_action": "what should be done about it"
    }
  ],
  "overall_summary": "one paragraph a compliance officer can act on"
}

Rules:
- Only report violations you can actually see evidence of in the image.
- Use "low" severity for anything you are unsure about.
- If the photo shows no violations, return an empty findings array."""

_SEVERITIES = {member.value for member in ViolationSeverity}
_VALID_SOURCES = {member.value for member in FindingSource}


@dataclass(slots=True)
class VisionFinding:
    """One violation the vision model reported."""

    title: str
    severity: ViolationSeverity
    confidence: Decimal
    description: str | None = None
    corrective_action: str | None = None


@dataclass(slots=True)
class VisionResult:
    """Full result of one photo analysis."""

    findings: list[VisionFinding]
    summary: str | None
    model_name: str
    raw: dict[str, Any]


def analyze_site_photo(image_bytes: bytes, mime_type: str, settings: Settings) -> VisionResult:
    """Send one photo to Gemini and return structured findings.

    Raises ``ValueError`` when no API key is configured or the response cannot
    be parsed; the caller decides what fallback to record.
    """
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is not configured; cannot analyse site photos")

    client = genai.Client(api_key=settings.gemini_api_key)
    model_name = "gemini-2.0-flash"

    response = client.models.generate_content(
        model=model_name,
        contents=[
            genai.types.Content(
                role="user",
                parts=[
                    genai.types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    genai.types.Part.from_text(text=DETECTION_PROMPT),
                ],
            )
        ],
        config=genai.types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )

    text = (response.text or "").strip()
    if not text:
        raise ValueError("Vision model returned an empty response")

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"Vision model returned invalid JSON: {error}") from error

    return _parse_payload(payload, model_name)


def _parse_payload(payload: Any, model_name: str) -> VisionResult:
    """Validate and normalise the model's JSON into typed findings."""
    if not isinstance(payload, dict):
        raise ValueError("Vision response was not a JSON object")

    findings: list[VisionFinding] = []
    for item in payload.get("findings", []) or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue

        severity_raw = str(item.get("severity") or "medium").strip().lower()
        severity = ViolationSeverity(severity_raw) if severity_raw in _SEVERITIES else ViolationSeverity.MEDIUM

        try:
            confidence = Decimal(str(item.get("confidence", "0.5"))).quantize(Decimal("0.001"))
        except Exception:
            confidence = Decimal("0.500")

        findings.append(
            VisionFinding(
                title=title[:200],
                severity=severity,
                confidence=confidence,
                description=(str(item["description"]).strip() or None) if item.get("description") else None,
                corrective_action=(
                    str(item["corrective_action"]).strip() or None
                ) if item.get("corrective_action") else None,
            )
        )

    summary = payload.get("overall_summary")
    return VisionResult(
        findings=findings,
        summary=(str(summary).strip() or None) if summary else None,
        model_name=model_name,
        raw=payload,
    )
