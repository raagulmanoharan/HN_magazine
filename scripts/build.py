"""Build today's Morning Edition.

Steps:
  1. Fetch across the twenty enabled sources in parallel.
  2. Curate with Claude (or heuristic fallback).
  3. Render the magazine HTML.
  4. Write to magazines/YYYY-MM-DD.html.
  5. Re-render the landing page (index.html) and RSS feed (feed.xml).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import pathlib
import sys

import re

# Make script-directory imports work whether we're run as a module or a script.
HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from curate import curate                       # noqa: E402
from fetch_sources import fetch_all, _normalize_url  # noqa: E402
from render import fmt_date, render_magazine    # noqa: E402

ROOT = HERE.parent
MAGAZINES_DIR = ROOT / "magazines"
INDEX_PATH = ROOT / "index.html"
FEED_PATH = ROOT / "feed.xml"
LATEST_PATH = ROOT / "latest.json"
PUBLISHED_MANIFEST = MAGAZINES_DIR / ".published-urls.json"
SPILLOVER_PATH = MAGAZINES_DIR / ".spillover.json"

DEDUP_WINDOW_DAYS = 14
MANIFEST_RETENTION_DAYS = 60
MIN_CANDIDATES_AFTER_DEDUP = 25
SPILLOVER_MAX_AGE_DAYS = 3
SPILLOVER_PRIOR_DISCOUNT = 0.85

log = logging.getLogger("build")


# --------------------------------------------------------------------------
# Cross-issue deduplication
# --------------------------------------------------------------------------
def _load_manifest() -> dict[str, str]:
    """Returns {normalized_url: "YYYY-MM-DD"} of previously-published picks."""
    try:
        return json.loads(PUBLISHED_MANIFEST.read_text())
    except (FileNotFoundError, ValueError):
        return {}


def _save_manifest(manifest: dict[str, str], today: dt.date) -> None:
    cutoff = today - dt.timedelta(days=MANIFEST_RETENTION_DAYS)
    pruned = {}
    for url, date_str in manifest.items():
        try:
            if dt.date.fromisoformat(date_str) >= cutoff:
                pruned[url] = date_str
        except ValueError:
            continue
    PUBLISHED_MANIFEST.write_text(json.dumps(pruned, indent=2, sort_keys=True))


def _recent_urls(manifest: dict[str, str], today: dt.date) -> set[str]:
    cutoff = today - dt.timedelta(days=DEDUP_WINDOW_DAYS)
    out = set()
    for url, date_str in manifest.items():
        try:
            if dt.date.fromisoformat(date_str) >= cutoff:
                out.add(url)
        except ValueError:
            continue
    return out


# --------------------------------------------------------------------------
# Spillover — carry interesting runners-up to the next edition
# --------------------------------------------------------------------------
def _load_spillover(today: dt.date) -> list[dict]:
    """Load candidates from last build that weren't picked, drop stale ones."""
    try:
        data = json.loads(SPILLOVER_PATH.read_text())
    except (FileNotFoundError, ValueError):
        return []
    cutoff = today - dt.timedelta(days=SPILLOVER_MAX_AGE_DAYS)
    kept = []
    for item in data:
        saved = item.get("_spillover_date", "")
        try:
            if dt.date.fromisoformat(saved) >= cutoff:
                item["prior"] = round(float(item.get("prior", 0)) * SPILLOVER_PRIOR_DISCOUNT, 3)
                item["_from_spillover"] = True
                kept.append(item)
        except ValueError:
            continue
    return kept


def _save_spillover(candidates: list[dict], picked_urls: set[str], today: dt.date) -> None:
    """Save non-picked candidates as spillover for the next build."""
    today_iso = today.isoformat()
    keep = []
    for c in candidates:
        key = _normalize_url(c.get("url", ""))
        if key in picked_urls:
            continue
        c["_spillover_date"] = c.get("_spillover_date", today_iso)
        c.pop("_from_spillover", None)
        keep.append(c)
    keep.sort(key=lambda x: float(x.get("prior", 0)), reverse=True)
    SPILLOVER_PATH.write_text(json.dumps(keep[:50], indent=2))


