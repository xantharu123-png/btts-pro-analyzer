"""Local-only UI regression examples; no provider or account writes."""
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'tests'))

import streamlit as st
from app import _apply_app_styles
import challenge_15k
from challenge_engine import MARKET_BY_KEY
from test_challenge_15k import candidate
from test_riskobet_ui import _bundle
from riskobet_domain import FactorRole
from riskobet_surface import build_riskobet_card
import riskobet_ui

st.set_page_config(page_title='BetBoy · lokale Reparaturprüfung', layout='wide')
_apply_app_styles()
st.warning('LOKALE UI-PRÜFUNG · künstliche Beispiele, keine echten Tipps oder Wetten')
view = st.radio('Prüfansicht', ['15K', 'RisikoBet'], horizontal=True)
if view == '15K':
    now = datetime.now(timezone.utc)
    rows = []
    for key in ('RESULT_HOME', 'RESULT_AWAY', 'AWAY_UNDER_1_5', 'AWAY_OVER_1_5'):
        spec = MARKET_BY_KEY[key]
        row = replace(candidate('1:'+key, 1, .75), market_key=key,
                      market=spec.market, selection=spec.selection,
                      home_team='Petrolul Ploiesti', away_team='Csikszereda')
        row.context = {'injuries': {'availability': 'not_covered', 'coverage_available': False,
                        'status': 'unavailable', 'checked_at': now.isoformat()}}
        rows.append(row)
    challenge_15k._render_price_check(dict(shortlist=[], forecast_shortlist=rows,
        basis_forecasts=rows, price_candidates=rows, reference_quotes={}), None, {})
else:
    snapshot, card = _bundle('Tennis', sport='tennis')
    observation = replace(snapshot.factors[0], factor_key='tennis_workload_a_0',
                          role=FactorRole.DISPLAY_ONLY, summary='Spieler A: zuletzt drei Sätze beobachtet; genaue Endzeit nicht bekannt.')
    snapshot = replace(snapshot, factors=(*snapshot.factors, observation))
    card = replace(card, snapshot_id=snapshot.snapshot_id,
                   pros=('Grundmodell: Spielstärke auf Hartplatz.',),
                   cons=('Verletzungs- und Müdigkeitswirkung noch nicht belegt.',))
    display = build_riskobet_card(card)
    with st.container(key='riskobet_page'):
        riskobet_ui._render_featured((display,), {card.candidate_id: card}, {snapshot.snapshot_id: snapshot})
