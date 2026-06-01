"""Build the Weekly Edition — fully generative layouts.

Unlike the daily Morning Edition (which uses 18 pre-built CSS templates),
the Weekly Edition asks Claude to design each spread from scratch. Every
story gets a unique visual treatment: custom colors, typography, layout,
and decorative elements.

Steps:
  1. Fetch candidates with a 7-day freshness window.
  2. Curate the top 10 stories of the week.
  3. Generate a unique HTML/CSS spread for each story via Claude.
  4. Stitch into a self-contained magazine.
  5. Write to magazines/weekly-YYYY-MM-DD.html.
  6. Re-render the landing page and RSS feed.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import logging
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from build import render_index, render_feed, render_latest, _issue_list, INDEX_PATH, FEED_PATH, LATEST_PATH  # noqa: E402
from curate import curate                         # noqa: E402
from fetch_sources import fetch_all, FRESHNESS_DAYS  # noqa: E402
from render import fmt_date                       # noqa: E402

ROOT = HERE.parent
MAGAZINES_DIR = ROOT / "magazines"

log = logging.getLogger("build_weekly")

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")


def _sanitize_spread(html: str, class_name: str) -> str:
    """Ensure a generated spread is a single well-formed <section>."""
    html = html.strip()
    # Extract just the section element if there's junk before/after
    start = html.find("<section")
    if start > 0:
        html = html[start:]
    # Ensure it ends with </section>
    if not html.rstrip().endswith("</section>"):
        html = html.rstrip() + "\n</section>"
    # Remove duplicate </section> tags
    html = re.sub(r"(</section>\s*)+$", "</section>", html)
    # Fix truncated style blocks (opened but never closed)
    if '<style>' in html and '</style>' not in html:
        last_brace = html.rfind('}')
        if last_brace != -1:
            html = html[:last_brace + 1] + f"""
.{class_name} {{ min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: clamp(24px, 5vw, 72px); }}
</style>
<div style="text-align:center;max-width:600px;">
  <p style="font-size:22px;opacity:0.7;">This spread was truncated during generation.</p>
</div>
</section>"""
            return html
    # Ensure dark-background spreads have a light text color set
    bg_match = re.search(
        rf'\.{re.escape(class_name)}\s*\{{([^}}]+)\}}', html)
    if bg_match:
        body = bg_match.group(1)
        has_dark_bg = re.search(
            r'background(?:-color)?\s*:\s*#[0-3]', body)
        has_color = re.search(r'(?<!background-)color\s*:', body)
        if has_dark_bg and not has_color:
            html = html.replace(
                bg_match.group(0),
                bg_match.group(0).replace('{', '{ color: #f0eee8;', 1))
    return html


# --------------------------------------------------------------------------
# Generative spread rendering
# --------------------------------------------------------------------------
_SPREAD_SYSTEM = """\
You are a world-class magazine art director designing a single full-viewport
spread for a digital magazine called MORNING EDITION — Weekly. The reader is
a UX designer who cares about craft, so your design must be genuinely good:
bold, expressive, and unique. Every spread should feel like its own poster.

CONSTRAINTS (hard rules):
- Output ONLY a single <section class="spread spread-{n}"> element.
- Put a <style> tag INSIDE the section. All CSS selectors MUST be prefixed
  with `.spread-{n}` so styles don't leak between spreads.
- Use Google Fonts via @import at the top of the <style> tag. Pick 1-2 fonts
  that match this story's mood — never default to the same pair twice in a row.
- Minimum font size anywhere: 18px. Body text: 20-24px.
- The spread must be min-height: 100vh, responsive from 360px to 1440px.
  Use clamp(), vw units, and a @media breakpoint around 720px.
- Include a prominent CTA link: <a class="cta" href="{url}" target="_blank"
  rel="noopener">Read → </a>
- If the story has applies_to_me = true, add a visible "APPLIES TO YOU"
  badge/stamp/indicator with the apply_note text nearby.
- No JavaScript. No external images. Pure CSS + HTML.
- Keep decorative elements (gradients, shapes, borders, pseudo-elements)
  ambitious but working — test your CSS mentally before writing it.

