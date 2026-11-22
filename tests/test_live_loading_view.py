"""The live tab must not present an in-flight first discovery as an empty league list."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

import app
import live_football_feed
from live_football_feed import LiveFootballFeed, LiveRefreshIssue, LiveSourceError


LOADING = "Live-Spielstände werden geladen"
EMPTY = "Kein Live-Spiel"
PROVIDER_ERROR = "Live-Daten des Anbieters sind derzeit nicht verfügbar"


def _page():
    import app
    import streamlit as st

    st.session_state["workspace"] = "Live"
    app.render_live(object())


class HeldDiscovery:
    def __init__(self, outcome):
        self.outcome = outcome
        self.entered = Event()
        self.release = Event()
        self.fixture = {
            "fixture": {"id": 72, "status": {"short": "2H", "elapsed": 70}},
            "teams": {"home": {"id": 1, "name": "Testheim"}, "away": {"id": 2, "name": "Testgast"}},
            "goals": {"home": 2, "away": 1}, "league": {"id": 39, "name": "Testliga"},
            "events": [], "statistics": [],
        }

    def discover(self):
        self.entered.set()
        if not self.release.wait(timeout=20):
            raise TimeoutError("Test did not release discovery")
        if self.outcome == "provider_error":
            raise LiveSourceError(LiveRefreshIssue.PROVIDER_ERROR)
        return [self.fixture] if self.outcome == "score" else []

    def details(self, ids):
        assert ids == [72]
        return [self.fixture]


def _offline_page(monkeypatch, ticker, source):
    monkeypatch.setenv("BETBOY_CUSTOMER_ACCESS_REQUIRED", "0")
    monkeypatch.setattr(app, "_live_session_connected", lambda: True)
    monkeypatch.setattr(app, "load_app_config", lambda _: SimpleNamespace(api_football_key="offline", freemode=False))
    monkeypatch.setattr(app, "_live_ticker_resources", lambda _: (ticker, source))
    monkeypatch.setattr(app, "_analyze_ticker_fixture", lambda *_: (None, None))
    return AppTest.from_function(_page, default_timeout=10)


def test_first_viewer_receives_loading_before_the_blocking_provider_call_returns(monkeypatch):
    # AppTest exposes only the completed tree. Observe the same deltas Streamlit
    # sends to the browser to verify what the first viewer sees *during* discovery.
    from streamlit.runtime.forward_msg_queue import ForwardMsgQueue

    source = HeldDiscovery("score")
    page = _offline_page(monkeypatch, LiveFootballFeed(), source)
    alerts = []
    enqueue = ForwardMsgQueue.enqueue

    def observe(queue, msg):
        if msg.delta.new_element.HasField("alert"):
            alerts.append(msg.delta.new_element.alert.body)
        enqueue(queue, msg)

    monkeypatch.setattr(ForwardMsgQueue, "enqueue", observe)
    with ThreadPoolExecutor(max_workers=1) as pool:
        viewing = pool.submit(page.run)
        try:
            assert source.entered.wait(timeout=5)
            assert any(LOADING in text for text in alerts), alerts
        finally:
            source.release.set()
        viewing.result(timeout=5)
    assert not page.exception
    assert not any(EMPTY in text for text in alerts)
    assert not any(LOADING in el.value for el in page.info)
    assert "2:1" in page.button(key="live_fixture_72").label


def test_warm_score_is_not_removed_while_its_next_detail_call_blocks(monkeypatch):
    from streamlit.runtime.forward_msg_queue import ForwardMsgQueue

    monkeypatch.setattr(live_football_feed, "DETAIL_INTERVAL", timedelta(0))
    source = HeldDiscovery("score")
    source.release.set()
    page = _offline_page(monkeypatch, LiveFootballFeed(), source)
    updates = []
    enqueue = ForwardMsgQueue.enqueue

    def observe(queue, msg):
        if msg.delta.HasField("new_element"):
            updates.append((tuple(msg.metadata.delta_path), msg.delta.new_element))
        enqueue(queue, msg)

    monkeypatch.setattr(ForwardMsgQueue, "enqueue", observe)
    page.run()
    assert not page.exception
    score = page.button(key="live_fixture_72")
    assert "2:1" in score.label
    path = next(p for p, el in updates if el.HasField("button") and el.button.id == score.id)
    updates.clear()
    entered, release = Event(), Event()

    def slow_details(ids):
        entered.set()
        if not release.wait(timeout=20):
            raise TimeoutError("Test did not release detail refresh")
        return [{**source.fixture, "goals": {"home": 3, "away": 1}}]

    source.details = slow_details
    with ThreadPoolExecutor(max_workers=1) as pool:
        viewing = pool.submit(page.run)
        try:
            assert entered.wait(timeout=5)
            # Replacing an ancestor with a leaf erases the live score. Republishing
            # the score button in place, on the other hand, would also be legitimate.
            assert not [(p, el.WhichOneof("type")) for p, el in updates
                        if path[:len(p)] == p and not (p == path and el.button.id == score.id)]
        finally:
            release.set()
        viewing.result(timeout=5)
    assert not page.exception
    assert "3:1" in page.button(key="live_fixture_72").label


@pytest.mark.parametrize("outcome", ["score", "empty", "provider_error"])
def test_second_viewer_shows_loading_until_the_shared_provider_replies(monkeypatch, outcome):
    ticker, source = LiveFootballFeed(), HeldDiscovery(outcome)
    page = _offline_page(monkeypatch, ticker, source)
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(ticker.tick, source, now=datetime.now(timezone.utc))
        try:
            assert source.entered.wait(timeout=5)
            page.run()
            assert not page.exception
            pending = " ".join(el.value for el in page.info)
            assert LOADING in pending and EMPTY not in pending and PROVIDER_ERROR not in pending
            assert not page.button
        finally:
            source.release.set()
        first.result(timeout=5)

    page.run()
    assert not page.exception
    completed = " ".join(el.value for el in page.info)
    assert LOADING not in completed
    assert (EMPTY in completed) == (outcome == "empty")
    assert (PROVIDER_ERROR in completed) == (outcome == "provider_error")
    if outcome == "score":
        label = page.button(key="live_fixture_72").label
        assert "2:1" in label and "Testheim" in label and "Testgast" in label
    else:
        assert not page.button
