"""Sports Editorial presentation layer; no model, quote or account decisions."""
from base64 import b64encode
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def editorial_css():
    font = b64encode((Path(__file__).parent / 'assets/fonts/BarlowCondensed-ExtraBold.ttf').read_bytes()).decode('ascii')
    return '<style>@font-face{font-family:BB Sport;src:url(data:font/ttf;base64,' + font + ') format("truetype");font-weight:800;font-display:swap;}' + _CSS + '</style>'


_CSS = r'''
:root { --bb-ink:#18201b; --bb-muted:#687269; --bb-line:#d9ddd3;
  --bb-surface:#fffefb; --bb-canvas:#f7f6f0; --bb-green:#154d39; --bb-green-soft:#e8eee5;
  --bb-editorial-yellow:#f4d86b; --bb-editorial-red:#ab4842; }
html, body, [data-testid="stAppViewContainer"], .stApp, [data-testid="stMain"] {
  background:var(--bb-canvas) !important; color:var(--bb-ink); }
[data-testid="stMain"] .block-container {max-width:1380px !important; padding:1.1rem 2.5rem 3rem !important;}
[data-testid="stHeader"] {height:.45rem !important; min-height:0 !important; max-height:.45rem !important; background:var(--bb-green) !important;}
[data-testid="stToolbar"], [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
  [data-testid="collapsedControl"], .bb-context {display:none !important;}
[data-testid="stMain"] h1 {font-family:'BB Sport',Impact,sans-serif !important; font-size:clamp(2.9rem,5vw,4.5rem) !important;
  font-weight:800 !important; line-height:1.03 !important; letter-spacing:-.015em !important; margin:1.2rem 0 .15rem !important;}
[data-testid="stMain"] h2 {font-family:'BB Sport',Impact,sans-serif !important; font-size:2rem !important; letter-spacing:0 !important;}
[data-testid="stMain"] h3 {font-family:'BB Sport',Impact,sans-serif !important; font-size:1.5rem !important;}
.st-key-bb_editorial_header p.bb-brand {font-family:Georgia,'Times New Roman',serif; font-weight:900; font-size:2.5rem !important; letter-spacing:-.07em; margin:0 !important;line-height:1.1;}
.bb-brand span {color:var(--bb-green);}
.st-key-bb_editorial_header p.bb-brand-note {font-size:.63rem !important;letter-spacing:.18em;font-weight:700;color:var(--bb-muted);margin:.45rem 0 0 !important;}
.st-key-bb_editorial_header {border-bottom:1px solid var(--bb-line);padding:.9rem 0 1.15rem;}
.st-key-bb_editorial_header [data-testid="stHorizontalBlock"] {align-items:center;}
.st-key-bb_desktop_nav [data-testid="stButtonGroup"] button {border:0 !important;border-radius:0 !important;
  background:transparent !important;color:var(--bb-muted) !important;padding:.8rem .65rem !important;min-height:44px;}
.st-key-bb_desktop_nav [data-testid="stButtonGroup"] button[aria-checked="true"] {
  background:transparent !important;color:var(--bb-green) !important;border-bottom:3px solid var(--bb-green) !important;}
.st-key-bb_desktop_nav [data-testid="stButtonGroup"] button p {font-weight:700 !important;font-size:.95rem !important;}
[data-testid="stButtonGroup"] button {min-height:44px !important;border-radius:7px !important; border-color:var(--bb-line) !important;}
[data-testid="stButtonGroup"] button[aria-checked="true"] {background:var(--bb-green) !important;color:white !important;}
[data-testid="stButtonGroup"] button[aria-checked="true"] p {color:inherit !important;}
button:focus-visible, summary:focus-visible {outline:3px solid #b6900e !important;outline-offset:3px !important;}
[data-testid="stButton"] button, [data-testid="stFormSubmitButton"] button {min-height:44px;border-radius:7px !important;}
[data-testid="stTextInput"] input, [data-baseweb="select"]>div {background:var(--bb-surface) !important;}
.st-key-wettfinder_v2_mode {border-bottom:0 !important;padding:.8rem 0 !important;}
.st-key-wettfinder_v2_mode [data-testid="stButtonGroup"] button {padding:.65rem 1.1rem !important;}
.st-key-wettfinder_v2_sports {padding:0 0 1.15rem;}
.st-key-wettfinder_v2_sports [data-testid="stButtonGroup"] button {background:#fffefb !important;padding:.5rem .85rem !important;}
.st-key-wettfinder_v2_sports [data-testid="stButtonGroup"] button[aria-checked="true"] {background:var(--bb-green) !important;}
.wf-section-heading, .wf-additional-heading {border:0 !important;margin:.5rem 0 .6rem !important;}
.st-key-wettfinder_v2_page .wf-section-heading h2, .st-key-wettfinder_v2_page .wf-additional-heading h2 {font-size:2rem !important;margin:0 !important;}
[class*="st-key-wettfinder_v2_game_"] > [data-testid="stExpander"] {border:1px solid var(--bb-line) !important;
  border-radius:12px !important;background:var(--bb-surface) !important;overflow:visible;}
[class*="st-key-wettfinder_v2_game_"] [data-testid="stExpander"] > details > summary {min-height:56px;
  padding:.9rem 1.2rem !important;background:transparent !important;color:var(--bb-ink) !important;}
[class*="st-key-wettfinder_v2_game_"] [data-testid="stExpander"] > details > summary p {font-weight:750;font-size:1rem !important;line-height:1.5;}
.se-match {display:grid;grid-template-columns:1fr auto 1fr;gap:1.2rem;align-items:center;padding:1.3rem .6rem 1.5rem;border-bottom:1px solid var(--bb-line);}
.se-team {display:flex;align-items:center;gap:.8rem;min-width:0;}
.se-team:last-child {flex-direction:row-reverse;text-align:right;}
.se-team strong {font-family:'BB Sport',Impact,sans-serif;font-size:1.85rem;line-height:1.07;overflow-wrap:anywhere;}
.se-shield {display:grid;place-items:center;flex:0 0 48px;width:48px;height:56px;background:var(--bb-green-soft);
  color:var(--bb-green);font-size:1rem;font-weight:800;clip-path:polygon(0 0,100% 0,100% 78%,50% 100%,0 78%);}
.se-match-time {display:flex;flex-direction:column;text-align:center;color:var(--bb-muted);font-size:.76rem;gap:.25rem;}
.se-match-time b {font-family:'BB Sport',sans-serif;font-size:1.35rem;color:var(--bb-ink);}
.st-key-wettfinder_v2_page article.se-card, article.se-card {display:block !important;background:transparent !important;
  border:0 !important;border-radius:0 !important;padding:1.1rem .4rem !important;box-shadow:none !important;min-width:0;}
[class*="st-key-wettfinder_v2_game_market_"] + [class*="st-key-wettfinder_v2_game_market_"] {border-top:1px solid var(--bb-line);}
.se-pick {display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:1rem;align-items:center;margin-bottom:1rem;}
.se-pick-label {display:flex;flex-direction:column;gap:.25rem;min-width:0;}
.se-pick-label span {font-size:.75rem;color:var(--bb-muted);}
.se-pick-label strong {font-family:'BB Sport',sans-serif;font-size:1.85rem;line-height:1.15;color:var(--bb-green);}
.se-number {display:flex;flex-direction:column;min-width:94px;gap:.2rem;padding:.7rem .9rem;background:var(--bb-green-soft);border-radius:7px;text-align:center;}
.se-number span {font-size:.65rem;color:var(--bb-muted);letter-spacing:.07em;text-transform:uppercase;}
.se-number strong {font-family:'BB Sport',sans-serif;font-size:1.8rem;line-height:1.1;font-variant-numeric:tabular-nums;}
.se-number-quote {background:#f4f0de;}
.se-card .se-event {font-family:'BB Sport',sans-serif;font-size:1.6rem;line-height:1.12;margin:0 0 .8rem;font-weight:800;}
.se-card .se-meta {font-size:.7rem;color:var(--bb-muted);margin:0 0 .4rem;}
.st-key-wettfinder_v2_page .se-card .wf-analysis, .se-card .wf-analysis {display:block !important;grid-column:auto !important;
  border:0 !important;background:transparent !important;padding:0 !important;margin:0 !important;}
.wf-analysis-short {font-size:.91rem !important;font-weight:600 !important;line-height:1.55 !important;margin:0 0 .9rem !important;color:var(--bb-ink) !important;}
.wf-analysis-support {font-size:.8rem !important;color:var(--bb-green) !important;}
.wf-facts {display:flex !important;flex-wrap:wrap !important;gap:.45rem !important;margin:1rem 0 .65rem !important;}
.wf-fact {background:#f1f2ea !important;border:1px solid #e2e5da !important;border-radius:6px !important;
  font-size:.8rem !important;padding:.4rem .55rem !important;position:relative;max-width:100%;overflow-wrap:anywhere;}
details.wf-fact {padding:0 !important;}
.wf-fact > summary {min-height:44px;padding:.5rem .65rem;cursor:pointer;}
.wf-fact > summary span {color:var(--bb-muted);}
.wf-fact strong {font-weight:700 !important;}
.wf-fact-detail {max-width:100% !important;overflow-wrap:anywhere;line-height:1.5;}
.wf-fact-detail p {font-size:.8rem !important;}
.wf-analysis-alert {font-size:.75rem !important;line-height:1.45;color:#805b20 !important;}
.wf-analysis-footer {display:flex !important;flex-wrap:wrap !important;align-items:center;gap:.7rem;margin-top:.9rem;font-size:.68rem;color:var(--bb-muted);}
.wf-analysis-footer .wf-fact {border:0 !important;background:transparent !important;}
.wf-analysis-footer .wf-fact summary {padding:.2rem 0;}
.sports-form {background:#f5f5ee;padding:1rem;border:1px solid #e7e9de;border-radius:8px;margin:1rem 0;color:var(--bb-ink);min-width:0;}
.form-heading {display:flex;align-items:center;gap:.8rem;margin-bottom:.9rem;}
.form-heading h4 {font-family:'BB Sport',sans-serif !important;font-size:1.5rem !important;margin:0 !important;line-height:1.1;}
.form-heading>span {font-size:.65rem;color:var(--bb-muted);margin-left:auto;}
.form-toggle {display:flex;align-items:center;background:#e8ebdf;border-radius:6px;position:relative;}
.form-toggle input {position:absolute;width:1px;height:1px;opacity:0;}
.form-toggle label, .form-ten-unavailable {display:grid;place-items:center;width:44px;height:44px;cursor:pointer;font-size:.8rem;font-weight:700;border-radius:5px;}
.form-ten-unavailable {opacity:.35;cursor:not-allowed;}
.form-toggle label:first-of-type {background:var(--bb-green);color:white;}
.form-toggle:has(input[value="10"]:checked) label:first-of-type {background:transparent;color:var(--bb-ink);}
.form-toggle input:checked+label {background:var(--bb-green);color:white;}
.form-toggle input:focus-visible+label {outline:3px solid #b6900e;outline-offset:2px;}
.form-window {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1.1rem;}
.form-window-10 {display:none;}
.sports-form:has(input[value="10"]:checked) .form-window-5 {display:none;}
.sports-form:has(input[value="10"]:checked) .form-window-10 {display:grid;}
.form-team {position:relative;min-width:0;padding-bottom:.2rem;}
.form-team-heading {display:flex;flex-direction:column;gap:.2rem;margin-bottom:.2rem;}
.form-team-heading strong {font-size:.9rem;overflow-wrap:anywhere;}
.form-team-heading>span, .form-team>small {font-size:.75rem;color:var(--bb-muted);}
.form-results {display:flex;gap:5px;flex-wrap:wrap;margin:.7rem 0 .2rem;}
.form-result {position:static !important;flex:0 0 44px;border:0 !important;}
.form-result > summary {display:flex;flex-direction:column;justify-content:center;align-items:center;gap:2px;
  list-style:none;width:44px;min-height:48px;border-radius:5px;cursor:pointer;color:white;line-height:1.1;}
.form-result > summary::-webkit-details-marker {display:none;}
.form-result summary b {font-size:.8rem;}
.form-result summary>span {font-size:.8rem;font-weight:600;font-variant-numeric:tabular-nums;}
.form-s > summary {background:var(--bb-green);}
.form-u > summary {background:var(--bb-editorial-yellow);color:#433700;}
.form-n > summary {background:var(--bb-editorial-red);}
.form-result-detail {position:absolute;left:0;right:0;z-index:10;background:var(--bb-surface);border:1px solid var(--bb-line);
  box-shadow:0 8px 24px #18201b18;border-radius:6px;padding:.75rem;display:flex;flex-direction:column;gap:.3rem;margin-top:.35rem;font-size:.76rem;overflow-wrap:anywhere;}
.form-result[open] > summary {outline:2px solid var(--bb-ink);outline-offset:2px;}
.form-opponents > summary {font-size:.8rem;color:var(--bb-green);cursor:pointer;min-height:44px;display:flex;align-items:center;}
.form-opponents > summary:after {content:' +';margin-left:.3rem;}
.form-opponents[open] > summary:after {content:' −';}
.form-opponents ol {list-style:none;margin:0;padding:0;}
.form-opponents li {display:flex;flex-direction:column;gap:.15rem;font-size:.72rem;line-height:1.45;padding:.4rem 0;border-top:1px solid var(--bb-line);}
.form-opponents li>span {font-size:.65rem;color:var(--bb-muted);}
.st-key-editorial_daily3_rail {border-top:5px solid var(--bb-green);border-radius:8px;background:#efeedf;padding:1.1rem;}
.st-key-editorial_daily3_rail p.se-rail-title {font-family:'BB Sport',sans-serif;font-size:1.75rem !important;line-height:1.08;margin:0 0 .5rem !important;}
.st-key-editorial_daily3_rail p.se-rail-kicker {text-transform:uppercase;letter-spacing:.13em;font-size:.62rem !important;font-weight:700;color:var(--bb-green);margin:0 0 .6rem !important;}
.st-key-editorial_daily3_rail p.se-rail-sub {font-size:.75rem !important;color:var(--bb-muted);line-height:1.5;margin:0 0 1rem !important;}
.se-rail-choice {border-top:1px solid #d8dacb;padding:.8rem 0;display:flex;flex-direction:column;gap:.3rem;}
.se-rail-choice strong {font-size:.83rem;}
.se-rail-choice span {font-size:.7rem;color:var(--bb-muted);}
.se-rail-choice b {font-family:'BB Sport',sans-serif;color:var(--bb-green);font-size:1.25rem;}
.st-key-daily3_choices_layout .form-window {grid-template-columns:1fr;}
.st-key-riskobet_summary {background:var(--bb-green-soft) !important;border-color:var(--bb-line) !important;border-radius:8px !important;}
.st-key-riskobet_summary p {color:var(--bb-ink) !important;}
.st-key-riskobet_page .rb-card, .st-key-riskobet_page .rb-row {border-color:var(--bb-line) !important;background:var(--bb-surface) !important;border-radius:12px !important;box-shadow:none !important;}
.st-key-riskobet_page .rb-card .rb-event {font-family:'BB Sport',sans-serif !important;font-size:1.8rem !important;}
.st-key-riskobet_page .rb-pick {background:var(--bb-green-soft) !important;color:var(--bb-green) !important;border-radius:6px;}
.st-key-riskobet_page .rb-primary-probability {color:var(--bb-green) !important;}
.st-key-riskobet_page .rb-probabilities>div {background:var(--bb-green-soft);padding:.7rem;border-radius:7px;}
.st-key-riskobet_page .rb-probabilities strong {font-family:'BB Sport',sans-serif !important;font-size:2.2rem !important;line-height:1.1;}
.st-key-riskobet_page .rb-uncertainty-note {font-size:.68rem !important;}
.st-key-riskobet_page .rb-reasons {border-color:var(--bb-line) !important;background:#f5f5ee !important;}
.st-key-riskobet_page .rb-reasons h4 {font-family:'BB Sport',sans-serif !important;font-size:1.25rem !important;}
.st-key-bb_bottomnav {display:none;}
@media(min-width:761px) {
  .st-key-editorial_auto_layout>[data-testid="stHorizontalBlock"] {gap:2rem !important;align-items:flex-start;}
  .st-key-editorial_daily3_rail {position:sticky;top:1rem;}
}
@media(max-width:1023px) {
  .st-key-daily3_choices_layout>[data-testid="stHorizontalBlock"] {flex-direction:column !important;}
  .st-key-daily3_choices_layout>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"] {width:100% !important;flex:1 1 100% !important;min-width:0 !important;}
  [data-testid="stMain"] .block-container {padding-left:1.4rem !important;padding-right:1.4rem !important;}
  .se-team strong {font-size:1.5rem;}
  .se-match {gap:.6rem;}
  .se-shield {flex-basis:38px;width:38px;height:45px;font-size:.8rem;}
  .form-window {grid-template-columns:1fr;}
}
@media(max-width:760px) {
  [data-testid="stMain"] .block-container {padding: .6rem 1rem calc(7rem + env(safe-area-inset-bottom)) !important;}
  [data-testid="stMain"] h1 {font-size:3rem !important;margin:.9rem 0 .1rem !important;}
  [data-testid="stMain"] h2 {font-size:1.75rem !important;}
  .st-key-bb_editorial_header p.bb-brand {font-size:2.2rem !important;}
  .st-key-bb_editorial_header p.bb-brand-note {font-size:.52rem !important;}
  .st-key-bb_editorial_header {padding:.6rem 0 .75rem;}
  .st-key-bb_desktop_nav {display:none !important;}
  .st-key-bb_editorial_header [data-testid="stColumn"]:has(.st-key-bb_desktop_nav) {display:none !important;}
  .st-key-editorial_auto_layout>[data-testid="stHorizontalBlock"] {flex-direction:column !important;gap:1rem !important;}
  .st-key-editorial_auto_layout>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"] {width:100% !important;flex:1 1 100% !important;min-width:0 !important;}
  .st-key-editorial_auto_layout .st-key-editorial_daily3_rail {padding:.85rem;border-top-width:3px;}
  .st-key-editorial_daily3_rail p.se-rail-title {font-size:1.5rem !important;}
  .se-rail-choice {padding:.5rem 0;}
  .se-match {padding:.7rem 0 1rem;grid-template-columns:1fr auto 1fr;gap:.5rem;}
  .se-team {flex-direction:column !important;text-align:center !important;gap:.45rem;}
  .se-team strong {font-size:1.35rem;}
  .se-match-time {font-size:.75rem;}
  .se-match-time b {font-size:1.1rem;}
  .se-pick {grid-template-columns:1fr 1fr;gap:.6rem;}
  .se-pick-label {grid-column:1/-1;}
  .se-pick-label strong {font-size:1.65rem;}
  .se-number {min-width:0;padding:.6rem .5rem;}
  .se-number strong {font-size:1.8rem;}
  .sports-form {padding:.75rem;}
  .form-window {grid-template-columns:1fr;gap:1.25rem;}
  .form-heading {gap:.4rem;}
  .form-heading h4 {font-size:1.3rem !important;}
  .form-heading>span {font-size:.58rem;}
  .form-toggle label, .form-ten-unavailable {width:44px;}
  .form-results {gap:4px;}
  [class*="st-key-wettfinder_v2_game_"] [data-testid="stExpander"] > details > summary {padding:.75rem !important;}
  [class*="st-key-wettfinder_v2_game_"] [data-testid="stExpander"] > details > summary p {font-size:.85rem !important;}
  .st-key-bb_bottomnav {display:block !important;position:fixed;bottom:0;left:0;right:0;z-index:999;
    background:var(--bb-surface) !important;border-top:1px solid var(--bb-line);padding:.35rem .4rem calc(.35rem + env(safe-area-inset-bottom));}
  .st-key-bb_bottomnav [data-testid="stButtonGroup"]>[role="radiogroup"] {display:grid !important;grid-template-columns:repeat(5,minmax(0,1fr)) !important;gap:0 !important;}
  .st-key-bb_bottomnav [data-testid="stButtonGroup"] button {display:flex !important;flex-direction:column !important;gap:.2rem !important;
    border:0 !important;background:transparent !important;color:var(--bb-muted) !important;padding:.3rem 0 !important;min-height:58px !important;border-radius:6px !important;width:100% !important;font-size:.64rem !important;}
  .st-key-bb_bottomnav [data-testid="stButtonGroup"] button[aria-checked="true"] {background:var(--bb-green-soft) !important;color:var(--bb-green) !important;}
  .st-key-bb_bottomnav button:before {content:'';display:block;width:20px;height:20px;background:currentColor;mask-size:contain;mask-repeat:no-repeat;}
  .st-key-bb_bottomnav button:nth-child(1):before {mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2'%3E%3Ccircle cx='10' cy='10' r='6'/%3E%3Cpath d='m15 15 6 6'/%3E%3C/svg%3E");}
  .st-key-bb_bottomnav button:nth-child(2):before {mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2'%3E%3Cpath d='M12 2 21 6v6c0 5-9 10-9 10S3 17 3 12V6z'/%3E%3C/svg%3E");}
  .st-key-bb_bottomnav button:nth-child(3):before {mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2'%3E%3Ccircle cx='12' cy='12' r='2'/%3E%3Cpath d='M7 6a8 8 0 0 0 0 12M17 6a8 8 0 0 1 0 12M3 3a13 13 0 0 0 0 18M21 3a13 13 0 0 1 0 18'/%3E%3C/svg%3E");}
  .st-key-bb_bottomnav button:nth-child(4):before {mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2'%3E%3Cpath d='M3 20 10 13l4 3 7-12M13 4h8v8'/%3E%3C/svg%3E");}
  .st-key-bb_bottomnav button:nth-child(5):before {mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2'%3E%3Cpath d='m12 2 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1z'/%3E%3C/svg%3E");}
}
@media(max-width:360px) {
  [data-testid="stMain"] .block-container {padding-left:.65rem !important;padding-right:.65rem !important;}
  .se-match-time {max-width:58px;}
  .se-team strong {font-size:1.2rem;}
  .form-results {gap:3px;}
  .sports-form {padding:.5rem;}
  .form-result {flex-basis:44px;}
  .st-key-wettfinder_v2_sports [data-testid="stButtonGroup"] button {padding:.45rem .65rem !important;}
}
'''
