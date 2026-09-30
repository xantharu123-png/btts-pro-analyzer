"""Participant imagery is presentation-only; every network response is mocked."""
import base64
from dataclasses import FrozenInstanceError
from io import BytesIO
import json
from pathlib import Path
from unittest.mock import Mock

from PIL import Image
import pytest
import requests

import sports_identity_media as media


CREST = "https://media.api-sports.io/football/teams/33.png"
PHOTO = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Rafael_Nadal.jpg/330px-Rafael_Nadal.jpg"
SOURCE = "https://commons.wikimedia.org/wiki/File:Rafael_Nadal.jpg"


def raster(format="PNG", size=(32, 32)):
    output = BytesIO()
    Image.new("RGB", size, "green").save(output, format=format)
    return output.getvalue()


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch, tmp_path):
    media._download_image.cache_clear()
    media._read_manifest.cache_clear()
    monkeypatch.setattr(media, "_MANIFEST_PATH", tmp_path / "missing.json")
    session = Mock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    session.get.side_effect = AssertionError("Unit tests must explicitly mock a response")
    monkeypatch.setattr(media.requests, "Session", Mock(return_value=session))
    yield session
    media._download_image.cache_clear()
    media._read_manifest.cache_clear()


def reply(session, *, data=None, status=200, mime="image/png", url=CREST, headers=None, chunks=None):
    response = Mock(status_code=status, url=url)
    response.headers = {"Content-Type": mime, **(headers or {})}
    response.iter_content.return_value = iter([raster() if data is None else data] if chunks is None else chunks)
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    session.get.side_effect = None
    session.get.return_value = response
    return response


def portrait_manifest(monkeypatch, tmp_path, entries=None):
    path = tmp_path / "portraits.json"
    entry = {"names": ["Rafael Nadal"], "file": "Rafael Nadal.jpg", "url": PHOTO,
             "source": SOURCE, "credit": "Test author · CC BY-SA 4.0"}
    path.write_text(json.dumps({"entries": [entry] if entries is None else entries}), encoding="utf-8")
    monkeypatch.setattr(media, "_MANIFEST_PATH", path)
    return path, entry


def football(**kwargs):
    return media.participant_image("football", "Manchester United", team_id=kwargs.pop("team_id", 33),
                                   fixture_source=kwargs.pop("fixture_source", "api-football"), **kwargs)


def test_native_crest_download_is_bounded_verified_and_immutable(no_real_network):
    data = raster()
    reply(no_real_network, data=data)
    image = football(context_evidence={"secret": "must-not-be-sent"})
    assert base64.b64decode(image.data_uri.split(",", 1)[1]) == data
    assert image.data_uri.startswith("data:image/png;base64,")
    assert image.source_url == CREST and image.credit is None
    assert no_real_network.trust_env is False
    no_real_network.get.assert_called_once_with(CREST, stream=True, timeout=(2, 3), allow_redirects=False,
        headers={"User-Agent": "BetBoy/1.0 (public participant images)"})
    with pytest.raises(FrozenInstanceError):
        image.credit = "changed"


@pytest.mark.parametrize("provider", [None, "", "sofascore", "ESPN", "api-sports", "odds-api"])
def test_other_or_absent_team_namespaces_never_become_api_football_ids(no_real_network, provider):
    assert football(fixture_source=provider) is None
    no_real_network.get.assert_not_called()


@pytest.mark.parametrize("team_id", [None, True, False, 0, -1, 33.0, "033", "33.0", "api-football:team:33", "33?key=secret", 2**100, "9" * 50])
def test_crest_id_is_not_guessed_or_coerced(no_real_network, team_id):
    assert football(team_id=team_id) is None
    no_real_network.get.assert_not_called()


@pytest.mark.parametrize("provider", ["API-Football", "api_football"])
def test_canonical_decimal_team_id_is_supported(no_real_network, provider):
    reply(no_real_network)
    assert football(team_id="33", fixture_source=provider) is not None


def test_unsupported_sport_and_missing_manifest_stay_offline(no_real_network):
    assert media.participant_image("basketball", "Rafael Nadal", team_id=33, fixture_source="api-football") is None
    assert media.participant_image("tennis", "Rafael Nadal") is None
    no_real_network.get.assert_not_called()


@pytest.mark.parametrize("name", ["Rafael Nadal", "Nadal Rafael", "Ráfael Nadál", "  rafael   nadal "])
def test_curated_full_names_can_fold_accents_or_reverse_exact_tokens(no_real_network, monkeypatch, tmp_path, name):
    portrait_manifest(monkeypatch, tmp_path)
    reply(no_real_network, url=PHOTO)
    image = media.participant_image("tennis", name, team_id="foreign-player-id", fixture_source="ESPN")
    assert image is not None and image.source_url == SOURCE
    assert image.credit == "Test author · CC BY-SA 4.0 · Bildausschnitt"


