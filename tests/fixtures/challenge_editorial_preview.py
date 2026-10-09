"""Isolated 15K visual QA: synthetic forecasts, no API scans or ledger writes."""
from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]

import streamlit as st
import app
from challenge_15k import _render_model_challenge, _render_progress
from test_challenge_15k import stress_safe_ticket_candidates
from test_challenge_15k_model_ui import editorial_snapshot

st.set_page_config(page_title='BetBoy · 15K Designprüfung', layout='wide', initial_sidebar_state='collapsed')
app._apply_app_styles()
st.session_state.setdefault('workspace', '15K')
app._session_scope_id = lambda: 'challenge-editorial-visual-qa'
workspace = app._render_sidebar(None)
app._render_editorial_header(workspace)
app._render_mobile_nav(workspace)
st.markdown('<p class="se-qa-note">LOKALE DESIGNPRÜFUNG · BEISPIELDATEN · KEIN SPORTSCAN</p>', unsafe_allow_html=True)
st.title('15K Challenge')
st.caption('Dein nächstes Challenge-Ticket.')
settings = dict(current_balance=100.0, target_balance=15000.0, starting_balance=100.0, stake_fraction=.05)

def reject_booking(*_args, **_kwargs):
    raise ValueError('Die isolierte Designprüfung erfasst keine Wetten.')

ledger = SimpleNamespace(settings=lambda: settings, pending_tickets=lambda: [], place_ticket=reject_booking)
_render_progress(ledger)
candidates = stress_safe_ticket_candidates()
candidates[0].home_team, candidates[0].away_team = 'FC Porto', 'Manchester City'
candidates[0].home_team_id, candidates[0].away_team_id = 212, 50
candidates[1].home_team, candidates[1].away_team = 'Arsenal', 'Chelsea'
candidates[1].home_team_id, candidates[1].away_team_id = 42, 49
snapshot = st.session_state.setdefault('_qa_snapshot', editorial_snapshot(candidates))
if st.query_params.get('case') == 'Keine Historie':
    snapshot = {**snapshot, 'challenge_display_records': {}}
_render_model_challenge(snapshot, ledger, settings)
