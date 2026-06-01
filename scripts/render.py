"""Render the curated picks as a single self-contained HTML magazine.

The magazine is one long document; each of the 10 stories gets its own
full-viewport spread with a distinct background, layout, and numeral
treatment. No inline font is smaller than 18px — base body type is 22px
and display type goes up to 16vw.

Typography: Fraunces (serif display) + Inter (sans body), both via
Google Fonts. Both required by the brief.
"""
from __future__ import annotations

import datetime as dt
import html
import random
from typing import Any

# Ordered list of spread renderers is wired up at the bottom of this file
# (after each render_* function is defined).

GOOGLE_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?'
    'family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,500;0,9..144,700;0,9..144,900;1,9..144,500;1,9..144,900'
    '&family=Inter:wght@400;500;600;800&family=JetBrains+Mono:wght@400;700'
    '&display=swap" rel="stylesheet">'
)

# --------------------------------------------------------------------------
# Font pairings — rotated per issue for visual variety.
# Each pairing: (display_serif, body_sans, mono, google_families_param)
# The google_families_param is everything between "css2?" and "&display=swap".
# --------------------------------------------------------------------------
FONT_PAIRINGS = [
    {
        "display": "Fraunces",
        "body": "Inter",
        "mono": "JetBrains Mono",
        "google": (
            "family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,500;0,9..144,700;0,9..144,900;1,9..144,500;1,9..144,900"
            "&family=Inter:wght@400;500;600;800"
            "&family=JetBrains+Mono:wght@400;700"
        ),
    },
    {
        "display": "Playfair Display",
        "body": "DM Sans",
        "mono": "Fira Code",
        "google": (
            "family=Playfair+Display:ital,wght@0,400;0,700;0,900;1,400;1,700;1,900"
            "&family=DM+Sans:wght@400;500;600;700"
            "&family=Fira+Code:wght@400;700"
        ),
    },
    {
        "display": "Crimson Pro",
        "body": "Source Sans 3",
        "mono": "Source Code Pro",
        "google": (
            "family=Crimson+Pro:ital,wght@0,300;0,500;0,700;0,900;1,500;1,900"
            "&family=Source+Sans+3:wght@400;500;600;800"
            "&family=Source+Code+Pro:wght@400;700"
        ),
    },
    {
        "display": "Alegreya",
        "body": "Albert Sans",
        "mono": "IBM Plex Mono",
        "google": (
            "family=Alegreya:ital,wght@0,400;0,500;0,700;0,900;1,400;1,900"
            "&family=Albert+Sans:wght@400;500;600;800"
            "&family=IBM+Plex+Mono:wght@400;700"
        ),
    },
    {
        "display": "Vollkorn",
        "body": "Fira Sans",
        "mono": "Fira Code",
        "google": (
            "family=Vollkorn:ital,wght@0,400;0,700;0,900;1,400;1,900"
            "&family=Fira+Sans:wght@400;500;600;800"
            "&family=Fira+Code:wght@400;700"
        ),
    },
    {
        "display": "Merriweather",
        "body": "Open Sans",
        "mono": "Roboto Mono",
        "google": (
            "family=Merriweather:ital,wght@0,300;0,400;0,700;0,900;1,400;1,900"
            "&family=Open+Sans:wght@400;500;600;800"
            "&family=Roboto+Mono:wght@400;700"
        ),
    },
    {
        "display": "Bitter",
        "body": "Karla",
        "mono": "Space Mono",
        "google": (
            "family=Bitter:ital,wght@0,300;0,500;0,700;0,900;1,500;1,900"
            "&family=Karla:wght@400;500;600;800"
            "&family=Space+Mono:wght@400;700"
        ),
    },
    {
        "display": "Noto Serif Display",
        "body": "Noto Sans",
        "mono": "JetBrains Mono",
        "google": (
            "family=Noto+Serif+Display:ital,wght@0,300;0,500;0,700;0,900;1,500;1,900"
            "&family=Noto+Sans:wght@400;500;600;800"
            "&family=JetBrains+Mono:wght@400;700"
        ),
    },
    {
        "display": "Lora",
        "body": "Raleway",
        "mono": "Fira Code",
        "google": (
            "family=Lora:ital,wght@0,400;0,500;0,700;1,400;1,700"
            "&family=Raleway:wght@400;500;600;800"
            "&family=Fira+Code:wght@400;700"
        ),
    },
    {
        "display": "Cormorant Garamond",
        "body": "Work Sans",
        "mono": "IBM Plex Mono",
        "google": (
            "family=Cormorant+Garamond:ital,wght@0,300;0,400;0,700;1,400;1,700"
            "&family=Work+Sans:wght@400;500;600;800"
            "&family=IBM+Plex+Mono:wght@400;700"
        ),
    },
    {
        "display": "Spectral",
        "body": "Rubik",
        "mono": "Roboto Mono",
        "google": (
            "family=Spectral:ital,wght@0,300;0,500;0,700;0,800;1,500;1,800"
            "&family=Rubik:wght@400;500;600;800"
            "&family=Roboto+Mono:wght@400;700"
        ),
    },
    {
        "display": "EB Garamond",
        "body": "Manrope",
        "mono": "Source Code Pro",
        "google": (
            "family=EB+Garamond:ital,wght@0,400;0,500;0,700;0,800;1,400;1,800"
            "&family=Manrope:wght@400;500;600;800"
            "&family=Source+Code+Pro:wght@400;700"
        ),
    },
]


def _pick_fonts(today: dt.date) -> dict:
    n = len(FONT_PAIRINGS)
    epoch = dt.date(2025, 1, 1)
    day_num = (today - epoch).days
    cycle = day_num // n
    pos = day_num % n
    rng = random.Random(cycle)
    order = list(range(n))
    rng.shuffle(order)
    return FONT_PAIRINGS[order[pos]]


def _swap_fonts(html_str: str, fonts: dict) -> str:
    """Replace default font names and Google Fonts link with the day's pairing."""
    if fonts["display"] == "Fraunces":
        return html_str

    gf_link = (
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        f'<link href="https://fonts.googleapis.com/css2?{fonts["google"]}'
        '&display=swap" rel="stylesheet">'
    )
    out = html_str.replace(GOOGLE_FONTS, gf_link)
    out = out.replace("'Fraunces'", f"'{fonts['display']}'")
    out = out.replace("'Inter'", f"'{fonts['body']}'")
    out = out.replace("'JetBrains Mono'", f"'{fonts['mono']}'")
    out = out.replace("Fraunces and Inter", f"{fonts['display']} and {fonts['body']}")
    return out


def esc(s: Any) -> str:
    """HTML-escape; accepts anything stringifiable."""
    return html.escape("" if s is None else str(s), quote=True)


def fmt_date(d: dt.date) -> str:
    return d.strftime("%A, %B %-d, %Y").upper()


def numeral(n: int) -> str:
    """Two-digit numeral string. 1 -> 01, 10 -> 10."""
    return f"{n:02d}"


