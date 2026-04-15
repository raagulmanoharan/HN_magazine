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
import pathlib
import re
from typing import Any

log = logging.getLogger(__name__)

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# Optional per-reader taste profile. Tuned via WhatsApp replies; the webhook
# at api/twilio-whatsapp rewrites this file. If missing (fresh install) we
# fall back to the in-prompt defaults below.
TASTE_JSON = pathlib.Path(__file__).resolve().parent.parent / "taste.json"


def _load_taste() -> dict:
    try:
        return json.loads(TASTE_JSON.read_text())
    except FileNotFoundError:
        return {}
    except Exception as e:
        log.warning("taste.json unreadable, using defaults: %s", e)
        return {}

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

DEFAULT_PROFILE = (
    "Loves: UX, interface design, typography, information design. "
    "AI tools that work today (not AGI takes) — agentic workflows, LLM tooling, "
    "evals, prompt craft, shipping news from Anthropic / Claude / OpenAI. "
    "Creative software — design tools, music software, video, generative art. "
    "Developer tools — editors, terminals, languages, build systems, databases, "
    "debuggers, local-first, self-hosted. Privacy, encryption, security research, "
    "surveillance resistance. Weird science — biology, neuroscience, physics, "
    "math curios, archaeology, strange empirical findings. Actionable things — "
    "'I could use this today' libraries, guides, Show HNs with working demos.\n\n"
    "Skip: low-effort hot takes without a concrete artifact. Pure VC / funding "
    "announcements with no product substance. Crypto price chatter, tokenomics, "
    "NFT drama. US political flame-wars. Layoff announcements without real "
    "analysis. Recycled listicles, SEO spam, LinkedIn-flavored leadership posts."
)
DEFAULT_APPLIES_RULE = (
    'Flag "applies_to_me: true" when the reader could literally use the thing '
    "today — a new Claude feature, a dev tool they'd install, a privacy utility, "
    "an editor plugin, a library, a how-to with a working demo."
)
DEFAULT_VOICE = (
    "sharp, curious, a little dry. Blurbs are 2-3 sentences, ~45 words. Explain "
    "WHY it matters to this reader specifically, not a summary of the headline. "
    'No exclamation points. No "in this post". No clickbait.'
)


def _build_taste_profile() -> str:
    """Combine the editable reader profile (from taste.json, tuned via
    WhatsApp) with the static structural rules (JSON schema, spread palette,
    style-assignment rules). Returns the full system prompt."""
    t = _load_taste()
    profile = (t.get("profile") or DEFAULT_PROFILE).strip()
    applies_rule = (t.get("applies_to_me_rule") or DEFAULT_APPLIES_RULE).strip()
    voice = (t.get("voice") or DEFAULT_VOICE).strip()

    recent = t.get("recent_changes") or []
    recent_block = ""
    if recent:
        # Surface the 10 most recent tuning changes so the editor understands
        # the trajectory of the reader's taste, not just the static snapshot.
        recent_lines = "\n".join(
            f"- {c.get('when','')}: {c.get('change','')}" for c in recent[-10:]
        )
        recent_block = (
            "\n\nRECENT TUNING (what the reader has said lately, newest last):\n"
            + recent_lines
        )

    header = f"""\
You are the Editor-in-Chief of a one-reader daily called MORNING EDITION. The
reader's taste is specific and strong. Curate ruthlessly.

THE READER (verbatim profile, tuned over time via WhatsApp):
{profile}
{recent_block}

APPLIES-TO-ME FLAG:
{applies_rule}

EDITORIAL VOICE: {voice}
"""
    return header + _SOURCES_BLOCK + _RANKING_BLOCK + _STATIC_SCHEMA_TAIL


_SOURCES_BLOCK = """
CANDIDATE SOURCES (each item includes a `source` field):
  hn              — Hacker News front page. Broad, noisy, strong on dev + AI.
  lobsters        — Lobste.rs. Smaller, higher-signal systems / languages.
  anthropic       — Anthropic official news. Claude shipping news, nearly always relevant.
  openai          — OpenAI news. Product + research shipping.
  deepmind        — Google DeepMind blog. Research + Gemini shipping.
  simonwillison   — Simon Willison's blog. LLM tooling, evals, prompt craft, hands-on.
  github_trending — Repos created in the last 7 days with rising stars. Actionable tools.
  sidebar         — Curated design/UX links. Rare + high-value for a UX designer.
  quanta          — Quanta Magazine. Editorial-grade science journalism.
  schneier        — Schneier on Security. Analytical, not breach-report chum.
  producthunt     — Product Hunt feed. More marketing noise; filter hard.

Each candidate also carries a local `prior` in [0..~1.2] combining source
weight, within-source rank, and log-score. Treat `prior` as a weak
tiebreaker, not a verdict.
"""

