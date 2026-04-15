"""Curate the top 10 HN stories with Claude.

The taste profile + editorial instructions are cached with prompt caching
(cache_control) so only the day's story list changes between runs. The model
returns strict JSON describing the 10 picks, a blurb for each, an
"applies_to_me" flag, and a spread style from a fixed palette.

Falls back to a keyword heuristic if ANTHROPIC_API_KEY is missing.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

log = logging.getLogger(__name__)

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

SPREAD_STYLES = [
    "hero",          # #1 cover story — massive display type
    "midnight",      # deep dark spread, neon accent
    "rose-alert",    # rose background, stamp-style "APPLIES TO YOU" when flagged
    "terminal",      # CLI aesthetic, green on black, monospace numerals
    "academic",      # cream, giant serif drop-cap, editorial footnotes
    "big-stat",      # one giant stat/number dominates the page
    "newsprint",     # two-column newsprint, ink-on-cream
    "neon",          # magenta/cyan gradient, brutalist sans
    "zine",          # handmade zine, offset, marker accents
    "pullquote",     # single enormous pull quote
]

TASTE_PROFILE = """\
You are the Editor-in-Chief of a one-reader daily called MORNING EDITION. The
reader's taste is specific and strong. Curate ruthlessly.

WHAT THE READER LOVES (boost):
- UX, interface design, typography, information design
- AI tools you can actually use today (not AGI takes), agentic workflows, LLM
  tooling, evals, prompt craft, Claude / Anthropic / OpenAI shipping news
- Creative software: design tools, music software, video, generative art
- Developer tools: editors, terminals, languages, build systems, databases,
  debuggers, local-first, self-hosted
- Privacy, encryption, security research, surveillance resistance
- Weird science: biology, neuroscience, physics, math curios, archaeology,
  strange empirical findings
- Actionable things: "I could use this today" — libraries, guides, show HNs
  with working demos, field reports

WHAT TO SKIP (penalize hard):
- Low-effort posts: generic hot takes, rage bait, vague blog posts without a
  concrete artifact
- Pure VC / funding announcements with no product substance
- Crypto price chatter, tokenomics, NFT drama
- US political flame-wars and culture-war pieces
- "X company laid off N people" unless there's real analysis
- Recycled listicles, SEO spam, LinkedIn-flavored leadership posts

FLAG "applies_to_me: true" when the reader could literally use the thing
today: a new Claude feature, a dev tool they'd install, a privacy utility,
an editor plugin, a library, a how-to with a working demo.

EDITORIAL VOICE: sharp, curious, a little dry. Blurbs are 2-3 sentences, ~45
words. They must explain WHY it matters to this reader specifically — not a
summary of the headline. No exclamation points. No "in this post". No clickbait.

SPREAD STYLE PALETTE (assign exactly one per story, use each style once):
  hero, midnight, rose-alert, terminal, academic, big-stat, newsprint,
  neon, zine, pullquote

Rules for style assignment:
- Position 1 (the cover / lead): ALWAYS "hero".
- "rose-alert" should go to a story where applies_to_me is true — the stamp
  lands. If multiple qualify, pick the most actionable. If none qualify,
  assign rose-alert to the most urgent/actionable anyway.
- "terminal" should go to a dev-tools / CLI / systems story when possible.
- "academic" should go to the most research- or science-flavored pick.
- "big-stat" should go to a story with a meaningful number to pull out
  (benchmark, %, count, dollars, years). Provide that number in `stat_value`
  and a short `stat_label`.
- "pullquote" should go to a story where one sentence from the headline or
  blurb hits hard — provide `pullquote` text (<= 14 words).
- The remaining styles fill in naturally.