# --------------------------------------------------------------------------
# Base CSS — shared resets, type scale, and per-spread rules. Every rule
# here is deliberately written to keep text large (>= 18px everywhere).
# --------------------------------------------------------------------------
BASE_CSS = r"""
*,*::before,*::after{box-sizing:border-box}
html,body{margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:'Inter',system-ui,sans-serif;font-size:22px;line-height:1.45;
  color:#111;background:#f6f1e7;-webkit-font-smoothing:antialiased;
  text-rendering:optimizeLegibility}
a{color:inherit;text-underline-offset:4px}
.spread{position:relative;min-height:100vh;padding:clamp(48px,6vw,110px);
  overflow:hidden;display:flex;flex-direction:column;justify-content:space-between}
.spread--short{min-height:auto}
.spread h2,.cover-title{overflow-wrap:break-word;word-break:break-word}
.kicker{font-family:'Inter',sans-serif;font-weight:800;letter-spacing:.28em;
  font-size:20px;text-transform:uppercase}
.meta-row{display:flex;gap:28px;flex-wrap:wrap;font-family:'Inter',sans-serif;
  font-weight:500;font-size:18px;letter-spacing:.08em;text-transform:uppercase;opacity:.75}
.body-lead{font-family:'Fraunces',serif;font-weight:400;font-size:clamp(24px,2.2vw,32px);
  line-height:1.45;max-width:28ch}
.body-lead--wide{max-width:40ch}
.tag-applies{display:inline-block;padding:10px 20px;border:3px solid currentColor;
  font-family:'Inter',sans-serif;font-weight:800;font-size:18px;letter-spacing:.22em;
  text-transform:uppercase;border-radius:2px}
.apply-note{font-family:'Inter',sans-serif;font-size:22px;line-height:1.5;font-weight:500;
  max-width:42ch}
.read-more{font-family:'Inter',sans-serif;font-weight:700;font-size:20px;letter-spacing:.12em;
  text-transform:uppercase;border-bottom:3px solid currentColor;padding-bottom:6px;
  text-decoration:none;display:inline-block}
.footer-slug{font-family:'Inter',sans-serif;font-size:18px;letter-spacing:.22em;
  text-transform:uppercase;opacity:.55;margin-top:40px}

/* ---- 01 HERO ---- */
.s-hero{background:#f4ecd8;color:#17140e}
.s-hero .masthead{display:flex;justify-content:space-between;align-items:flex-end;
  border-bottom:4px solid #17140e;padding-bottom:18px}
.s-hero .masthead h1{font-family:'Fraunces',serif;font-style:italic;font-weight:900;
  font-size:clamp(44px,5vw,72px);margin:0;letter-spacing:-.02em}
.s-hero .issue-meta{text-align:right;font-family:'Inter',sans-serif;font-weight:600;
  font-size:20px;letter-spacing:.14em;text-transform:uppercase;line-height:1.5}
.s-hero .cover-body{display:grid;grid-template-columns:1fr auto;gap:48px;align-items:end;
  margin-top:auto}
.s-hero .cover-numeral{font-family:'Fraunces',serif;font-weight:900;
  font-size:clamp(200px,28vw,420px);line-height:.82;letter-spacing:-.05em;color:#b63b1f}
.s-hero .cover-title{font-family:'Fraunces',serif;font-weight:900;
  font-size:clamp(56px,7.5vw,136px);line-height:.95;letter-spacing:-.035em;margin:0 0 28px}
.s-hero .cover-tagline{font-family:'Fraunces',serif;font-style:italic;font-weight:500;
  font-size:clamp(26px,2.4vw,36px);max-width:30ch;line-height:1.3;margin:0 0 32px}
.s-hero .cover-kicker{font-family:'Inter',sans-serif;font-weight:800;
  font-size:22px;letter-spacing:.3em;text-transform:uppercase;color:#b63b1f;margin-bottom:24px}
@media(max-width:900px){.s-hero .cover-body{grid-template-columns:1fr}
  .s-hero .cover-numeral{font-size:42vw}}

/* ---- 02 MIDNIGHT ---- */
.s-midnight{background:#0b0b14;color:#f3ecd8}
.s-midnight .bg-num{position:absolute;right:-4vw;top:10%;font-family:'Fraunces',serif;
  font-weight:900;font-size:56vw;line-height:.8;color:transparent;
  -webkit-text-stroke:2px rgba(243,236,216,.18);pointer-events:none;user-select:none}
.s-midnight .content{position:relative;z-index:2;max-width:62ch}
.s-midnight .kicker{color:#9ad9ff}
.s-midnight h2{font-family:'Fraunces',serif;font-style:italic;font-weight:500;
  font-size:clamp(52px,6.4vw,108px);line-height:1;letter-spacing:-.02em;margin:28px 0 36px}
.s-midnight .body-lead{color:#f3ecd8;opacity:.9}
.s-midnight .read-more{color:#9ad9ff;border-color:#9ad9ff}
.s-midnight .apply-note{color:#9ad9ff}

/* ---- 03 ROSE ALERT ---- */
.s-rose{background:#e9b1a3;color:#3a0f08}
.s-rose .stamp{position:absolute;top:72px;right:72px;transform:rotate(9deg);
  border:5px double #8a1a0c;color:#8a1a0c;padding:22px 32px;font-family:'Inter',sans-serif;
  font-weight:800;font-size:22px;letter-spacing:.28em;text-transform:uppercase;
  background:rgba(255,255,255,.06);border-radius:6px;line-height:1.1;text-align:center}
.s-rose .numeral-xl{font-family:'Fraunces',serif;font-weight:900;font-size:clamp(140px,18vw,260px);
  line-height:.85;color:#8a1a0c;letter-spacing:-.04em;margin:0}
.s-rose h2{font-family:'Fraunces',serif;font-weight:900;font-size:clamp(44px,5.4vw,90px);
  line-height:1;letter-spacing:-.025em;margin:24px 0 32px;max-width:22ch}
.s-rose .kicker{color:#8a1a0c}
.s-rose .read-more{color:#8a1a0c;border-color:#8a1a0c}
.s-rose .apply-note{color:#3a0f08}
@media(max-width:700px){.s-rose .stamp{top:24px;right:24px;padding:14px 20px;font-size:18px}}

/* ---- 04 TERMINAL ---- */
.s-terminal{background:#050807;color:#7fffb0;font-family:'JetBrains Mono',monospace}
.s-terminal .window{border:2px solid #2a3a32;border-radius:8px;padding:28px 36px;
  background:#070d0b;max-width:100%;box-shadow:0 0 80px rgba(127,255,176,.08)}
.s-terminal .chrome{display:flex;gap:10px;margin-bottom:28px}
.s-terminal .dot{width:14px;height:14px;border-radius:50%;background:#2a3a32}
.s-terminal .prompt{font-size:24px;line-height:1.6}
.s-terminal .prompt .dollar{color:#4a8a6a}
.s-terminal .prompt .cmd{color:#7fffb0}
.s-terminal .prompt .arg{color:#f3e87a}
.s-terminal h2{font-family:'JetBrains Mono',monospace;font-weight:700;
  font-size:clamp(36px,4.4vw,72px);line-height:1.15;letter-spacing:-.01em;
  color:#eafff3;margin:18px 0 28px}
.s-terminal .ascii-num{white-space:pre;font-size:clamp(20px,1.6vw,26px);line-height:1;
  color:#4a8a6a;margin-bottom:28px;font-weight:700}
.s-terminal .body-lead{font-family:'JetBrains Mono',monospace;font-size:22px;
  line-height:1.6;color:#c7f5d9;max-width:62ch}
.s-terminal .read-more{color:#7fffb0;border-color:#7fffb0;font-family:'JetBrains Mono',monospace}
.s-terminal .apply-note{color:#f3e87a;font-family:'JetBrains Mono',monospace}
.s-terminal .kicker{color:#f3e87a}

/* ---- 05 ACADEMIC ---- */
.s-academic{background:#efe7d4;color:#1a1712}
.s-academic .masthead-line{display:flex;justify-content:space-between;align-items:baseline;
  border-bottom:1.5px solid #1a1712;padding-bottom:10px;font-family:'Fraunces',serif;
  font-style:italic;font-size:20px}
.s-academic .roman{font-family:'Fraunces',serif;font-weight:500;font-size:24px;letter-spacing:.3em}
.s-academic h2{font-family:'Fraunces',serif;font-weight:500;font-size:clamp(44px,5vw,88px);
  line-height:1.05;letter-spacing:-.015em;margin:40px 0 28px;max-width:24ch}
.s-academic .body-lead{column-count:2;column-gap:56px;max-width:none;font-size:24px;line-height:1.55}
.s-academic .body-lead::first-letter{font-family:'Fraunces',serif;font-weight:900;float:left;
  font-size:clamp(110px,12vw,180px);line-height:.82;margin:12px 18px 0 -6px;color:#6b2414}
.s-academic .footnote{font-family:'Fraunces',serif;font-style:italic;font-size:20px;
  border-top:1.5px solid #1a1712;padding-top:16px;max-width:60ch;margin-top:32px}
.s-academic .kicker{color:#6b2414}
@media(max-width:800px){.s-academic .body-lead{column-count:1}}

/* ---- 06 BIG STAT ---- */
.s-stat{background:#ffffff;color:#0a0a0a;display:grid;grid-template-rows:auto 1fr auto;gap:0}
.s-stat .top{display:flex;justify-content:space-between;align-items:flex-start}
.s-stat .chip{font-family:'Inter',sans-serif;font-weight:800;font-size:20px;
  letter-spacing:.22em;text-transform:uppercase;border:3px solid #0a0a0a;padding:10px 18px}
.s-stat .stat-wrap{display:flex;flex-direction:column;justify-content:center;align-items:center;
  text-align:center;padding:40px 0}
.s-stat .stat-value{font-family:'Fraunces',serif;font-weight:900;
  font-size:clamp(200px,34vw,520px);line-height:.82;letter-spacing:-.06em;color:#e04b28}
.s-stat .stat-label{font-family:'Inter',sans-serif;font-weight:800;
  font-size:clamp(22px,1.8vw,28px);letter-spacing:.32em;text-transform:uppercase;margin-top:12px}
.s-stat h2{font-family:'Fraunces',serif;font-weight:500;font-style:italic;
  font-size:clamp(32px,3.4vw,54px);line-height:1.15;max-width:30ch;margin:32px 0 18px}
.s-stat .read-more{color:#e04b28;border-color:#e04b28}

/* ---- 07 NEWSPRINT ---- */
.s-newsprint{background:#ece4d0;color:#141210;background-image:
  repeating-linear-gradient(0deg,rgba(20,18,16,.025) 0 1px,transparent 1px 3px)}
.s-newsprint .masthead-bar{font-family:'Fraunces',serif;font-weight:900;font-style:italic;
  font-size:clamp(40px,4.6vw,72px);border-top:6px solid #141210;border-bottom:2px solid #141210;
  padding:14px 0;letter-spacing:-.01em}
.s-newsprint .badge{display:inline-flex;align-items:center;justify-content:center;
  width:clamp(96px,9vw,140px);height:clamp(96px,9vw,140px);border:4px solid #141210;
  border-radius:50%;font-family:'Fraunces',serif;font-weight:900;
  font-size:clamp(40px,4vw,64px);line-height:1}
.s-newsprint .title-row{display:grid;grid-template-columns:auto 1fr;gap:36px;align-items:center;margin-top:36px}
.s-newsprint h2{font-family:'Fraunces',serif;font-weight:900;font-size:clamp(42px,5vw,88px);
  line-height:1;letter-spacing:-.02em;margin:0}
.s-newsprint .cols{column-count:2;column-gap:48px;margin-top:36px;font-size:22px;line-height:1.55}
@media(max-width:800px){.s-newsprint .cols{column-count:1}}

/* ---- 08 NEON ---- */
.s-neon{background:linear-gradient(135deg,#ff2bd6 0%,#ff7a00 45%,#10e5ff 100%);color:#0a0018}
.s-neon .numeral-slash{font-family:'Inter',sans-serif;font-weight:800;font-style:italic;
  font-size:clamp(180px,26vw,420px);line-height:.8;transform:skewX(-12deg);
  -webkit-text-stroke:4px #0a0018;color:transparent;letter-spacing:-.04em}
.s-neon h2{font-family:'Inter',sans-serif;font-weight:800;font-size:clamp(44px,5.6vw,96px);
  line-height:.95;letter-spacing:-.025em;margin:16px 0 28px;text-transform:uppercase;max-width:22ch}
.s-neon .kicker{background:#0a0018;color:#10e5ff;padding:10px 16px;display:inline-block}
.s-neon .body-lead{color:#0a0018;font-family:'Inter',sans-serif;font-weight:500}
.s-neon .read-more{color:#0a0018;border-color:#0a0018}
.s-neon .apply-note{background:#0a0018;color:#10e5ff;padding:20px 24px;display:inline-block}

/* ---- 09 ZINE ---- */
.s-zine{background:#f2e9d0;color:#1a1a1a;background-image:
  radial-gradient(circle at 15% 20%,rgba(0,0,0,.04) 0 1px,transparent 1px),
  radial-gradient(circle at 70% 60%,rgba(0,0,0,.04) 0 1px,transparent 1px);
  background-size:14px 14px,22px 22px}
.s-zine .sticker{display:inline-block;background:#ffd93a;padding:14px 22px;
  font-family:'Inter',sans-serif;font-weight:800;font-size:22px;letter-spacing:.22em;
  text-transform:uppercase;transform:rotate(-3deg);border:3px solid #1a1a1a;
  box-shadow:6px 6px 0 #1a1a1a}
.s-zine .marker-num{font-family:'Fraunces',serif;font-style:italic;font-weight:900;
  font-size:clamp(160px,22vw,340px);line-height:.85;color:#1a1a1a;transform:rotate(-4deg);
  display:inline-block;position:relative}
.s-zine .marker-num::after{content:"";position:absolute;left:-4%;right:-4%;top:48%;height:18%;
  background:#ff4d3a;mix-blend-mode:multiply;z-index:-1;transform:rotate(2deg);border-radius:6px}
.s-zine h2{font-family:'Fraunces',serif;font-weight:900;font-size:clamp(44px,5.4vw,92px);
  line-height:1;letter-spacing:-.02em;margin:28px 0 28px;transform:rotate(-.5deg);max-width:22ch}
.s-zine .read-more{color:#ff4d3a;border-color:#ff4d3a}
.s-zine .scribble{display:block;width:220px;height:8px;background:#ff4d3a;
  clip-path:polygon(0 40%,10% 60%,20% 30%,30% 70%,40% 40%,50% 60%,60% 30%,70% 70%,80% 40%,90% 60%,100% 40%,100% 100%,0 100%);
  margin:10px 0 20px}

/* ---- 10 PULLQUOTE ---- */
.s-pullquote{background:#111820;color:#f3ecd8}
.s-pullquote .top{display:flex;justify-content:space-between;align-items:baseline}
.s-pullquote .tiny-num{font-family:'Fraunces',serif;font-weight:500;font-style:italic;
  font-size:clamp(40px,4vw,64px);opacity:.6}
.s-pullquote .quote-open{font-family:'Fraunces',serif;font-weight:900;font-size:clamp(200px,24vw,360px);
  line-height:.7;color:#d9b26a;margin:0 0 -20px -20px;display:block}
.s-pullquote .pq{font-family:'Fraunces',serif;font-style:italic;font-weight:500;
  font-size:clamp(48px,6.4vw,120px);line-height:1.02;letter-spacing:-.02em;
  max-width:26ch;margin:0 0 40px}
.s-pullquote .attrib{font-family:'Inter',sans-serif;font-weight:600;font-size:22px;
  letter-spacing:.2em;text-transform:uppercase;opacity:.8}
.s-pullquote .read-more{color:#d9b26a;border-color:#d9b26a}
.s-pullquote .apply-note{color:#d9b26a}

/* ---- 11 GRID (Swiss) ---- */
.s-grid{background:#ffffff;color:#111}
.s-grid .grid-top{display:flex;justify-content:space-between;align-items:baseline;
  border-bottom:2px solid #e63025;padding-bottom:14px}
.s-grid .tag{font-family:'Inter',sans-serif;font-weight:800;font-size:20px;
  letter-spacing:.28em;text-transform:uppercase;color:#e63025}
.s-grid .num-corner{font-family:'Inter',sans-serif;font-weight:800;font-size:28px;
  letter-spacing:.06em;color:#111}
.s-grid .grid-body{display:grid;grid-template-columns:1.3fr 1fr;gap:56px;margin-top:56px;align-items:start}
.s-grid h2{font-family:'Inter',sans-serif;font-weight:800;font-size:clamp(42px,5vw,84px);
  line-height:1.02;letter-spacing:-.025em;margin:0}
.s-grid .side{border-left:3px solid #e63025;padding-left:24px}
.s-grid .side .body-lead{font-family:'Inter',sans-serif;font-weight:500;font-size:22px;
  line-height:1.5;max-width:34ch;color:#111}
.s-grid .read-more{color:#e63025;border-color:#e63025}
@media(max-width:800px){.s-grid .grid-body{grid-template-columns:1fr;gap:28px;margin-top:32px}}

/* ---- 12 MANIFESTO ---- */
.s-manifesto{background:#0a0a0a;color:#f5ebd7}
.s-manifesto .top{display:flex;justify-content:space-between;align-items:baseline}
.s-manifesto .kicker{color:#e8a34b}
.s-manifesto .tiny-num{font-family:'Fraunces',serif;font-style:italic;font-weight:500;
  font-size:28px;opacity:.6;letter-spacing:.06em}
.s-manifesto h2{font-family:'Fraunces',serif;font-style:italic;font-weight:900;
  font-size:clamp(60px,8vw,160px);line-height:.98;letter-spacing:-.03em;
  margin:auto 0;max-width:18ch}
.s-manifesto .mark{color:#e8a34b}
.s-manifesto .attrib{font-family:'Inter',sans-serif;font-weight:600;font-size:20px;
  letter-spacing:.22em;text-transform:uppercase;opacity:.7}
.s-manifesto .read-more{color:#e8a34b;border-color:#e8a34b}
.s-manifesto .apply-note{color:#e8a34b}

/* ---- 13 POLAROID (scrapbook) ---- */
.s-polaroid{background:#d9c28c;color:#1d1408;background-image:
  radial-gradient(circle at 30% 20%,rgba(0,0,0,.04) 0 1px,transparent 1px),
  radial-gradient(circle at 80% 70%,rgba(0,0,0,.06) 0 1px,transparent 1px);
  background-size:10px 10px,16px 16px}
.s-polaroid .photo{background:#fdfaf1;padding:28px 28px 56px;
  box-shadow:0 20px 40px rgba(0,0,0,.25);transform:rotate(-3deg);
  max-width:clamp(280px,42vw,540px);position:relative}
.s-polaroid .photo-body{min-height:clamp(180px,28vw,340px);
  background:linear-gradient(135deg,#9ec1c4 0%,#cfa4a6 45%,#edd6ac 100%);
  display:flex;align-items:center;justify-content:center;text-align:center;
  padding:24px;font-family:'Fraunces',serif;font-weight:500;font-style:italic;
  color:#1d1408;font-size:clamp(20px,2vw,28px);line-height:1.25;
  hyphens:auto;overflow-wrap:break-word}
.s-polaroid .photo-caption{font-family:'Inter',sans-serif;font-weight:600;font-size:20px;
  letter-spacing:.1em;text-transform:uppercase;margin-top:18px;text-align:center}
.s-polaroid .tape{position:absolute;width:140px;height:28px;top:-14px;left:50%;
  transform:translateX(-50%) rotate(-3deg);background:rgba(231,165,122,.75);
  border-left:1px dashed rgba(0,0,0,.08);border-right:1px dashed rgba(0,0,0,.08)}
.s-polaroid .layout{display:grid;grid-template-columns:auto 1fr;gap:48px;align-items:center;margin-top:32px}
.s-polaroid h2{font-family:'Fraunces',serif;font-weight:900;font-size:clamp(38px,4.6vw,76px);
  line-height:1;letter-spacing:-.02em;margin:0 0 24px;max-width:20ch}
.s-polaroid .kicker{color:#7c3a0c}
.s-polaroid .read-more{color:#7c3a0c;border-color:#7c3a0c}
@media(max-width:800px){.s-polaroid .layout{grid-template-columns:1fr;gap:28px}
  .s-polaroid .photo{transform:rotate(-2deg);max-width:none}}

/* ---- 14 TICKER (hazard tape) ---- */
.s-ticker{background:#111;color:#ffe73d;padding-top:0;padding-bottom:0}
.s-ticker .bar{height:56px;background:repeating-linear-gradient(45deg,
  #ffe73d 0 24px,#111 24px 48px);display:flex;align-items:center;
  font-family:'Inter',sans-serif;font-weight:800;letter-spacing:.3em;font-size:20px;
  text-transform:uppercase;padding:0 32px;color:#111;
  -webkit-text-stroke:0;background-clip:padding-box}
.s-ticker .bar .bar-inner{background:#ffe73d;padding:6px 18px}
.s-ticker .core{padding:clamp(48px,6vw,110px);flex:1;
  display:flex;flex-direction:column;justify-content:center;gap:24px}
.s-ticker .kicker{color:#ffe73d}
.s-ticker h2{font-family:'Inter',sans-serif;font-weight:800;font-size:clamp(44px,5.6vw,96px);
  line-height:.98;letter-spacing:-.025em;margin:0;color:#fdfdfd;max-width:22ch;text-transform:uppercase}
.s-ticker .big-num{font-family:'JetBrains Mono',monospace;font-weight:700;color:#ffe73d;
  font-size:clamp(32px,3.4vw,56px);letter-spacing:.08em}
.s-ticker .body-lead{color:#f4f4f4;font-family:'Inter',sans-serif;font-weight:500;max-width:46ch}
.s-ticker .read-more{color:#ffe73d;border-color:#ffe73d}
.s-ticker .apply-note{color:#ffe73d}

/* ---- 15 BLUEPRINT (technical) ---- */
.s-blueprint{background:#0d1b3a;color:#d6e3ff;background-image:
  linear-gradient(rgba(214,227,255,.07) 1px,transparent 1px),
  linear-gradient(90deg,rgba(214,227,255,.07) 1px,transparent 1px);
  background-size:32px 32px,32px 32px}
.s-blueprint .frame{border:1.5px solid rgba(214,227,255,.4);padding:32px;position:relative}
.s-blueprint .frame::before,.s-blueprint .frame::after{content:"";position:absolute;
  width:12px;height:12px;border:1.5px solid rgba(214,227,255,.6)}
.s-blueprint .frame::before{top:-7px;left:-7px}
.s-blueprint .frame::after{bottom:-7px;right:-7px}
.s-blueprint .spec{font-family:'JetBrains Mono',monospace;font-size:20px;
  letter-spacing:.06em;color:rgba(214,227,255,.75);display:flex;justify-content:space-between;
  margin-bottom:24px;flex-wrap:wrap;gap:16px}
.s-blueprint h2{font-family:'Fraunces',serif;font-weight:300;font-size:clamp(44px,5.2vw,92px);
  line-height:1.02;letter-spacing:-.015em;margin:0 0 28px;max-width:24ch;color:#f2f6ff}
.s-blueprint .kicker{color:#7fbfff;font-family:'JetBrains Mono',monospace;font-weight:700;letter-spacing:.2em}
.s-blueprint .big-n{font-family:'JetBrains Mono',monospace;font-weight:700;font-size:clamp(80px,11vw,180px);
  line-height:.9;color:rgba(127,191,255,.65);letter-spacing:-.02em}
.s-blueprint .body-lead{color:#d6e3ff;font-family:'Inter',sans-serif;font-weight:500;max-width:52ch}
.s-blueprint .read-more{color:#7fbfff;border-color:#7fbfff;font-family:'JetBrains Mono',monospace}
.s-blueprint .apply-note{color:#7fbfff}

/* ---- 16 RISOGRAPH (duotone) ---- */
.s-riso{background:#f4efe2;color:#1a1a1a;position:relative;overflow:hidden}
.s-riso::before{content:"";position:absolute;inset:0;background-image:
  radial-gradient(circle at 15% 22%,rgba(255,71,140,.18) 0 2px,transparent 2px),
  radial-gradient(circle at 60% 70%,rgba(10,184,190,.16) 0 2px,transparent 2px);
  background-size:12px 12px,14px 14px;pointer-events:none;mix-blend-mode:multiply}
.s-riso .layout{position:relative;z-index:1}
.s-riso .kicker{color:#ff478c}
.s-riso h2{font-family:'Fraunces',serif;font-weight:900;font-size:clamp(44px,5.4vw,96px);
  line-height:1;letter-spacing:-.02em;margin:16px 0 32px;max-width:22ch;color:#1a1a1a;
  text-shadow:3px 3px 0 rgba(10,184,190,.55),-3px -3px 0 rgba(255,71,140,.45)}
.s-riso .riso-num{font-family:'Fraunces',serif;font-weight:900;font-size:clamp(160px,22vw,320px);
  line-height:.85;color:#ff478c;letter-spacing:-.04em;display:inline-block;position:relative}
.s-riso .riso-num::after{content:attr(data-n);position:absolute;left:6px;top:6px;
  color:#0ab8be;mix-blend-mode:multiply;z-index:-1}
.s-riso .body-lead{color:#1a1a1a;max-width:52ch}
.s-riso .read-more{color:#ff478c;border-color:#ff478c}
.s-riso .apply-note{color:#0a7b80}

/* ---- 17 INDEX CARD (3x5 ruled note) ----
   Decoration is anchored to elements (border-bottom on header, background
   on body) rather than absolute pixel offsets, so the red rule and ruled
   lines never overlap the title. */
.s-index{background:#fdf6e3;color:#1a1a1a;position:relative;overflow:hidden}
.s-index::before{content:"";position:absolute;left:clamp(48px,7vw,120px);top:0;bottom:0;
  width:2px;background:#d64545;pointer-events:none;z-index:1}
.s-index .ix-top{display:flex;justify-content:space-between;align-items:baseline;
  font-family:'JetBrains Mono',monospace;font-size:20px;color:#5a5040;
  letter-spacing:.12em;text-transform:uppercase;
  border-bottom:2px solid #d64545;padding:0 0 18px clamp(70px,9vw,148px);
  position:relative;z-index:2}
.s-index .ix-body{padding:36px 0 0 clamp(70px,9vw,148px);position:relative;z-index:2;
  background-image:repeating-linear-gradient(0deg,
    transparent 0 41px,rgba(102,150,200,.42) 41px 42px);
  background-position:0 36px}
.s-index h2{font-family:'Fraunces',serif;font-style:italic;font-weight:500;
  font-size:clamp(36px,4.4vw,64px);line-height:1.3;letter-spacing:-.01em;
  margin:0 0 28px;max-width:26ch}
.s-index .body-lead{font-family:'Fraunces',serif;font-weight:400;line-height:1.5;
  font-size:22px;max-width:52ch}
.s-index .read-more{color:#d64545;border-color:#d64545}
.s-index .apply-note{color:#1a1a1a}

/* ---- 18 POSTCARD (airmail) ---- */
.s-postcard{background:#f5ebd7;color:#1a1712;position:relative;
  border:14px solid transparent;border-image:repeating-linear-gradient(45deg,
  #d42c2c 0 14px,#f5ebd7 14px 28px,#2a53d4 28px 42px,#f5ebd7 42px 56px) 14}
.s-postcard .pc-inner{position:relative}
.s-postcard .stamp{position:absolute;top:0;right:0;width:clamp(130px,14vw,200px);
  height:clamp(160px,16vw,240px);background:#f0d9b7;border:6px solid #f5ebd7;
  outline:2px dashed rgba(26,23,18,.5);transform:rotate(4deg);
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  padding:20px;text-align:center;font-family:'Fraunces',serif;font-style:italic;
  font-weight:900;font-size:clamp(28px,3vw,46px);color:#7c2020;line-height:1;letter-spacing:-.02em}
.s-postcard .stamp small{display:block;font-family:'Inter',sans-serif;font-style:normal;
  font-weight:800;font-size:18px;letter-spacing:.18em;text-transform:uppercase;
  margin-top:10px;color:#1a1712}
.s-postcard .postmark{position:absolute;top:clamp(80px,8vw,120px);right:clamp(90px,10vw,160px);
  width:clamp(100px,10vw,150px);height:clamp(100px,10vw,150px);
  border:3px solid rgba(26,23,18,.55);border-radius:50%;display:flex;align-items:center;
  justify-content:center;text-align:center;font-family:'Inter',sans-serif;font-weight:800;
  font-size:14px;letter-spacing:.18em;text-transform:uppercase;color:rgba(26,23,18,.7);
  transform:rotate(-8deg);line-height:1.15;padding:8px}
.s-postcard h2{font-family:'Fraunces',serif;font-style:italic;font-weight:900;
  font-size:clamp(40px,4.8vw,80px);line-height:1.05;letter-spacing:-.015em;
  margin:0 0 24px;max-width:18ch;padding-right:clamp(140px,16vw,240px)}
.s-postcard .kicker{color:#7c2020}
.s-postcard .body-lead{max-width:30ch;color:#1a1712}
.s-postcard .read-more{color:#7c2020;border-color:#7c2020}
.s-postcard .apply-note{color:#1a1712}
@media(max-width:720px){
  .s-postcard{border-width:10px;border-image-slice:10}
  .s-postcard .stamp{position:static;transform:none;margin:0 0 18px auto;
    width:120px;height:150px;font-size:26px}
  .s-postcard .postmark{position:static;margin:0 0 12px 0;width:100px;height:100px}
  .s-postcard h2{padding-right:0}
}

/* ---- Closing colophon ---- */
.colophon{background:#17140e;color:#f4ecd8;padding:clamp(48px,6vw,110px);
  display:flex;flex-direction:column;gap:32px}
.colophon h3{font-family:'Fraunces',serif;font-style:italic;font-weight:500;
  font-size:clamp(48px,5vw,84px);margin:0;line-height:1}
.colophon p{font-family:'Fraunces',serif;font-size:24px;line-height:1.5;max-width:56ch;margin:0}
.colophon .smallprint{font-family:'Inter',sans-serif;font-size:18px;letter-spacing:.18em;
  text-transform:uppercase;opacity:.55}

/* ============================================================
   MOBILE NAV — sticky bar + story drawer (hidden on desktop)
   ============================================================ */
#m-nav{display:none}
#m-drawer{
  display:none;position:fixed;top:44px;left:0;right:0;bottom:0;
  background:#17140e;z-index:99;overflow-y:auto;
  -webkit-overflow-scrolling:touch;padding-bottom:32px
}
#m-drawer.open{display:block}
.m-drawer-close{
  display:flex;align-items:center;justify-content:space-between;
  padding:14px 18px;border-bottom:1px solid rgba(244,236,216,.15);
  font-family:'Inter',sans-serif;font-size:11px;font-weight:700;
  letter-spacing:.2em;text-transform:uppercase;
  color:rgba(244,236,216,.5);cursor:pointer;user-select:none
}
.m-drawer-item{
  display:flex;align-items:flex-start;gap:14px;padding:15px 18px;
  border-bottom:1px solid rgba(244,236,216,.08);
  cursor:pointer;color:#f4ecd8;
  -webkit-tap-highlight-color:rgba(217,178,106,.15)
}
.m-drawer-item:active{background:rgba(244,236,216,.06)}
.m-drawer-num{
  font-family:'Inter',sans-serif;font-weight:800;font-size:11px;
  letter-spacing:.14em;color:#d9b26a;min-width:20px;
  padding-top:4px;flex-shrink:0
}
.m-drawer-title{
  font-family:'Fraunces',serif;font-style:italic;
  font-size:19px;line-height:1.3;color:#f4ecd8
}
.m-drawer-kicker{
  font-family:'Inter',sans-serif;font-size:10px;font-weight:700;
  letter-spacing:.18em;text-transform:uppercase;
  color:#d9b26a;margin-bottom:4px;display:block
}

/* ============================================================
   MOBILE LAYOUT  ≤ 720px
   Full-height scroll-snap cards. Portrait-first hierarchy:
   kicker → title → body → full-width CTA.
   All tap targets ≥ 44 × 44px. Font floor: 15px.
   ============================================================ */
@media(max-width:720px){

  /* --- Snap frame --- */
  html{scroll-snap-type:y mandatory}
  body{font-size:17px}

  /* --- Sticky nav bar --- */
  #m-nav{
    display:block;position:fixed;top:0;left:0;right:0;z-index:100
  }
  #m-nav-inner{
    display:flex;align-items:center;justify-content:space-between;
    padding:0 16px;height:44px;
    background:rgba(15,12,9,.94);
    backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);
    border-bottom:1px solid rgba(244,236,216,.1);
    position:relative;overflow:hidden
  }
  #m-nav-title{
    font-family:'Inter',sans-serif;font-weight:800;font-size:11px;
    letter-spacing:.18em;text-transform:uppercase;color:#f4ecd8;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
    max-width:55%
  }
  #m-toc-btn{
    display:flex;align-items:center;gap:7px;background:none;border:none;
    color:#f4ecd8;padding:8px 0 8px 8px;cursor:pointer;
    -webkit-tap-highlight-color:transparent;min-width:44px;
    justify-content:flex-end
  }
  #m-progress{
    font-family:'Inter',sans-serif;font-weight:700;font-size:11px;
    letter-spacing:.12em;color:#d9b26a
  }
  #m-bar{
    position:absolute;bottom:0;left:0;height:2px;
    background:linear-gradient(90deg,#d9b26a,#b63b1f);
    transition:width .3s ease;pointer-events:none
  }

  /* --- Spread: full-height snap card --- */
  .spread{
    padding:28px 20px 32px;
    min-height:100svh;min-height:100vh;
    scroll-snap-align:start;
    overflow:hidden
  }
  /* First spread clears the 44px nav bar */
  .spread:first-of-type{padding-top:60px}

  /* --- Base type --- */
  .kicker{font-size:12px;letter-spacing:.22em}
  .body-lead{font-size:17px;max-width:none;line-height:1.55;margin-top:14px}
  .apply-note{font-size:16px;max-width:none}
  /* Full-width touch-friendly CTA */
  .read-more{
    font-size:15px;padding:14px 20px;border-width:2.5px;border-radius:3px;
    display:block;text-align:center;width:100%
  }
  .meta-row{font-size:12px;gap:12px}
  .tag-applies{padding:8px 12px;font-size:12px;border-width:2px}
  .footer-slug{font-size:13px;letter-spacing:.14em;margin-top:22px}

  /* Inline CTA rows: stack vertically */
  .spread [style*="display:flex"][style*="gap:24px"]{
    flex-direction:column!important;gap:10px!important;align-items:stretch!important
  }

  /* --- 01 HERO --- */
  .s-hero{padding:0}
  .s-hero .masthead{
    padding:56px 20px 14px;
    flex-direction:column;align-items:flex-start;gap:4px;
    border-bottom-width:3px
  }
  .s-hero .masthead h1{font-size:28px;line-height:1;letter-spacing:-.01em}
  .s-hero .issue-meta{text-align:left;font-size:12px;letter-spacing:.1em}
  .s-hero .cover-body{
    padding:20px 20px 28px;display:flex;flex-direction:column;
    justify-content:space-between;flex:1;grid-template-columns:1fr;
    gap:0;margin-top:0
  }
  .s-hero .cover-numeral{display:none}
  .s-hero .cover-kicker{font-size:12px;letter-spacing:.22em;margin-bottom:12px}
  .s-hero .cover-title{font-size:clamp(32px,9vw,50px);margin:0 0 14px;line-height:.97}
  .s-hero .cover-tagline{font-size:17px;margin:0 0 16px;max-width:none;line-height:1.4}

  /* --- 02 MIDNIGHT --- */
  .s-midnight .bg-num{font-size:66vw;right:-6vw;top:6%;opacity:.55}
  .s-midnight .content{max-width:none}
  .s-midnight h2{font-size:clamp(30px,9vw,50px);margin:14px 0 16px;line-height:1.05}

  /* --- 03 ROSE --- */
  .s-rose .stamp{
    top:68px;right:16px;padding:7px 10px;font-size:11px;
    border-width:3px;letter-spacing:.16em;line-height:1.1;transform:rotate(6deg)
  }
  .s-rose .numeral-xl{font-size:32vw;line-height:.85;margin:16px 0 -4px}
  .s-rose h2{font-size:clamp(26px,8vw,44px);margin:12px 0 14px}

  /* --- 04 TERMINAL --- */
  .s-terminal .window{padding:14px 12px;border-radius:6px}
  .s-terminal .chrome{margin-bottom:14px}
  .s-terminal .dot{width:10px;height:10px}
  .s-terminal .ascii-num{font-size:9px;line-height:1.1;margin-bottom:12px}
  .s-terminal h2{font-size:clamp(20px,6.5vw,36px);margin:10px 0 12px}
  .s-terminal .body-lead{font-size:15px;line-height:1.55;max-width:none}
  .s-terminal .prompt{font-size:14px}

  /* --- 05 ACADEMIC --- */
  .s-academic .masthead-line{font-size:15px}
  .s-academic h2{font-size:clamp(26px,7.5vw,42px);margin:16px 0 14px}
  .s-academic .body-lead{column-count:1;font-size:17px}
  .s-academic .body-lead::first-letter{font-size:clamp(56px,17vw,84px);margin:4px 10px 0 -2px}
  .s-academic .footnote{font-size:15px}
  .s-academic .roman{font-size:16px}

  /* --- 06 BIG STAT --- */
  .s-stat .top{flex-direction:column;gap:10px;align-items:flex-start}
  .s-stat .chip{font-size:12px;padding:7px 12px;border-width:2px}
  .s-stat .stat-wrap{padding:16px 0}
  .s-stat .stat-value{font-size:38vw;line-height:.85}
  .s-stat .stat-label{font-size:13px;letter-spacing:.18em;margin-top:8px}
  .s-stat h2{font-size:clamp(18px,5vw,28px);margin:14px 0 8px}

  /* --- 07 NEWSPRINT --- */
  .s-newsprint .masthead-bar{font-size:28px;padding:7px 0;border-top-width:4px}
  .s-newsprint .title-row{grid-template-columns:1fr;gap:10px;margin-top:16px}
  .s-newsprint .badge{width:52px;height:52px;font-size:24px;border-width:3px}
  .s-newsprint h2{font-size:clamp(24px,7.5vw,42px)}
  .s-newsprint .cols{column-count:1;font-size:17px;margin-top:16px;line-height:1.6}

  /* --- 08 NEON --- */
  .s-neon .numeral-slash{font-size:44vw;-webkit-text-stroke-width:2px}
  .s-neon h2{font-size:clamp(26px,8vw,46px);margin:6px 0 14px}
  .s-neon .kicker{padding:7px 12px}
  .s-neon .apply-note{padding:12px 14px}

  /* --- 09 ZINE --- */
  .s-zine .marker-num{font-size:38vw}
  .s-zine h2{font-size:clamp(26px,8vw,44px);margin:12px 0 12px;transform:none}
  .s-zine .sticker{font-size:12px;padding:8px 12px;
    box-shadow:3px 3px 0 #1a1a1a;transform:none}
  .s-zine .scribble{width:70%;height:6px}

  /* --- 10 PULLQUOTE --- */
  .s-pullquote .quote-open{font-size:44vw;line-height:.72;margin:0 0 -6px -4px}
  .s-pullquote .pq{font-size:clamp(22px,7.5vw,38px);line-height:1.1;
    margin:0 0 14px;max-width:none}
  .s-pullquote .tiny-num{font-size:24px}
  .s-pullquote .attrib{font-size:12px;letter-spacing:.12em}

  /* --- 11 GRID --- */
  .s-grid h2{font-size:clamp(24px,7.5vw,42px)}
  .s-grid .tag{font-size:12px;letter-spacing:.18em}
  .s-grid .num-corner{font-size:16px}
  .s-grid .side{padding-left:14px;border-left-width:2px}
  .s-grid .side .body-lead{font-size:17px}

  /* --- 12 MANIFESTO --- */
  .s-manifesto h2{font-size:clamp(26px,8.5vw,46px);line-height:1.05;max-width:none}
  .s-manifesto .tiny-num{font-size:16px}
  .s-manifesto .attrib{font-size:12px;letter-spacing:.12em}

  /* --- 13 POLAROID --- */
  .s-polaroid .layout{grid-template-columns:1fr;gap:16px;margin-top:16px}
  .s-polaroid .photo{
    padding:12px 12px 26px;transform:rotate(-1.5deg);max-width:100%
  }
  .s-polaroid .photo-body{min-height:130px;font-size:15px}
  .s-polaroid .photo-caption{font-size:12px;letter-spacing:.12em;margin-top:10px}
  .s-polaroid .tape{width:64px}
  .s-polaroid h2{font-size:clamp(24px,7.5vw,42px);margin:0 0 14px}

  /* --- 14 TICKER --- */
  .s-ticker .bar{height:32px;font-size:11px;letter-spacing:.16em;padding:0 12px}
  .s-ticker .bar .bar-inner{padding:3px 8px}
  .s-ticker .core{padding:20px 20px;gap:14px}
  .s-ticker h2{font-size:clamp(24px,8.5vw,42px)}
  .s-ticker .big-num{font-size:17px;letter-spacing:.06em}

  /* --- 15 BLUEPRINT --- */
  .s-blueprint{background-size:16px 16px,16px 16px}
  .s-blueprint .frame{padding:16px 14px}
  .s-blueprint .spec{font-size:11px;gap:8px;margin-bottom:14px}
  .s-blueprint h2{font-size:clamp(24px,7vw,42px);margin-bottom:14px}
  .s-blueprint .big-n{font-size:16vw}
  /* collapse the inline big-n / body-lead side-by-side grid */
  .s-blueprint [style*="grid-template-columns:auto 1fr"]{
    grid-template-columns:1fr!important;gap:12px!important
  }

  /* --- 16 RISO --- */
  .s-riso h2{
    font-size:clamp(26px,8vw,44px);margin:10px 0 14px;
    text-shadow:2px 2px 0 rgba(10,184,190,.55),-2px -2px 0 rgba(255,71,140,.45)
  }
  .s-riso .riso-num{font-size:38vw}

  /* --- 17 INDEX CARD --- */
  .s-index::before{left:20px}
  .s-index .ix-top{
    font-size:12px;letter-spacing:.08em;padding-left:38px;padding-bottom:12px
  }
  .s-index .ix-body{
    padding-left:38px;padding-top:16px;
    background-image:repeating-linear-gradient(
      0deg,transparent 0 30px,rgba(102,150,200,.42) 30px 31px);
    background-position:0 16px
  }
  .s-index h2{font-size:clamp(20px,6.5vw,34px);margin:0 0 14px;line-height:1.3}
  .s-index .body-lead{font-size:16px;line-height:1.5}

  /* --- 18 POSTCARD --- */
  .s-postcard{border-width:10px;border-image-slice:10}
  .s-postcard .stamp{
    position:static;transform:none;margin:0 0 14px auto;
    width:96px;height:118px;font-size:20px
  }
  .s-postcard .postmark{
    position:static;margin:0 0 10px 0;
    width:82px;height:82px;font-size:11px
  }
  .s-postcard h2{font-size:clamp(22px,7.5vw,40px);padding-right:0}
  .s-postcard .body-lead{max-width:none}

  /* --- Colophon --- */
  .colophon{padding:32px 20px 52px;scroll-snap-align:start}
  .colophon h3{font-size:32px}
  .colophon p{font-size:17px}
}
"""


