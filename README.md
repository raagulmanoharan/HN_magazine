# Morning Edition

A one-reader daily. Every morning at 7 AM, a GitHub Actions cron job fetches
the Hacker News front page, asks Claude to curate the 10 stories that fit
your taste (UX, AI tools, creative software, dev tools, privacy, weird
science, actionable things), renders them as a self-contained editorial
magazine with ten distinct spreads, publishes to GitHub Pages, and WhatsApps
you the link.

## How it works

```
.github/workflows/morning-edition.yml   cron @ 11:00 + 12:00 UTC (07:00 ET DST-safe)
  └── scripts/build.py                  orchestrator
        ├── scripts/fetch_hn.py         HN Firebase API, threaded top-30
        ├── scripts/curate.py           Claude editorial curator (prompt cached)
        └── scripts/render.py           10 distinct magazine spreads
  └── commit magazines/YYYY-MM-DD.html + index.html back to the branch
  └── actions/deploy-pages              publish
  └── scripts/notify.py                 Twilio WhatsApp message with public URL
```

### The ten spreads

Each story gets its own full-viewport spread with a distinct background,
layout, and numeral treatment. No inline font is smaller than 18px.

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

## Setup (one-time)

### 1. Enable GitHub Pages

Settings → Pages → Source: **GitHub Actions**.

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

Edit `TASTE_PROFILE` in `scripts/curate.py` to adjust what gets boosted and
what gets skipped. The block is sent to Claude with `cache_control:
ephemeral`, so daily runs benefit from prompt caching — only the story list
changes between calls.
