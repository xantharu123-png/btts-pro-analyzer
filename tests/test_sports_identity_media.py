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
    media._read_team_manifest.cache_clear()
    monkeypatch.setattr(media, "_MANIFEST_PATH", tmp_path / "missing.json")
    monkeypatch.setattr(media, "_TEAM_MANIFEST_PATH", tmp_path / "missing-teams.json")
    network = Mock(side_effect=AssertionError("Participant URL resolution must stay offline"))
    monkeypatch.setattr(socket, "create_connection", network)
    monkeypatch.setattr(socket.socket, "connect", network)
    yield network
    network.assert_not_called()
    media._read_manifest.cache_clear()
    media._read_team_manifest.cache_clear()


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
    assert media._read_team_manifest.cache_info().maxsize == 1


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


NBA_LOGO = "https://a.espncdn.com/i/teamlogos/nba/500/2.png"
NHL_LOGO = "https://assets.nhle.com/logos/nhl/svg/TOR_light.svg"
EURO_LOGO = "https://mediacentre.euroleague.net/uploads/euroleaguecore/teams/logos/positive_3363.png"
CRICKET_LOGO = "https://static.cricbuzz.com/a/img/v1/152x152/i1/c172115/india.jpg"
NAVi_LOGO = "https://img.navi.gg/teams/2025/10/teams-4028/thumbnail/58234/Team-Yandex_46x46.png"


def team_manifest(monkeypatch, tmp_path, entries=None):
    row = {"sport": "ice_hockey", "provider": "nhl", "team_id": "10",
           "names": ["TOR", "Toronto Maple Leafs"], "url": NHL_LOGO,
           "source": "https://records.nhl.com/site/api/team"}
    path = tmp_path / "team-logos.json"
    path.write_text(json.dumps({"entries": [row] if entries is None else entries}), encoding="utf-8")
    monkeypatch.setattr(media, "_TEAM_MANIFEST_PATH", path)
    return path, row


@pytest.mark.parametrize("team_id,competition", [("espn:basketball:team:2", "NBA"), (2, "NBA"), ("2", "nba")])
def test_nba_logo_uses_espn_native_namespace_without_network(no_real_network, team_id, competition):
    image = media.participant_image("basketball", "BOS", team_id=team_id,
                                    fixture_source="ESPN", competition=competition)
    assert image.image_url == NBA_LOGO
    assert media.participant_image_url_matches_kind("basketball", image.image_url)


@pytest.mark.parametrize("team_id,provider,competition", [
    (2, "ESPN", None), (2, "ESPN", "Euroleague"), (2, "NBA.com", "NBA"),
    ("nhl:ice_hockey:team:2", "ESPN", "NBA"), ("espn:ice_hockey:team:2", "ESPN", "NBA"),
    ("espn:basketball:team:02", "ESPN", "NBA"), (True, "ESPN", "NBA"),
    ("espn:basketball:team:5", "ESPN", "WNBA"), ("espn:basketball:team:2", "ESPN", None),
    ("espn:basketball:team:5", "ESPN", "NCAA"),
    (2.0, "ESPN", "NBA"), ("2?apiKey=secret", "ESPN", "NBA"),
])
def test_nba_ids_cannot_cross_provider_sport_or_competition_namespaces(no_real_network, team_id, provider, competition):
    assert media.participant_image("basketball", "BOS", team_id=team_id,
                                    fixture_source=provider, competition=competition) is None


@pytest.mark.parametrize("team_id,name", [("nhl:ice_hockey:team:10", "TOR"), (10, "Toronto Maple Leafs"), ("10", "toronto maple leafs")])
def test_nhl_logo_requires_reviewed_native_id_and_whole_team_name(no_real_network, monkeypatch, tmp_path, team_id, name):
    team_manifest(monkeypatch, tmp_path)
    image = media.participant_image("ice_hockey", name, team_id=team_id, fixture_source="NHL")
    assert image.image_url == NHL_LOGO
    assert media.participant_image_url_matches_kind("ice_hockey", image.image_url)


@pytest.mark.parametrize("team_id,name,provider", [
    ("espn:basketball:team:10", "TOR", "NHL"), (10, "TOR", "ESPN"), (9, "TOR", "NHL"),
    (10, "Toronto", "NHL"), (10, "BOS", "NHL"), ("010", "TOR", "NHL"),
])
def test_nhl_does_not_guess_from_name_or_foreign_id(no_real_network, monkeypatch, tmp_path, team_id, name, provider):
    team_manifest(monkeypatch, tmp_path)
    assert media.participant_image("ice_hockey", name, team_id=team_id, fixture_source=provider) is None


