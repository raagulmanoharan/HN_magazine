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


def send(url: str, issue_date: str, applies_count: int = 0, tagline: str = "") -> bool:
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    sender = os.environ.get("TWILIO_WHATSAPP_FROM")
    recipient = os.environ.get("WHATSAPP_TO")

    if not all([sid, token, sender, recipient]):
        log.warning("Twilio env vars missing; skipping WhatsApp notification.")
        return False

    try:
        from twilio.rest import Client
    except ImportError:
        log.warning("twilio package not installed; skipping WhatsApp notification.")
        return False

    body = _format_message(url, issue_date, applies_count, tagline)
    client = Client(sid, token)
    msg = client.messages.create(from_=sender, to=recipient, body=body)
    log.info("WhatsApp message queued: sid=%s", msg.sid)
    return True


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
    sys.exit(0 if ok else 1)
