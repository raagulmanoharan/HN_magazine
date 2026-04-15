"""Build today's Morning Edition.

Steps:
  1. Fetch across the eleven enabled sources in parallel.
  2. Curate with Claude (or heuristic fallback).
  3. Render the magazine HTML.
  4. Write to magazines/YYYY-MM-DD.html.
  5. Re-render the landing page (index.html) listing every issue.
  6. Optionally send a WhatsApp notification with the public URL.

The script exits 0 on success so GitHub Actions can continue to the deploy
and commit steps even if notification fails.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import pathlib
import sys

# Make script-directory imports work whether we're run as a module or a script.
HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from curate import curate                       # noqa: E402
from fetch_sources import fetch_all             # noqa: E402
from render import fmt_date, render_magazine    # noqa: E402
import notify                                    # noqa: E402

ROOT = HERE.parent
MAGAZINES_DIR = ROOT / "magazines"
INDEX_PATH = ROOT / "index.html"

log = logging.getLogger("build")


# --------------------------------------------------------------------------
# Landing page
# --------------------------------------------------------------------------
def _issue_list() -> list[dict]:
    out = []
    for p in sorted(MAGAZINES_DIR.glob("*.html"), reverse=True):
        name = p.stem  # YYYY-MM-DD
        try:
            d = dt.date.fromisoformat(name)
        except ValueError:
            continue
        out.append({"date": d, "href": f"magazines/{p.name}"})
    return out


INDEX_CSS = r"""
*,*::before,*::after{box-sizing:border-box}
html,body{margin:0;padding:0}
body{font-family:'Inter',system-ui,sans-serif;font-size:22px;line-height:1.5;
  color:#17140e;background:#f4ecd8;-webkit-font-smoothing:antialiased}
.wrap{max-width:1100px;margin:0 auto;padding:clamp(48px,6vw,110px)}
.masthead{display:flex;justify-content:space-between;align-items:flex-end;
  border-bottom:4px solid #17140e;padding-bottom:18px;margin-bottom:56px;flex-wrap:wrap;gap:18px}
h1{font-family:'Fraunces',serif;font-style:italic;font-weight:900;
  font-size:clamp(48px,7vw,104px);margin:0;line-height:.95;letter-spacing:-.02em}
.sub{font-family:'Fraunces',serif;font-size:clamp(24px,2.4vw,34px);font-style:italic;font-weight:400;
  max-width:42ch;line-height:1.35}
.issue-list{margin-top:56px;list-style:none;padding:0}
.issue-list li{border-bottom:1.5px solid rgba(23,20,14,.2);padding:24px 0}
.issue-list a{display:flex;justify-content:space-between;align-items:baseline;gap:24px;
  color:#17140e;text-decoration:none;flex-wrap:wrap}
.issue-list .d{font-family:'Fraunces',serif;font-weight:700;font-size:clamp(28px,3vw,42px);
  letter-spacing:-.01em}
.issue-list .n{font-family:'Inter',sans-serif;font-size:20px;letter-spacing:.18em;
  text-transform:uppercase;opacity:.6}
.issue-list a:hover .d{color:#b63b1f}
.empty{font-family:'Fraunces',serif;font-style:italic;font-size:26px;opacity:.7}
footer{margin-top:96px;padding-top:24px;border-top:1.5px solid rgba(23,20,14,.2);
  font-size:18px;letter-spacing:.18em;text-transform:uppercase;opacity:.6}
"""


def render_index(issues: list[dict]) -> str:
    if not issues:
        body = '<p class="empty">No issues yet. The first one drops tomorrow at 7am.</p>'
    else:
        items = []
        for i, it in enumerate(issues):
            d = it["date"]
            label = d.strftime("%A, %B %-d, %Y")
            issue_no = (d - dt.date(2025, 1, 1)).days + 1
            items.append(
                f'<li><a href="{it["href"]}">'
                f'<span class="d">{label}</span>'
                f'<span class="n">Issue No. {issue_no:04d}</span>'
                f"</a></li>"
            )
        body = f'<ul class="issue-list">{"".join(items)}</ul>'

    latest = issues[0]["date"].isoformat() if issues else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Morning Edition</title>
<meta name="description" content="A daily, hand-curated magazine across eleven sources.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,700;0,9..144,900;1,9..144,400;1,9..144,900&family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
<style>{INDEX_CSS}</style>
</head>
<body>
<div class="wrap">
  <header class="masthead">
    <h1>Morning Edition</h1>
    <div class="sub">A one-reader daily.<br>Hand-picked across eleven sources while you slept.</div>
  </header>
  {body}
  <footer>Latest issue: {latest or "—"} &middot; Built with Claude</footer>
</div>
</body>
</html>
"""


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------
def build(date: dt.date, public_base_url: str | None = None, notify_enabled: bool = True) -> dict:
    MAGAZINES_DIR.mkdir(parents=True, exist_ok=True)

    log.info("fetching candidates from all sources ...")
    # Read per-source enable flags from taste.json if present.
    taste_path = ROOT / "taste.json"
    enabled: dict[str, bool] = {}
    try:
        taste = json.loads(taste_path.read_text())
        sources_cfg = taste.get("sources") or {}
        enabled = {k: bool(v.get("enabled", True)) for k, v in sources_cfg.items()}
    except Exception:
        pass
    stories = fetch_all(enabled=enabled, top_k=60)
    log.info("fetched %d candidates", len(stories))

    log.info("curating ...")
    curation = curate(stories)

    # Persist the raw curation for debugging.
    debug_dir = MAGAZINES_DIR / ".curation"
    debug_dir.mkdir(exist_ok=True)
    (debug_dir / f"{date.isoformat()}.json").write_text(json.dumps(curation, indent=2))

    log.info("rendering ...")
    html_out = render_magazine(curation, date)

    out_path = MAGAZINES_DIR / f"{date.isoformat()}.html"
    out_path.write_text(html_out, encoding="utf-8")
    log.info("wrote %s (%d bytes)", out_path, len(html_out))

    # Landing page
    INDEX_PATH.write_text(render_index(_issue_list()), encoding="utf-8")
    log.info("wrote %s", INDEX_PATH)

    applies_count = sum(1 for p in curation.get("picks", []) if p.get("applies_to_me"))
    result = {
        "date": date.isoformat(),
        "path": str(out_path.relative_to(ROOT)),
        "applies_count": applies_count,
        "tagline": curation.get("issue_tagline", ""),
    }

    if notify_enabled and public_base_url:
        url = public_base_url.rstrip("/") + f"/magazines/{date.isoformat()}.html"
        if _is_paused(date):
            log.info("notification suppressed — reader is paused")
            result["notified"] = False
            result["paused"] = True
            result["public_url"] = url
        else:
            try:
                notify.send(url, fmt_date(date), applies_count, result["tagline"])
                result["notified"] = True
                result["public_url"] = url
            except Exception as e:
                log.exception("notification failed: %s", e)
                result["notified"] = False

    return result


def _is_paused(today: dt.date) -> bool:
    """Returns True if taste.json has paused_until >= today."""
    taste_path = ROOT / "taste.json"
    try:
        taste = json.loads(taste_path.read_text())
    except Exception:
        return False
    until = taste.get("paused_until")
    if not until:
        return False
    try:
        # Accepts "YYYY-MM-DDTHH:MM:SSZ" — compare dates only.
        until_date = dt.date.fromisoformat(until[:10])
    except ValueError:
        return False
    return today <= until_date


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Build today's Morning Edition magazine")
    ap.add_argument("--date", help="ISO date YYYY-MM-DD (default: today UTC)")
    ap.add_argument("--public-base-url", default=os.environ.get("PUBLIC_BASE_URL", ""),
                    help="Public origin for Pages, e.g. https://user.github.io/HN_magazine")
    ap.add_argument("--no-notify", action="store_true",
                    help="Skip the WhatsApp notification step")
    args = ap.parse_args()

    date = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    result = build(
        date,
        public_base_url=args.public_base_url or None,
        notify_enabled=not args.no_notify,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