@pytest.mark.parametrize("name,team_id,expected", [
    ("BOS", 6, "Boston Bruins"),
    ("BOS", "6", "Boston Bruins"),
    ("BOS", "nhl:ice_hockey:team:6", "Boston Bruins"),
    ("PHI", 4, "Philadelphia Flyers"),
    ("PHI", "4", "Philadelphia Flyers"),
    ("PHI", "nhl:ice_hockey:team:4", "Philadelphia Flyers"),
])
def test_display_name_expands_exact_reviewed_nhl_identity_offline(
        no_real_network, monkeypatch, name, team_id, expected):
    monkeypatch.setattr(media, "_TEAM_MANIFEST_PATH",
                        Path(__file__).resolve().parents[1] / "assets" / "identity" / "team-logos.json")
    assert media.participant_display_name("ice_hockey", name, team_id=team_id,
                                         fixture_source="NHL", competition="NHL") == expected


@pytest.mark.parametrize("team_id,name,provider,competition", [
    (None, "BOS", "NHL", "NHL"),
    (True, "BOS", "NHL", "NHL"),
    (False, "BOS", "NHL", "NHL"),
    (0, "BOS", "NHL", "NHL"),
    (-6, "BOS", "NHL", "NHL"),
    (6.0, "BOS", "NHL", "NHL"),
    ("06", "BOS", "NHL", "NHL"),
    ("6.0", "BOS", "NHL", "NHL"),
    ("6?key=secret", "BOS", "NHL", "NHL"),
    (2**63, "BOS", "NHL", "NHL"),
    (4, "BOS", "NHL", "NHL"),
    (6, "PHI", "NHL", "NHL"),
    (6, "Boston", "NHL", "NHL"),
    (6, "Bruins", "NHL", "NHL"),
    (6, "Boston Bruns", "NHL", "NHL"),
    (6, "  BOS Junior  ", "NHL", "NHL"),
    (6, "BOS\n", "NHL", "NHL"),
    (6, "", "NHL", "NHL"),
    (6, "BOS", None, "NHL"),
    (6, "BOS", "ESPN", "NHL"),
    (6, "BOS", "api-sports", "NHL"),
    (6, "BOS", "NHL", None),
    (6, "BOS", "NHL", ""),
    (6, "BOS", "NHL", "AHL"),
    (6, "BOS", "NHL", "NHL Preseason"),
    ("espn:basketball:team:6", "BOS", "NHL", "NHL"),
    ("nhl:basketball:team:6", "BOS", "NHL", "NHL"),
    ("nhl:ice_hockey:team:06", "BOS", "NHL", "NHL"),
])
def test_display_name_preserves_input_for_invalid_nhl_identity_context(
        no_real_network, monkeypatch, team_id, name, provider, competition):
    monkeypatch.setattr(media, "_TEAM_MANIFEST_PATH",
                        Path(__file__).resolve().parents[1] / "assets" / "identity" / "team-logos.json")
    assert media.participant_display_name("ice_hockey", name, team_id=team_id,
                                         fixture_source=provider, competition=competition) == name


@pytest.mark.parametrize("kind", ["football", "basketball", "tennis", "cricket", "esports", "hockey", ""])
def test_display_name_does_not_expand_a_reviewed_nhl_code_in_other_sports(
        no_real_network, monkeypatch, kind):
    monkeypatch.setattr(media, "_TEAM_MANIFEST_PATH",
                        Path(__file__).resolve().parents[1] / "assets" / "identity" / "team-logos.json")
    assert media.participant_display_name(kind, "BOS", team_id=6,
                                         fixture_source="NHL", competition="NHL") == "BOS"


def test_display_name_preserves_original_label_when_manifest_is_missing(no_real_network):
    assert media.participant_display_name("ice_hockey", "  BOS  ", team_id=6,
                                         fixture_source="NHL", competition="NHL") == "  BOS  "


@pytest.mark.parametrize("names", [["TOR", "Toronto Maple Leafs"], ["Other Team"]])
def test_display_name_rejects_duplicate_native_manifest_identity(
        no_real_network, monkeypatch, tmp_path, names):
    _, row = team_manifest(monkeypatch, tmp_path)
    team_manifest(monkeypatch, tmp_path, [row, {**row, "names": names}])
    assert media.participant_display_name("ice_hockey", "TOR", team_id=10,
                                         fixture_source="NHL", competition="NHL") == "TOR"


