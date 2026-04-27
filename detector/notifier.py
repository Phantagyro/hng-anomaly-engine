"""
notifier.py - Sends Slack alerts for bans, unbans, and global anomalies.
Webhook URL is loaded from config.yaml.
"""

import requests
import time


class Notifier:
    def __init__(self, config: dict):
        import os; self.webhook_url = os.getenv("SLACK_WEBHOOK_URL", config["slack_webhook_url"])

    def _send(self, message: str):
        """Send a message to Slack."""
        try:
            response = requests.post(
                self.webhook_url,
                json={"text": message},
                timeout=5,
            )
            if response.status_code != 200:
                print(f"[notifier] Slack error: {response.status_code} {response.text}")
        except requests.RequestException as e:
            print(f"[notifier] Failed to send Slack alert: {e}")

    def send_ban_alert(self, ip: str, rate: float, baseline: float,
                       condition: str, duration: str):
        """Send a ban notification to Slack."""
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        message = (
            f":rotating_light: *IP BANNED*\n"
            f"*IP:* `{ip}`\n"
            f"*Condition:* {condition}\n"
            f"*Current Rate:* {rate:.4f} req/s\n"
            f"*Baseline Mean:* {baseline:.4f} req/s\n"
            f"*Ban Duration:* {duration}\n"
            f"*Timestamp:* {timestamp}"
        )
        self._send(message)

    def send_unban_alert(self, ip: str, duration: int):
        """Send an unban notification to Slack."""
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        message = (
            f":white_check_mark: *IP UNBANNED*\n"
            f"*IP:* `{ip}`\n"
            f"*Previous Ban Duration:* {duration}s\n"
            f"*Timestamp:* {timestamp}"
        )
        self._send(message)

    def send_global_alert(self, rate: float, baseline: float, condition: str):
        """Send a global anomaly notification to Slack."""
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        message = (
            f":warning: *GLOBAL TRAFFIC ANOMALY*\n"
            f"*Condition:* {condition}\n"
            f"*Current Global Rate:* {rate:.4f} req/s\n"
            f"*Baseline Mean:* {baseline:.4f} req/s\n"
            f"*Action:* Alert only (no block)\n"
            f"*Timestamp:* {timestamp}"
        )
        self._send(message)
