"""Real navigation callbacks/routing, with external page engines kept offline."""
import ast
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


AREAS = ["Automatisch", "Eigene Suche", "RisikoBet", "3 a day", "15K", "Live", "Meine Tipps"]
ROOT = Path(__file__).resolve().parents[1]


def _navigation_namespace(st, features):
    """Execute app-owned routing; replace only data engines and external access I/O."""
    from datetime import date, datetime, timedelta, timezone
    from html import escape
    from types import SimpleNamespace
    from account_identity import account_scope_ready
    from customer_access import PAGE_FEATURES

    names = {
        "PAGE_INFO", "MAIN_PAGES", "LEGACY_PAGE_ALIASES", "PAGE_SCAN_JOBS",
        "AREA_OPTIONS", "FINDER_SINGLE_SPORT_OPTIONS", "FINDER_SPORT_OPTIONS", "SEARCH_HORIZONS",
        "_render_sidebar", "_render_editorial_header", "_render_mobile_nav",
        "_commit_workspace_choice", "_set_active_area", "_commit_area_choice", "_area_for_workspace",
        "_render_account_storage_unavailable", "_render_editorial_rail",
        "render_wettfinder", "main", "_segmented", "_finder_sports_for_selection",
    }
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    selected = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            node.decorator_list = []
            selected.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in names for target in node.targets
        ):
            selected.append(node)
    namespace = {
        "st": st, "__file__": str(ROOT / "app.py"), "Path": Path,
        "date": date, "datetime": datetime, "timedelta": timedelta, "timezone": timezone,
        "escape": escape, "PAGE_FEATURES": PAGE_FEATURES,
        "account_scope_ready": account_scope_ready,
        "_REQUIRED_ANALYZER_MODULE_VERSION": 1,
        "get_analyzer": lambda *_args: None,
        "bind_customer": lambda _st: True,
        "_session_scope_id": lambda: "navigation-test",
        "_apply_app_styles": lambda: None,
        "_sidebar_scan_poller": lambda: None,
        "scan_jobs": SimpleNamespace(running_pages=lambda *_args, **_kw: ()),
        "_alternative_markets": SimpleNamespace(FOOTBALL_MARKET_SCOPES=("Beste Märkte",)),
        "zurich_today": lambda: date(2030, 1, 1),
        "_render_automated_daily_selection": lambda: st.markdown("PAGE: Automatisch"),
        "_render_selected_finder": lambda *_args, **_kw: st.markdown("PAGE: Eigene Suche"),
        "render_live": lambda _analyzer: st.markdown("PAGE: Live"),
        "render_challenge_15k": lambda: st.markdown("PAGE: 15K"),
    }
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(ROOT / "app.py"), "exec"), namespace)

    # Keep the production entitlement guard, replacing its loopback network read.
    guard_tree = ast.parse((ROOT / "customer_access.py").read_text(encoding="utf-8"))
    guard = next(node for node in guard_tree.body if isinstance(node, ast.FunctionDef) and node.name == "require_feature")
    guard_namespace = {
        "enabled": lambda: True,
        "fetch_access": lambda _cookies: {"features": list(features)},
        "CustomerAccessDenied": ValueError,
    }
    exec(compile(ast.Module(body=[guard], type_ignores=[]), "customer_access.py", "exec"), guard_namespace)
    namespace["require_feature"] = guard_namespace["require_feature"]
    return namespace


def _run_navigation(workspace="Wettfinder", mode="Automatisch", features=None, identity=True, rail=False):
    import streamlit as st
    from unittest.mock import patch
    from test_unified_navigation import _navigation_namespace

    if "workspace" not in st.session_state:
        st.session_state["workspace"] = workspace
        st.session_state["wettfinder_mode_v2"] = mode
        if identity:
            st.session_state["_betboy_account_scope"] = "a" * 32
    features = features if features is not None else ("automatic", "search", "riskobet", "daily3", "15k", "live", "saved")
    namespace = _navigation_namespace(st, features)
    with (
        patch("riskobet_ui.render_riskobet", lambda: st.markdown("PAGE: RisikoBet")),
        patch("my_tips.render_my_tips", lambda: st.markdown("PAGE: Meine Tipps")),
        patch("daily3_ui.render_daily3", lambda _st: st.markdown("PAGE: 3 a day")),
    ):
        namespace["main"]()
        if rail:
            namespace["_render_editorial_rail"]([], [], daily3_allowed=True, target_label="Heute")


def _area(app):
    return next((item for item in app.selectbox if item.label == "Bereich"), None)


def _page_text(app):
    return " ".join(item.value for item in app.markdown)


def test_one_area_selector_exposes_all_views_without_nested_or_bottom_navigation():
    # Break caught: a destination is omitted, or a competing main/mode widget survives.
    app = AppTest.from_function(_run_navigation).run(timeout=30)
    assert not app.exception
    area = _area(app)
    assert area is not None, "The shared Bereich selector must be rendered"
    assert area.options == AREAS
    assert area.value == "Automatisch"
    assert not app.get("button_group")
    assert "PAGE: Automatisch" in _page_text(app)


