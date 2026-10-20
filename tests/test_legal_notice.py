"""Pflichthinweise im Streamlit-Footer (Audit 16.10.2026, H11)."""
import inspect

import pytest
from streamlit.testing.v1 import AppTest

from legal_notice import LEGAL_ENV, LEGAL_PENDING, PERSONAL_MODE, footer_html, legal_links, legal_ready

ACCESS_ENV = ("BETBOY_CUSTOMER_ACCESS_REQUIRED", "BETBOY_PORTAL_INTERNAL_TOKEN")
PUBLISHED = {
    "BETBOY_LEGAL_URL": "https://betboy.example/de/legal/",
    "BETBOY_PRIVACY_URL": "https://betboy.example/de/privacy/",
    "BETBOY_TERMS_URL": "https://betboy.example/de/terms/",
}


@pytest.fixture
def clean_env(monkeypatch):
    for name in (*LEGAL_ENV.values(), *ACCESS_ENV, "BETBOY_LEGAL_READY"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def _render_footer():
    import streamlit as st
    from legal_notice import render_legal_footer
    render_legal_footer(st)


def _footer_text(app):
    assert not app.exception
    blocks = [item.value for item in app.markdown if "bb-legal" in item.value]
    assert len(blocks) == 1
    return blocks[0]


def test_footer_names_age_limit_risk_and_swiss_help_lines(clean_env):
    text = _footer_text(AppTest.from_function(_render_footer).run(timeout=30))
    assert "18+" in text
    assert "Wetten können zum Verlust des Einsatzes führen." in text
    assert 'href="https://www.sos-spielsucht.ch/"' in text and "SOS Spielsucht" in text
    assert "0800 040 080" in text and 'href="tel:0800040080"' in text
    assert 'href="https://www.suchtschweiz.ch/"' in text and "Sucht Schweiz" in text
    assert 'rel="noopener noreferrer"' in text


def test_footer_without_legal_urls_states_that_pages_are_not_published(clean_env):
    text = _footer_text(AppTest.from_function(_render_footer).run(timeout=30))
    assert LEGAL_PENDING in text
    assert 'href="https://betboy.example' not in text
    assert ">Datenschutz<" not in text and ">AGB<" not in text


def test_footer_with_legal_urls_links_operator_privacy_and_terms(clean_env):
    for name, value in PUBLISHED.items():
        clean_env.setenv(name, value)
    text = _footer_text(AppTest.from_function(_render_footer).run(timeout=30))
    assert LEGAL_PENDING not in text
    for value, label in zip(PUBLISHED.values(), ("Anbieterinformationen", "Datenschutz", "AGB")):
        assert f'<a href="{value}" target="_blank" rel="noopener noreferrer">{label}</a>' in text


@pytest.mark.parametrize("broken", [
    {"BETBOY_TERMS_URL": ""},                                  # one of three missing
    {"BETBOY_PRIVACY_URL": "http://betboy.example/privacy/"},  # no https
    {"BETBOY_LEGAL_URL": "javascript:alert(1)"},
    {"BETBOY_LEGAL_URL": "//evil.example/legal/"},
])
def test_incomplete_or_unsafe_legal_urls_fall_back_to_the_honest_placeholder(clean_env, broken):
    for name, value in {**PUBLISHED, **broken}.items():
        clean_env.setenv(name, value)
    assert legal_links() == {}
    assert legal_ready() is False
    text = _footer_text(AppTest.from_function(_render_footer).run(timeout=30))
    assert LEGAL_PENDING in text
    assert "evil.example" not in text and "javascript:" not in text


def test_site_relative_paths_are_accepted_like_the_portal_qa_settings(clean_env):
    for name, value in {"BETBOY_LEGAL_URL": "/de/legal/", "BETBOY_PRIVACY_URL": "/de/privacy/", "BETBOY_TERMS_URL": "/de/terms/"}.items():
        clean_env.setenv(name, value)
    assert legal_links() == {"legal": "/de/legal/", "privacy": "/de/privacy/", "terms": "/de/terms/"}


def test_footer_shows_personal_mode_only_while_customer_access_is_not_enforced(clean_env):
    assert PERSONAL_MODE in _footer_text(AppTest.from_function(_render_footer).run(timeout=30))
    clean_env.setenv("BETBOY_CUSTOMER_ACCESS_REQUIRED", "0")
    assert PERSONAL_MODE in _footer_text(AppTest.from_function(_render_footer).run(timeout=30))
    clean_env.setenv("BETBOY_CUSTOMER_ACCESS_REQUIRED", "1")
    assert PERSONAL_MODE not in _footer_text(AppTest.from_function(_render_footer).run(timeout=30))


def test_footer_html_escapes_labels_and_urls():
    text = footer_html({"legal": "https://x.example/?a=1&b=2", "privacy": "/p", "terms": "/t"}, "enforced")
    assert 'href="https://x.example/?a=1&amp;b=2"' in text
    assert PERSONAL_MODE not in text


def test_app_main_renders_the_legal_footer_instead_of_the_bare_caption():
    import app
    source = inspect.getsource(app.main)
    assert "render_legal_footer(st)" in source
    assert "Modellwerte sind Schätzungen" not in source