# --------------------------------------------------------------------------
# Landing page
# --------------------------------------------------------------------------
def _extract_tagline(path: pathlib.Path) -> str:
    try:
        head = path.read_text(encoding="utf-8")[:2000]
        m = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', head)
        return m.group(1) if m else ""
    except Exception:
        return ""


def _issue_list() -> list[dict]:
    out = []
    for p in sorted(MAGAZINES_DIR.glob("*.html"), reverse=True):
        name = p.stem  # YYYY-MM-DD or weekly-YYYY-MM-DD
        is_weekly = name.startswith("weekly-")
        date_str = name.replace("weekly-", "")
        try:
            d = dt.date.fromisoformat(date_str)
        except ValueError:
            continue
        out.append({
            "date": d,
            "href": f"magazines/{p.name}",
            "weekly": is_weekly,
            "tagline": _extract_tagline(p),
        })
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
.issue-list .left{display:flex;flex-direction:column;gap:6px}
.issue-list .tagline{font-family:'Fraunces',serif;font-style:italic;font-weight:700;
  font-size:clamp(26px,2.8vw,38px);letter-spacing:-.01em;line-height:1.2}
.issue-list .d{font-family:'Inter',sans-serif;font-weight:500;font-size:clamp(16px,1.4vw,20px);
  letter-spacing:.08em;text-transform:uppercase;opacity:.55}
.issue-list .n{font-family:'Inter',sans-serif;font-size:20px;letter-spacing:.18em;
  text-transform:uppercase;opacity:.6}
