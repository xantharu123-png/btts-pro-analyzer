"""Participant image URLs resolve offline; only the browser fetches the bytes."""
from dataclasses import FrozenInstanceError
import json
import os
from pathlib import Path
import socket
from unittest.mock import Mock

import pytest

import sports_identity_media as media


CREST = "https://media.api-sports.io/football/teams/33.png"
PHOTO = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Rafael_Nadal.jpg/330px-Rafael_Nadal.jpg"
SOURCE = "https://commons.wikimedia.org/wiki/File:Rafael_Nadal.jpg"


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch, tmp_path):
    media._read_manifest.cache_clear()
    monkeypatch.setattr(media, "_MANIFEST_PATH", tmp_path / "missing.json")
    network = Mock(side_effect=AssertionError("Participant URL resolution must stay offline"))
    monkeypatch.setattr(socket, "create_connection", network)
    monkeypatch.setattr(socket.socket, "connect", network)
    yield network
    network.assert_not_called()
    media._read_manifest.cache_clear()


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


def test_native_crest_is_direct_public_url_and_immutable(no_real_network):
    image = football(context_evidence={"secret": "must-not-be-sent"})
    assert image.image_url == CREST
    assert image.source_url == CREST and image.credit is None
    assert not hasattr(image, "data_uri")
    with pytest.raises(FrozenInstanceError):
        image.credit = "changed"


def test_resolver_has_no_http_binary_decoder_or_image_cache():
    for removed in ("requests", "Image", "base64", "BytesIO", "_download_image", "_verified_data_uri"):
        assert removed not in vars(media)
    assert media._read_manifest.cache_info().maxsize == 1


def test_repeated_resolution_does_not_write_files_or_grow_an_image_cache(no_real_network, monkeypatch, tmp_path):
    portrait_manifest(monkeypatch, tmp_path)
    before = {item.name: item.read_bytes() for item in tmp_path.iterdir()}
    for _ in range(20):
        assert football().image_url == CREST
        assert media.participant_image("tennis", "Rafael Nadal").image_url == PHOTO
    assert {item.name: item.read_bytes() for item in tmp_path.iterdir()} == before


@pytest.mark.parametrize("provider", [None, "", "sofascore", "ESPN", "api-sports", "odds-api"])
def test_other_or_absent_team_namespaces_never_become_api_football_ids(no_real_network, provider):
    assert football(fixture_source=provider) is None


@pytest.mark.parametrize("team_id", [None, True, False, 0, -1, 33.0, "033", "33.0", "api-football:team:33", "33?key=secret", 2**100, "9" * 50])
def test_crest_id_is_not_guessed_or_coerced(no_real_network, team_id):
    assert football(team_id=team_id) is None


@pytest.mark.parametrize("provider", ["API-Football", "api_football"])
def test_canonical_decimal_team_id_is_supported(no_real_network, provider):
    assert football(team_id="33", fixture_source=provider).image_url == CREST


def test_native_id_limit_matches_public_url_validation(no_real_network):
    result = football(team_id=2**63 - 1)
    assert media.safe_participant_image_url(result.image_url) == result.image_url
    assert football(team_id=2**63) is None


def test_unsupported_sport_and_missing_manifest_stay_offline(no_real_network):
    assert media.participant_image("basketball", "Rafael Nadal", team_id=33, fixture_source="api-football") is None
    assert media.participant_image("tennis", "Rafael Nadal") is None


@pytest.mark.parametrize("name", ["Rafael Nadal", "Nadal Rafael", "Ráfael Nadál", "  rafael   nadal "])
def test_curated_full_names_can_fold_accents_or_reverse_exact_tokens(no_real_network, monkeypatch, tmp_path, name):
    portrait_manifest(monkeypatch, tmp_path)
    image = media.participant_image("tennis", name, team_id="foreign-player-id", fixture_source="ESPN")
    assert image.image_url == PHOTO and image.source_url == SOURCE
    assert image.credit == "Test author · CC BY-SA 4.0 · Bildausschnitt"


@pytest.mark.parametrize("name", ["Nadal", "R Nadal", "R. Nadal", "Rafael N.", "Rafael Nadal Jr", "Rafeal Nadal", "Nadál Rafael Extra"])
def test_partial_initial_or_fuzzy_names_do_not_select_portraits(no_real_network, monkeypatch, tmp_path, name):
    portrait_manifest(monkeypatch, tmp_path)
    assert media.participant_image("tennis", name) is None