# --------------------------------------------------------------------------
# Shared fragments
# --------------------------------------------------------------------------
def _applies_badge(p: dict) -> str:
    if not p.get("applies_to_me"):
        return ""
    return '<span class="tag-applies">Applies to you</span>'


def _apply_note(p: dict) -> str:
    note = (p.get("apply_note") or "").strip()
    if not note:
        return ""
    return f'<p class="apply-note">&rarr; {esc(note)}</p>'


def _read_more(p: dict, label: str = "Read the story") -> str:
    return (
        f'<a class="read-more" href="{esc(p["url"])}" target="_blank" '
        f'rel="noopener">{esc(label)} &rarr;</a>'
    )


def _meta_line(p: dict) -> str:
    # Intentionally blank: spreads now surface a single CTA per article
    # (the source-link read-more) plus the optional "Applies to you" badge
    # and apply-note. Points/comments/discussion links were visual clutter.
    return ""


# --------------------------------------------------------------------------
# Spread renderers — one per style
# --------------------------------------------------------------------------
def render_hero(p: dict, issue: dict) -> str:
    date = issue["date_display"]
    issue_no = issue["issue_no"]
    tagline = issue.get("tagline") or ""
    return f"""
<section class="spread s-hero">
  <div class="masthead">
    <h1>Morning Edition</h1>
    <div class="issue-meta">
      <div>{esc(date)}</div>
      <div>Issue No. {esc(issue_no)}</div>
    </div>
  </div>
  <div class="cover-body">
    <div>
      <div class="cover-kicker">Today&rsquo;s lead &middot; {esc(p.get("kicker",""))}</div>
      <h2 class="cover-title">{esc(p["title"])}</h2>
      <p class="cover-tagline">{esc(tagline)}</p>
      <p class="body-lead body-lead--wide">{esc(p.get("blurb",""))}</p>
      <div style="margin-top:32px;display:flex;gap:24px;align-items:center;flex-wrap:wrap">
        {_read_more(p, "Open the lead")}
        {_applies_badge(p)}
      </div>
      {_apply_note(p)}
      {_meta_line(p)}
    </div>
    <div class="cover-numeral" aria-hidden="true">{numeral(p["rank"])}</div>
  </div>
</section>
"""


