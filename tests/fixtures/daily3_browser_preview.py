"""Local-only visual QA with clearly labelled sample data and a required QA DB."""
from datetime import datetime, timezone
from dataclasses import replace
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
from app import _apply_app_styles
from wettfinder_surface import build_wettfinder_card, render_top_card_html, render_compact_row_html
from test_forecast_compact import row_with_names
from test_forecast_analysis import _basis, _signal
from forecast_analysis import project_football_analysis
from test_daily3_selection import football, tennis

database = Path(os.environ['BETBOY_DAILY3_QA_DB']).resolve()
if not database.is_relative_to(ROOT/'.pytest_tmp'):
    raise RuntimeError('An isolated QA database under .pytest_tmp is required')
st.set_page_config(page_title='Daily3 · lokale Prüfung', layout='wide')
_apply_app_styles()
st.warning('LOKALE UI-PRÜFUNG · Beispieldaten, keine echten Tipps oder Kontobewegungen')
st.session_state['_betboy_account_scope'] = 'f'*32
now = datetime(2030, 1, 1, 12, tzinfo=timezone.utc)
importlib.reload(daily3_ui)
sample_row = row_with_names()
sample_row['modeled_at'] = now.isoformat()
sample_row['analysis_evidence'] = project_football_analysis(sample_row, model_basis=_basis(sample_row))
sample_signal = replace(_signal(sample_row), market='Doppelte Chance', selection='1X')
pool = (sample_signal, football(2, 'BTTS_YES', now=now), tennis(now=now))
if st.query_params.get('state') == 'empty':
    pool = ()
with st.container(key='wettfinder_v2_page'):
    if st.query_params.get('view') == 'cards':
        card = build_wettfinder_card(sample_signal, now=now)
        with st.container(key='wettfinder_v2_top_grid'):
            with st.columns(2)[0]:
                with st.container(key='wettfinder_v2_top_card_qa'):
                    st.markdown(render_top_card_html(card), unsafe_allow_html=True)
        with st.container(key='wettfinder_v2_additional_row_qa'):
            st.markdown(render_compact_row_html(card), unsafe_allow_html=True)
    else:
        daily3_ui.render_daily3(st, now=now,
            snapshot_loader=lambda **kwargs: SimpleNamespace(forecasts=pool),
            store_factory=lambda: Daily3Store(database, key=b'q'*32, clock=lambda: now))