@pytest.mark.parametrize("name", ["Nadal", "R Nadal", "R. Nadal", "Rafael N.", "Rafael Nadal Jr", "Rafeal Nadal", "Nadál Rafael Extra"])
def test_partial_initial_or_fuzzy_names_do_not_select_portraits(no_real_network, monkeypatch, tmp_path, name):
    portrait_manifest(monkeypatch, tmp_path)
    assert media.participant_image("tennis", name) is None
    no_real_network.get.assert_not_called()


def test_chinese_name_order_requires_the_entire_name(no_real_network, monkeypatch, tmp_path):
    _, row = portrait_manifest(monkeypatch, tmp_path)
    row["names"] = ["Zhizhen Zhang", "Zhang Zhizhen"]
    portrait_manifest(monkeypatch, tmp_path, [row])
    reply(no_real_network, url=PHOTO)
    assert media.participant_image("tennis", "Zhang Zhizhen") is not None
    assert media.participant_image("tennis", "Zhang") is None


def test_alias_collision_is_ambiguous_even_when_one_order_is_exact(no_real_network, monkeypatch, tmp_path):
    _, row = portrait_manifest(monkeypatch, tmp_path)
    portrait_manifest(monkeypatch, tmp_path, [row, {**row, "names": ["Nadal Rafael"]}])
    assert media.participant_image("tennis", "Rafael Nadal") is None
    no_real_network.get.assert_not_called()


def test_name_token_multiplicity_is_significant(no_real_network, monkeypatch, tmp_path):
    _, row = portrait_manifest(monkeypatch, tmp_path)
    portrait_manifest(monkeypatch, tmp_path, [{**row, "names": ["Li Li Zhang"]}])
    assert media.participant_image("tennis", "Li Zhang") is None
    no_real_network.get.assert_not_called()


@pytest.mark.parametrize("host", ["upload.wikimedia.org", "thumb.wikimedia.org"])
def test_both_verified_commons_thumbnail_hosts_are_allowed(no_real_network, monkeypatch, tmp_path, host):
    _, row = portrait_manifest(monkeypatch, tmp_path)
    url = PHOTO.replace("upload.wikimedia.org", host)
    portrait_manifest(monkeypatch, tmp_path, [{**row, "url": url}])
    reply(no_real_network, url=url)
    assert media.participant_image("tennis", "Rafael Nadal") is not None


def test_checked_in_registry_resolves_every_full_name_without_network(no_real_network, monkeypatch):
    path = Path(media.__file__).resolve().parent / "assets" / "identity" / "tennis-portraits.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    monkeypatch.setattr(media, "_MANIFEST_PATH", path)
    assert isinstance(manifest, list) and len(manifest) >= 13
    for row in manifest:
        for name in row["names"]:
            portrait = media._portrait(name, 0)
            assert portrait is not None, name
            assert portrait.url == row["url"] and portrait.source == row["source"]
    no_real_network.get.assert_not_called()


def test_manifest_can_distinguish_a_local_slug_from_the_original_commons_file(no_real_network, monkeypatch, tmp_path):
    _, row = portrait_manifest(monkeypatch, tmp_path)
    row.update(file="portrait-local-slug.jpg", source_file="Rafael Nadal.jpg")
    portrait_manifest(monkeypatch, tmp_path, [row])
    reply(no_real_network, url=PHOTO)
    assert media.participant_image("tennis", "Rafael Nadal") is not None


@pytest.mark.parametrize("crop", [None, [35, 0, 1.7], [0, 100, 1], [100, 0, 3]])
def test_optional_crop_is_frozen_metadata_and_never_edits_raster_bytes(no_real_network, monkeypatch, tmp_path, crop):
    _, row = portrait_manifest(monkeypatch, tmp_path)
    portrait_manifest(monkeypatch, tmp_path, [{**row, "crop": crop}])
    original = raster()
    reply(no_real_network, url=PHOTO, data=original)
    image = media.participant_image("tennis", "Rafael Nadal")
    assert image.crop == (None if crop is None else tuple(float(value) for value in crop))
    assert base64.b64decode(image.data_uri.split(",", 1)[1]) == original
    with pytest.raises(FrozenInstanceError):
        image.crop = (50, 50, 1)


@pytest.mark.parametrize("crop", [[35, 0], [35, 0, 1.7, 0], "35,0,1.7", [True, 0, 1.7],
    [35, False, 1.7], [35, 0, True], [-1, 0, 1.7], [101, 0, 1.7], [35, -1, 1.7],
    [35, 101, 1.7], [35, 0, .99], [35, 0, 3.01], [float("nan"), 0, 1.7],
    [35, float("inf"), 1.7], [35, 0, float("-inf")], [35, 0, "1.7"]])
def test_invalid_or_nonfinite_crop_fails_closed_before_network(no_real_network, monkeypatch, tmp_path, crop):
    _, row = portrait_manifest(monkeypatch, tmp_path)
    portrait_manifest(monkeypatch, tmp_path, [{**row, "crop": crop}])
    assert media.participant_image("tennis", "Rafael Nadal") is None
    no_real_network.get.assert_not_called()


