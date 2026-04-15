"""Twilio WhatsApp inbound webhook → taste.json updater.

Vercel deploys this as a serverless function at /api/twilio-whatsapp.
Twilio POSTs form-urlencoded payloads here whenever the reader texts the
bot. We:

  1. Verify the request really came from Twilio (signature check).
  2. Check the From number is whitelisted (single-user bot for now).
  3. Ask Claude Haiku to classify the intent and propose a patch:
       - add_like / add_skip       (taste-profile tweak)
       - update_voice              (tone change)
       - update_applies_rule       (flag rule change)
       - pause <days>              (don't send for N days)
       - show                      (echo current profile)
       - reset                     (restore defaults)
       - noop                      (ambiguous → ask back)
  4. For mutation intents: fetch taste.json from GitHub via the Contents
     API, apply the patch in-memory, PUT it back with a commit message.
  5. Reply to the user via TwiML so they see a confirmation in WhatsApp.

Secrets (Vercel env vars):
  TWILIO_AUTH_TOKEN         — for signature verification
  ALLOWED_WHATSAPP_FROM     — e.g. "whatsapp:+15551234567"
  ANTHROPIC_API_KEY         — Haiku classifier
  GH_TOKEN                  — fine-grained PAT with Contents:write on the repo
  GH_REPO                   — e.g. "raagulmanoharan/HN_magazine"
  GH_BRANCH                 — e.g. "main"
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, quote

import urllib.request
import urllib.error

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

TASTE_PATH = "taste.json"
HAIKU_MODEL = os.environ.get("ANTHROPIC_HAIKU_MODEL", "claude-haiku-4-5-20251001")

CLASSIFIER_SYSTEM = """\
You are the intent classifier for a one-reader WhatsApp bot that tunes a
daily HN-curation taste profile. The reader texts short messages; you emit
a strict JSON patch describing what to change. Never prose.

Schema:
{
  "intent": "add_like" | "add_skip" | "update_voice" | "update_applies_rule"
            | "pause" | "show" | "reset" | "noop",
  "payload": "<string — the phrase to add, the new rule, days to pause, etc.>",
  "reply": "<short confirmation to send back over WhatsApp, <= 160 chars>"
}