.issue-list a:hover .d{color:#b63b1f}
.issue-list .weekly-badge{display:inline-block;background:#b63b1f;color:#f4ecd8;
  padding:4px 12px;font-family:'Inter',sans-serif;font-size:14px;font-weight:800;
  letter-spacing:.2em;text-transform:uppercase;border-radius:3px;vertical-align:middle;
  margin-left:12px}
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
            is_weekly = it.get("weekly", False)
            if is_weekly:
                week_num = d.isocalendar()[1]
                badge = '<span class="weekly-badge">Weekly</span>'
                issue_label = f"Week {week_num:02d}"
            else:
                issue_no = (d - dt.date(2025, 1, 1)).days + 1
                badge = ""
                issue_label = f"Issue No. {issue_no:04d}"
            tagline = it.get("tagline", "")
            tagline_html = f'<span class="tagline">{tagline}</span>' if tagline else ""
            title_line = tagline_html if tagline_html else f'<span class="tagline">{label}</span>'
            items.append(
                f'<li><a href="{it["href"]}">'
                f'<span class="left">{title_line}<span class="d">{label}{badge}</span></span>'
                f'<span class="n">{issue_label}</span>'
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
<meta name="description" content="A daily, hand-curated magazine across twenty sources.">
<link rel="alternate" type="application/rss+xml" title="Morning Edition" href="feed.xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,700;0,9..144,900;1,9..144,400;1,9..144,900&family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
<style>{INDEX_CSS}</style>
</head>
<body>
<div class="wrap">
  <header class="masthead">
    <h1>Morning Edition</h1>
    <div class="sub">A one-reader daily.<br>Hand-picked across twenty sources while you slept.</div>
  </header>
  {body}
  <footer>Latest issue: {latest or "—"} &middot; Built with Claude</footer>
</div>
</body>
</html>
"""


# --------------------------------------------------------------------------
# RSS feed
# --------------------------------------------------------------------------
def render_feed(issues: list[dict], base_url: str) -> str:
    from email.utils import format_datetime
    base = base_url.rstrip("/")
    items = []
    for it in issues[:30]:
        d = it["date"]
        pub = dt.datetime(d.year, d.month, d.day, 11, 0, tzinfo=dt.timezone.utc)
        label = "Weekly" if it.get("weekly") else "Morning Edition"
        tagline = it.get("tagline", "")
        title = tagline if tagline else f"{label} — {fmt_date(d)}"
        link = f"{base}/{it['href']}"
        items.append(
            f"<item>"
            f"<title>{_xml_escape(title)}</title>"
            f"<link>{link}</link>"
            f"<guid isPermaLink=\"true\">{link}</guid>"
            f"<pubDate>{format_datetime(pub)}</pubDate>"
            f"<description>{_xml_escape(f'{label} — {fmt_date(d)}')}</description>"
            f"</item>"
        )
    items_xml = "\n    ".join(items)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>Morning Edition</title>
  <description>A daily, hand-curated magazine across twenty sources.</description>
  <link>{base}/</link>
  <atom:link href="{base}/feed.xml" rel="self" type="application/rss+xml"/>
  <language>en-us</language>
  {items_xml}
</channel>
</rss>
"""


def _xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def render_latest(issues: list[dict], base_url: str) -> str:
    base = base_url.rstrip("/")
    if not issues:
        return json.dumps({"title": "No issues yet", "url": base, "date": "", "edition": ""})
    it = issues[0]
    d = it["date"]
    label = "weekly" if it.get("weekly") else "morning"
    tagline = it.get("tagline", "")
    title = tagline if tagline else f"Morning Edition — {fmt_date(d)}"
    return json.dumps({
        "title": title,
        "url": f"{base}/{it['href']}",
        "date": d.isoformat(),
        "edition": label,
    }, indent=2)


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------
def build(date: dt.date, public_base_url: str | None = None) -> dict:
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
    stories = fetch_all(enabled=enabled, top_k=80)
    log.info("fetched %d candidates", len(stories))

    # Merge spillover from the previous build (runners-up that are still fresh).
    spillover = _load_spillover(date)
    if spillover:
        existing_urls = {_normalize_url(s.get("url", "")) for s in stories}
        added = [s for s in spillover if _normalize_url(s.get("url", "")) not in existing_urls]
        stories.extend(added)
        log.info("spillover: merged %d carried-over candidates", len(added))

    # Cross-issue dedup: drop anything we ran in the last DEDUP_WINDOW_DAYS.
    manifest = _load_manifest()
    recent = _recent_urls(manifest, date)
    if recent:
        before = len(stories)
        filtered = [s for s in stories if _normalize_url(s.get("url", "")) not in recent]
        if len(filtered) >= MIN_CANDIDATES_AFTER_DEDUP:
            log.info("dedup: dropped %d already-published stories (%d → %d)",
                     before - len(filtered), before, len(filtered))
            stories = filtered
        else:
            log.warning("dedup: would leave only %d candidates; skipping filter",
                        len(filtered))

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

    # Record today's picks in the published-URLs manifest.
    today_iso = date.isoformat()
    picked_urls = set()
    for pick in curation.get("picks", []):
        key = _normalize_url(pick.get("url", ""))
        if key:
            picked_urls.add(key)
            if key not in manifest:
                manifest[key] = today_iso
    _save_manifest(manifest, date)
    log.info("manifest: %d urls tracked", len(manifest))

    # Save runners-up as spillover for the next build.
    _save_spillover(stories, picked_urls, date)
    log.info("spillover: saved runners-up for next build")

    # Landing page + RSS feed
    issues = _issue_list()
    INDEX_PATH.write_text(render_index(issues), encoding="utf-8")
    log.info("wrote %s", INDEX_PATH)
    if public_base_url:
        FEED_PATH.write_text(render_feed(issues, public_base_url), encoding="utf-8")
        LATEST_PATH.write_text(render_latest(issues, public_base_url), encoding="utf-8")
        log.info("wrote %s, %s", FEED_PATH, LATEST_PATH)

    applies_count = sum(1 for p in curation.get("picks", []) if p.get("applies_to_me"))
    return {
        "date": date.isoformat(),
        "path": str(out_path.relative_to(ROOT)),
        "applies_count": applies_count,
        "tagline": curation.get("issue_tagline", ""),
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Build today's Morning Edition magazine")
    ap.add_argument("--date", help="ISO date YYYY-MM-DD (default: today UTC)")
    ap.add_argument("--public-base-url", default=os.environ.get("PUBLIC_BASE_URL", ""),
                    help="Public origin for Pages, e.g. https://user.github.io/HN_magazine")
    args = ap.parse_args()

    date = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    result = build(date, public_base_url=args.public_base_url or None)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