def render_midnight(p: dict, issue: dict) -> str:
    return f"""
<section class="spread s-midnight">
  <div class="bg-num" aria-hidden="true">{numeral(p["rank"])}</div>
  <div class="content">
    <div class="kicker">{esc(p.get("kicker","") or "After dark")}</div>
    <h2>{esc(p["title"])}</h2>
    <p class="body-lead">{esc(p.get("blurb",""))}</p>
    <div style="margin-top:36px;display:flex;gap:24px;align-items:center;flex-wrap:wrap">
      {_read_more(p)}
      {_applies_badge(p)}
    </div>
    {_apply_note(p)}
    {_meta_line(p)}
  </div>
  <div class="footer-slug">Morning Edition &middot; After Dark</div>
</section>
"""


def render_rose(p: dict, issue: dict) -> str:
    stamp = ""
    if p.get("applies_to_me"):
        stamp = '<div class="stamp">Applies<br>to&nbsp;you</div>'
    return f"""
<section class="spread s-rose">
  {stamp}
  <div>
    <div class="kicker">{esc(p.get("kicker","") or "Actionable")}</div>
    <div class="numeral-xl" aria-hidden="true">{numeral(p["rank"])}</div>
    <h2>{esc(p["title"])}</h2>
    <p class="body-lead">{esc(p.get("blurb",""))}</p>
  </div>
  <div>
    {_apply_note(p)}
    <div style="margin-top:28px">{_read_more(p, "Try it now")}</div>
    {_meta_line(p)}
    <div class="footer-slug">Morning Edition &middot; Alert Desk</div>
  </div>
</section>
"""