Guidance:
- "more rust stuff" → add_like, payload "Rust systems programming".
- "less crypto please" → add_skip, payload "crypto, tokens, NFTs".
- "pause 3 days" → pause, payload "3".
- "show me my profile" → show, payload "".
- "reset to defaults" → reset, payload "".
- Anything unclear → noop with a reply asking for clarification.
- The reply should be friendly and confirm the action taken (or ask back).
"""


# --------------------------------------------------------------------------
# Twilio signature verification
# --------------------------------------------------------------------------
def _twilio_signature_valid(url: str, params: dict, signature: str, token: str) -> bool:
    data = url + "".join(k + params[k] for k in sorted(params.keys()))
    digest = hmac.new(token.encode(), data.encode(), hashlib.sha1).digest()
    expected = base64.b64encode(digest).decode()
    return hmac.compare_digest(expected, signature)


# --------------------------------------------------------------------------
# GitHub Contents API: read + write taste.json
# --------------------------------------------------------------------------
def _gh_request(method: str, path: str, token: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "hn-magazine-bot",
        },
        data=json.dumps(body).encode() if body is not None else None,
    )
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _get_taste(token: str, repo: str, branch: str) -> tuple[dict, str]:
    """Returns (taste_dict, file_sha)."""
    data = _gh_request(
        "GET",
        f"/repos/{repo}/contents/{quote(TASTE_PATH)}?ref={quote(branch)}",
        token,
    )
    content = base64.b64decode(data["content"]).decode()
    return json.loads(content), data["sha"]


def _put_taste(token: str, repo: str, branch: str, taste: dict, sha: str, message: str) -> None:
    body = {
        "message": message,
        "content": base64.b64encode(
            json.dumps(taste, indent=2, ensure_ascii=False).encode()
        ).decode(),
        "sha": sha,
        "branch": branch,
    }
    _gh_request("PUT", f"/repos/{repo}/contents/{quote(TASTE_PATH)}", token, body)


# --------------------------------------------------------------------------
# Haiku classifier
# --------------------------------------------------------------------------
def _classify(text: str) -> dict:
    import anthropic

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=400,
        system=CLASSIFIER_SYSTEM,
        messages=[{"role": "user", "content": text}],
    )
    raw = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    raw = raw.strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        return {"intent": "noop", "payload": "", "reply": "Sorry, didn't catch that. Try: 'more rust', 'less crypto', 'pause 3 days', 'show', 'reset'."}
    return json.loads(raw[start : end + 1])


# --------------------------------------------------------------------------
# Patch application
# --------------------------------------------------------------------------
def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _log_change(taste: dict, change: str) -> None:
    taste.setdefault("recent_changes", []).append({"when": _now_iso(), "change": change})
    taste["recent_changes"] = taste["recent_changes"][-20:]
    taste["updated_at"] = _now_iso()


def _apply(taste: dict, intent: str, payload: str) -> str:
    """Mutate taste dict in-place. Returns the commit message."""
    if intent == "add_like":
        taste["profile"] = (taste.get("profile", "") + f"\n\nAlso loves: {payload}.").strip()
        _log_change(taste, f"added like: {payload}")
        return f"taste: add like — {payload}"
    if intent == "add_skip":
        taste["profile"] = (taste.get("profile", "") + f"\n\nAlso skip: {payload}.").strip()
        _log_change(taste, f"added skip: {payload}")
        return f"taste: add skip — {payload}"
    if intent == "update_voice":
        taste["voice"] = payload
        _log_change(taste, f"voice: {payload}")
        return "taste: update voice"
    if intent == "update_applies_rule":
        taste["applies_to_me_rule"] = payload
        _log_change(taste, f"applies rule: {payload}")
        return "taste: update applies-to-me rule"
    if intent == "pause":
        from datetime import datetime, timedelta, timezone
        try:
            days = int(payload)
        except (TypeError, ValueError):
            days = 1
        until = datetime.now(timezone.utc) + timedelta(days=days)
        taste["paused_until"] = until.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        _log_change(taste, f"paused for {days} day(s)")
        return f"taste: pause {days}d"
    if intent == "reset":
        taste["profile"] = ""
        taste["voice"] = ""
        taste["applies_to_me_rule"] = ""
        taste["paused_until"] = None
        _log_change(taste, "reset to defaults")
        return "taste: reset to defaults"
    raise ValueError(f"unsupported mutation intent: {intent}")


# --------------------------------------------------------------------------
# TwiML reply
# --------------------------------------------------------------------------
def _twiml(text: str) -> bytes:
    # Minimal TwiML response. Escape the essentials.
    safe = (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )
    return (
        f"<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        f"<Response><Message>{safe}</Message></Response>"
    ).encode()


# --------------------------------------------------------------------------
# Request handler (Vercel's Python runtime uses BaseHTTPRequestHandler)
# --------------------------------------------------------------------------
class handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 — required name
        try:
            self._handle()
        except Exception as e:
            log.exception("webhook error: %s", e)
            self._reply(_twiml("Bot hit an error — check logs."))

    def _handle(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode() if length else ""
        params_multi = parse_qs(raw, keep_blank_values=True)
        params = {k: v[0] for k, v in params_multi.items()}

        # 1. Signature check
        token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        signature = self.headers.get("X-Twilio-Signature", "")
        # Vercel terminates TLS; reconstruct the external URL Twilio signed.
        host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host", "")
        proto = self.headers.get("X-Forwarded-Proto", "https")
        full_url = f"{proto}://{host}{self.path}"
        if not token or not signature or not _twilio_signature_valid(full_url, params, signature, token):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"invalid signature")
            return

        # 2. Whitelist check
        sender = params.get("From", "")
        allowed = os.environ.get("ALLOWED_WHATSAPP_FROM", "")
        if allowed and sender != allowed:
            log.warning("rejected message from %s", sender)
            self._reply(_twiml("This bot is single-user for now."))
            return

        body = (params.get("Body") or "").strip()
        if not body:
            self._reply(_twiml("Send a tweak like 'more rust', 'less crypto', 'pause 3 days', 'show', or 'reset'."))
            return

        # 3. Classify
        result = _classify(body)
        intent = result.get("intent", "noop")
        payload = result.get("payload", "")
        reply = result.get("reply") or "Got it."

        # 4. Read-only intents
        gh_token = os.environ.get("GH_TOKEN", "")
        repo = os.environ.get("GH_REPO", "")
        branch = os.environ.get("GH_BRANCH", "main")

        if intent == "show":
            try:
                taste, _ = _get_taste(gh_token, repo, branch)
                summary = (
                    f"Profile: {(taste.get('profile') or '')[:300]}…\n\n"
                    f"Voice: {(taste.get('voice') or '')[:120]}\n\n"
                    f"Paused: {taste.get('paused_until') or 'no'}"
                )
                self._reply(_twiml(summary))
            except Exception as e:
                log.exception("show failed: %s", e)
                self._reply(_twiml("Couldn't fetch profile — check GH_TOKEN."))
            return

        if intent == "noop":
            self._reply(_twiml(reply))
            return

        # 5. Mutation intents
        try:
            taste, sha = _get_taste(gh_token, repo, branch)
            message = _apply(taste, intent, payload)
            _put_taste(gh_token, repo, branch, taste, sha, message)
            self._reply(_twiml(reply))
        except Exception as e:
            log.exception("mutation failed: %s", e)
            self._reply(_twiml("Saved locally but couldn't push to GitHub. Try again later."))

    def do_GET(self):  # noqa: N802
        # Handy liveness probe.
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"morning-edition webhook alive")

    def _reply(self, body: bytes, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
