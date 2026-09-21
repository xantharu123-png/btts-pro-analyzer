"""Local visual fixture. No provider calls and no account writes."""
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'tests'))
import streamlit as st
from app import _apply_app_styles
from daily3_ui import render_daily3
from test_daily3_tennis_comparison import signal, NOW

st.set_page_config(page_title='BetBoy Daily3 · lokale Testdaten', layout='wide')
_apply_app_styles()
st.warning('LOKALE PRÜFUNG · künstliche Modellbeispiele, keine echten Tipps')
class NoAccount:
    def history(self, scope): return {}
    def command(self, *a, **kw): raise RuntimeError('No account writes in visual fixture')
render_daily3(st, now=NOW, snapshot_loader=lambda **kw:SimpleNamespace(forecasts=(signal(),)),
    store_factory=NoAccount)
