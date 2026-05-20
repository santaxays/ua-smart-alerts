"""Claude API enrichment: groups alerts by campaign and enriches each group in one call."""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

import anthropic

from detectors.base import Alert

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_REAL_PROMPT = _PROMPTS_DIR / "system_prompt.ru.md"
_EXAMPLE_PROMPT = _PROMPTS_DIR / "system_prompt.example.md"

MODEL = "claude-sonnet-4-5"
# Group of N alerts needs ~400 tokens per alert in the response, plus overhead.
# 1200 fits up to ~3 alerts comfortably; raise if larger groups appear.
MAX_TOKENS = 1200

# Cached at module level so we read disk only once per process
_system_prompt: Optional[str] = None


def load_system_prompt() -> str:
    """Return system prompt text, caching after first load.

    Prefers system_prompt.ru.md; falls back to system_prompt.example.md
    and prints a WARN if the fallback is used.
    """
    global _system_prompt
    if _system_prompt is not None:
        return _system_prompt

    if _REAL_PROMPT.exists():
        _system_prompt = _REAL_PROMPT.read_text(encoding="utf-8")
    else:
        print(
            f"WARN: {_REAL_PROMPT.name} not found — using example prompt. "
            "Enrichment quality will be generic.",
            file=sys.stderr,
        )
        _system_prompt = _EXAMPLE_PROMPT.read_text(encoding="utf-8")

    return _system_prompt


def _format_user_message(alerts: list[Alert]) -> str:
    """Build the user message for a group of alerts from one campaign."""
    lines = [f"campaign: {alerts[0].campaign}", ""]
    if len(alerts) == 1:
        lines.append(f"dedup_key: {alerts[0].dedup_key}")
        lines.append(f"detector_name: {alerts[0].detector_name}")
        lines.append(f"severity: {alerts[0].severity}")
        lines.append(f"title: {alerts[0].title}")
        lines.append(f"body: {alerts[0].body}")
        lines.append(f"metric_value: {alerts[0].metric_value}")
        lines.append(f"baseline_value: {alerts[0].baseline_value}")
    else:
        lines.append(f"В этой группе {len(alerts)} связанных алёрта — свяжи их единой гипотезой.")
        lines.append("")
        for i, alert in enumerate(alerts, 1):
            lines.append(f"--- Алёрт {i} ---")
            lines.append(f"dedup_key: {alert.dedup_key}")
            lines.append(f"detector_name: {alert.detector_name}")
            lines.append(f"severity: {alert.severity}")
            lines.append(f"title: {alert.title}")
            lines.append(f"body: {alert.body}")
            lines.append(f"metric_value: {alert.metric_value}")
            lines.append(f"baseline_value: {alert.baseline_value}")
            lines.append("")
    return "\n".join(lines)


def _strip_markdown_fence(raw: str) -> str:
    """Remove ```json ... ``` wrapper if Claude added one."""
    if raw.startswith("```"):
        lines = raw.split("\n")
        return "\n".join(lines[1:-1]).strip()
    return raw


def _enrich_one_group(client: anthropic.Anthropic, alerts: list[Alert]) -> dict[str, dict]:
    """Call Claude once for a group of alerts (same campaign). Returns {dedup_key: enrichment}."""
    user_message = _format_user_message(alerts)
    expected_keys = {a.dedup_key for a in alerts}

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=load_system_prompt(),
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text.strip()
    except Exception as exc:
        print(
            f"WARN: Claude API error for campaign {alerts[0].campaign}: {exc}",
            file=sys.stderr,
        )
        return {}

    raw = _strip_markdown_fence(raw)

    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise TypeError(f"expected dict, got {type(parsed).__name__}")
    except (json.JSONDecodeError, TypeError) as exc:
        print(
            f"WARN: Could not parse Claude response for {alerts[0].campaign}: {exc}",
            file=sys.stderr,
        )
        return {}

    # Keep only keys we asked about, validate shape
    result: dict[str, dict] = {}
    for key in expected_keys:
        entry = parsed.get(key)
        if not isinstance(entry, dict):
            print(
                f"WARN: missing or malformed enrichment for {key}",
                file=sys.stderr,
            )
            continue
        try:
            result[key] = {
                "context": str(entry["context"]),
                "recommendation": str(entry["recommendation"]),
            }
        except KeyError as exc:
            print(
                f"WARN: enrichment for {key} missing field: {exc}",
                file=sys.stderr,
            )
    return result


def enrich_alerts(alerts: list[Alert]) -> dict[str, dict]:
    """Enrich a flat list of alerts. Groups by campaign internally, one Claude call per group.

    Returns {alert.dedup_key: {'context': str, 'recommendation': str}}.
    Failed enrichments are absent from the dict — callers should use .get(key).
    """
    if not alerts:
        return {}

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("WARN: ANTHROPIC_API_KEY not set — skipping enrichment.", file=sys.stderr)
        return {}

    # Group alerts by campaign name
    groups: dict[str, list[Alert]] = defaultdict(list)
    for alert in alerts:
        groups[alert.campaign].append(alert)

    client = anthropic.Anthropic(api_key=api_key)
    enrichments: dict[str, dict] = {}
    for campaign_alerts in groups.values():
        enrichments.update(_enrich_one_group(client, campaign_alerts))
    return enrichments