def render_terminal(p: dict, issue: dict) -> str:
    ascii_n = _ascii_numeral(p["rank"])
    host = _domain_only(p["url"]) or "news.ycombinator.com"
    return f"""
<section class="spread s-terminal">
  <div class="window">
    <div class="chrome"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>
    <div class="ascii-num" aria-hidden="true">{esc(ascii_n)}</div>
    <div class="kicker">{esc(p.get("kicker","") or "Systems")}</div>
    <div class="prompt"><span class="dollar">$</span> <span class="cmd">curl</span> <span class="arg">{esc(host)}</span></div>
    <h2>{esc(p["title"])}</h2>
    <p class="body-lead">&gt; {esc(p.get("blurb",""))}</p>
    <div style="margin-top:28px;display:flex;gap:24px;align-items:center;flex-wrap:wrap">
      {_read_more(p, "$ open")}
      {_applies_badge(p)}
    </div>
    {_apply_note(p)}
    {_meta_line(p)}
  </div>
</section>
"""


def render_academic(p: dict, issue: dict) -> str:
    roman = _to_roman(p["rank"])
    return f"""
<section class="spread s-academic">
  <div class="masthead-line">
    <span>Morning Edition &mdash; Review</span>
    <span class="roman">{esc(roman)}</span>
  </div>
  <div>
    <div class="kicker">{esc(p.get("kicker","") or "Research")}</div>
    <h2>{esc(p["title"])}</h2>
    <div class="body-lead">{esc(p.get("blurb",""))}</div>
    <div style="margin-top:40px;display:flex;gap:24px;align-items:center;flex-wrap:wrap">
      {_read_more(p, "Continue reading")}
      {_applies_badge(p)}
    </div>
    {_apply_note(p)}
  </div>
  <div>
    <div class="footnote">&sect; filed under {esc((p.get('kicker','') or 'review').lower())}</div>
  </div>
</section>
"""


