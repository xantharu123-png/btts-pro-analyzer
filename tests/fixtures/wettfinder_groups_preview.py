"""Local-only real game-block renderer with named, non-production sample data."""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]

import streamlit as st
import app
from test_daily3_selection import football, tennis
from test_workflow_integrity import _automatic_status

st.set_page_config(page_title='Spielblöcke · lokale Prüfung', layout='wide')
app._apply_app_styles()
st.warning('LOKALE UI-PRÜFUNG · Beispieldaten, keine echten Tipps')
# Stable across UI reruns so the preview never generates a new model on click.
now = st.session_state.setdefault('_qa_model_time', datetime.now(timezone.utc))
pool = [football(1, 'AWAY_OVER_2_5', .215, now=now),
        football(1, 'AWAY_RANGE_2_4', .447, now=now),
        football(1, 'DC_X2', .617, now=now),
        football(2, 'BTTS_YES', now=now), tennis(now=now)]
pool += [football(i, 'HOME_OVER_1_5', now=now) for i in range(3, 26)]
# Real market actions rendered; no account, reservations, saved bets or DB setup.
app.automated_wettfinder_snapshot = lambda **_: SimpleNamespace(
    status=_automatic_status(now), forecasts=tuple(pool), signals=())
with st.container(key='wettfinder_v2_page'):
    app._render_automated_daily_selection()
