"""Send the daily Morning Edition link via WhatsApp using Twilio.

Required environment variables:
  TWILIO_ACCOUNT_SID       Twilio account SID
  TWILIO_AUTH_TOKEN        Twilio auth token
  TWILIO_WHATSAPP_FROM     WhatsApp-enabled sender, e.g. "whatsapp:+14155238886"
                           (the Twilio sandbox number works for testing)
  WHATSAPP_TO              Your number, e.g. "whatsapp:+15551234567"

The function is best-effort: if any required var is missing, it logs a warning
and returns without raising so the build still succeeds.
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)


def _format_message(url: str, issue_date: str, applies_count: int, tagline: str) -> str:
    lines = [
        f"Morning Edition — {issue_date}",
    ]
    if tagline:
        lines.append(f"\u201c{tagline}\u201d")
    if applies_count:
        lines.append(f"{applies_count} story(ies) flagged as directly applicable to you.")
    lines.append("")
    lines.append(url)
    return "\n".join(lines)


def _ensure_whatsapp_prefix(number: str) -> str:
    """Add 'whatsapp:' prefix if missing."""
    number = number.strip()
    if not number.startswith("whatsapp:"):
        number = f"whatsapp:{number}"
    return number


def send(url: str, issue_date: str, applies_count: int = 0, tagline: str = "") -> bool:
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
    token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
    sender = os.environ.get("TWILIO_WHATSAPP_FROM", "").strip()
    recipient = os.environ.get("WHATSAPP_TO", "").strip()

    missing = [
        name for name, val in [
            ("TWILIO_ACCOUNT_SID", sid), ("TWILIO_AUTH_TOKEN", token),
            ("TWILIO_WHATSAPP_FROM", sender), ("WHATSAPP_TO", recipient),
        ] if not val
    ]
    if missing:
        log.warning("Twilio env vars missing (%s); skipping notification.", ", ".join(missing))
        return False

    try:
        from twilio.rest import Client
    except ImportError:
        log.warning("twilio package not installed; skipping WhatsApp notification.")
        return False

    sender = _ensure_whatsapp_prefix(sender)
    recipient = _ensure_whatsapp_prefix(recipient)

    body = _format_message(url, issue_date, applies_count, tagline)
    log.info("Sending WhatsApp: from=%s to=%s", sender, recipient)

    try:
        client = Client(sid, token)
        msg = client.messages.create(from_=sender, to=recipient, body=body)
        log.info("WhatsApp message queued: sid=%s status=%s", msg.sid, msg.status)
        return True
    except Exception as e:
        log.error("Twilio API call failed: %s", e)
        return False


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 3:
        print("usage: notify.py <url> <issue_date> [applies_count] [tagline]", file=sys.stderr)
        sys.exit(2)
    url = sys.argv[1]
    date = sys.argv[2]
    applies = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    tagline = sys.argv[4] if len(sys.argv) > 4 else ""
    ok = send(url, date, applies, tagline)
    sys.exit(0)