def test_display_name_preserves_code_when_reviewed_row_has_no_full_label(
        no_real_network, monkeypatch, tmp_path):
    _, row = team_manifest(monkeypatch, tmp_path)
    team_manifest(monkeypatch, tmp_path, [{**row, "names": ["TOR"]}])
    assert media.participant_display_name("ice_hockey", "TOR", team_id=10,
                                         fixture_source="NHL", competition="NHL") == "TOR"


def test_display_name_uses_first_reviewed_full_label_without_touching_manifest(
        no_real_network, monkeypatch, tmp_path):
    path, row = team_manifest(monkeypatch, tmp_path)
    team_manifest(monkeypatch, tmp_path, [{**row, "names": ["TOR", "Toronto Maple Leafs", "Toronto Leafs"]}])
    original = path.read_bytes()
    assert media.participant_display_name("ice_hockey", "  tor  ", team_id=10,
                                         fixture_source=" nhl ", competition=" nhl ") == "Toronto Maple Leafs"
    assert path.read_bytes() == original


def test_euroleague_logo_uses_exact_reviewed_club_code_and_source(no_real_network, monkeypatch, tmp_path):
    row = {"sport": "basketball", "provider": "euroleague", "team_id": "BAR",
           "names": ["BAR", "FC Barcelona"], "url": EURO_LOGO,
           "source": "https://mediacentre.euroleague.net/mediacentre/en/games/view/18487/yes"}
    team_manifest(monkeypatch, tmp_path, [row])
    for key in ("BAR", "euroleague:basketball:team:BAR"):
        assert media.participant_image("basketball", "BAR", team_id=key, fixture_source="EuroLeague").image_url == EURO_LOGO
    assert media.participant_image("basketball", "FC Barcelona", team_id="PAR", fixture_source="EuroLeague") is None
    assert media.participant_image("basketball", "Barcelona", team_id="BAR", fixture_source="EuroLeague") is None


def test_cricket_country_can_match_only_unique_reviewed_provider_identity(no_real_network, monkeypatch, tmp_path):
    row = {"sport": "cricket", "provider": "cricbuzz", "team_id": "2", "names": ["India", "IND"],
           "url": CRICKET_LOGO, "source": "https://www.cricbuzz.com/cricket-team/india/2"}
    team_manifest(monkeypatch, tmp_path, [row])
    assert media.participant_image("cricket", "India", team_id="2", fixture_source="Cricbuzz").image_url == CRICKET_LOGO
    assert media.participant_image("cricket", "India", team_id="4", fixture_source="Cricbuzz") is None
    assert media.participant_image("cricket", "India", fixture_source="Cricbuzz") is None
    row.update(provider="cricketdata", team_id="")
    team_manifest(monkeypatch, tmp_path, [row])
    assert media.participant_image("cricket", "India", fixture_source="CricketData").image_url == CRICKET_LOGO
    assert media.participant_image("cricket", "India A", fixture_source="CricketData") is None
    assert media.participant_image("cricket", "India", team_id=2, fixture_source="CricketData") is None


def test_esports_team_logo_needs_exact_manifest_id_name_provider_and_url(no_real_network, monkeypatch, tmp_path):
    row = {"sport": "esports", "provider": "pandascore", "team_id": "1653", "names": ["Natus Vincere", "NAVI"],
           "url": NAVi_LOGO, "source": "https://navi.gg/en"}
    team_manifest(monkeypatch, tmp_path, [row])
    image = media.participant_image("esports", "NAVI", team_id=1653, fixture_source="PandaScore")
    assert image.image_url == NAVi_LOGO
    assert media.participant_image_url_matches_kind("esports", image.image_url)
    assert media.participant_image("esports", "NAVI", team_id=1654, fixture_source="PandaScore") is None
    assert media.participant_image("esports", "Navi junior", team_id=1653, fixture_source="PandaScore") is None
    assert media.participant_image("esports", "NAVI", team_id=1653, fixture_source="ESPN") is None