def test_malformed_or_oversize_manifest_is_not_loaded(no_real_network, monkeypatch, tmp_path):
    path, _ = portrait_manifest(monkeypatch, tmp_path)
    for content in ("not json", "x" * (media._MAX_MANIFEST_BYTES + 1)):
        path.write_text(content, encoding="utf-8")
        assert media.participant_image("tennis", "Rafael Nadal") is None
    no_real_network.get.assert_not_called()


@pytest.mark.parametrize("url", [
    "http://media.api-sports.io/football/teams/33.png",
    "https://media.api-sports.io/football/teams/33.png?key=secret",
    "https://media.api-sports.io/football/teams/33.png#fragment",
    "https://user:password@media.api-sports.io/football/teams/33.png",
    "https://media.api-sports.io:443/football/teams/33.png",
    "https://media.api-sports.io.evil.test/football/teams/33.png",
    "https://media.api-sports.io/football/players/33.png",
    "https://127.0.0.1/football/teams/33.png",
    "https://upload.wikimedia.org/not-commons/photo.png",
    "https://upload.wikimedia.org/wikipedia/commons/a/ab/photo.svg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/photo.svg/330px-photo.svg.png",
    "https://upload.wikimedia.org/wikipedia/commons/a/ab/%2e%2e/photo.png",
])
def test_arbitrary_urls_and_vector_sources_never_trigger_network(no_real_network, url):
    assert media._download_image(url, 0) is None
    no_real_network.get.assert_not_called()


@pytest.mark.parametrize("change", [
    {"source": "https://commons.wikimedia.org/wiki/File:Other.jpg"},
    {"url": PHOTO.replace("Rafael_Nadal", "Someone_else")},
    {"url": PHOTO + "?token=secret"}, {"credit": ""}, {"names": ["R. Nadal"]},
    {"file": "Rafael Nadal.svg"}, {"source": SOURCE + "?key=secret"},
])
def test_invalid_manifest_entries_fail_closed(no_real_network, monkeypatch, tmp_path, change):
    _, row = portrait_manifest(monkeypatch, tmp_path)
    portrait_manifest(monkeypatch, tmp_path, [{**row, **change}])
    assert media.participant_image("tennis", "Rafael Nadal") is None
    no_real_network.get.assert_not_called()


@pytest.mark.parametrize("status", [301, 302, 403, 404, 500])
def test_blocked_missing_or_redirected_media_cache_failure(no_real_network, status):
    reply(no_real_network, status=status)
    assert football() is None and football() is None
    no_real_network.get.assert_called_once()


def test_successes_and_failures_retry_only_in_a_new_daily_bucket(no_real_network, monkeypatch):
    clock = [100_000]
    monkeypatch.setattr(media.time, "time", lambda: clock[0])
    reply(no_real_network, status=403)
    assert football() is None and football() is None
    assert no_real_network.get.call_count == 1
    clock[0] += media._CACHE_SECONDS
    reply(no_real_network)
    assert football() is not None and football() is not None
    assert no_real_network.get.call_count == 2
    assert media._download_image.cache_info().maxsize == 128


@pytest.mark.parametrize("headers", [{"Content-Length": str(media._MAX_BYTES + 1)},
    {"Content-Length": "-1"}, {"Content-Length": "not-a-number"}, {"Content-Length": "0"}])
def test_declared_size_is_bounded_before_reading(no_real_network, headers):
    response = reply(no_real_network, headers=headers)
    assert football() is None
    response.iter_content.assert_not_called()


def test_streamed_size_is_bounded_without_content_length(no_real_network):
    reply(no_real_network, chunks=[b"a" * media._MAX_BYTES, b"x"])
    assert football() is None


@pytest.mark.parametrize("format,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp")])
def test_original_verified_raster_bytes_are_not_reencoded(no_real_network, format, mime):
    data = raster(format)
    reply(no_real_network, data=data, mime=mime)
    image = football()
    assert image.data_uri == f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


@pytest.mark.parametrize("data,mime", [(b"<svg></svg>", "image/svg+xml"), (b"<html>blocked</html>", "image/png"),
    (raster("JPEG"), "image/png"), (raster(), "text/html"), (raster()[:30], "image/png"),
    (raster("JPEG")[:80], "image/jpeg"), (b"RIFF0000WEBPinvalid", "image/webp")])
def test_mime_magic_or_decode_failure_never_returns_an_image(no_real_network, data, mime):
    reply(no_real_network, data=data, mime=mime)
    assert football() is None


@pytest.mark.parametrize("size", [(4097, 1), (2001, 2000)])
def test_dimension_and_pixel_caps_reject_large_rasters(no_real_network, size):
    reply(no_real_network, data=raster(size=size))
    assert football() is None


def test_foreign_final_response_url_is_rejected_without_following(no_real_network):
    reply(no_real_network, url="https://evil.test/crest.png")
    assert football() is None


def test_request_errors_are_cached_and_do_not_escape_into_rendering(no_real_network):
    no_real_network.get.side_effect = requests.Timeout("unavailable")
    assert football() is None and football() is None
    no_real_network.get.assert_called_once()