_RANKING_BLOCK = """
RANKING RUBRIC (apply top-down):
1. TASTE ALIGNMENT — the reader profile is a hard filter first. If a story
   doesn't match the profile, it doesn't make the issue, regardless of prior.
2. UX / DESIGN PRIORITY — the reader is a UX designer. Typography,
   interface design, information design, design-system or creative-software
   finds jump near the top. These signals are rare; never pass one up.
3. AI SHIPPING FRESHNESS — new Claude / OpenAI / DeepMind features beat old
   thinkpieces. An anthropic/openai/deepmind item from this week is almost
   certainly cover-material unless it's a minor aside.
4. ACTIONABILITY — "I could install this, open this, use this today" beats
   abstract commentary. Favor Show-HN-style or github_trending finds with
   a working demo.
5. CROSS-SOURCE DIVERSITY — the issue shouldn't be 10 HN items when other
   sources have gold. Aim for at least 4 non-HN picks when quality allows.
6. PRIOR AS TIEBREAKER — with all else equal, prefer higher `prior`.

HARD SKIPS (never include):
- Funding / M&A announcements with no product substance.
- Crypto / NFT / tokenomics.
- US political flame-wars, culture-war pieces.
- Layoffs without real analysis.
- Recycled listicles, SEO bait, LinkedIn-style leadership posts.
"""

_STATIC_SCHEMA_TAIL = """
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

    # Compact candidate list — keep prompt lean. Candidates arrive
    # pre-ranked by local `prior`; curator re-ranks by taste.
    candidates = [
        {
            "id": s.get("id"),
            "title": s["title"],
            "url": s["url"],
            "hn_url": s.get("hn_url", ""),
            "source": s.get("source", "hn"),
            "score": s.get("score", 0),
            "comments": s.get("comments", s.get("descendants", 0)),
            "domain": _domain(s["url"]),
            "snippet": _snippet(s.get("text", "")),
            "published_at": s.get("published_at", ""),
            "prior": s.get("prior"),
            "rank_within_source": s.get("rank_within_source"),
        }
        for s in stories
    ]

    user_payload = (
        "Today's candidates, pre-ranked by a local `prior` signal "
        "(source weight × within-source rank + log-score). Re-rank by taste:\n\n"
        + json.dumps(candidates, indent=2)
        + "\n\nReturn the JSON now."
    )

    resp = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": _build_taste_profile(),
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
    """Heuristic ranking used when the Anthropic API is unavailable. In a
    multi-source world, raw `score` (HN points vs GitHub stars vs 0) is
    incomparable, so we lean on (a) the cross-source `prior` from
    fetch_sources, which already blends source weight + log-score, and
    (b) keyword signals from the title/domain."""
    t = (story["title"] + " " + _domain(story["url"])).lower()
    # Prior is the dominant signal (0..~1.2 range → up to 120 pts).
    s = float(story.get("prior", 0.0) or 0.0) * 100.0
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
        score = int(s.get("score", 0) or 0)
        comments = int(s.get("comments", s.get("descendants", 0)) or 0)
        source = s.get("source", "hn")
        kicker_map = {
            "hn": "FRONT PAGE", "lobsters": "LOBSTE.RS",
            "anthropic": "ANTHROPIC", "openai": "OPENAI",
            "deepmind": "DEEPMIND", "simonwillison": "SIMON WILLISON",
            "github_trending": "TRENDING", "sidebar": "DESIGN",
            "quanta": "SCIENCE", "schneier": "SECURITY",
            "producthunt": "LAUNCH",
        }
        pick = {
            "rank": i + 1,
            "hn_id": s.get("id", i),
            "title": s["title"],
            "url": s["url"],
            "hn_url": s.get("hn_url", ""),
            "score": score,
            "comments": comments,
            "kicker": kicker_map.get(source, "FRONT PAGE"),
            "blurb": (
                f"From {_domain(s['url'])}. Surfaced via {source}; ranked on the "
                f"pre-score. Worth a look on the commute."
            ),
            "applies_to_me": _applies(s),
            "apply_note": "Open the link and skim the README." if _applies(s) else "",
            "spread_style": style,
            "stat_value": str(score) if style == "big-stat" and score else "",
            "stat_label": "POINTS" if style == "big-stat" and score else "",
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
