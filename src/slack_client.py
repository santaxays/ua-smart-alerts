"""Thin wrapper around slack_sdk.WebClient for sending alert attachments."""
from __future__ import annotations

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackClient:
    def __init__(self, token: str) -> None:
        self._client = WebClient(token=token)

    def send_attachment(
        self,
        channel_id: str,
        attachment_payload: dict,
        fallback_text: str,
    ) -> None:
        """Post an attachment-wrapped Block Kit message to a Slack channel.

        attachment_payload must be the dict from alert_builder.build_slack_blocks():
            {"attachments": [{"color": "...", "blocks": [...]}]}

        Raises RuntimeError with a descriptive message on Slack API error.
        """
        try:
            self._client.chat_postMessage(
                channel=channel_id,
                text=fallback_text,
                attachments=attachment_payload["attachments"],
            )
        except SlackApiError as exc:
            error_code = exc.response.get("error", "unknown_error")
            raise RuntimeError(
                f"Slack API error ({error_code}) while posting to {channel_id}: {exc}"
            ) from exc