def render_stat(p: dict, issue: dict) -> str:
    value = (p.get("stat_value") or "").strip() or str(p.get("score", "")) or "—"
    label = (p.get("stat_label") or "").strip() or "POINTS ON HN"
    return f"""
<section class="spread s-stat">
  <div class="top">
    <div class="chip">No. {numeral(p["rank"])} &middot; {esc(p.get("kicker","") or "By the numbers")}</div>
    {_applies_badge(p)}
  </div>
  <div class="stat-wrap">
    <div class="stat-value" aria-hidden="true">{esc(value)}</div>
    <div class="stat-label">{esc(label)}</div>
  </div>
  <div>
    <h2>{esc(p["title"])}</h2>
    <p class="body-lead">{esc(p.get("blurb",""))}</p>
    <div style="margin-top:24px">{_read_more(p)}</div>
    {_apply_note(p)}
    {_meta_line(p)}
  </div>
</section>
"""


def render_newsprint(p: dict, issue: dict) -> str:
    blurb = p.get("blurb", "")
    # Break blurb into two paragraphs for column flow
    halves = _split_half(blurb)
    return f"""
<section class="spread s-newsprint">
  <div class="masthead-bar">The Daily Ledger</div>
  <div class="title-row">
    <div class="badge">{numeral(p["rank"])}</div>
    <div>
      <div class="kicker">{esc(p.get("kicker","") or "Dispatch")}</div>
      <h2>{esc(p["title"])}</h2>
    </div>
  </div>
  <div class="cols">
    <p>{esc(halves[0])}</p>
    <p>{esc(halves[1])}</p>
  </div>
  <div style="margin-top:36px;display:flex;gap:24px;align-items:center;flex-wrap:wrap">
    {_read_more(p, "Full dispatch")}
    {_applies_badge(p)}
  </div>
  {_apply_note(p)}
  {_meta_line(p)}
</section>
"""


