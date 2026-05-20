"""Tests for claude_enrich — Claude API is fully mocked."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import claude_enrich
from detectors.base import Alert


def _make_alert(**kwargs) -> Alert:
    defaults = dict(
        detector_name="cpi_spike",
        campaign="TestCamp_US",
        severity="warning",
        title="Скачок CPI — TestCamp_US",
        body="CPI вырос с $2.00 до $3.50 (+75%)",
        metric_value=3.50,
        baseline_value=2.00,
    )
    defaults.update(kwargs)
    return Alert(**defaults)


def _mock_response(text: str) -> MagicMock:
    """Build a fake anthropic Messages response containing `text`."""
    content_block = MagicMock()
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    return response


# ── Test 1: single alert in a list ─────────────────────────────────────────────

def test_single_alert_returns_dict_with_one_key(monkeypatch):
    """One alert in → dict with one dedup_key in result."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    claude_enrich._system_prompt = "system prompt text"

    alert = _make_alert()
    good_json = (
        '{"' + alert.dedup_key + '": '
        '{"context": "Auto-bid разогнался.", "recommendation": "Снизь bid на 20-30%."}}'
    )

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_response(good_json)

    with patch("claude_enrich.anthropic.Anthropic", return_value=mock_client):
        result = claude_enrich.enrich_alerts([alert])

    assert result == {
        alert.dedup_key: {
            "context": "Auto-bid разогнался.",
            "recommendation": "Снизь bid на 20-30%.",
        }
    }
    assert mock_client.messages.create.call_count == 1


# ── Test 2: multiple alerts of one campaign → one API call ────────────────────

def test_group_of_alerts_same_campaign_one_api_call(monkeypatch):
    """Two alerts of one campaign → one Claude call, dict with two keys."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    claude_enrich._system_prompt = "system prompt text"

    a1 = _make_alert(detector_name="cpi_spike")
    a2 = _make_alert(detector_name="budget_overrun")
    good_json = (
        '{'
        f'"{a1.dedup_key}": {{"context": "ctx1", "recommendation": "rec1"}},'
        f'"{a2.dedup_key}": {{"context": "ctx2", "recommendation": "rec2"}}'
        '}'
    )

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_response(good_json)

    with patch("claude_enrich.anthropic.Anthropic", return_value=mock_client):
        result = claude_enrich.enrich_alerts([a1, a2])

    assert set(result.keys()) == {a1.dedup_key, a2.dedup_key}
    assert mock_client.messages.create.call_count == 1


# ── Test 3: two campaigns → two API calls ─────────────────────────────────────

def test_two_campaigns_two_api_calls(monkeypatch):
    """Two alerts of different campaigns → two separate Claude calls."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    claude_enrich._system_prompt = "system prompt text"

    a1 = _make_alert(campaign="CampA_US")
    a2 = _make_alert(campaign="CampB_UK")

    responses = [
        _mock_response('{"' + a1.dedup_key + '": {"context": "x", "recommendation": "y"}}'),
        _mock_response('{"' + a2.dedup_key + '": {"context": "x", "recommendation": "y"}}'),
    ]
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = responses

    with patch("claude_enrich.anthropic.Anthropic", return_value=mock_client):
        result = claude_enrich.enrich_alerts([a1, a2])

    assert mock_client.messages.create.call_count == 2
    assert set(result.keys()) == {a1.dedup_key, a2.dedup_key}


# ── Test 4: invalid JSON → empty dict ─────────────────────────────────────────

def test_invalid_json_returns_empty_dict(monkeypatch):
    """When Claude returns garbage, enrich_alerts returns {}."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    claude_enrich._system_prompt = "system prompt text"

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_response("Извини, не могу помочь.")

    with patch("claude_enrich.anthropic.Anthropic", return_value=mock_client):
        result = claude_enrich.enrich_alerts([_make_alert()])

    assert result == {}


# ── Test 5: missing API key → empty dict, no exception ────────────────────────

def test_missing_api_key_returns_empty_dict(monkeypatch):
    """No ANTHROPIC_API_KEY → {}, no exception, no Claude call."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    result = claude_enrich.enrich_alerts([_make_alert()])

    assert result == {}


# ── Test 6: network error → empty dict ────────────────────────────────────────

def test_network_error_returns_empty_dict(monkeypatch):
    """If the API call raises, enrich_alerts swallows it and returns {}."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    claude_enrich._system_prompt = "system prompt text"

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = ConnectionError("timeout")

    with patch("claude_enrich.anthropic.Anthropic", return_value=mock_client):
        result = claude_enrich.enrich_alerts([_make_alert()])

    assert result == {}


# ── Test 7: markdown-fenced JSON is unwrapped ─────────────────────────────────

def test_markdown_fence_is_stripped(monkeypatch):
    """If Claude wraps JSON in ```json ... ```, it should still parse."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    claude_enrich._system_prompt = "system prompt text"

    alert = _make_alert()
    fenced = (
        "```json\n"
        '{"' + alert.dedup_key + '": '
        '{"context": "ctx", "recommendation": "rec"}}'
        "\n```"
    )

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_response(fenced)

    with patch("claude_enrich.anthropic.Anthropic", return_value=mock_client):
        result = claude_enrich.enrich_alerts([alert])

    assert alert.dedup_key in result