DESIGN BRIEF:
Be expressive. Each spread should feel different from the others. Consider:
- Color: moody darks, vibrant gradients, muted earth tones, stark white...
- Layout: asymmetric grids, centered posters, split-screen, full-bleed type...
- Typography: oversized display type, elegant serifs, brutalist sans, mixed...
- Texture: CSS patterns, layered pseudo-elements, borders, shadows...
- The story's content should drive the visual — a security story might feel
  different from a design-tool story or a weird-science piece.

Output the <section> with its <style> and nothing else. No markdown, no
explanation, no code fences.
"""


def _generate_spread(pick: dict, index: int, issue_meta: dict) -> str:
    """Call Claude to generate a unique HTML/CSS spread for one story."""
    import anthropic

    client = anthropic.Anthropic()

    story_brief = f"""\
Spread #{index + 1} of 10 in the {issue_meta['date_display']} Weekly Edition.

Story data:
- Title: {pick['title']}
- Kicker: {pick.get('kicker', 'NEWS')}
- Blurb: {pick.get('blurb', '')}
- URL: {pick['url']}
- Source: {pick.get('source', '')} (score: {pick.get('score', 0)}, comments: {pick.get('comments', 0)})
- Applies to reader: {pick.get('applies_to_me', False)}
- Apply note: {pick.get('apply_note', '')}
- Stat value: {pick.get('stat_value', '')}
- Stat label: {pick.get('stat_label', '')}
- Pullquote: {pick.get('pullquote', '')}

Use class prefix: spread-{index + 1}
Use {{n}} = {index + 1:02d} for any numeral display.

Generate the spread now.
"""

    system_prompt = _SPREAD_SYSTEM.replace("{n}", str(index + 1)).replace("{url}", pick["url"])

    resp = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        system=[{"type": "text", "text": system_prompt}],
        messages=[{"role": "user", "content": story_brief}],
    )

    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
    return _sanitize_spread(text.strip(), f"spread-{index + 1}")


def _generate_cover(issue_meta: dict) -> str:
    """Generate a cover/hero spread for the weekly edition."""
    import anthropic

    client = anthropic.Anthropic()

    brief = f"""\
Design the COVER PAGE for Morning Edition — Weekly, {issue_meta['date_display']}.
Issue No. {issue_meta['issue_no']}.
Tagline: "{issue_meta['tagline']}"

This is the opening spread. It should be dramatic — big display type, strong
visual presence. The title is "Morning Edition" with subtitle "Weekly". Show
the date and issue number. Include the tagline.

Use class prefix: spread-cover
No CTA link needed — this is just the cover.

Generate the <section> now.
"""

    resp = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        system=[{"type": "text", "text": _SPREAD_SYSTEM.replace("{n}", "cover").replace("{url}", "#")}],
        messages=[{"role": "user", "content": brief}],
    )

    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
    return _sanitize_spread(text.strip(), "spread-cover")


def _generate_colophon(issue_meta: dict, applies_count: int) -> str:
    """Simple closing section — not generative, just clean."""
    return f"""
<section class="spread spread-colophon">
<style>
.spread-colophon{{background:#17140e;color:#f4ecd8;padding:clamp(48px,6vw,110px);
  min-height:50vh;display:flex;flex-direction:column;justify-content:center;gap:28px;
  font-family:system-ui,sans-serif}}
.spread-colophon h3{{font-size:clamp(36px,5vw,72px);margin:0;font-weight:300;
  font-style:italic;line-height:1.1}}