def render_neon(p: dict, issue: dict) -> str:
    return f"""
<section class="spread s-neon">
  <div>
    <div class="kicker">{esc(p.get("kicker","") or "Signal")}</div>
  </div>
  <div>
    <div class="numeral-slash" aria-hidden="true">{numeral(p["rank"])}</div>
    <h2>{esc(p["title"])}</h2>
    <p class="body-lead">{esc(p.get("blurb",""))}</p>
    <div style="margin-top:32px;display:flex;gap:24px;align-items:center;flex-wrap:wrap">
      {_read_more(p, "Go loud")}
      {_applies_badge(p)}
    </div>
    {_apply_note(p)}
    {_meta_line(p)}
  </div>
</section>
"""


def render_zine(p: dict, issue: dict) -> str:
    return f"""
<section class="spread s-zine">
  <div>
    <div class="sticker">Cut &amp; keep</div>
  </div>
  <div>
    <div class="marker-num" aria-hidden="true">{numeral(p["rank"])}</div>
    <div class="scribble" aria-hidden="true"></div>
    <div class="kicker">{esc(p.get("kicker","") or "Dispatch")}</div>
    <h2>{esc(p["title"])}</h2>
    <p class="body-lead">{esc(p.get("blurb",""))}</p>
    <div style="margin-top:28px;display:flex;gap:24px;align-items:center;flex-wrap:wrap">
      {_read_more(p, "Read it")}
      {_applies_badge(p)}
    </div>
    {_apply_note(p)}
    {_meta_line(p)}
  </div>
</section>
"""


def render_pullquote(p: dict, issue: dict) -> str:
    pq = (p.get("pullquote") or "").strip() or p["title"]
    return f"""
<section class="spread s-pullquote">
  <div class="top">
    <div class="kicker" style="color:#d9b26a">{esc(p.get("kicker","") or "In their words")}</div>
    <div class="tiny-num" aria-hidden="true">{numeral(p["rank"])}</div>
  </div>
  <div>
    <span class="quote-open" aria-hidden="true">&ldquo;</span>
    <p class="pq">{esc(pq)}</p>
    <div class="attrib">&mdash; {esc(_domain_only(p["url"]) or "source")}</div>
  </div>
  <div>
    <p class="body-lead" style="color:#c9c2ae;max-width:56ch">{esc(p.get("blurb",""))}</p>
    <div style="margin-top:28px;display:flex;gap:24px;align-items:center;flex-wrap:wrap">
      {_read_more(p)}
      {_applies_badge(p)}
    </div>
    {_apply_note(p)}
    {_meta_line(p)}
  </div>
</section>
"""


def render_grid(p: dict, issue: dict) -> str:
    return f"""
<section class="spread s-grid">
  <div class="grid-top">
    <div class="tag">{esc(p.get("kicker","") or "Index")}</div>
    <div class="num-corner">No. {numeral(p["rank"])}</div>
  </div>
  <div class="grid-body">
    <h2>{esc(p["title"])}</h2>
    <div class="side">
      <p class="body-lead">{esc(p.get("blurb",""))}</p>
      <div style="margin-top:28px;display:flex;gap:24px;align-items:center;flex-wrap:wrap">
        {_read_more(p)}
        {_applies_badge(p)}
      </div>
      {_apply_note(p)}
      {_meta_line(p)}
    </div>
  </div>
</section>
"""


def render_manifesto(p: dict, issue: dict) -> str:
    pq = (p.get("pullquote") or "").strip() or p["title"]
    return f"""
<section class="spread s-manifesto">
  <div class="top">
    <div class="kicker">{esc(p.get("kicker","") or "Position")}</div>
    <div class="tiny-num" aria-hidden="true">{numeral(p["rank"])}</div>
  </div>
  <h2>{esc(pq)}<span class="mark">.</span></h2>
  <div>
    <p class="body-lead" style="color:#d8cfb8;max-width:56ch">{esc(p.get("blurb",""))}</p>
    <div class="attrib" style="margin-top:24px">&mdash; {esc(_domain_only(p["url"]) or "source")}</div>
    <div style="margin-top:28px;display:flex;gap:24px;align-items:center;flex-wrap:wrap">
      {_read_more(p)}
      {_applies_badge(p)}
    </div>
    {_apply_note(p)}
    {_meta_line(p)}
  </div>
</section>
"""


def render_polaroid(p: dict, issue: dict) -> str:
    caption_source = _domain_only(p["url"]) or "dispatch"
    return f"""
<section class="spread s-polaroid">
  <div class="kicker">{esc(p.get("kicker","") or "Field notes")}</div>
  <div class="layout">
    <div class="photo">
      <div class="tape" aria-hidden="true"></div>
      <div class="photo-body">{esc(p["title"])}</div>
      <div class="photo-caption">No. {numeral(p["rank"])} &middot; {esc(caption_source)}</div>
    </div>
    <div>
      <p class="body-lead">{esc(p.get("blurb",""))}</p>
      <div style="margin-top:28px;display:flex;gap:24px;align-items:center;flex-wrap:wrap">
        {_read_more(p)}
        {_applies_badge(p)}
      </div>
      {_apply_note(p)}
      {_meta_line(p)}
    </div>
  </div>
</section>
"""


def render_ticker(p: dict, issue: dict) -> str:
    return f"""
<section class="spread s-ticker">
  <div class="bar"><span class="bar-inner">Breaking &middot; {esc(p.get("kicker","") or "Signal")} &middot; Morning Edition</span></div>
  <div class="core">
    <div class="big-num" aria-hidden="true">No. {numeral(p["rank"])}</div>
    <div class="kicker">{esc(p.get("kicker","") or "Wire")}</div>
    <h2>{esc(p["title"])}</h2>
    <p class="body-lead">{esc(p.get("blurb",""))}</p>
    <div style="margin-top:16px;display:flex;gap:24px;align-items:center;flex-wrap:wrap">
      {_read_more(p, "Over the wire")}
      {_applies_badge(p)}
    </div>
    {_apply_note(p)}
    {_meta_line(p)}
  </div>
  <div class="bar"><span class="bar-inner">Filed {esc(issue["date_display"])}</span></div>
</section>
"""


def render_blueprint(p: dict, issue: dict) -> str:
    host = _domain_only(p["url"]) or "source"
    return f"""
<section class="spread s-blueprint">
  <div class="frame">
    <div class="spec">
      <span>REV.{numeral(p["rank"])}</span>
      <span>{esc(host.upper())}</span>
      <span>SHEET {esc(p["rank"])}/10</span>
    </div>
    <div class="kicker">{esc((p.get("kicker","") or "Systems").upper())}</div>
    <h2>{esc(p["title"])}</h2>
    <div style="display:grid;grid-template-columns:auto 1fr;gap:48px;align-items:center">
      <div class="big-n" aria-hidden="true">{numeral(p["rank"])}</div>
      <p class="body-lead">{esc(p.get("blurb",""))}</p>
    </div>
    <div style="margin-top:32px;display:flex;gap:24px;align-items:center;flex-wrap:wrap">
      {_read_more(p, "View schematic")}
      {_applies_badge(p)}
    </div>
    {_apply_note(p)}
    {_meta_line(p)}
  </div>
</section>
"""


def render_riso(p: dict, issue: dict) -> str:
    return f"""
<section class="spread s-riso">
  <div class="layout">
    <div class="kicker">{esc(p.get("kicker","") or "Press")}</div>
    <div class="riso-num" data-n="{numeral(p["rank"])}" aria-hidden="true">{numeral(p["rank"])}</div>
    <h2>{esc(p["title"])}</h2>
    <p class="body-lead">{esc(p.get("blurb",""))}</p>
    <div style="margin-top:28px;display:flex;gap:24px;align-items:center;flex-wrap:wrap">
      {_read_more(p, "Pull a proof")}
      {_applies_badge(p)}
    </div>
    {_apply_note(p)}
    {_meta_line(p)}
  </div>
</section>
"""


def render_index_card(p: dict, issue: dict) -> str:
    return f"""
<section class="spread s-index">
  <div class="ix-top">
    <span>Card No. {numeral(p["rank"])}</span>
    <span>{esc((p.get("kicker","") or "Note").upper())}</span>
  </div>
  <div class="ix-body">
    <h2>{esc(p["title"])}</h2>
    <p class="body-lead">{esc(p.get("blurb",""))}</p>
    <div style="margin-top:28px;display:flex;gap:24px;align-items:center;flex-wrap:wrap">
      {_read_more(p, "Follow the thread")}
      {_applies_badge(p)}
    </div>
    {_apply_note(p)}
    {_meta_line(p)}
  </div>
</section>
"""


def render_postcard(p: dict, issue: dict) -> str:
    host = _domain_only(p["url"]) or "field"
    return f"""
<section class="spread s-postcard">
  <div class="pc-inner">
    <div class="stamp" aria-hidden="true">{numeral(p["rank"])}<small>Morning<br>Edition</small></div>
    <div class="postmark" aria-hidden="true">{esc(issue["date_display"].split(",")[0])}<br>&middot;&middot;&middot;</div>
    <div class="kicker">{esc(p.get("kicker","") or "Dispatch")}</div>
    <h2>{esc(p["title"])}</h2>
    <p class="body-lead">{esc(p.get("blurb",""))}</p>
    <div style="margin-top:32px;display:flex;gap:24px;align-items:center;flex-wrap:wrap">
      {_read_more(p, "Wish you were here")}
      {_applies_badge(p)}
    </div>
    {_apply_note(p)}
    {_meta_line(p)}
    <div class="footer-slug">Morning Edition &middot; Airmail from {esc(host)}</div>
  </div>
</section>
"""


