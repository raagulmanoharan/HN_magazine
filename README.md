# Morning Edition

A one-reader daily. Every morning at 7 AM, a GitHub Actions cron job sweeps
~11 curated sources (HN, Lobste.rs, Anthropic / OpenAI / DeepMind news,
Simon Willison, GitHub trending, Sidebar, Quanta, Schneier, Product Hunt),
asks Claude to rank across them by taste (UX, AI shipping news, creative
software, dev tools, privacy, weird science, actionable things), picks 10,
and renders them as a self-contained editorial magazine — each story cast
into one of eighteen spread styles, ten of which land in any given issue.
It publishes to GitHub Pages and WhatsApps you the link.

## How it works

```
.github/workflows/morning-edition.yml   cron @ 11:00 + 12:00 UTC (07:00 ET DST-safe)
  └── scripts/build.py                  orchestrator
        ├── scripts/fetch_sources.py    parallel fetch across all sources,
        │     └── scripts/fetch_hn.py   dedup by URL, pre-rank by `prior`
        ├── scripts/curate.py           Claude editorial curator (prompt cached)
        └── scripts/render.py           10 distinct magazine spreads
  └── commit magazines/YYYY-MM-DD.html + index.html back to main
  └── GitHub Pages                      serves main directly
  └── scripts/notify.py                 Twilio WhatsApp message with public URL
```

### Ten spreads, cast from an eighteen-style palette

Each story gets its own full-viewport spread with a distinct background,
layout, and numeral treatment. No inline font is smaller than 18px. Claude
picks ten distinct styles each issue — the other eight sit out, which is
where day-to-day variance comes from.

**Core ten (v1)**

1. **hero** — cover page, giant Fraunces display
2. **midnight** — dark, outlined numeral in the bleed, neon accent
3. **rose-alert** — rose pink, rotated `APPLIES TO YOU` stamp when flagged
4. **terminal** — monospace CLI aesthetic with ASCII block numeral
5. **academic** — cream, drop-cap editorial with Roman numeral
6. **big-stat** — one giant number dominates the page
7. **newsprint** — two-column letterpress-flavored newsprint
8. **neon** — magenta/cyan gradient, brutalist skewed numeral
9. **zine** — zine sticker, marker scribble, offset title
10. **pullquote** — single enormous Fraunces italic pull quote

**Expansion pack (v2)**

11. **grid** — Swiss modernist, pure white, red-accent modular grid
12. **manifesto** — pitch-black, giant Fraunces italic declaration
13. **polaroid** — kraft scrapbook with a rotated photo card + washi tape
14. **ticker** — yellow/black hazard-tape bars, BREAKING marquee
15. **blueprint** — deep navy CAD aesthetic with technical annotations
16. **risograph** — duotone magenta/teal overprint, halftone texture
17. **index-card** — ruled 3x5 research note with red margin
18. **postcard** — airmail chevrons, rotated stamp + postmark

## Setup (one-time)

### 1. Enable GitHub Pages

Settings → Pages → Source: **Deploy from a branch → main → /(root)**.

### 2. Add secrets

Repo → Settings → Secrets and variables → Actions → New repository secret:

| Secret | What it's for |
|---|---|
| `ANTHROPIC_API_KEY` | Claude curator. Without it the pipeline falls back to a keyword-based curator so the build still ships. |
| `TWILIO_ACCOUNT_SID` | WhatsApp via Twilio |
| `TWILIO_AUTH_TOKEN` | WhatsApp via Twilio |
| `TWILIO_WHATSAPP_FROM` | e.g. `whatsapp:+14155238886` (Twilio sandbox works for testing) |
| `WHATSAPP_TO` | your number, e.g. `whatsapp:+15551234567` |

Optional repository variable:

| Variable | Default |
|---|---|
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` |

### 3. Tweak the schedule

`.github/workflows/morning-edition.yml` runs at 11:00 and 12:00 UTC, which
is 7 AM US Eastern year-round (it runs twice to be DST-safe, and the
downstream writes are idempotent). Change the `cron:` lines if you want a
different timezone.

## Local testing

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Dry run with no API key — heuristic curator, no WhatsApp
python scripts/build.py --no-notify

# Real run
export ANTHROPIC_API_KEY=sk-...
python scripts/build.py --no-notify
open magazines/$(date +%F).html
```

The curator falls back to a keyword heuristic when `ANTHROPIC_API_KEY` is
absent, so you can iterate on the renderer without burning tokens.

## Taste profile

The reader profile lives in `taste.json` at the repo root. `scripts/curate.py`
loads it at build time and interpolates it into the Claude system prompt
(wrapped in `cache_control: ephemeral` so only the day's story list changes
between runs).

Edit it by hand to tune what gets picked. Fields you can change:

- `profile` — the long prose description of loves/skips. Appended verbatim
  into the Claude system prompt.
- `applies_to_me_rule` — when the "APPLIES TO YOU" stamp should fire.
- `voice` — blurb tone, length, what to avoid.
- `sources.<name>.enabled` — flip `true`/`false` to silence a source.
- `paused_until` — ISO date; while set, the daily WhatsApp send is skipped
  (the build still runs and the HTML still publishes).

Commit and push; the next scheduled build picks it up.

## Sources & ranking

| Source | Weight | Why |
|---|---|---|
| `anthropic` | 0.98 | Claude shipping news — cover-material by default. |
| `openai` | 0.92 | Product + research shipping. |
| `simonwillison` | 0.88 | Hands-on LLM tooling, evals, prompt craft. |
| `deepmind` | 0.86 | Research + Gemini shipping. |
| `sidebar` | 0.84 | Curated design/UX links — rare, high-value for a UX designer. |
| `github_trending` | 0.82 | Repos with rising stars in the last 7 days. |
| `lobsters` | 0.80 | Smaller, higher-signal systems/languages than HN. |
| `hn` | 0.75 | Broad, noisy, strong on dev + AI. |
| `quanta` | 0.72 | Editorial-grade science journalism. |
| `schneier` | 0.66 | Analytical security, not breach-report chum. |
| `producthunt` | 0.55 | Marketing-heavy; filtered hard. |

Each candidate arrives with a local `prior = source_weight × rank_factor + log_score`,
but the curator treats `prior` as a tiebreaker. The real ranking rubric
(in `scripts/curate.py`) is: taste alignment → UX/design priority → AI
shipping freshness → actionability → cross-source diversity → prior.

Source feeds live in `scripts/fetch_sources.py` (`FEED_URLS`). To disable a
source without editing code, set `sources.<name>.enabled` to `false` in
`taste.json`. If a publisher changes their RSS path, update `FEED_URLS`.