def test_reviewed_logo_retains_author_and_license_credit(no_real_network, monkeypatch, tmp_path):
    row = {"sport": "esports", "provider": "pandascore", "team_id": "1653", "names": ["NAVI"],
           "url": NAVi_LOGO, "source": "https://navi.gg/en", "credit": "NAVI · offizieller Spielplan"}
    team_manifest(monkeypatch, tmp_path, [row])
    assert media.participant_image("esports", "NAVI", team_id=1653, fixture_source="pandascore").credit == row["credit"]


def test_existing_pandascore_metadata_can_supply_a_small_direct_logo_without_network(no_real_network, monkeypatch):
    import participant_logo_catalog
    url = "https://cdn.pandascore.co/images/team/image/1653/thumb_navi.png"
    resolve = Mock(return_value=url)
    monkeypatch.setattr(participant_logo_catalog, "resolve_pandascore_logo", resolve)
    image = media.participant_image("esports", "NAVI", team_id=1653, fixture_source="PandaScore")
    assert image.image_url == url
    resolve.assert_called_once_with("1653", "NAVI")
    assert media.participant_image_url_matches_kind("esports", url)


@pytest.mark.parametrize("url", [
    "https://cdn.pandascore.co/images/team/image/999/thumb_navi.png",
    "https://cdn.pandascore.co/images/team/image/1653/navi.png",
    "https://cdn.pandascore.co/images/team/image/1653/thumb_navi.svg",
    "https://cdn.pandascore.co/images/team/image/1653/thumb_navi.png?key=secret",
    "https://evil.test/images/team/image/1653/thumb_navi.png",
])
def test_pandascore_metadata_cannot_grant_other_team_original_or_foreign_host(no_real_network, monkeypatch, url):
    import participant_logo_catalog
    monkeypatch.setattr(participant_logo_catalog, "resolve_pandascore_logo", Mock(return_value=url))
    assert media.participant_image("esports", "NAVI", team_id=1653, fixture_source="pandascore") is None


def test_curated_esport_commons_logo_is_not_a_tennis_portrait(no_real_network, monkeypatch, tmp_path):
    url = "https://thumb.wikimedia.org/wikipedia/commons/thumb/3/39/MOUZlogo2021.png/330px-MOUZlogo2021.png"
    row = {"sport": "esports", "provider": "pandascore", "team_id": "134559", "names": ["MOUZ"],
           "url": url, "source": "https://commons.wikimedia.org/wiki/File:MOUZlogo2021.png"}
    team_manifest(monkeypatch, tmp_path, [row])
    assert media.participant_image_url_matches_kind("esports", url)
    assert not media.participant_image_url_matches_kind("tennis", url)


def test_reviewed_small_logo_exceptions_do_not_grant_neighbor_urls_or_query_changes(no_real_network):
    for url in media._REVIEWED_ESPORT_IMAGE_URLS:
        assert media.safe_participant_image_url(url) == url
        assert media.participant_image_url_matches_kind("esports", url)
        assert not media.participant_image_url_matches_kind("tennis", url)
        assert media.safe_participant_image_url(url + "&token=secret") is None
        assert media.safe_participant_image_url(url + "#fragment") is None
        if "330px-" in url:
            assert media.safe_participant_image_url(url.replace("330px-", "331px-")) is None


def test_duplicate_team_manifest_identity_is_ambiguous(no_real_network, monkeypatch, tmp_path):
    _, row = team_manifest(monkeypatch, tmp_path)
    team_manifest(monkeypatch, tmp_path, [row, row])
    assert media.participant_image("ice_hockey", "TOR", team_id=10, fixture_source="NHL") is None


@pytest.mark.parametrize("change", [
    {"team_id": "010"}, {"names": []}, {"names": ["TOR\n"]}, {"sport": "tennis"},
    {"provider": "ESPN"}, {"url": NHL_LOGO + "?token=secret"}, {"url": "https://evil.test/TOR_light.svg"},
    {"url": NHL_LOGO.replace("_light", "_dark")}, {"url": CREST}, {"source": "javascript:alert(1)"},
])
def test_malformed_team_manifest_fails_closed(no_real_network, monkeypatch, tmp_path, change):
    _, row = team_manifest(monkeypatch, tmp_path)
    team_manifest(monkeypatch, tmp_path, [{**row, **change}])
    assert media.participant_image("ice_hockey", "TOR", team_id=10, fixture_source="NHL") is None


