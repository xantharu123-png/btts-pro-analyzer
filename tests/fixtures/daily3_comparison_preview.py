"""Local-only preview; synthetic evidence, no account or production writes."""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]

import streamlit as st
import app
from daily3_ui import render_daily3
from test_daily3_selection import football

st.set_page_config(page_title='Daily3 Vergleich · lokale Prüfung', layout='wide')
app._apply_app_styles()
st.warning('LOKALE UI-PRÜFUNG · erfundene Beispieldaten, keine echten Tipps')
now = st.session_state.setdefault('_qa_model_time', datetime.now(timezone.utc))
missing = st.checkbox('Ohne passende Vergleichsdaten')
pool = [football(1, 'AWAY_UNDER_2_5', .953, baseline=.93, now=now),
        football(2, 'AWAY_UNDER_2_5', .91, baseline=.88, now=now),
        football(3, 'HOME_OVER_0_5', .908, baseline=.87, now=now),
        football(4, 'BTTS_YES', .74, baseline=.45, now=now),
        football(5, 'TOTAL_OVER_2_5', .73, baseline=.43, now=now),
        football(6, 'HOME_UNDER_1_5', .79, baseline=.54, now=now)]
if missing:
    pool = [football(1, now=now, comparison=False)]
render_daily3(st, now=now,
              snapshot_loader=lambda **_: SimpleNamespace(forecasts=tuple(pool)))
