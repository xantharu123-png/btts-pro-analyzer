"""Local-only visual QA with clearly labelled sample data and a required QA DB."""
from datetime import datetime, timezone
import os
import importlib
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'tests'))

import streamlit as st
from daily3_store import Daily3Store
import daily3_ui
from test_daily3_selection import football, tennis

database = Path(os.environ['BETBOY_DAILY3_QA_DB']).resolve()
if not database.is_relative_to(ROOT/'.pytest_tmp'):
    raise RuntimeError('An isolated QA database under .pytest_tmp is required')
st.set_page_config(page_title='Daily3 · lokale Prüfung', layout='wide')
st.warning('LOKALE UI-PRÜFUNG · Beispieldaten, keine echten Tipps oder Kontobewegungen')
st.session_state['_betboy_account_scope'] = 'f'*32
now = datetime(2030, 1, 1, 12, tzinfo=timezone.utc)
importlib.reload(daily3_ui)
pool = (football(1, now=now), football(2, 'BTTS_YES', now=now), tennis(now=now))
if st.query_params.get('state') == 'empty':
    pool = ()
daily3_ui.render_daily3(st, now=now,
    snapshot_loader=lambda **kwargs: SimpleNamespace(forecasts=pool),
    store_factory=lambda: Daily3Store(database, key=b'q'*32, clock=lambda: now))
