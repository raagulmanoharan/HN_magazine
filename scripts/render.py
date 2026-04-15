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

/* ---- Closing colophon ---- */
.colophon{background:#17140e;color:#f4ecd8;padding:clamp(48px,6vw,110px);
  display:flex;flex-direction:column;gap:32px}
.colophon h3{font-family:'Fraunces',serif;font-style:italic;font-weight:500;
  font-size:clamp(48px,5vw,84px);margin:0;line-height:1}
.colophon p{font-family:'Fraunces',serif;font-size:24px;line-height:1.5;max-width:56ch;margin:0}
.colophon .smallprint{font-family:'Inter',sans-serif;font-size:18px;letter-spacing:.18em;
  text-transform:uppercase;opacity:.55}

/* ---- Mobile (<= 720px) ---------------------------------------------------
   Desktop spreads use huge minimum font sizes that overflow narrow viewports.
   Below 720px we reduce padding, collapse multi-column grids, and shrink
   the decorative numerals so everything fits without horizontal scroll.
   Body copy stays >= 18px so the "no small fonts" rule still holds. */
@media (max-width:720px){
  body{font-size:20px}
  .spread{padding:36px 22px;min-height:auto}
  .kicker{font-size:16px;letter-spacing:.22em}
  .body-lead{font-size:19px;max-width:none}
  .apply-note{font-size:19px;max-width:none}
  .read-more{font-size:17px}
  .meta-row{font-size:15px;gap:14px}
  .tag-applies{padding:8px 14px;font-size:15px;border-width:2px}

  /* 01 hero */
  .s-hero .masthead{flex-direction:column;align-items:flex-start;gap:6px}
  .s-hero .masthead h1{font-size:38px}
  .s-hero .issue-meta{text-align:left;font-size:15px}
  .s-hero .cover-body{grid-template-columns:1fr;gap:14px;margin-top:32px}
  .s-hero .cover-numeral{font-size:38vw;order:-1;line-height:.85;align-self:flex-end;margin-bottom:-10px}
  .s-hero .cover-title{font-size:clamp(42px,11vw,72px);margin:0 0 18px}
  .s-hero .cover-tagline{font-size:22px;margin:0 0 22px}
  .s-hero .cover-kicker{font-size:16px;letter-spacing:.22em;margin-bottom:16px}

  /* 02 midnight */
  .s-midnight .bg-num{font-size:80vw;right:-14vw;top:2%}
  .s-midnight h2{font-size:clamp(38px,10vw,64px);margin:18px 0 22px}

  /* 03 rose */
  .s-rose .stamp{top:18px;right:18px;padding:9px 12px;font-size:13px;border-width:3px;letter-spacing:.22em}
  .s-rose .numeral-xl{font-size:42vw}
  .s-rose h2{font-size:clamp(32px,8.4vw,54px);margin:16px 0 20px}

  /* 04 terminal */
  .s-terminal .window{padding:20px}
  .s-terminal h2{font-size:clamp(28px,7vw,48px);margin:14px 0 18px}
  .s-terminal .body-lead{font-size:18px}
  .s-terminal .prompt{font-size:18px}
  .s-terminal .ascii-num{font-size:13px;line-height:1.1}

  /* 05 academic */
  .s-academic h2{font-size:clamp(32px,8.4vw,56px);margin:24px 0 18px}
  .s-academic .body-lead{column-count:1;font-size:20px}
  .s-academic .body-lead::first-letter{font-size:clamp(72px,22vw,120px);margin:6px 12px 0 -2px}
  .s-academic .footnote{font-size:17px}
  .s-academic .roman{font-size:20px}

  /* 06 big-stat */
  .s-stat .top{flex-direction:column;gap:12px;align-items:flex-start}
  .s-stat .chip{font-size:15px;padding:8px 12px;border-width:2px}
  .s-stat .stat-value{font-size:48vw;line-height:.8}
  .s-stat .stat-label{font-size:17px;letter-spacing:.22em}
  .s-stat h2{font-size:24px;margin:22px 0 12px}

  /* 07 newsprint */
  .s-newsprint .masthead-bar{font-size:38px;padding:10px 0}
  .s-newsprint .title-row{grid-template-columns:1fr;gap:14px;margin-top:24px}
  .s-newsprint .badge{width:68px;height:68px;font-size:34px;border-width:3px}
  .s-newsprint h2{font-size:clamp(30px,8vw,52px)}
  .s-newsprint .cols{column-count:1;font-size:19px;margin-top:22px}

  /* 08 neon */
  .s-neon .numeral-slash{font-size:58vw;-webkit-text-stroke-width:3px}
  .s-neon h2{font-size:clamp(34px,9vw,60px);margin:10px 0 18px}
  .s-neon .kicker{padding:8px 12px}
  .s-neon .apply-note{padding:14px 16px}

  /* 09 zine */
  .s-zine .marker-num{font-size:50vw}
  .s-zine h2{font-size:clamp(32px,8.4vw,56px);margin:18px 0 18px}
  .s-zine .sticker{font-size:16px;padding:10px 14px;box-shadow:4px 4px 0 #1a1a1a}
  .s-zine .scribble{width:60%}

  /* 10 pullquote */
  .s-pullquote .quote-open{font-size:55vw;line-height:.72;margin:0 0 -8px -6px}
  .s-pullquote .pq{font-size:clamp(30px,8.4vw,58px);line-height:1.05;margin:0 0 22px;max-width:none}
  .s-pullquote .tiny-num{font-size:32px}
  .s-pullquote .attrib{font-size:16px;letter-spacing:.16em}

  .colophon{padding:36px 22px}
  .colophon h3{font-size:40px}
  .colophon p{font-size:20px}
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
}

STYLE_ORDER = [
    "hero", "midnight", "rose-alert", "terminal", "academic",
    "big-stat", "newsprint", "neon", "zine", "pullquote",
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
    return picks


# --------------------------------------------------------------------------
# Colophon + page chrome
# --------------------------------------------------------------------------
def render_colophon(issue: dict, applies_count: int) -> str:
    return f"""
<section class="colophon">
  <div class="smallprint">Colophon</div>
  <h3>That was today.</h3>
  <p>Ten stories, hand-curated across eleven sources before you were awake.
  {applies_count} of them are flagged as directly applicable &mdash; open those first.</p>
  <p>Set in Fraunces and Inter. Rendered by a small Python pipeline and an Anthropic model
  at {esc(issue["built_at"])}.</p>
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
        spreads.append(fn(p, issue))
    applies_count = sum(1 for p in picks if p.get("applies_to_me"))
    colophon = render_colophon(issue, applies_count)

    title = f"Morning Edition &middot; {issue['date_display']}"
    desc = esc(issue.get("tagline") or "Hand-picked across eleven sources while you slept.")
    return f"""<!doctype html>
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
{''.join(spreads)}
{colophon}
</body>
</html>
"""


if __name__ == "__main__":
    import json
    import sys
    data = json.load(sys.stdin)
    sys.stdout.write(render_magazine(data))