@pytest.mark.parametrize(("workspace", "mode", "expected"), [
    ("Wettfinder", "Eigene Suche", "Eigene Suche"),
    ("Tennis", "3 a day", "3 a day"),
    ("15K Challenge", "Automatisch", "15K"),
    ("RisikoBet", "Eigene Suche", "RisikoBet"),
    ("System", "not-a-mode", "Automatisch"),
])
def test_legacy_routes_restore_the_corresponding_flat_area(workspace, mode, expected):
    # Break caught: legacy route normalization discards the active finder mode.
    app = AppTest.from_function(_run_navigation, args=(workspace, mode)).run(timeout=30)
    assert not app.exception
    area = _area(app)
    assert area is not None, "Restored routes need the shared area selector"
    assert area.value == expected
    assert f"PAGE: {expected}" in _page_text(app)


@pytest.mark.parametrize(("chosen", "workspace", "mode"), [
    ("Eigene Suche", "Wettfinder", "Eigene Suche"),
    ("3 a day", "Wettfinder", "3 a day"),
    ("RisikoBet", "RisikoBet", "Automatisch"),
    ("15K", "15K", "Automatisch"),
    ("Live", "Live", "Automatisch"),
    ("Meine Tipps", "Meine Tipps", "Automatisch"),
])
def test_selecting_an_area_synchronizes_real_route_and_render(chosen, workspace, mode):
    # Break caught: callback changes the visual selection but routes to another page.
    app = AppTest.from_function(_run_navigation).run(timeout=30)
    assert _area(app) is not None, "Navigation must use the shared selector"
    _area(app).select(chosen).run(timeout=30)
    assert not app.exception
    assert app.session_state["workspace"] == workspace
    assert app.session_state["wettfinder_mode_v2"] == mode
    assert _area(app).value == chosen
    assert f"PAGE: {chosen}" in _page_text(app)
    _area(app).select("Automatisch").run(timeout=30)
    assert app.session_state["workspace"] == "Wettfinder"
    assert app.session_state["wettfinder_mode_v2"] == "Automatisch"


@pytest.mark.parametrize("chosen", ["Eigene Suche", "RisikoBet", "3 a day", "15K", "Live"])
def test_paid_area_is_guarded_but_does_not_trap_the_shared_navigation(chosen):
    # Break caught: feature dispatch bypasses require_feature, or st.stop hides navigation.
    app = AppTest.from_function(_run_navigation, kwargs={"features": ["automatic", "saved"]}).run(timeout=30)
    assert _area(app) is not None, "The selector must precede every paid-content guard"
    _area(app).select(chosen).run(timeout=30)
    assert not app.exception
    assert "PAGE:" not in _page_text(app)
    assert any("höheren Abo" in item.value for item in app.info)
    assert _area(app).value == chosen
    _area(app).select("Automatisch").run(timeout=30)
    assert "PAGE: Automatisch" in _page_text(app)


@pytest.mark.parametrize("chosen", ["15K", "Meine Tipps"])
def test_personal_areas_still_fail_closed_until_account_storage_is_ready(chosen):
    # Break caught: unified routing renders private page engines without durable identity.
    app = AppTest.from_function(_run_navigation, kwargs={"identity": False}).run(timeout=30)
    assert _area(app) is not None
    _area(app).select(chosen).run(timeout=30)
    assert not app.exception
    assert "PAGE:" not in _page_text(app)
    assert any("persönlicher Speicher" in item.value for item in app.info)
    _area(app).select("Automatisch").run(timeout=30)
    assert "PAGE: Automatisch" in _page_text(app)


def test_daily3_rail_opens_daily3_via_the_same_active_area_state():
    # Break caught: direct entry changes mode but leaves the selector on Automatisch.
    app = AppTest.from_function(_run_navigation, kwargs={"rail": True}).run(timeout=30)
    assert not app.exception
    next(button for button in app.button if button.key == "editorial_daily3_open").click().run(timeout=30)
    assert not app.exception
    assert _area(app) is not None
    assert _area(app).value == "3 a day"
    assert app.session_state["workspace"] == "Wettfinder"
    assert app.session_state["wettfinder_mode_v2"] == "3 a day"
    assert "PAGE: 3 a day" in _page_text(app)


def _run_real_my_tips_navigation():
    """Render the owning collection selector; fake only its data/ledger engines."""
    import streamlit as st
    from unittest.mock import patch
    from test_unified_navigation import _navigation_namespace

    if "workspace" not in st.session_state:
        st.session_state["workspace"] = "Meine Tipps"
        st.session_state["wettfinder_mode_v2"] = "Automatisch"
        st.session_state["_betboy_account_scope"] = "a" * 32
    namespace = _navigation_namespace(st, ("saved", "automatic"))
    with (
        patch("my_tips.render_saved_tips", lambda: st.markdown("COLLECTION: Wettfinder")),
        patch("challenge_15k.render_challenge_history", lambda: st.markdown("COLLECTION: 15K")),
    ):
        namespace["main"]()


def test_real_personal_collection_filter_cannot_be_confused_with_area_navigation():
    app = AppTest.from_function(_run_real_my_tips_navigation).run(timeout=30)
    assert not app.exception
    assert len([item for item in app.selectbox if item.label == "Bereich"]) == 1
    assert _area(app).value == "Meine Tipps"
    source = next(item for item in app.selectbox if item.label == "Tippquelle")
    assert source.options == ["Wettfinder", "15K Challenge"]
    source.select("15K Challenge").run(timeout=30)
    assert not app.exception
    assert app.session_state["workspace"] == "Meine Tipps"
    assert _area(app).value == "Meine Tipps"
    assert "COLLECTION: 15K" in _page_text(app)
    _area(app).select("Automatisch").run(timeout=30)
    assert not app.exception
    assert "PAGE: Automatisch" in _page_text(app)