def test_chinese_name_order_requires_the_entire_name(no_real_network, monkeypatch, tmp_path):
    _, row = portrait_manifest(monkeypatch, tmp_path)
    row["names"] = ["Zhizhen Zhang", "Zhang Zhizhen"]
    portrait_manifest(monkeypatch, tmp_path, [row])
    assert media.participant_image("tennis", "Zhang Zhizhen").image_url == PHOTO
    assert media.participant_image("tennis", "Zhang") is None


def test_alias_collision_is_ambiguous_even_when_one_order_is_exact(no_real_network, monkeypatch, tmp_path):
    _, row = portrait_manifest(monkeypatch, tmp_path)
    portrait_manifest(monkeypatch, tmp_path, [row, {**row, "names": ["Nadal Rafael"]}])
    assert media.participant_image("tennis", "Rafael Nadal") is None


def test_name_token_multiplicity_is_significant(no_real_network, monkeypatch, tmp_path):
    _, row = portrait_manifest(monkeypatch, tmp_path)
    portrait_manifest(monkeypatch, tmp_path, [{**row, "names": ["Li Li Zhang"]}])
    assert media.participant_image("tennis", "Li Zhang") is None


@pytest.mark.parametrize("host", ["upload.wikimedia.org", "thumb.wikimedia.org"])
def test_both_verified_commons_thumbnail_hosts_are_allowed(no_real_network, monkeypatch, tmp_path, host):
    _, row = portrait_manifest(monkeypatch, tmp_path)
    url = PHOTO.replace("upload.wikimedia.org", host)
    portrait_manifest(monkeypatch, tmp_path, [{**row, "url": url}])
    assert media.participant_image("tennis", "Rafael Nadal").image_url == url


def test_checked_in_registry_resolves_every_full_name_as_small_thumbnail_without_network(no_real_network, monkeypatch):
    path = Path(media.__file__).resolve().parent / "assets" / "identity" / "tennis-portraits.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    monkeypatch.setattr(media, "_MANIFEST_PATH", path)
    assert isinstance(manifest, list) and len(manifest) >= 13
    for row in manifest:
        for name in row["names"]:
            image = media.participant_image("tennis", name)
            assert image is not None, name
            assert image.image_url == row["url"] and image.source_url == row["source"]
            assert media.safe_participant_image_url(image.image_url) == image.image_url
            assert "/330px-" in image.image_url


def test_manifest_can_distinguish_stable_slug_from_original_commons_file(no_real_network, monkeypatch, tmp_path):
    _, row = portrait_manifest(monkeypatch, tmp_path)
    row.update(file="portrait-local-slug.jpg", source_file="Rafael Nadal.jpg")
    portrait_manifest(monkeypatch, tmp_path, [row])
    assert media.participant_image("tennis", "Rafael Nadal").image_url == PHOTO


@pytest.mark.parametrize("crop", [None, [35, 0, 1.7], [0, 100, 1], [100, 0, 3]])
def test_optional_crop_is_frozen_metadata_and_leaves_original_url_unchanged(no_real_network, monkeypatch, tmp_path, crop):
    _, row = portrait_manifest(monkeypatch, tmp_path)
    portrait_manifest(monkeypatch, tmp_path, [{**row, "crop": crop}])
    image = media.participant_image("tennis", "Rafael Nadal")
    assert image.crop == (None if crop is None else tuple(float(value) for value in crop))
    assert image.image_url == PHOTO
    with pytest.raises(FrozenInstanceError):
        image.crop = (50, 50, 1)


@pytest.mark.parametrize("crop", [[35, 0], [35, 0, 1.7, 0], "35,0,1.7", [True, 0, 1.7],
    [35, False, 1.7], [35, 0, True], [-1, 0, 1.7], [101, 0, 1.7], [35, -1, 1.7],
    [35, 101, 1.7], [35, 0, .99], [35, 0, 3.01], [float("nan"), 0, 1.7],
    [35, float("inf"), 1.7], [35, 0, float("-inf")], [35, 0, "1.7"]])
def test_invalid_or_nonfinite_crop_fails_closed_before_browser_receives_a_url(no_real_network, monkeypatch, tmp_path, crop):
    _, row = portrait_manifest(monkeypatch, tmp_path)
    portrait_manifest(monkeypatch, tmp_path, [{**row, "crop": crop}])
    assert media.participant_image("tennis", "Rafael Nadal") is None


