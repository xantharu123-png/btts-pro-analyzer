"""Isolated visual QA. Only synthetic test records; no scans or production DB."""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]

import streamlit as st
import app
from test_sports_editorial import editorial_football, editorial_tennis
from test_workflow_integrity import _automatic_status

st.set_page_config(page_title='BetBoy · isolierte Designprüfung', layout='wide', initial_sidebar_state='collapsed')
app._apply_app_styles()
st.session_state.setdefault('workspace', 'Wettfinder')
app._session_scope_id = lambda: 'editorial-visual-qa'
workspace = app._render_sidebar(None)
from streamlit.components.v1 import html as component_html
# Mirror the native nested zero-height bridge wrapper without a real account,
# production database, browser storage, or network call.
component_html('<html><body></body></html>', height=0, scrolling=False)
app._render_editorial_header(workspace)
app._render_mobile_nav(workspace)
if workspace == 'RisikoBet':
    st.title('RisikoBet')
st.markdown('<p class="se-qa-note">LOKALE DESIGNPRÜFUNG · BEISPIELDATEN · KEIN SPORTSCAN</p>', unsafe_allow_html=True)
scenario = st.query_params.get('case', 'Normal')
if scenario == 'Abo-Hinweis':
    st.info('Dieser Bereich ist in einem höheren Abo enthalten.')
    st.stop()
now = st.session_state.setdefault('_qa_model_time', datetime.now(timezone.utc).replace(hour=7, minute=0, second=0, microsecond=0))
# Freeze the display evaluation as well, so a midnight rollover or a long QA
# session cannot expire synthetic matches or remove Daily3's fixture cards.
class QADatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return now.astimezone(tz or timezone.utc)
app.datetime = QADatetime
count = 3 if scenario == 'Kurze Historie' else 10
pool = [editorial_football(now=now, count=count, long=scenario == 'Langer Teamname', start_hours=.1),
    editorial_football(now=now, count=count, fixture=1, key='TOTAL_OVER_2_5', start_hours=.1),
    editorial_football(now=now, count=count, fixture=2, key='BTTS_YES', start_hours=.1), editorial_tennis(now=now, count=count)]
if scenario == 'Keine Auswahl':
    pool = []
if scenario == 'Daily3':
    pool.append(editorial_football(now=now, count=count, fixture=3, key='DC_1X', start_hours=.1))
app.automated_wettfinder_snapshot = lambda **_: SimpleNamespace(
    status=_automatic_status(now), forecasts=tuple(pool), signals=())
if scenario == 'RisikoBet' or st.session_state['workspace'] == 'RisikoBet':
    import riskobet_ui
    from test_riskobet_ui import _bundle, _view
    riskobet_ui.load_riskobet_view = lambda *_a, **_kw: _view(_bundle('1'), _bundle('2', sport='tennis'))
    riskobet_ui.render_riskobet()
elif scenario == 'Daily3' or st.session_state.get('wettfinder_mode_v2') == '3 a day':
    from daily3_ui import render_daily3
    from daily3_store import Daily3Store
    st.session_state['_betboy_account_scope'] = 'b'*32
    render_daily3(st, now=now, snapshot_loader=app.automated_wettfinder_snapshot,
        store_factory=lambda: Daily3Store(ROOT/'output/editorial-preview/daily3.db', key=b'v'*32, clock=lambda: now))
else:
    with st.container(key='wettfinder_v2_page'):
        app._render_automated_daily_selection()