def test_team_metadata_cache_is_bounded_and_does_not_persist_images(no_real_network, monkeypatch, tmp_path):
    team_manifest(monkeypatch, tmp_path)
    before = {item.name: item.read_bytes() for item in tmp_path.iterdir()}
    for _ in range(25):
        assert media.participant_image("ice_hockey", "TOR", team_id=10, fixture_source="NHL").image_url == NHL_LOGO
    assert {item.name: item.read_bytes() for item in tmp_path.iterdir()} == before
    assert media._read_team_manifest.cache_info().maxsize == 1


def test_oversized_or_too_many_team_manifest_rows_are_rejected(no_real_network, monkeypatch, tmp_path):
    path, row = team_manifest(monkeypatch, tmp_path)
    path.write_text("x" * (media._MAX_TEAM_MANIFEST_BYTES + 1), encoding="utf-8")
    assert media.participant_image("ice_hockey", "TOR", team_id=10, fixture_source="NHL") is None
    team_manifest(monkeypatch, tmp_path, [row] * 257)
    assert media.participant_image("ice_hockey", "TOR", team_id=10, fixture_source="NHL") is None


@pytest.mark.parametrize("url", [NBA_LOGO, NHL_LOGO, EURO_LOGO, CRICKET_LOGO, NAVi_LOGO])
def test_only_specific_reviewed_public_team_logo_paths_are_allowed(no_real_network, url):
    assert media.safe_participant_image_url(url) == url


@pytest.mark.parametrize("url", [
    NBA_LOGO.replace("/nba/", "/nhl/"), NBA_LOGO.replace("/500/", "/100/"), NBA_LOGO.replace("/2.png", "/02.png"),
    NHL_LOGO.replace("/nhl/", "/players/"), NHL_LOGO.replace("TOR_light.svg", "TOR.svg"),
    NHL_LOGO.replace("TOR_light.svg", "TOR_dark.svg"), NHL_LOGO.replace("nhle.com", "nhle.com.evil.test"),
    EURO_LOGO.replace("positive_", "negative_"), EURO_LOGO.replace(".png", ".svg"),
    CRICKET_LOGO.replace("152x152", "420x420"), CRICKET_LOGO.replace("c172115", "c0172115"),
    NAVi_LOGO.replace("58234", "58235"), "https://img.navi.gg/unreviewed.png", "https://assets.nhle.com/logo.svg",
    "https://img.navi.gg/teams/2026/09/teams-2561/thumbnail/64186/conversions/dota2_46x46-webp.webp",
])
def test_foreign_unreviewed_originals_or_oversized_team_urls_are_rejected(no_real_network, url):
    assert media.safe_participant_image_url(url) is None


@pytest.mark.parametrize("kind,url", [
    ("football", NBA_LOGO), ("football", NHL_LOGO), ("tennis", NBA_LOGO), ("tennis", NHL_LOGO),
    ("basketball", NHL_LOGO), ("ice_hockey", NBA_LOGO), ("cricket", NHL_LOGO), ("esports", NBA_LOGO),
])
def test_valid_team_url_cannot_be_rendered_in_a_foreign_sport_slot(no_real_network, kind, url):
    assert not media.participant_image_url_matches_kind(kind, url)


def test_all_actual_reviewed_team_entries_resolve_offline_with_identity_and_credit(no_real_network, monkeypatch):
    monkeypatch.setattr(media, '_TEAM_MANIFEST_PATH', Path(__file__).resolve().parents[1] / 'assets' / 'identity' / 'team-logos.json')
    manifest = json.loads(media._TEAM_MANIFEST_PATH.read_text(encoding='utf-8'))
    assert len(manifest['entries']) == 47
    for row in manifest['entries']:
        for name in row['names']:
            image = media.participant_image(row['sport'], name,
                team_id=row['team_id'], fixture_source=row['provider'])
            assert image is not None, (row['sport'], row['team_id'], name)
            assert image.image_url == row['url']
            assert image.credit == row.get('credit')
            assert media.participant_image_url_matches_kind(row['sport'], image.image_url)


def test_dota_game_icon_is_not_granted_as_1win_team_logo(no_real_network, monkeypatch):
    import participant_logo_catalog
    monkeypatch.setattr(participant_logo_catalog, 'resolve_pandascore_logo', Mock(return_value=None))
    assert media.participant_image('esports', '1win', team_id=134536,
                                   fixture_source='pandascore') is None
    assert media.safe_participant_image_url(
        'https://img.navi.gg/teams/2026/09/teams-2561/thumbnail/64186/conversions/dota2_46x46-webp.webp') is None
