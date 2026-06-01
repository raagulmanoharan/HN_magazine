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
    # Lab blogs — high weight, low volume, almost always relevant
    "anthropic":        0.98,
    "openai":           0.92,
    "simonwillison":    0.88,
    "deepmind":         0.86,
    "meta_ai":          0.84,
    "sidebar":          0.84,   # UX/design signal is scarce, weight high
    # Design + UX sources — weighted high to balance the tech-heavy mix
    "smashingmag":      0.84,
    "dense_discovery":  0.83,   # Kai Brach's weekly — very high craft/signal ratio
    "nngroup":          0.82,
    "heydesigner":      0.80,   # daily design links aggregator
    "figma":            0.80,
    "codrops":          0.78,
    # AI thought leaders / newsletters
    "karpathy":         0.86,
    "importai":         0.84,
    "lilianweng":       0.82,
    "interconnects":    0.80,
    # Aggregators + community
    "github_trending":  0.82,
    "lobsters":         0.80,
    "huggingface":      0.78,
    "reddit_ml":        0.76,
    "hn":               0.75,
    "quanta":           0.72,
    "schneier":         0.66,
    # Industry press — noisier, filter hard
    "techcrunch":       0.62,
    "theverge":         0.58,
    "producthunt":      0.55,
}

# Per-source fetch caps. Keep lab blogs small (low volume, high signal) and
# HN trimmed (otherwise it numerically drowns everything else).
DEFAULT_LIMITS = {
    "hn":               25,
    "lobsters":         15,
    "reddit_ml":        20,
    "github_trending":  12,
    "huggingface":      10,
    "quanta":            8,
    "producthunt":       8,
    "techcrunch":        8,
    "theverge":          8,
    "anthropic":         5,
    "openai":            5,
    "deepmind":          5,
    "meta_ai":           5,
    "simonwillison":     5,
    "karpathy":          5,
    "importai":          5,
    "lilianweng":        5,
    "interconnects":     5,
    "schneier":          5,
    "sidebar":           5,
    "smashingmag":       8,
    "dense_discovery":   5,
    "nngroup":           5,
    "heydesigner":       8,
    "figma":             5,
    "codrops":           8,
}

FRESHNESS_DAYS = {
    "hn":               3,
    "lobsters":         3,
    "reddit_ml":        3,
    "github_trending":  7,
    "huggingface":      7,
    "anthropic":        14,
    "openai":           14,
    "deepmind":         14,
    "meta_ai":          14,
    "simonwillison":    7,
    "karpathy":         14,
    "importai":         7,
    "lilianweng":       14,
    "interconnects":    7,
    "schneier":         10,
    "sidebar":          3,
    "smashingmag":      3,
    "dense_discovery":  7,   # weekly newsletter; give the full week to surface
    "nngroup":          7,
    "heydesigner":      3,   # daily links; 3 days is plenty
    "figma":            7,
    "codrops":          5,
    "quanta":           14,
    "techcrunch":       3,
    "theverge":         3,
    "producthunt":      3,
}

