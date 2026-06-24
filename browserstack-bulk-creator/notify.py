"""
Notification module.
Sends a completion notification via one or more channels when a batch finishes.

Supported channels:
  1. Slack incoming webhook   (--webhook <url> --webhook-type slack)
  2. Teams incoming webhook   (--webhook <url> --webhook-type teams)
  3. Generic JSON webhook     (--webhook <url> --webhook-type generic)
  4. Windows desktop toast    (--toast)  — uses PowerShell, no extra pip dep
  5. Terminal print only      (default, always active)

Usage from code:
    from notify import Notifier
    n = Notifier(webhook_url="https://...", webhook_type="slack", toast=True)
    n.send(title="Batch complete", body="90 created, 0 failed", success=True)
"""

import json
import subprocess
import sys
from typing import Any

import requests


class Notifier:
    def __init__(
        self,
        webhook_url: str = "",
        webhook_type: str = "slack",
        toast: bool = False,
    ) -> None:
        self._webhook_url = webhook_url.strip()
        self._webhook_type = webhook_type.lower()
        self._toast = toast

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def send(self, title: str, body: str, success: bool = True) -> None:
        """Send the notification to all configured channels."""
        icon = "✅" if success else "❌"

        if self._webhook_url:
            self._send_webhook(title, body, icon, success)

        if self._toast:
            self._send_toast(title, body, icon)

    # ------------------------------------------------------------------
    # Webhook
    # ------------------------------------------------------------------

    def _send_webhook(
        self, title: str, body: str, icon: str, success: bool
    ) -> None:
        try:
            payload = self._build_payload(title, body, icon, success)
            resp = requests.post(
                self._webhook_url,
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code in (200, 204):
                print(f"  🔔  Webhook notification sent ({self._webhook_type}).")
            else:
                print(
                    f"  ⚠ Webhook notification failed: "
                    f"HTTP {resp.status_code} {resp.text[:120]}"
                )
        except requests.RequestException as exc:
            print(f"  ⚠ Webhook notification error: {exc}")

    def _build_payload(
        self, title: str, body: str, icon: str, success: bool
    ) -> dict[str, Any]:
        colour = "good" if success else "danger"
        hex_colour = "#36a64f" if success else "#d93025"

        if self._webhook_type == "slack":
            return {
                "attachments": [
                    {
                        "color": colour,
                        "title": f"{icon}  {title}",
                        "text": body,
                        "footer": "BrowserStack Bulk Creator",
                    }
                ]
            }

        if self._webhook_type == "teams":
            return {
                "@type": "MessageCard",
                "@context": "http://schema.org/extensions",
                "themeColor": hex_colour,
                "summary": title,
                "sections": [
                    {
                        "activityTitle": f"{icon}  {title}",
                        "activityText": body,
                    }
                ],
            }

        # Generic / custom webhook — plain JSON
        return {"title": title, "body": body, "success": success}

    # ------------------------------------------------------------------
    # Windows desktop toast (PowerShell, no extra pip dep)
    # ------------------------------------------------------------------

    def _send_toast(self, title: str, body: str, icon: str) -> None:
        if sys.platform != "win32":
            print("  ⚠ Desktop toast is only supported on Windows.")
            return

        # Escape single quotes for PowerShell string embedding.
        safe_title = title.replace("'", "''")
        safe_body = body.replace("'", "''")

        ps_script = (
            "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
            "ContentType = WindowsRuntime] | Out-Null; "
            "[Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, "
            "ContentType = WindowsRuntime] | Out-Null; "
            "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, "
            "ContentType = WindowsRuntime] | Out-Null; "
            "$template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02; "
            "$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template); "
            f"$xml.GetElementsByTagName('text')[0].AppendChild($xml.CreateTextNode('{safe_title}')) | Out-Null; "
            f"$xml.GetElementsByTagName('text')[1].AppendChild($xml.CreateTextNode('{safe_body}')) | Out-Null; "
            "$toast = [Windows.UI.Notifications.ToastNotification]::new($xml); "
            "[Windows.UI.Notifications.ToastNotificationManager]::"
            "CreateToastNotifier('BrowserStack Creator').Show($toast);"
        )

        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                check=True,
                capture_output=True,
                timeout=10,
            )
            print("  🔔  Windows desktop toast sent.")
        except (subprocess.SubprocessError, FileNotFoundError) as exc:
            print(f"  ⚠ Desktop toast failed: {exc}")
