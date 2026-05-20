"""Build Slack Block Kit payloads for alerts.

Slack does not support block-level colours; the only way to get a coloured
sidebar is to wrap the blocks inside an *attachment*.  The returned dict is
therefore shaped for chat.postMessage's `attachments` field:

    {"attachments": [{"color": "#C44545", "blocks": [...]}]}

Pass the whole dict as `attachment_payload` to SlackClient.send_attachment().
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from detectors.base import Alert

_SEVERITY_EMOJI = {
    "critical": "🚨",
    "warning":  "⚠️",
    "info":     "ℹ️",
}

_SEVERITY_COLOR = {
    "critical": "#C44545",
    "warning":  "#C19A4B",
    "info":     "#5B8FC4",
}

_FOOTER = "ua-smart-alerts · автоматический мониторинг"


def build_slack_blocks(
    alert: Alert,
    enrichment: Optional[dict],
) -> tuple[dict, str]:
    """Return (attachment_payload, fallback_text) for a single alert.

    attachment_payload is ready for Slack's chat.postMessage `attachments` param.
    fallback_text is a plain-text fallback for notifications.
    """
    emoji = _SEVERITY_EMOJI.get(alert.severity, "•")
    fallback_text = f"{emoji} {alert.title}"

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{emoji} {alert.title}", "emoji": True},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": alert.body},
        },
    ]

    if enrichment is not None:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*💡 Контекст*\n{enrichment['context']}",
            },
        })
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Действие*\n{enrichment['recommendation']}",
            },
        })

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"{alert.detector_name} · {ts} · {_FOOTER}",
            }
        ],
    })

    color = _SEVERITY_COLOR.get(alert.severity, "#888888")
    attachment_payload = {
        "attachments": [
            {
                "color":  color,
                "blocks": blocks,
            }
        ]
    }

    return attachment_payload, fallback_text
