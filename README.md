# Morning Edition

A one-reader daily. Every morning at 7 AM, a GitHub Actions cron job sweeps
~11 curated sources (HN, Lobste.rs, Anthropic / OpenAI / DeepMind news,
Simon Willison, GitHub trending, Sidebar, Quanta, Schneier, Product Hunt),
asks Claude to rank across them by taste (UX, AI shipping news, creative
software, dev tools, privacy, weird science, actionable things), picks 10,
and renders them as a self-contained editorial magazine with ten distinct
spreads. It publishes to GitHub Pages and WhatsApps you the link.

## How it works

```
.github/workflows/morning-edition.yml   cron @ 11:00 + 12:00 UTC (07:00 ET DST-safe)
  └── scripts/build.py                  orchestrator
        ├── scripts/fetch_sources.py    parallel fetch across all sources,
        │     └── scripts/fetch_hn.py   dedup by URL, pre-rank by `prior`
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

The reader profile lives in `taste.json` at the repo root. `scripts/curate.py`
loads it at build time and interpolates it into the Claude system prompt
(wrapped in `cache_control: ephemeral` so only the day's story list changes
between runs).

You don't edit this file by hand. Instead, text the WhatsApp bot.

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

Source feeds live in `scripts/fetch_sources.py` (`FEED_URLS`). To toggle a
source on or off, text the bot: `stop product hunt` or `turn sidebar back on`.

## Tuning by WhatsApp (Shape A)

`api/twilio-whatsapp.py` is a Vercel serverless function that receives
inbound WhatsApp messages, classifies intent with Claude Haiku, and rewrites
`taste.json` through the GitHub Contents API. Messages you can send:

| Message | Effect |
|---|---|
| `more rust stuff` | Appends to the "Loves" list |
| `less crypto please` | Appends to the "Skip" list |
| `stop product hunt` | Disables a source |
| `turn sidebar back on` | Re-enables a source |
| `pause 3 days` | Sets `paused_until` — build script skips sends until then |
| `show` | Echoes your current profile |
| `reset` | Wipes profile back to defaults |

### One-time webhook setup

1. Sign up at [vercel.com](https://vercel.com) and import this repo.
2. In Vercel → Settings → Environment Variables, set:
   - `TWILIO_AUTH_TOKEN` — same value as the GH Actions secret
   - `ALLOWED_WHATSAPP_FROM` — your own `whatsapp:+…` number
   - `ANTHROPIC_API_KEY` — reused
   - `GH_TOKEN` — a fine-grained PAT with `Contents: write` on this repo
   - `GH_REPO` — e.g. `raagulmanoharan/HN_magazine`
   - `GH_BRANCH` — `main`
3. Deploy. Vercel gives you a URL like `https://hn-magazine.vercel.app`.
4. In Twilio Console → WhatsApp sender → "When a message comes in", paste
   `https://<your-vercel-url>/api/twilio-whatsapp` and save.

Now every reply you send to the morning link adjusts the next morning's
curation.