.spread-colophon p{{font-size:22px;line-height:1.5;max-width:56ch;margin:0;opacity:.85}}
.spread-colophon .sm{{font-size:18px;letter-spacing:.18em;text-transform:uppercase;opacity:.5}}
</style>
<h3>That was this week.</h3>
<p>Ten stories, curated across twenty sources. {applies_count} flagged as
directly applicable. Each spread designed from scratch by Claude.</p>
<p><a href="../index.html" style="color:#d9b26a;text-decoration:underline;
text-underline-offset:4px;font-size:22px">Browse all issues &rarr;</a></p>
<p class="sm">Morning Edition — Weekly &middot; Issue No. {issue_meta['issue_no']}
&middot; {issue_meta['date_display']}</p>
</section>
"""


# --------------------------------------------------------------------------
# Stitching
# --------------------------------------------------------------------------
def _stitch_magazine(cover: str, spreads: list[str], colophon: str,
                     issue_meta: dict) -> str:
    title = f"Morning Edition — Weekly &middot; {issue_meta['date_display']}"
    desc = issue_meta.get("tagline") or "The week's best, each spread designed from scratch."

    body = "\n".join([cover] + spreads + [colophon])

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:type" content="article">
<style>
*,*::before,*::after{{box-sizing:border-box}}
html,body{{margin:0;padding:0}}
html{{scroll-behavior:smooth}}
body{{background:#111;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}}
.spread{{position:relative;min-height:100vh;overflow:hidden}}
a{{color:inherit}}
</style>
</head>
<body>
{body}
</body>
</html>
"""


