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
  --bb-surface:#fffefb; --bb-canvas:#faf9f5; --bb-green:#154d39; --bb-green-soft:#e8eee5;
  --bb-editorial-yellow:#ffcf42; --bb-editorial-red:#c64140; }
html, body, [data-testid="stAppViewContainer"], .stApp, [data-testid="stMain"] {background:var(--bb-canvas) !important;color:var(--bb-ink);}
.stApp [data-testid="stMainBlockContainer"], [data-testid="stMain"] .block-container {max-width:1560px !important;padding:2.4rem 2.25rem 2rem !important;}
[data-testid="stHeader"] {height:6px !important;min-height:0 !important;max-height:6px !important;background:var(--bb-green) !important;}
[data-testid="stToolbar"], [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"], .bb-context {display:none !important;}
/* Nonvisual styles/account bridges must not leave empty layout rows. */
[data-testid="stElementContainer"]:has([data-testid="stMarkdownContainer"] style) {display:none !important;}
[data-testid="stElementContainer"]:has(iframe[height="0"]) {position:absolute;height:0;width:0;overflow:hidden;}
[data-testid="stElementContainer"]:has(.se-edition) {position:fixed;top:0;left:0;right:0;z-index:990;}
.se-edition {display:flex;justify-content:space-between;gap:1rem;padding:5px 2.25rem;background:var(--bb-green);color:white;
  font-size:.66rem;line-height:1.2;letter-spacing:.15em;}
[data-testid="stMain"] h1, [data-testid="stMain"] h2, [data-testid="stMain"] h3 {font-family:'BB Sport',Impact,sans-serif !important;font-weight:800 !important;letter-spacing:-.015em !important;}
[data-testid="stMain"] h1 {font-size:clamp(3rem,4.9vw,4.7rem) !important;line-height:1.02 !important;margin:.15rem 0 !important;padding:0 !important;}
[data-testid="stMain"] h2 {font-size:1.8rem !important;} [data-testid="stMain"] h3 {font-size:1.6rem !important;}
.st-key-bb_editorial_header {border-bottom:1px solid #aeb4ac;padding:.4rem 0 .7rem;}
.st-key-bb_editorial_header [data-testid="stHorizontalBlock"] {align-items:center;gap:1.8rem;}
.st-key-bb_editorial_header p.bb-brand {font-family:Georgia,'Times New Roman',serif;font-weight:900;font-size:2.75rem !important;letter-spacing:-.075em;line-height:1.1;margin:0 !important;color:#101510;}
.bb-brand:after {content:'';display:block;width:34px;height:4px;background:var(--bb-green);margin-top:4px;}
.st-key-bb_desktop_nav [data-testid="stButtonGroup"] button {border:0 !important;border-radius:0 !important;background:transparent !important;color:var(--bb-ink) !important;padding:.6rem .7rem !important;min-height:44px;}
.st-key-bb_desktop_nav [data-testid="stButtonGroup"] button[aria-checked="true"] {border-bottom:4px solid var(--bb-green) !important;background:transparent !important;color:var(--bb-ink) !important;}
.st-key-bb_desktop_nav [data-testid="stButtonGroup"] button p {font-size:1.05rem !important;font-weight:650 !important;}
button:focus-visible, summary:focus-visible {outline:3px solid #a67b00 !important;outline-offset:3px !important;}
[data-testid="stButton"] button, [data-testid="stFormSubmitButton"] button {min-height:44px;border-radius:6px !important;}
[data-testid="stButtonGroup"] button {min-height:44px !important;border-radius:8px !important;border-color:var(--bb-line) !important;}
[data-testid="stButtonGroup"] button[aria-checked="true"] {background:var(--bb-green) !important;color:white !important;}
[data-testid="stButtonGroup"] button[aria-checked="true"] p {color:inherit !important;}
[data-testid="stTextInput"] input, [data-baseweb="select"]>div {background:var(--bb-surface) !important;}
.st-key-wettfinder_v2_mode {padding:0 !important;border:0 !important;}
.st-key-wettfinder_v2_mode [data-testid="stButtonGroup"] button {background:transparent !important;border:0 !important;padding:.3rem .8rem !important;min-height:38px !important;color:var(--bb-muted) !important;}
.st-key-wettfinder_v2_mode [data-testid="stButtonGroup"] button[aria-checked="true"] {color:var(--bb-green) !important;background:var(--bb-green-soft) !important;}
.st-key-editorial_auto_layout [data-testid="stHorizontalBlock"] {gap:2rem !important;align-items:flex-start;}
.st-key-editorial_auto_layout [data-testid="stHorizontalBlock"]>[data-testid="stColumn"] {min-width:0 !important;}
.se-title-mobile {display:none;}
.st-key-wettfinder_v2_sports {padding:0 !important;}
.st-key-wettfinder_v2_sports [role="radiogroup"] {gap:.45rem !important;flex-wrap:wrap;}
.st-key-wettfinder_v2_sports [data-testid="stButtonGroup"] button {background:#efeee8 !important;border:0 !important;border-radius:14px !important;padding:.55rem .85rem !important;min-height:46px !important;}
.st-key-wettfinder_v2_sports [data-testid="stButtonGroup"] button[aria-checked="true"] {background:var(--bb-green) !important;}
.st-key-wettfinder_v2_sports button p {font-size:.9rem !important;font-weight:550;}
.st-key-wettfinder_v2_sports button:before {content:'';width:19px;height:19px;display:block;margin-right:.4rem;border:1.5px solid currentColor;border-radius:50%;background:transparent;flex-shrink:0;}
.st-key-wettfinder_v2_sports button:nth-child(1):before {border-radius:4px;box-shadow:inset 0 0 0 4px #ffffff30;}
.st-key-wettfinder_v2_sports button:nth-child(2):before {background:conic-gradient(from 0deg,transparent 0 12%,currentColor 12% 22%,transparent 22% 43%,currentColor 43% 53%,transparent 53% 74%,currentColor 74% 84%,transparent 84%);}
.st-key-wettfinder_v2_sports button:nth-child(3):before {box-shadow:inset 4px 0 0 -2px currentColor,inset -4px 0 0 -2px currentColor;}
.st-key-wettfinder_v2_sports button:nth-child(4):before {background:linear-gradient(90deg,transparent 44%,currentColor 44% 54%,transparent 54%);}
.st-key-wettfinder_v2_sports button:nth-child(5):before {border-radius:50% 50% 35% 35%;transform:rotate(-25deg);}
.st-key-wettfinder_v2_sports button:nth-child(7):before {border-radius:6px;box-shadow:inset 3px 0 0 0 currentColor;}
.wf-section-heading, .wf-additional-heading {border:0 !important;margin:.3rem 0 !important;}
.st-key-wettfinder_v2_page .wf-additional-heading h2 {font-family:inherit !important;font-size:1rem !important;letter-spacing:0 !important;padding:0;margin:0;}
/* Closed events stay compact native disclosure rows; no detached market cards. */
[class*="st-key-wettfinder_v2_game_"] [data-testid="stExpander"] {border:1px solid var(--bb-line) !important;border-radius:7px !important;background:var(--bb-surface) !important;overflow:visible;}
[class*="st-key-wettfinder_v2_game_"] [data-testid="stExpander"]>details>summary {min-height:48px;padding:.45rem .9rem !important;color:var(--bb-ink) !important;background:transparent !important;}
[class*="st-key-wettfinder_v2_game_"] [data-testid="stExpander"]>details>summary p {font-size:.88rem !important;font-weight:650;line-height:1.4;}
[class*="st-key-wettfinder_v2_game_"] [data-testid="stExpanderDetails"] {padding:0 .95rem .65rem !important;}
[class*="st-key-wettfinder_v2_game_market_"]+[class*="st-key-wettfinder_v2_game_market_"] {border-top:1px solid var(--bb-line);}
.st-key-wettfinder_v2_page article.se-card, article.se-card {display:block !important;background:transparent !important;border:0 !important;border-radius:0 !important;padding:.65rem 0 !important;box-shadow:none !important;min-width:0;}
.se-card-top {display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:1rem;align-items:center;}
.se-card-top-market {grid-template-columns:1fr;}
.se-card-top-market .se-pick {grid-template-columns:minmax(0,1fr) 100px 90px;margin:0;}
.se-card-top-market .se-pick-label {border:0;padding:.3rem 0;}
.se-card-top-market .se-number {border:0;padding:.3rem;}
.se-market-details>summary {font-size:.75rem;min-height:44px;display:flex;align-items:center;color:var(--bb-green);cursor:pointer;}
.se-market-details>summary:after {content:' +';margin-left:.3rem;}
.se-market-details[open]>summary:after {content:' −';}
.se-qa-note {font-size:.6rem !important;letter-spacing:.07em;color:var(--bb-muted);margin:0 !important;}
.se-match {display:grid;grid-template-columns:1fr auto 1fr;gap:.6rem;align-items:center;min-width:0;padding:.4rem 0 .9rem;}
.se-team {display:flex;flex-direction:column;align-items:center;text-align:center;gap:.65rem;min-width:0;}
.se-team strong {font-family:'BB Sport',Impact,sans-serif;font-size:1.65rem;line-height:1.08;overflow-wrap:anywhere;}
.se-shield {position:relative;display:grid;place-items:center;flex:0 0 94px;width:78px;height:94px;background:var(--bb-green);border:5px solid var(--bb-green);color:white;font-size:1.4rem;font-weight:800;clip-path:polygon(50% 0,100% 18%,95% 78%,50% 100%,5% 78%,0 18%);}
.se-shield:after {content:'';position:absolute;inset:4px;border:2px solid #ffffffa0;clip-path:polygon(50% 0,100% 18%,95% 78%,50% 100%,5% 78%,0 18%);}
.se-team:last-child .se-shield {background:#193a53;border-color:#193a53;}
.se-match-time {display:flex;flex-direction:column;text-align:center;color:var(--bb-muted);font-size:.7rem;gap:.25rem;max-width:95px;}
.se-match-time b {font-family:'BB Sport',sans-serif;font-size:1.2rem;color:var(--bb-ink);}
.se-pick {display:grid;grid-template-columns:minmax(0,1.4fr) minmax(0,1fr) minmax(0,.9fr);gap:.5rem;margin-bottom:.7rem;align-items:stretch;}
.se-pick-label {display:flex;flex-direction:column;gap:.4rem;padding:.6rem;border:1px solid #e6e6dd;border-radius:5px;min-width:0;}
.se-pick-label span {font-size:.7rem;color:var(--bb-muted);}
.se-pick-label strong {font-family:'BB Sport',sans-serif;font-size:1.55rem;line-height:1.04;color:var(--bb-ink);overflow-wrap:anywhere;}
.se-number {display:flex;flex-direction:column;justify-content:center;gap:.4rem;padding:.5rem .3rem;border:1px solid #e6e6dd;background:transparent;border-radius:5px;text-align:center;min-width:0;}
.se-number span {font-size:.65rem;color:var(--bb-muted);letter-spacing:.06em;text-transform:uppercase;}
.se-number strong {font-family:'BB Sport',sans-serif;font-size:2.05rem;line-height:1.1;color:var(--bb-green);font-variant-numeric:tabular-nums;white-space:nowrap;}
.se-number-quote strong {color:var(--bb-ink);}
.se-reason {border-left:5px solid var(--bb-green);padding-left:.65rem;margin:.6rem 0;}
.se-reason h4 {font-family:'BB Sport',sans-serif !important;font-size:1.2rem !important;line-height:1.1;margin:0 0 .3rem !important;}
.se-reason p {font-size:.85rem !important;line-height:1.45;margin:.2rem 0 !important;}
.se-reason .se-reason-support {font-size:.75rem !important;color:var(--bb-green);}
.se-card .se-meta {font-size:.7rem;color:var(--bb-muted);}
.se-card .se-event {font-family:'BB Sport',sans-serif;font-size:1.6rem;overflow-wrap:anywhere;}
.st-key-wettfinder_v2_page .se-card .wf-analysis, .se-card .wf-analysis {display:block !important;grid-column:auto !important;border:0 !important;background:transparent !important;padding:0 !important;margin:0 !important;}
.wf-analysis-short {font-size:.9rem !important;line-height:1.5 !important;}
.wf-facts {display:flex !important;flex-wrap:wrap !important;gap:.35rem !important;margin:.7rem 0 .2rem !important;}
.wf-fact {background:transparent !important;border:0 !important;border-radius:4px !important;font-size:.78rem !important;padding:.2rem .5rem !important;position:relative;max-width:100%;overflow-wrap:anywhere;}
details.wf-fact {padding:0 !important;}
.wf-fact>summary {min-height:44px;padding:.5rem;cursor:pointer;} .wf-fact>summary span {color:var(--bb-muted);}
.wf-fact-detail {max-width:100% !important;overflow-wrap:anywhere;line-height:1.5;background:var(--bb-surface);}
.wf-fact-detail p {font-size:.8rem !important;}
.wf-analysis-alert {font-size:.75rem !important;color:#805b20 !important;}
.wf-analysis-footer {display:flex !important;flex-wrap:wrap !important;align-items:center;gap:.6rem;font-size:.68rem;color:var(--bb-muted);margin:.15rem 0 !important;}
.wf-analysis-footer .wf-fact summary {padding:.2rem 0;}
.sports-form {background:transparent;padding:1rem 0 .35rem;border:0;border-top:1px solid var(--bb-line);border-radius:0;margin:.7rem 0 0;min-width:0;}
.form-heading {display:flex;align-items:center;gap:.6rem;margin-bottom:.8rem;flex-wrap:wrap;}
.form-heading h4 {font-family:'BB Sport',sans-serif !important;font-size:1.55rem !important;line-height:1.1;margin:0 !important;}
.form-heading>span {font-size:.6rem;color:var(--bb-muted);margin-left:auto;}
.form-toggle {display:flex;align-items:center;background:#edede5;border-radius:22px;position:relative;}
.form-toggle input {position:absolute;width:1px;height:1px;opacity:0;}
.form-toggle label, .form-ten-unavailable {display:grid;place-items:center;min-width:74px;height:44px;padding:0 .5rem;cursor:pointer;font-size:.8rem;font-weight:550;border-radius:22px;}
.form-ten-unavailable {opacity:.4;cursor:not-allowed;}
.form-toggle label:first-of-type, .form-toggle input:checked+label {background:var(--bb-green);color:white;}
.form-toggle:has(input[value="10"]:checked) label:first-of-type {background:transparent;color:var(--bb-ink);}
.form-toggle input:focus-visible+label {outline:3px solid #a67b00;outline-offset:2px;}
.form-window {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1.3rem;}
.form-window-10 {display:none;}
.sports-form:has(input[value="10"]:checked) .form-window-5 {display:none;}
.sports-form:has(input[value="10"]:checked) .form-window-10 {display:grid;}
.form-team {position:relative;min-width:0;padding:0 .1rem;} .form-team+.form-team {border-left:1px solid var(--bb-line);padding-left:1rem;}
.form-team-heading {display:flex;flex-direction:column;gap:.15rem;margin-bottom:.2rem;}
.form-team-heading strong {font-size:1rem;overflow-wrap:anywhere;} .form-team-heading>span, .form-team>small {font-size:.68rem;color:var(--bb-muted);}
.form-results {display:flex;gap:6px;flex-wrap:wrap;margin:.65rem 0 .6rem;}
.form-result {position:static !important;flex:0 0 48px;border:0 !important;}
.form-result>summary {display:flex;flex-direction:column;justify-content:center;align-items:center;gap:3px;list-style:none;width:48px;min-height:50px;border-radius:5px;cursor:pointer;color:white;line-height:1.1;}
.form-result>summary::-webkit-details-marker {display:none;} .form-result summary b {font-size:.75rem;}
.form-result summary>span {font-size:1.05rem;font-weight:650;font-variant-numeric:tabular-nums;}
.form-s>summary, .form-outcome-s {background:#27874b;} .form-u>summary, .form-outcome-u {background:var(--bb-editorial-yellow);color:#242113;}
.form-n>summary, .form-outcome-n {background:var(--bb-editorial-red);}
.form-result-detail {position:absolute;left:0;right:0;z-index:10;background:var(--bb-surface);border:1px solid var(--bb-line);box-shadow:0 8px 24px #18201b18;border-radius:6px;padding:.75rem;display:flex;flex-direction:column;gap:.3rem;margin-top:.3rem;font-size:.75rem;overflow-wrap:anywhere;}
.form-result[open]>summary {outline:2px solid var(--bb-ink);outline-offset:2px;}
.form-opponent-preview h5 {font:500 .75rem/1.3 sans-serif;margin:.6rem 0 .2rem;}
.form-opponent-preview ol, .form-opponents ol {list-style:none;padding:0;margin:0;}
.form-opponent-preview li, .form-opponents li {border-top:1px solid var(--bb-line);}
.form-opponent-row>summary {display:grid;grid-template-columns:22px minmax(0,1fr) auto 20px;gap:.45rem;align-items:center;min-height:44px;cursor:pointer;list-style:none;font-size:.88rem;}
.form-opponent-row>summary::-webkit-details-marker {display:none;}
.form-opponent-row strong {font-weight:500;overflow-wrap:anywhere;} .form-opponent-row b {font-variant-numeric:tabular-nums;font-size:.8rem;}
.form-opponent-row p {font-size:.7rem !important;color:var(--bb-muted);padding:.1rem .3rem .5rem;margin:0 !important;}
.form-opponent-mark {display:grid;place-items:center;width:20px;height:22px;background:#e5e7dd;font-size:.65rem;clip-path:polygon(0 0,100% 0,100% 75%,50% 100%,0 75%);}
.form-outcome {display:grid;place-items:center;border-radius:3px;font-size:.6rem;width:20px;height:20px;color:white;} .form-outcome-u {color:#242113;}
.form-opponents>summary {font-size:.73rem;color:var(--bb-green);cursor:pointer;min-height:44px;display:flex;align-items:center;}
.form-opponents>summary:after {content:' +';margin-left:.3rem;} .form-opponents[open]>summary:after {content:' −';}
.st-key-editorial_daily3_rail, .st-key-editorial_tennis_rail {border:1px solid var(--bb-line);border-radius:6px;overflow:hidden;background:var(--bb-surface);padding:0 0 .6rem;}
.st-key-editorial_daily3_cover {position:relative;overflow:hidden;background:var(--bb-green);}
.st-key-editorial_daily3_cover [data-testid="stImage"] img {height:280px !important;object-fit:cover;}
.st-key-editorial_daily3_rail [data-testid="stImage"] button, .st-key-editorial_tennis_rail [data-testid="stImage"] button {display:none !important;}
.st-key-editorial_daily3_cover [data-testid="stElementContainer"]:has(.se-cover-content) {position:absolute;inset:0;}
.se-cover-content {box-sizing:border-box;height:280px;padding:1.3rem;display:flex;flex-direction:column;justify-content:center;background:linear-gradient(0deg,#062c22e8,#062c2230);color:white;}
.se-cover-tag {align-self:flex-start;background:var(--bb-editorial-yellow);color:#101510;font-size:.8rem;font-weight:800;padding:.45rem .7rem;border-radius:5px;margin-bottom:1rem;}
.se-cover-content h2 {font-family:'BB Sport',sans-serif;font-size:3.2rem !important;line-height:.99 !important;padding:0 !important;margin:0 !important;color:white;}
.se-cover-content p {color:white;font-size:.88rem !important;margin:.7rem 0 0 !important;line-height:1.45;}
.se-rail-choice {display:flex;align-items:flex-start;gap:.65rem;border-bottom:1px solid var(--bb-line);padding:.85rem 1rem;}
.se-choice-rank {display:grid;place-items:center;flex:0 0 30px;width:30px;height:30px;border-radius:50%;background:var(--bb-green);color:white;font-size:.9rem;}
.se-rail-choice>div {display:flex;flex-direction:column;gap:.3rem;min-width:0;}
.se-rail-choice strong {font-size:.88rem;line-height:1.3;overflow-wrap:anywhere;} .se-rail-choice div>span {font-size:.8rem;line-height:1.4;}
.st-key-editorial_daily3_rail [data-testid="stCaptionContainer"], .st-key-editorial_daily3_rail [data-testid="stButton"], .st-key-editorial_tennis_rail [data-testid="stButton"] {padding:0 1rem;}
.st-key-editorial_daily3_rail [data-testid="stButton"] button {background:var(--bb-editorial-yellow);border:0 !important;color:var(--bb-ink);font-weight:650;}
.st-key-editorial_tennis_rail [data-testid="stImage"] img {height:165px !important;object-fit:cover;}
.se-tennis-tag {background:#e2ecd4;font-size:.8rem !important;font-weight:800;padding:.55rem 1rem;margin:0 !important;display:flex;justify-content:space-between;}
.se-tennis-tag span {font-size:.65rem;font-weight:500;text-transform:uppercase;}
.se-tennis-copy {padding:.8rem 1rem .2rem;} .se-tennis-copy h3 {font-size:1.7rem !important;line-height:1.06 !important;margin:0 0 .4rem !important;overflow-wrap:anywhere;}
.se-tennis-copy p {font-size:.82rem !important;color:var(--bb-muted);margin:.3rem 0 !important;}
.st-key-daily3_choices_layout .se-card-top, .st-key-daily3_choices_layout .form-window {grid-template-columns:1fr;}
.st-key-daily3_choices_layout .form-team+.form-team {border-left:0;padding-left:0;border-top:1px solid var(--bb-line);padding-top:.8rem;}
.st-key-riskobet_summary {background:var(--bb-green-soft) !important;border-color:var(--bb-line) !important;border-radius:6px !important;}
.st-key-riskobet_summary p {color:var(--bb-ink) !important;}
.st-key-riskobet_page .rb-card, .st-key-riskobet_page .rb-row {border-color:var(--bb-line) !important;background:var(--bb-surface) !important;border-radius:7px !important;box-shadow:none !important;}
.st-key-riskobet_page .rb-card .rb-event {font-family:'BB Sport',sans-serif !important;font-size:1.7rem !important;}
.st-key-riskobet_page .rb-pick {background:var(--bb-green-soft) !important;color:var(--bb-green) !important;border-radius:5px;}
.st-key-riskobet_page .rb-primary-probability {color:var(--bb-green) !important;}
.st-key-riskobet_page .rb-probabilities strong {font-family:'BB Sport',sans-serif !important;font-size:2rem !important;}
.st-key-riskobet_page .rb-reasons {background:transparent !important;border-color:var(--bb-line) !important;}
.st-key-riskobet_page .rb-reasons h4 {font-family:'BB Sport',sans-serif !important;font-size:1.2rem !important;}
.st-key-bb_bottomnav {display:none;}
@media(max-width:1100px) and (min-width:761px) {
  .se-card-top {grid-template-columns:1fr;} .se-match {max-width:420px;width:100%;margin:auto;}
  .form-window {grid-template-columns:1fr;} .form-team+.form-team {border-left:0;padding-left:0;border-top:1px solid var(--bb-line);padding-top:.8rem;}
  .se-cover-content h2 {font-size:2.2rem !important;} .st-key-bb_desktop_nav [data-testid="stButtonGroup"] button p {font-size:.9rem !important;}
}
@media(max-width:1023px) {
  .st-key-daily3_choices_layout [data-testid="stHorizontalBlock"] {flex-direction:column !important;}
  .st-key-daily3_choices_layout [data-testid="stHorizontalBlock"]>[data-testid="stColumn"] {width:100% !important;flex:1 1 100% !important;min-width:0 !important;}
}
@media(max-width:760px) {
  [data-testid="stElementContainer"]:has(.se-edition) {display:none;}
  .stApp [data-testid="stMainBlockContainer"], [data-testid="stMain"] .block-container {padding:.7rem .9rem calc(6.5rem + env(safe-area-inset-bottom)) !important;}
  [data-testid="stMain"] h1 {font-size:3.3rem !important;} .se-title-desktop {display:none;}.se-title-mobile {display:inline;}
  .st-key-bb_editorial_header {padding:.25rem 0 .6rem;} .st-key-bb_editorial_header p.bb-brand {font-size:2.65rem !important;}
  .st-key-bb_desktop_nav, .st-key-bb_editorial_header [data-testid="stColumn"]:has(.st-key-bb_desktop_nav) {display:none !important;}
  .st-key-editorial_auto_layout [data-testid="stHorizontalBlock"] {flex-direction:column !important;gap:1rem !important;}
  .st-key-editorial_auto_layout [data-testid="stHorizontalBlock"]>[data-testid="stColumn"] {width:100% !important;flex:1 1 100% !important;min-width:0 !important;}
  .st-key-wettfinder_v2_sports [role="radiogroup"] {flex-wrap:nowrap !important;overflow:auto;max-width:100%;padding:3px 0 7px;}
  .st-key-wettfinder_v2_sports [data-testid="stButtonGroup"] button {flex-shrink:0;white-space:nowrap;padding:.45rem .75rem !important;}
  .se-card-top {grid-template-columns:1fr;gap:.3rem;} .se-team strong {font-size:1.5rem;}
  .se-shield {flex-basis:70px;width:60px;height:70px;font-size:1.1rem;} .se-match {padding:.5rem 0 .2rem;}
  .se-match-time {font-size:.7rem;max-width:72px;}
  .se-pick {grid-template-columns:minmax(0,1.6fr) minmax(0,1fr) minmax(0,.8fr);gap:.4rem;}
  .se-card-top-market .se-pick {grid-template-columns:minmax(0,1.5fr) minmax(0,1fr) minmax(0,.8fr);}
  .se-pick-label {padding:.55rem .45rem;background:var(--bb-green-soft);border:0;}
  .se-pick-label strong {font-size:1.35rem;} .se-number strong {font-size:1.5rem;}
  .se-number span {font-size:.58rem;letter-spacing:0;}
  .se-reason h4 {font-size:1.2rem !important;} .se-reason p {font-size:.8rem !important;}
  .form-window {grid-template-columns:1fr;gap:1rem;} .form-team+.form-team {border-left:0;padding-left:0;border-top:1px solid var(--bb-line);padding-top:.8rem;}
  .form-heading {gap:.4rem;} .form-heading h4 {font-size:1.4rem !important;}
  .form-heading>span {width:100%;order:3;margin:0;} .form-toggle {margin-left:auto;}
  .form-toggle label, .form-ten-unavailable {min-width:62px;font-size:.73rem;}
  .form-results {gap:5px;} .form-result, .form-result>summary {width:46px;flex-basis:46px;}
  .st-key-editorial_daily3_cover [data-testid="stImage"] img, .se-cover-content {height:240px !important;}
  .se-cover-content {padding:1rem;}
  .se-cover-content h2 {font-size:2.6rem !important;}
  .se-cover-tag {margin-bottom:.65rem;}
  [class*="st-key-wettfinder_v2_game_"] [data-testid="stExpanderDetails"] {padding:0 .65rem .5rem !important;}
  [class*="st-key-wettfinder_v2_game_"] [data-testid="stExpander"]>details>summary p {font-size:.85rem !important;}
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
  .stApp [data-testid="stMainBlockContainer"], [data-testid="stMain"] .block-container {padding-left:.65rem !important;padding-right:.65rem !important;}
  .form-results {gap:4px;} .form-result, .form-result>summary {width:44px;flex-basis:44px;}
  .form-toggle label, .form-ten-unavailable {min-width:56px;} .form-heading h4 {font-size:1.2rem !important;}
  .se-team strong {font-size:1.25rem;}
  .se-cover-content h2 {font-size:2.3rem !important;}
}
'''
