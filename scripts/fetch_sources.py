"""Fetch candidate stories from many sources, pre-ranked.

Each source returns a uniform dict so the curator can compare across them.
Sources fail independently — a broken feed doesn't kill the build.

Output shape per item:
    {
      "id":                 "lobsters:abc123",
      "title":              "...",
      "url":                "https://...",
      "source":             "lobsters",
      "score":              42,     # upvotes / stars / 0
      "comments":           7,      # comment count / 0
      "text":               "snippet / description",
      "published_at":       "2026-04-15T10:00:00Z",
      "rank_within_source": 1,
      "hn_url":             "https://lobste.rs/s/abc123",  # discussion URL if any
      "prior":              0.82,   # local 0..1 priority signal
    }

The curator receives the items pre-ranked by `prior` descending, after URL
deduplication. `prior` is advisory — the curator is told to treat it as a
tiebreaker, not a verdict.
"""
from __future__ import annotations

import concurrent.futures
import json
import logging
import math
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from fetch_hn import fetch_front_page

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Source registry — tuned for a UX designer inclined to AI + tech.
# Higher weight = stronger baseline assumption that items are worth surfacing.
# --------------------------------------------------------------------------
SOURCE_WEIGHTS = {
    "anthropic":        0.98,
    "openai":           0.92,
    "deepmind":         0.86,
    "simonwillison":    0.88,
    "sidebar":          0.84,   # UX/design signal is scarce, weight high
    "github_trending":  0.82,
    "lobsters":         0.80,
    "hn":               0.75,
    "quanta":           0.72,
    "schneier":         0.66,
    "producthunt":      0.55,
}

# Per-source fetch caps. Keep lab blogs small (low volume, high signal) and
# HN trimmed (otherwise it numerically drowns everything else).
DEFAULT_LIMITS = {
    "hn":              25,
    "lobsters":        15,
    "github_trending": 12,
    "quanta":           8,
    "producthunt":      8,
    "anthropic":        5,
    "openai":           5,
    "deepmind":         5,
    "simonwillison":    5,
    "schneier":         5,
    "sidebar":          5,
}

# Staleness cap per source, in days. Blog feeds often contain older posts;
# we don't want last month's article to land in today's front page.
FRESHNESS_DAYS = {
    "hn": 3,
    "lobsters": 3,
    "github_trending": 7,
    "anthropic": 14,
    "openai": 14,
    "deepmind": 14,
    "simonwillison": 7,
    "schneier": 10,
    "sidebar": 3,
    "quanta": 14,
    "producthunt": 3,
}

# --------------------------------------------------------------------------
# Feed URLs. Edit these if a publisher changes their RSS path.
# --------------------------------------------------------------------------
FEED_URLS = {
    "anthropic":     "https://www.anthropic.com/news/rss.xml",
    "openai":        "https://openai.com/news/rss.xml",
    "deepmind":      "https://deepmind.google/blog/rss.xml",
    "simonwillison": "https://simonwillison.net/atom/everything/",
    "schneier":      "https://www.schneier.com/feed/atom/",
    "sidebar":       "https://sidebar.io/feed.xml",
    "quanta":        "https://www.quantamagazine.org/feed/",
    "producthunt":   "https://www.producthunt.com/feed",
}

# Many sites (Lobste.rs, Product Hunt, some CDN-fronted blogs) 403 on
# default urllib UAs. Pose as a normal browser.
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)


# ==========================================================================
# Helpers
# ==========================================================================
def _http_get(url: str, timeout: int = 15) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(t: Any) -> datetime | None:
    """Best-effort parse of whatever published-date shape the feed hands us."""
    if t is None:
        return None
    if isinstance(t, datetime):
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    if isinstance(t, (int, float)):
        return datetime.fromtimestamp(t, tz=timezone.utc)
    if isinstance(t, str):
        for fmt in (
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S%z",
            "%Y-%m-%d",
        ):
            try:
                dt = datetime.strptime(t, fmt)
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(t.replace("Z", "+00:00"))
        except ValueError:
            return None
    # feedparser's struct_time
    try:
        import time
        return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)
    except Exception:
        return None


def _fresh(published: datetime | None, days: int) -> bool:
    if published is None:
        return True  # don't drop entries with missing dates
    return (_now_utc() - published) <= timedelta(days=days)


def _normalize_url(u: str) -> str:
    """Collapse a URL to a dedup key: lowercase host, no www, no trailing
    slash, strip common tracking/utm params."""
    if not u:
        return ""
    try:
        p = urllib.parse.urlsplit(u)
    except ValueError:
        return u
    host = (p.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = (p.path or "").rstrip("/") or "/"
    # Drop utm_* and common tracking params
    q = [
        (k, v)
        for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True)
        if not k.lower().startswith(("utm_", "ref_", "fbclid", "gclid"))
    ]
    query = urllib.parse.urlencode(q)
    # Plain key: "host/path?query" (no scheme, no leading //).
    return f"{host}{path}" + (f"?{query}" if query else "")