OUTPUT: strict JSON, no prose, no code fences. Schema:
{
  "issue_tagline": "<6-10 word editorial tagline for today's issue>",
  "picks": [
    {
      "rank": 1,
      "hn_id": <int>,
      "title": "<as given>",
      "url": "<as given>",
      "hn_url": "<as given>",
      "score": <int>,
      "comments": <int>,
      "kicker": "<2-4 word section label, e.g. DEV TOOLS, WEIRD SCIENCE>",
      "blurb": "<2-3 sentences, ~45 words, editor voice>",
      "applies_to_me": <bool>,
      "apply_note": "<if applies_to_me, 1 short sentence on how to use it today, else empty string>",
      "spread_style": "<one of the palette>",
      "stat_value": "<string, only for big-stat, else empty>",
      "stat_label": "<string, only for big-stat, else empty>",
      "pullquote": "<string, only for pullquote, else empty>"
    },
    ... 10 total ...
  ]
}
"""


# --------------------------------------------------------------------------
# Claude path
# --------------------------------------------------------------------------
def _curate_with_claude(stories: list[dict]) -> dict:
    import anthropic

    client = anthropic.Anthropic()

    # Compact candidate list — keep prompt lean.
    candidates = [
        {
            "hn_id": s["id"],
            "title": s["title"],
            "url": s["url"],
            "hn_url": s["hn_url"],
            "score": s["score"],
            "comments": s["descendants"],
            "domain": _domain(s["url"]),
            "snippet": _snippet(s.get("text", "")),
        }
        for s in stories
    ]

    user_payload = (
        "Today's HN front page candidates (ranked by HN):\n\n"
        + json.dumps(candidates, indent=2)
        + "\n\nReturn the JSON now."
    )

    resp = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": TASTE_PROFILE,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_payload}],
    )

    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    data = _extract_json(text)
    _validate(data)
    return data


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    # Find the outermost {...}
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object found in model output: {text[:200]}")
    return json.loads(text[start : end + 1])


def _validate(data: dict) -> None:
    if "picks" not in data or not isinstance(data["picks"], list):
        raise ValueError("missing picks[]")
    if len(data["picks"]) != 10:
        raise ValueError(f"expected 10 picks, got {len(data['picks'])}")
    used_styles = {p.get("spread_style") for p in data["picks"]}
    missing = set(SPREAD_STYLES) - used_styles
    # Non-fatal — we'll repair in render — but log.
    if missing:
        log.warning("missing spread styles (will repair): %s", missing)


# --------------------------------------------------------------------------
# Heuristic fallback (no API key)
# --------------------------------------------------------------------------
_BOOST = [
    ("ai", 4), ("claude", 6), ("anthropic", 6), ("llm", 4), ("gpt", 3),
    ("agent", 3), ("rag", 3), ("eval", 2),
    ("ux", 4), ("typography", 4), ("design", 2), ("interface", 3),
    ("privacy", 5), ("encryption", 4), ("surveillance", 4), ("security", 3),
    ("editor", 3), ("terminal", 3), ("cli", 3), ("compiler", 3),
    ("database", 3), ("local-first", 5), ("self-host", 4), ("open source", 2),
    ("show hn", 3), ("neuroscience", 4), ("biology", 3), ("physics", 3),
    ("archaeolog", 4), ("math", 2),
]
_PENALTY = [
    ("crypto", -5), ("nft", -6), ("token", -3), ("ipo", -4), ("funding", -3),
    ("layoff", -4), ("ceo", -2), ("politic", -5), ("election", -5),
]


def _score(story: dict) -> float:
    t = (story["title"] + " " + _domain(story["url"])).lower()
    s = float(story.get("score", 0))
    for kw, w in _BOOST:
        if kw in t:
            s += w * 10
    for kw, w in _PENALTY:
        if kw in t:
            s += w * 10
    return s


def _applies(story: dict) -> bool:
    t = story["title"].lower()
    triggers = [
        "show hn", "released", "open-sourced", "open sourced", "now available",
        "claude", "anthropic", "library", "cli", "plugin", "extension",
        "self-host", "tutorial", "guide",
    ]
    return any(k in t for k in triggers)


def _curate_heuristic(stories: list[dict]) -> dict:
    ranked = sorted(stories, key=_score, reverse=True)[:10]
    picks = []
    for i, s in enumerate(ranked):
        style = SPREAD_STYLES[i]
        pick = {
            "rank": i + 1,
            "hn_id": s["id"],
            "title": s["title"],
            "url": s["url"],
            "hn_url": s["hn_url"],
            "score": s["score"],
            "comments": s["descendants"],
            "kicker": "FRONT PAGE",
            "blurb": (
                f"From {_domain(s['url'])}. HN is giving this {s['score']} points "
                f"and {s['descendants']} comments — worth a look on the commute."
            ),
            "applies_to_me": _applies(s),
            "apply_note": "Open the link and skim the README." if _applies(s) else "",
            "spread_style": style,
            "stat_value": str(s["score"]) if style == "big-stat" else "",
            "stat_label": "POINTS ON HN" if style == "big-stat" else "",
            "pullquote": s["title"] if style == "pullquote" else "",
        }
        picks.append(pick)
    return {
        "issue_tagline": "Hand-picked from the front page while you slept.",
        "picks": picks,
    }


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _domain(url: str) -> str:
    m = re.match(r"https?://([^/]+)", url or "")
    if not m:
        return ""
    d = m.group(1)
    return d[4:] if d.startswith("www.") else d


def _snippet(text: str, n: int = 240) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:n]


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------
def curate(stories: list[dict]) -> dict:
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return _curate_with_claude(stories)
        except Exception as e:
            log.exception("claude curation failed, falling back: %s", e)
    else:
        log.warning("ANTHROPIC_API_KEY not set — using heuristic curator")
    return _curate_heuristic(stories)


if __name__ == "__main__":
    import sys
    from fetch_hn import fetch_front_page

    logging.basicConfig(level=logging.INFO)
    stories = fetch_front_page(30)
    out = curate(stories)
    json.dump(out, sys.stdout, indent=2)