# --------------------------------------------------------------------------
# Spread style -> renderer dispatch
# --------------------------------------------------------------------------
RENDERERS = {
    "hero": render_hero,
    "midnight": render_midnight,
    "rose-alert": render_rose,
    "terminal": render_terminal,
    "academic": render_academic,
    "big-stat": render_stat,
    "newsprint": render_newsprint,
    "neon": render_neon,
    "zine": render_zine,
    "pullquote": render_pullquote,
    "grid": render_grid,
    "manifesto": render_manifesto,
    "polaroid": render_polaroid,
    "ticker": render_ticker,
    "blueprint": render_blueprint,
    "risograph": render_riso,
    "index-card": render_index_card,
    "postcard": render_postcard,
}

# Fallback order when _repair_picks needs to assign a style. Hero stays first
# (it's forced onto rank 1). The rest is shuffled weekly-ish to avoid the same
# "default 10" showing up every build when Claude returns junk styles.
STYLE_ORDER = [
    "hero", "midnight", "rose-alert", "terminal", "academic",
    "big-stat", "newsprint", "neon", "zine", "pullquote",
    "grid", "manifesto", "polaroid", "ticker", "blueprint",
    "risograph", "index-card", "postcard",
]


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def _domain_only(url: str) -> str:
    import re
    m = re.match(r"https?://([^/]+)", url or "")
    if not m:
        return ""
    d = m.group(1)
    return d[4:] if d.startswith("www.") else d


def _split_half(s: str) -> tuple[str, str]:
    s = (s or "").strip()
    if not s:
        return ("", "")
    mid = len(s) // 2
    left = s.rfind(". ", 0, mid + 30)
    if left != -1 and left > len(s) * 0.3:
        return (s[: left + 1].strip(), s[left + 1 :].strip())
    return (s[:mid].strip(), s[mid:].strip())


def _to_roman(n: int) -> str:
    vals = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    out = ""
    for v, sym in vals:
        while n >= v:
            out += sym
            n -= v
    return out


def _ascii_numeral(n: int) -> str:
    digits = {
        "0": ["#####", "#   #", "#   #", "#   #", "#####"],
        "1": ["  #  ", " ##  ", "  #  ", "  #  ", "#####"],
        "2": ["#####", "    #", "#####", "#    ", "#####"],
        "3": ["#####", "    #", " ####", "    #", "#####"],
        "4": ["#   #", "#   #", "#####", "    #", "    #"],
        "5": ["#####", "#    ", "#####", "    #", "#####"],
        "6": ["#####", "#    ", "#####", "#   #", "#####"],
        "7": ["#####", "    #", "   # ", "  #  ", " #   "],
        "8": ["#####", "#   #", "#####", "#   #", "#####"],
        "9": ["#####", "#   #", "#####", "    #", "#####"],
    }
    s = numeral(n)
    rows = ["", "", "", "", ""]
    for ch in s:
        for i in range(5):
            rows[i] += digits[ch][i] + "  "
    return "\n".join(rows)


# --------------------------------------------------------------------------
# Repair picks so every required field has something sensible
# --------------------------------------------------------------------------
def _repair_picks(picks: list[dict]) -> list[dict]:
    picks = sorted(picks, key=lambda p: p.get("rank", 99))
    picks = picks[:10]
    used = []
    for i, p in enumerate(picks):
        p["rank"] = i + 1
        style = p.get("spread_style") or ""
        if style not in RENDERERS or style in used:
            for s in STYLE_ORDER:
                if s not in used:
                    style = s
                    break
            p["spread_style"] = style
        used.append(style)
    if picks and picks[0].get("spread_style") != "hero":
        for q in picks:
            if q.get("spread_style") == "hero":
                q["spread_style"] = picks[0]["spread_style"]
                picks[0]["spread_style"] = "hero"
                break
        else:
            picks[0]["spread_style"] = "hero"
    for p in picks:
        title = p.get("title", "")
        if len(title) > 120:
            p["title"] = title[:117].rsplit(" ", 1)[0] + " …"
    return picks


# --------------------------------------------------------------------------
# Colophon + page chrome
# --------------------------------------------------------------------------
def render_colophon(issue: dict, applies_count: int) -> str:
    return f"""
<section class="colophon">
  <div class="smallprint">Colophon</div>
  <h3>That was today.</h3>
  <p>Ten stories, hand-curated across twenty sources before you were awake.
  {applies_count} of them are flagged as directly applicable &mdash; open those first.</p>
  <p>Set in Fraunces and Inter. Rendered by a small Python pipeline and an Anthropic model
  at {esc(issue["built_at"])}.</p>
  <p><a href="../index.html" style="color:#d9b26a;text-decoration:underline;
    text-underline-offset:4px;font-size:22px">Browse all issues &rarr;</a></p>
  <p class="smallprint">Morning Edition &middot; Issue No. {esc(issue["issue_no"])} &middot; {esc(issue["date_display"])}</p>
</section>
"""


def render_magazine(curation: dict, today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    picks = _repair_picks(curation.get("picks", []))
    issue = {
        "date_iso": today.isoformat(),
        "date_display": fmt_date(today),
        "issue_no": f"{(today - dt.date(2025, 1, 1)).days + 1:04d}",
        "tagline": curation.get("issue_tagline", ""),
        "built_at": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    }
    spreads = []
    for p in picks:
        fn = RENDERERS[p["spread_style"]]
        spread_html = fn(p, issue)
        # Tag each spread for the mobile progress tracker
        spread_html = spread_html.replace(
            '<section class="spread',
            f'<section data-story="{p["rank"]}" class="spread',
            1,
        )
        spreads.append(spread_html)
    applies_count = sum(1 for p in picks if p.get("applies_to_me"))
    colophon = render_colophon(issue, applies_count)

    fonts = _pick_fonts(today)
    total = len(picks)

    title = f"Morning Edition &middot; {issue['date_display']}"
    desc = esc(issue.get("tagline") or "Hand-picked across twenty sources while you slept.")

    mobile_nav = (
        '<div id="m-nav" role="banner">'
        '<div id="m-nav-inner">'
        '<span id="m-nav-title">Morning Edition</span>'
        f'<button id="m-toc-btn" aria-label="Open story list" aria-expanded="false">'
        f'<span id="m-progress">1 / {total}</span>'
        '<svg width="18" height="13" viewBox="0 0 18 13" fill="currentColor" aria-hidden="true">'
        '<rect width="18" height="2" rx="1"/>'
        '<rect y="5.5" width="18" height="2" rx="1"/>'
        '<rect y="11" width="18" height="2" rx="1"/>'
        '</svg>'
        '</button>'
        '<div id="m-bar" style="width:10%"></div>'
        '</div>'
        '</div>'
        '<div id="m-drawer" role="dialog" aria-modal="true" aria-label="All stories"></div>'
    )

    mobile_js = f"""<script>
(function(){{
if(typeof window==='undefined'||window.innerWidth>720)return;
var sp=document.querySelectorAll('[data-story]');
var total={total};
if(!sp.length)return;
var drawer=document.getElementById('m-drawer');
var prog=document.getElementById('m-progress');
var bar=document.getElementById('m-bar');
var ntitle=document.getElementById('m-nav-title');
var tbtn=document.getElementById('m-toc-btn');
function closeDrawer(){{drawer.classList.remove('open');tbtn.setAttribute('aria-expanded','false');}}
var cl=document.createElement('div');
cl.className='m-drawer-close';
cl.innerHTML='All stories · tap to jump <span aria-hidden="true">×</span>';
cl.addEventListener('click',closeDrawer);
drawer.appendChild(cl);
sp.forEach(function(s,i){{
var h=s.querySelector('h2')||s.querySelector('h1');
var k=s.querySelector('.kicker');
var txt=(h?h.textContent.trim():'');
if(txt.length>55)txt=txt.slice(0,52)+'…';
var it=document.createElement('div');
it.className='m-drawer-item';
it.innerHTML=(k?'<span class="m-drawer-kicker">'+k.textContent.trim().slice(0,22)+'</span>':'')
+'<span class="m-drawer-num">'+(i+1)+'</span>'
+'<span class="m-drawer-title">'+txt+'</span>';
it.addEventListener('click',function(){{closeDrawer();s.scrollIntoView({{behavior:'smooth'}});}});
drawer.appendChild(it);
}});
tbtn.addEventListener('click',function(){{
var open=drawer.classList.toggle('open');
tbtn.setAttribute('aria-expanded',String(open));
}});
document.addEventListener('keydown',function(e){{if(e.key==='Escape')closeDrawer();}});
if('IntersectionObserver' in window){{
var io=new IntersectionObserver(function(entries){{
entries.forEach(function(e){{
if(!e.isIntersecting)return;
var idx=parseInt(e.target.getAttribute('data-story'))||1;
if(prog)prog.textContent=idx+' / '+total;
if(bar)bar.style.width=Math.round(idx/total*100)+'%';
var k=e.target.querySelector('.kicker');
if(ntitle)ntitle.textContent=(idx===1)?'Morning Edition':(k?k.textContent.trim().slice(0,26):'Morning Edition');
}});
}},{{threshold:0.5}});
sp.forEach(function(s){{io.observe(s);}});
}}
}})();
</script>"""

    raw = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta property="og:title" content="Morning Edition · {esc(issue['date_display'])}">
<meta property="og:description" content="{desc}">
<meta property="og:type" content="article">
{GOOGLE_FONTS}
<style>{BASE_CSS}</style>
</head>
<body>
{mobile_nav}
{''.join(spreads)}
{colophon}
{mobile_js}
</body>
</html>
"""
    return _swap_fonts(raw, fonts)


if __name__ == "__main__":
    import json
    import sys
    data = json.load(sys.stdin)
    sys.stdout.write(render_magazine(data))