def _prior(source: str, rank: int, score: int | None) -> float:
    """Combine source weight, within-source rank, and raw score into a
    single 0..~1.2 priority signal. Relevance > popularity: the score
    bonus is capped so a viral HN post can't outweigh a relevant Anthropic
    launch that sits at rank 1 on its own feed."""
    w = SOURCE_WEIGHTS.get(source, 0.5)
    rank_factor = 1.0 / (1.0 + 0.15 * max(rank - 1, 0))  # 1.0, 0.87, 0.77, 0.69…
    raw = max(score or 0, 0)
    # Cap score contribution tight so a viral HN post can't outrank a
    # fresh Anthropic / OpenAI launch sitting at rank 1 on its own feed.
    score_factor = min(math.log10(raw + 1) / 8.0, 0.15)
    return round(w * rank_factor + score_factor, 3)


def _snippet(text: str, n: int = 240) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:n]


def _iso(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ==========================================================================
# Source fetchers
# ==========================================================================
def _fetch_hn(limit: int) -> list[dict]:
    stories = fetch_front_page(limit)
    out = []
    for i, s in enumerate(stories):
        out.append({
            "id":    f"hn:{s['id']}",
            "title": s["title"],
            "url":   s.get("url") or s.get("hn_url", ""),
            "source": "hn",
            "score":  int(s.get("score", 0)),
            "comments": int(s.get("descendants", 0) or 0),
            "text":   _snippet(s.get("text", "")),
            "published_at": _iso(_parse_time(s.get("time"))),
            "rank_within_source": i + 1,
            "hn_url": s.get("hn_url", ""),
        })
    return out


def _fetch_lobsters(limit: int) -> list[dict]:
    data = json.loads(_http_get("https://lobste.rs/hottest.json").decode("utf-8"))
    out = []
    for i, s in enumerate(data[:limit]):
        published = _parse_time(s.get("created_at"))
        out.append({
            "id":    f"lobsters:{s['short_id']}",
            "title": s["title"],
            "url":   s.get("url") or s.get("comments_url", ""),
            "source": "lobsters",
            "score":  int(s.get("score", 0)),
            "comments": int(s.get("comment_count", 0)),
            "text":   _snippet(s.get("description") or ""),
            "published_at": _iso(published),
            "rank_within_source": i + 1,
            "hn_url": s.get("comments_url", ""),
        })
    return out


def _fetch_github_trending(limit: int) -> list[dict]:
    """Official Search API stands in for "trending": repos created in the
    last 7 days, sorted by stars desc. No scraping, no auth required."""
    since = (_now_utc() - timedelta(days=7)).date().isoformat()
    q = f"created:>{since} stars:>20"
    url = (
        "https://api.github.com/search/repositories?"
        + urllib.parse.urlencode({
            "q": q, "sort": "stars", "order": "desc", "per_page": str(limit),
        })
    )
    req = urllib.request.Request(url, headers={
        "User-Agent": _USER_AGENT,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    out = []
    for i, r in enumerate(data.get("items", [])[:limit]):
        out.append({
            "id":    f"github:{r['id']}",
            "title": f"{r['full_name']} — {r.get('description') or ''}".strip(" —"),
            "url":   r["html_url"],
            "source": "github_trending",
            "score":  int(r.get("stargazers_count", 0)),
            "comments": int(r.get("open_issues_count", 0) or 0),
            "text":   _snippet(r.get("description") or ""),
            "published_at": _iso(_parse_time(r.get("created_at"))),
            "rank_within_source": i + 1,
            "hn_url": "",
        })
    return out


_ATOM_NS = "{http://www.w3.org/2005/Atom}"


def _parse_rss_or_atom(xml_bytes: bytes) -> list[dict]:
    """Minimal RSS 2.0 + Atom parser using stdlib. Returns a list of
    entries with keys: title, link, summary, published, guid. Robust
    enough for the handful of feeds we care about; no external deps."""
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise ValueError(f"feed XML parse failed: {e}")

    entries: list[dict] = []

    # RSS 2.0: <rss><channel><item>...
    for item in root.iterfind(".//item"):
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or "").strip()
        entries.append({
            "title":     (item.findtext("title") or "").strip(),
            "link":      link,
            "summary":   (item.findtext("description") or "").strip(),
            "published": (item.findtext("pubDate") or "").strip(),
            "guid":      guid or link,
        })
        if len(entries) >= 50:
            break

    # Atom: <feed><entry>...
    if not entries:
        for entry in root.iterfind(f"{_ATOM_NS}entry"):
            link = ""
            for ln in entry.iterfind(f"{_ATOM_NS}link"):
                rel = ln.get("rel", "alternate")
                if rel == "alternate" or not link:
                    link = (ln.get("href") or "").strip()
                    if rel == "alternate":
                        break
            published = (
                entry.findtext(f"{_ATOM_NS}published")
                or entry.findtext(f"{_ATOM_NS}updated")
                or ""
            ).strip()
            summary = (
                entry.findtext(f"{_ATOM_NS}summary")
                or entry.findtext(f"{_ATOM_NS}content")
                or ""
            ).strip()
            guid = (entry.findtext(f"{_ATOM_NS}id") or link).strip()
            entries.append({
                "title":     (entry.findtext(f"{_ATOM_NS}title") or "").strip(),
                "link":      link,
                "summary":   summary,
                "published": published,
                "guid":      guid,
            })
            if len(entries) >= 50:
                break

    return entries


def _parse_rss_date(s: str) -> datetime | None:
    """Parse an RFC-822 / ISO-8601 feed date, returning UTC."""
    if not s:
        return None
    # ISO-8601 first (Atom)
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    # RFC-822 (RSS pubDate)
    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _fetch_feed(source: str, limit: int) -> list[dict]:
    """Generic RSS/Atom fetcher using stdlib XML."""
    url = FEED_URLS.get(source)
    if not url:
        return []
    raw = _http_get(url, timeout=20)
    entries = _parse_rss_or_atom(raw)
    out = []
    for i, e in enumerate(entries[:limit]):
        published = _parse_rss_date(e.get("published", ""))
        link = e.get("link") or ""
        out.append({
            "id":    f"{source}:{e.get('guid') or link}",
            "title": e.get("title") or "",
            "url":   link,
            "source": source,
            "score":  0,  # no native popularity signal from blog feeds
            "comments": 0,
            "text":   _snippet(e.get("summary") or ""),
            "published_at": _iso(published),
            "rank_within_source": i + 1,
            "hn_url": "",
        })
    return out


FETCHERS: dict[str, Callable[[int], list[dict]]] = {
    "hn":              _fetch_hn,
    "lobsters":        _fetch_lobsters,
    "github_trending": _fetch_github_trending,
    "anthropic":       lambda n: _fetch_feed("anthropic", n),
    "openai":          lambda n: _fetch_feed("openai", n),
    "deepmind":        lambda n: _fetch_feed("deepmind", n),
    "simonwillison":   lambda n: _fetch_feed("simonwillison", n),
    "schneier":        lambda n: _fetch_feed("schneier", n),
    "sidebar":         lambda n: _fetch_feed("sidebar", n),
    "quanta":          lambda n: _fetch_feed("quanta", n),
    "producthunt":     lambda n: _fetch_feed("producthunt", n),
}


# ==========================================================================
# Orchestrator
# ==========================================================================
def fetch_all(
    enabled: dict[str, bool] | None = None,
    limits: dict[str, int] | None = None,
    top_k: int = 60,
) -> list[dict]:
    """Fetch from every enabled source in parallel, filter stale items,
    dedup by normalized URL, attach `prior`, return the top `top_k`
    sorted by `prior` descending."""
    enabled = enabled or {}
    limits = {**DEFAULT_LIMITS, **(limits or {})}

    active = [s for s in FETCHERS if enabled.get(s, True)]
    log.info("fetching from %d sources: %s", len(active), ", ".join(active))

    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(active), 10)) as pool:
        future_to_source = {
            pool.submit(FETCHERS[s], limits.get(s, 10)): s for s in active
        }
        for fut in concurrent.futures.as_completed(future_to_source):
            s = future_to_source[fut]
            try:
                items = fut.result()
                # Freshness filter
                days = FRESHNESS_DAYS.get(s, 14)
                fresh = [
                    it for it in items
                    if _fresh(_parse_time(it.get("published_at")), days)
                ]
                log.info("  %-16s → %d items (%d fresh)", s, len(items), len(fresh))
                results.extend(fresh)
            except Exception as e:
                log.warning("  %-16s → FAILED: %s", s, e)

    # Dedup by normalized URL, keeping the item with the strongest source weight.
    by_url: dict[str, dict] = {}
    for it in results:
        key = _normalize_url(it["url"]) or it["id"]
        prev = by_url.get(key)
        if prev is None or SOURCE_WEIGHTS.get(it["source"], 0) > SOURCE_WEIGHTS.get(prev["source"], 0):
            by_url[key] = it

    deduped = list(by_url.values())

    # Attach prior and sort.
    for it in deduped:
        it["prior"] = _prior(it["source"], it["rank_within_source"], it.get("score"))

    deduped.sort(key=lambda it: it["prior"], reverse=True)

    log.info("candidates: %d raw → %d after dedup → top %d", len(results), len(deduped), min(top_k, len(deduped)))
    return deduped[:top_k]


# --------------------------------------------------------------------------
# CLI for manual inspection
# --------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    items = fetch_all(top_k=60)
    json.dump(items, sys.stdout, indent=2)
