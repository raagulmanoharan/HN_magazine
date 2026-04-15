"""Fetch the Hacker News front page via the Firebase API.

Returns a list of story dicts with id, title, url, score, by, descendants (comments),
and time. We pull the top-N ids then fan out with a thread pool.
"""
from __future__ import annotations

import concurrent.futures
import logging
import time
from typing import Any

import requests

HN_TOPSTORIES = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{id}.json"

log = logging.getLogger(__name__)


def _get_json(url: str, timeout: float = 10.0) -> Any:
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()


def fetch_item(item_id: int) -> dict | None:
    try:
        data = _get_json(HN_ITEM.format(id=item_id))
    except Exception as e:
        log.warning("failed to fetch item %s: %s", item_id, e)
        return None
    if not data or data.get("dead") or data.get("deleted"):
        return None
    # Ask/Show/Story all fine; skip pure job posts
    if data.get("type") == "job":
        return None
    return {
        "id": data.get("id"),
        "title": data.get("title", "").strip(),
        "url": data.get("url") or f"https://news.ycombinator.com/item?id={data.get('id')}",
        "hn_url": f"https://news.ycombinator.com/item?id={data.get('id')}",
        "score": data.get("score", 0),
        "by": data.get("by", ""),
        "descendants": data.get("descendants", 0),
        "time": data.get("time", int(time.time())),
        "type": data.get("type", "story"),
        "text": data.get("text", "") or "",
    }


def fetch_front_page(limit: int = 30) -> list[dict]:
    ids = _get_json(HN_TOPSTORIES)[:limit]
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        results = list(ex.map(fetch_item, ids))
    stories = [s for s in results if s]
    # Preserve HN ranking order
    order = {sid: i for i, sid in enumerate(ids)}
    stories.sort(key=lambda s: order.get(s["id"], 999))
    return stories


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import json

    print(json.dumps(fetch_front_page(30), indent=2))