# --------------------------------------------------------------------------
# Validation — must pass before the magazine is written to disk
# --------------------------------------------------------------------------
def _validate_magazine(html: str) -> list[str]:
    """Run structural evals on the stitched magazine HTML. Returns errors."""
    errors: list[str] = []

    # 1. Every <style> must have a matching </style>
    style_opens = html.count('<style>')
    style_closes = html.count('</style>')
    if style_opens != style_closes:
        errors.append(f"Unbalanced style tags: {style_opens} <style> vs {style_closes} </style>")

    # 2. Every <section> must have a matching </section>
    section_opens = len(re.findall(r'<section', html))
    section_closes = html.count('</section>')
    if section_opens != section_closes:
        errors.append(f"Unbalanced sections: {section_opens} <section> vs {section_closes} </section>")

    # 3. Each spread section must contain both <style> and </style>
    for m in re.finditer(r'<section class="spread (spread-[\w-]+)">', html):
        cls = m.group(1)
        start = m.start()
        end_match = re.search(r'</section>', html[start:])
        if not end_match:
            errors.append(f"{cls}: no closing </section>")
            continue
        section = html[start:start + end_match.end()]
        if '<style>' in section and '</style>' not in section:
            errors.append(f"{cls}: <style> opened but never closed (CSS truncated)")
        if '<style>' not in section and cls != 'spread-colophon':
            if 'style="' not in section[:500]:
                errors.append(f"{cls}: no <style> block found")

    # 4. Dark backgrounds must have light text color
    for m in re.finditer(r'\.(spread-[\w-]+)\s*\{([^}]+)\}', html):
        cls = m.group(1)
        body = m.group(2)
        bg = re.search(r'background(?:-color)?\s*:\s*#([0-9a-fA-F]{2})', body)
        has_color = re.search(r'(?<!background-)color\s*:', body)
        if bg and int(bg.group(1), 16) < 0x30 and not has_color:
            errors.append(f"{cls}: dark background but no text color set")

    # 5. Minimum content check — each spread should have some HTML beyond just CSS
    for m in re.finditer(r'<section class="spread (spread-[\w-]+)">', html):
        cls = m.group(1)
        start = m.start()
        end_match = re.search(r'</section>', html[start:])
        if not end_match:
            continue
        section = html[start:start + end_match.end()]
        # Strip out the style block and check remaining HTML
        stripped = re.sub(r'<style>.*?</style>', '', section, flags=re.DOTALL)
        # Count actual content tags
        content_tags = len(re.findall(r'<(?:h[1-6]|p|a|div|span|main|header)', stripped))
        if content_tags < 2 and cls != 'spread-colophon':
            errors.append(f"{cls}: too little HTML content ({content_tags} tags)")

    return errors


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------
def build_weekly(date: dt.date, public_base_url: str | None = None) -> dict:
    MAGAZINES_DIR.mkdir(parents=True, exist_ok=True)

    # Fetch with wider freshness for weekly recap.
    weekly_freshness = {k: max(v, 7) for k, v in FRESHNESS_DAYS.items()}
    log.info("fetching candidates (7-day window) ...")
    taste_path = ROOT / "taste.json"
    enabled: dict[str, bool] = {}
    try:
        taste = json.loads(taste_path.read_text())
        sources_cfg = taste.get("sources") or {}
        enabled = {k: bool(v.get("enabled", True)) for k, v in sources_cfg.items()}
    except Exception:
        pass

    from fetch_sources import FRESHNESS_DAYS as _FD
    original = dict(_FD)
    _FD.update(weekly_freshness)
    try:
        stories = fetch_all(enabled=enabled, top_k=100)
    finally:
        _FD.update(original)

    log.info("fetched %d candidates", len(stories))

    log.info("curating week's best ...")
    curation = curate(stories)

    issue_meta = {
        "date_iso": date.isoformat(),
        "date_display": fmt_date(date),
        "issue_no": f"W{date.isocalendar()[1]:02d}",
        "tagline": curation.get("issue_tagline", ""),
        "built_at": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    }

    picks = curation.get("picks", [])[:10]
    applies_count = sum(1 for p in picks if p.get("applies_to_me"))

    # Generate each spread in parallel (up to 5 concurrent API calls).
    log.info("generating %d spreads + cover ...", len(picks))

    cover_html = ""
    spread_htmls = [""] * len(picks)

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        cover_future = pool.submit(_generate_cover, issue_meta)
        spread_futures = {
            pool.submit(_generate_spread, p, i, issue_meta): i
            for i, p in enumerate(picks)
        }

        try:
            cover_html = cover_future.result(timeout=120)
            log.info("  cover generated")
        except Exception as e:
            log.error("cover generation failed: %s", e)
            cover_html = f'<section class="spread"><h1 style="color:#fff;padding:80px">Morning Edition — Weekly<br>{issue_meta["date_display"]}</h1></section>'

        for fut in concurrent.futures.as_completed(spread_futures, timeout=180):
            idx = spread_futures[fut]
            try:
                spread_htmls[idx] = fut.result()
                log.info("  spread %d generated", idx + 1)
            except Exception as e:
                log.error("spread %d failed: %s", idx + 1, e)
                p = picks[idx]
                spread_htmls[idx] = (
                    f'<section class="spread" style="background:#222;color:#fff;'
                    f'padding:80px;min-height:100vh;font-family:system-ui">'
                    f'<h2 style="font-size:clamp(32px,5vw,64px)">{p.get("title","")}</h2>'
                    f'<p style="font-size:22px;max-width:56ch">{p.get("blurb","")}</p>'
                    f'<a href="{p.get("url","")}" style="color:#7af;font-size:20px">'
                    f'Read →</a></section>'
                )

    colophon = _generate_colophon(issue_meta, applies_count)
    html_out = _stitch_magazine(cover_html, spread_htmls, colophon, issue_meta)

    errors = _validate_magazine(html_out)
    if errors:
        for e in errors:
            log.error("EVAL FAIL: %s", e)
        raise RuntimeError(f"Magazine failed {len(errors)} eval(s): {'; '.join(errors)}")

    out_path = MAGAZINES_DIR / f"weekly-{date.isoformat()}.html"
    out_path.write_text(html_out, encoding="utf-8")
    log.info("wrote %s (%d bytes)", out_path, len(html_out))

    # Re-render landing page + RSS feed so the weekly shows up.
    issues = _issue_list()
    INDEX_PATH.write_text(render_index(issues), encoding="utf-8")
    log.info("wrote %s", INDEX_PATH)
    if public_base_url:
        FEED_PATH.write_text(render_feed(issues, public_base_url), encoding="utf-8")
        LATEST_PATH.write_text(render_latest(issues, public_base_url), encoding="utf-8")
        log.info("wrote %s, %s", FEED_PATH, LATEST_PATH)

    return {
        "date": date.isoformat(),
        "path": str(out_path.relative_to(ROOT)),
        "applies_count": applies_count,
        "tagline": curation.get("issue_tagline", ""),
        "edition": "weekly",
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Build this week's generative Weekly Edition")
    ap.add_argument("--date", help="ISO date YYYY-MM-DD (default: today UTC)")
    ap.add_argument("--public-base-url", default=os.environ.get("PUBLIC_BASE_URL", ""),
                    help="Public origin for Pages")
    args = ap.parse_args()

    date = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    result = build_weekly(date, public_base_url=args.public_base_url or None)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