# --------------------------------------------------------------------------
# Feed URLs. Edit these if a publisher changes their RSS path.
# --------------------------------------------------------------------------
FEED_URLS = {
    "anthropic":        "https://www.anthropic.com/news/rss.xml",
    "openai":           "https://openai.com/news/rss.xml",
    "deepmind":         "https://deepmind.google/blog/rss.xml",
    "meta_ai":          "https://ai.meta.com/blog/rss/",
    "simonwillison":    "https://simonwillison.net/atom/everything/",
    "karpathy":         "https://karpathy.ai/rss.xml",
    "importai":         "https://importai.substack.com/feed",
    "lilianweng":       "https://lilianweng.github.io/index.xml",
    "interconnects":    "https://www.interconnects.ai/feed",
    "schneier":         "https://www.schneier.com/feed/atom/",
    "sidebar":          "https://sidebar.io/feed.xml",
    "smashingmag":      "https://www.smashingmagazine.com/feed/",
    "dense_discovery":  "https://www.densediscovery.com/feed.xml",
    "nngroup":          "https://www.nngroup.com/feed/rss/",
    "heydesigner":      "https://heydesigner.com/feed/",
    "figma":            "https://www.figma.com/blog/feed/",
    "codrops":          "https://tympanus.net/codrops/feed/",
    "quanta":           "https://www.quantamagazine.org/feed/",
    "techcrunch":       "https://techcrunch.com/category/artificial-intelligence/feed/",
    "theverge":         "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "producthunt":      "https://www.producthunt.com/feed",
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


def _fetch_feed(source: str, limit: int, url_override: str | None = None) -> list[dict]:
    """Generic RSS/Atom fetcher using stdlib XML."""
    url = url_override or FEED_URLS.get(source)
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


def _fetch_reddit(limit: int) -> list[dict]:
    """Fetch hot posts from r/MachineLearning + r/LocalLLaMA."""
    subs = ["MachineLearning", "LocalLLaMA"]
    out = []
    per_sub = max(limit // len(subs), 5)
    for sub in subs:
        url = f"https://www.reddit.com/r/{sub}/hot.json?limit={per_sub}&raw_json=1"
        try:
            data = json.loads(_http_get(url, timeout=15).decode("utf-8"))
        except Exception as e:
            log.warning("reddit r/%s failed: %s", sub, e)
            continue
        for i, child in enumerate(data.get("data", {}).get("children", [])):
            d = child.get("data", {})
            if d.get("stickied"):
                continue
            link = d.get("url") or ""
            if link.startswith("/r/"):
                link = f"https://www.reddit.com{link}"
            permalink = f"https://www.reddit.com{d.get('permalink', '')}"
            published = _parse_time(d.get("created_utc"))
            out.append({
                "id":    f"reddit:{d.get('id', '')}",
                "title": d.get("title", ""),
                "url":   link if not link.startswith("https://www.reddit.com/r/") else permalink,
                "source": "reddit_ml",
                "score":  int(d.get("score", 0)),
                "comments": int(d.get("num_comments", 0)),
                "text":   _snippet(d.get("selftext") or ""),
                "published_at": _iso(published),
                "rank_within_source": len(out) + 1,
                "hn_url": permalink,
            })
    return out[:limit]


def _fetch_huggingface(limit: int) -> list[dict]:
    """Fetch trending daily papers from Hugging Face."""
    url = "https://huggingface.co/api/daily_papers"
    data = json.loads(_http_get(url, timeout=15).decode("utf-8"))
    out = []
    for i, item in enumerate(data[:limit]):
        paper = item.get("paper", {})
        pid = paper.get("id", "")
        published = _parse_time(paper.get("publishedAt"))
        out.append({
            "id":    f"hf:{pid}",
            "title": paper.get("title", ""),
            "url":   f"https://huggingface.co/papers/{pid}" if pid else "",
            "source": "huggingface",
            "score":  int(item.get("numLikes", 0)),
            "comments": int(item.get("numComments", 0)),
            "text":   _snippet(paper.get("summary") or ""),
            "published_at": _iso(published),
            "rank_within_source": i + 1,
            "hn_url": "",
        })
    return out


FETCHERS: dict[str, Callable[[int], list[dict]]] = {
    "hn":              _fetch_hn,
    "lobsters":        _fetch_lobsters,
    "reddit_ml":       _fetch_reddit,
    "github_trending": _fetch_github_trending,
    "huggingface":     _fetch_huggingface,
    "anthropic":       lambda n: _fetch_feed("anthropic", n),
    "openai":          lambda n: _fetch_feed("openai", n),
    "deepmind":        lambda n: _fetch_feed("deepmind", n),
    "meta_ai":         lambda n: _fetch_feed("meta_ai", n),
    "simonwillison":   lambda n: _fetch_feed("simonwillison", n),
    "karpathy":        lambda n: _fetch_feed("karpathy", n),
    "importai":        lambda n: _fetch_feed("importai", n),
    "lilianweng":      lambda n: _fetch_feed("lilianweng", n),
    "interconnects":   lambda n: _fetch_feed("interconnects", n),
    "schneier":        lambda n: _fetch_feed("schneier", n),
    "sidebar":         lambda n: _fetch_feed("sidebar", n),
    "smashingmag":     lambda n: _fetch_feed("smashingmag", n),
    "dense_discovery": lambda n: _fetch_feed("dense_discovery", n),
    "nngroup":         lambda n: _fetch_feed("nngroup", n),
    "heydesigner":     lambda n: _fetch_feed("heydesigner", n),
    "figma":           lambda n: _fetch_feed("figma", n),
    "codrops":         lambda n: _fetch_feed("codrops", n),
    "quanta":          lambda n: _fetch_feed("quanta", n),
    "techcrunch":      lambda n: _fetch_feed("techcrunch", n),
    "theverge":        lambda n: _fetch_feed("theverge", n),
    "producthunt":     lambda n: _fetch_feed("producthunt", n),
}


# ==========================================================================
# Orchestrator
# ==========================================================================
def fetch_all(
    enabled: dict[str, bool] | None = None,
    limits: dict[str, int] | None = None,
    custom_feeds: list[dict] | None = None,
    top_k: int = 60,
) -> list[dict]:
    """Fetch from every enabled source in parallel, filter stale items,
    dedup by normalized URL, attach `prior`, return the top `top_k`
    sorted by `prior` descending.

    custom_feeds: list of dicts from taste.json, each with keys:
        id, url, label, weight (0..1), limit (int), freshness_days (int), enabled (bool)
    """
    enabled = enabled or {}
    limits = {**DEFAULT_LIMITS, **(limits or {})}

    # Register custom feeds — local overrides so we never mutate module globals.
    extra_fetchers: dict[str, Callable[[int], list[dict]]] = {}
    extra_weights: dict[str, float] = {}
    extra_freshness: dict[str, int] = {}

    for cf in (custom_feeds or []):
        cid = (cf.get("id") or "").strip()
        curl = (cf.get("url") or "").strip()
        if not cid or not curl:
            continue
        if not cf.get("enabled", True):
            enabled[cid] = False
            continue
        extra_fetchers[cid] = lambda n, s=cid, u=curl: _fetch_feed(s, n, url_override=u)
        extra_weights[cid] = float(cf.get("weight", 0.75))
        extra_freshness[cid] = int(cf.get("freshness_days", 7))
        limits[cid] = int(cf.get("limit", 5))
        enabled.setdefault(cid, True)

    all_fetchers = {**FETCHERS, **extra_fetchers}
    all_weights = {**SOURCE_WEIGHTS, **extra_weights}
    all_freshness = {**FRESHNESS_DAYS, **extra_freshness}

    active = [s for s in all_fetchers if enabled.get(s, True)]
    log.info("fetching from %d sources: %s", len(active), ", ".join(active))

    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(active), 16)) as pool:
        future_to_source = {
            pool.submit(all_fetchers[s], limits.get(s, 10)): s for s in active
        }
        for fut in concurrent.futures.as_completed(future_to_source):
            s = future_to_source[fut]
            try:
                items = fut.result()
                days = all_freshness.get(s, 14)
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
        if prev is None or all_weights.get(it["source"], 0) > all_weights.get(prev["source"], 0):
            by_url[key] = it

    deduped = list(by_url.values())

    # Attach prior and sort.
    for it in deduped:
        w = all_weights.get(it["source"], SOURCE_WEIGHTS.get(it["source"], 0.5))
        rank = it["rank_within_source"]
        rank_factor = 1.0 / (1.0 + 0.15 * max(rank - 1, 0))
        raw = max(it.get("score") or 0, 0)
        score_factor = min(math.log10(raw + 1) / 8.0, 0.15)
        it["prior"] = round(w * rank_factor + score_factor, 3)

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