def test_malformed_or_oversize_manifest_is_not_loaded(no_real_network, monkeypatch, tmp_path):
    path, _ = portrait_manifest(monkeypatch, tmp_path)
    for content in ("not json", "x" * (media._MAX_MANIFEST_BYTES + 1)):
        path.write_text(content, encoding="utf-8")
        assert media.participant_image("tennis", "Rafael Nadal") is None


@pytest.mark.parametrize("url", [
    None, 33, "", "data:image/png;base64,AA==", "javascript:alert(1)",
    "http://media.api-sports.io/football/teams/33.png",
    "https://media.api-sports.io/football/teams/33.png?key=secret",
    "https://media.api-sports.io/football/teams/33.png#fragment",
    "https://user:password@media.api-sports.io/football/teams/33.png",
    "https://media.api-sports.io:443/football/teams/33.png",
    "https://media.api-sports.io.evil.test/football/teams/33.png",
    "https://media.api-sports.io/football/players/33.png",
    "https://media.api-sports.io/football/teams/0.png",
    "https://media.api-sports.io/football/teams/033.png",
    "https://media.api-sports.io/football/teams/9223372036854775808.png",
    "https://127.0.0.1/football/teams/33.png",
    "https://upload.wikimedia.org/not-commons/photo.png",
    "https://upload.wikimedia.org/wikipedia/commons/a/ab/photo.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/a/ab/photo.svg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/photo.svg/330px-photo.svg.png",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/photo.jpg/330px-other.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/photo.jpg/401px-photo.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/photo.jpg/4000px-photo.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/photo.jpg/0330px-photo.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/%2e%2e/photo.png",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/photo%5c.jpg/330px-photo%5c.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/photo%00.jpg/330px-photo%00.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/photo%FF.jpg/330px-photo%FF.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/photo%ZZ.jpg/330px-photo%ZZ.jpg",
    PHOTO + " ", PHOTO + "?width=400", PHOTO + "#fragment",
])
def test_unsafe_original_oversized_or_mismatched_urls_are_rejected_offline(no_real_network, url):
    assert media.safe_participant_image_url(url) is None


@pytest.mark.parametrize("width", [1, 100, 330, 400])
def test_thumbnail_width_bounds_accept_small_exact_file_only(width):
    url = PHOTO.replace("330px-", f"{width}px-")
    assert media.safe_participant_image_url(url) == url


@pytest.mark.parametrize("extension", ["png", "jpg", "jpeg", "webp", "JPG"])
def test_direct_thumbnail_supported_raster_extensions(extension):
    url = PHOTO.replace(".jpg", "." + extension)
    assert media.safe_participant_image_url(url) == url


@pytest.mark.parametrize("change", [
    {"source": "https://commons.wikimedia.org/wiki/File:Other.jpg"},
    {"url": PHOTO.replace("Rafael_Nadal", "Someone_else")},
    {"url": PHOTO.replace("330px-Rafael_Nadal", "330px-Someone_else")},
    {"url": PHOTO.replace("/thumb/", "/").rsplit("/", 1)[0]},
    {"url": PHOTO.replace("330px-", "401px-")},
    {"url": PHOTO + "?token=secret"}, {"credit": ""}, {"names": ["R. Nadal"]},
    {"file": "Rafael Nadal.svg"}, {"source": SOURCE + "?key=secret"},
])
def test_invalid_manifest_entries_fail_closed(no_real_network, monkeypatch, tmp_path, change):
    _, row = portrait_manifest(monkeypatch, tmp_path)
    portrait_manifest(monkeypatch, tmp_path, [{**row, **change}])
    assert media.participant_image("tennis", "Rafael Nadal") is None


def test_manifest_metadata_refreshes_in_new_daily_bucket_without_network(no_real_network, monkeypatch, tmp_path):
    path, row = portrait_manifest(monkeypatch, tmp_path)
    clock = [100_000]
    monkeypatch.setattr(media.time, "time", lambda: clock[0])
    assert media.participant_image("tennis", "Rafael Nadal").credit.startswith("Test author")
    stat = path.stat()
    row["credit"] = "Another author · CC BY-SA 4.0"
    portrait_manifest(monkeypatch, tmp_path, [row])
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert media.participant_image("tennis", "Rafael Nadal").credit.startswith("Test author")
    clock[0] += media._MANIFEST_REFRESH_SECONDS
    assert media.participant_image("tennis", "Rafael Nadal").credit.startswith("Another author")
    assert media._read_manifest.cache_info().maxsize == 1
