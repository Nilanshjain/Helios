"""Slack webhook integration for incident notifications"""

import requests
from typing import Dict, Any

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class SlackNotifier:
    """Send incident notifications to Slack"""

    SEVERITY_COLORS = {
        "critical": "#FF0000",  # Red
        "high": "#FFA500",      # Orange
        "medium": "#FFFF00",    # Yellow
        "low": "#00FF00",       # Green
    }

    def __init__(self) -> None:
        """Initialize Slack notifier"""
        if not settings.slack_enabled:
            logger.info("slack_notifications_disabled")
            return

        if not settings.slack_webhook_url:
            raise ValueError("SLACK_WEBHOOK_URL not configured")

        self.webhook_url = settings.slack_webhook_url
        self.channel = settings.slack_channel

        logger.info("slack_notifier_initialized", channel=self.channel)

    def send_report_notification(
        self,
        report_id: str,
        service: str,
        severity: str,
        summary: str,
        report_url: str = "",
    ) -> bool:
        """
        Send incident report notification to Slack.

        Args:
            report_id: Report identifier
            service: Affected service
            severity: Incident severity
            summary: Brief summary
            report_url: URL to full report

        Returns:
            True if sent successfully
        """
        if not settings.slack_enabled:
            return False

        try:
            message = self._build_message(
                report_id, service, severity, summary, report_url
            )

            response = requests.post(
                self.webhook_url,
                json=message,
                timeout=10,
            )

            if response.status_code == 200:
                logger.info("slack_notification_sent", report_id=report_id)
                return True
            else:
                logger.error(
                    "slack_notification_failed",
                    status_code=response.status_code,
                    response=response.text,
                )
                return False

        except Exception as e:
            logger.error("slack_send_error", error=str(e), report_id=report_id)
            return False

    def _build_message(
        self,
        report_id: str,
        service: str,
        severity: str,
        summary: str,
        report_url: str,
    ) -> Dict[str, Any]:
        """Build Slack message payload"""

        color = self.SEVERITY_COLORS.get(severity.lower(), "#808080")

        # Build emoji based on severity
        emoji_map = {
            "critical": ":rotating_light:",
            "high": ":warning:",
            "medium": ":large_orange_diamond:",
            "low": ":information_source:",
        }
        emoji = emoji_map.get(severity.lower(), ":bell:")

        message = {
            "channel": self.channel,
            "username": "Helios Incident Reporter",
            "icon_emoji": ":robot_face:",
            "attachments": [
                {
                    "color": color,
                    "title": f"{emoji} Incident Report Generated - {service}",
                    "title_link": report_url if report_url else None,
                    "fields": [
                        {
                            "title": "Service",
                            "value": service,
                            "short": True,
                        },
                        {
                            "title": "Severity",
                            "value": severity.upper(),
                            "short": True,
                        },
                        {
                            "title": "Report ID",
                            "value": f"`{report_id}`",
                            "short": True,
                        },
                        {
                            "title": "Summary",
                            "value": summary,
                            "short": False,
                        },
                    ],
                    "footer": "Helios Reporting Service",
                    "footer_icon": "https://platform.slack-edge.com/img/default_application_icon.png",
                }
            ],
        }

        if report_url:
            message["attachments"][0]["actions"] = [
                {
                    "type": "button",
                    "text": "View Full Report",
                    "url": report_url,
                    "style": "primary" if severity == "critical" else "default",
                }
            ]

        return message
