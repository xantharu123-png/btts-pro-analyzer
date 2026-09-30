"""Synthetic optional UI metadata, no provider requests or image downloads."""

from copy import deepcopy
from datetime import datetime, timezone
import json
from types import SimpleNamespace

import pytest

import participant_logo_catalog as catalog


def opponent(team_id=125063, name="Sengoku Gaming", file="sengoku-gaming-gnat0l9c.png"):
    return {"id": team_id, "name": name,
            "image_url": f"https://cdn.pandascore.co/images/team/image/{team_id}/{file}"}


def test_stores_only_bounded_metadata_and_resolves_exact_native_identity(tmp_path):
    path = tmp_path / "logos.json"
    raw = opponent()
    raw["secret"] = "must-not-be-copied"
    before = deepcopy(raw)
    assert catalog.remember_pandascore_logos([raw], path=path)
    assert raw == before
    url = catalog.resolve_pandascore_logo(125063, "Sengoku Gaming", path=path)
    assert url.endswith("/thumb_sengoku-gaming-gnat0l9c.png")
    assert catalog.resolve_pandascore_logo("125063", "Sengoku Gaming", path=path) == url
    assert catalog.resolve_pandascore_logo(125063, "sengoku gaming", path=path) is None
    assert catalog.resolve_pandascore_logo(125064, "Sengoku Gaming", path=path) is None
    assert catalog.resolve_pandascore_logo(125063, "Sengoku", path=path) is None
    assert "must-not-be-copied" not in path.read_text()
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("file", ["thumb_team.png", "team.jpg", "team.jpeg", "team.webp"])
def test_supported_small_thumbnail_variant_is_not_double_prefixed(tmp_path, file):
    path = tmp_path / "logos.json"
    assert catalog.remember_pandascore_logos([opponent(file=file)], path=path)
    expected = file if file.startswith("thumb_") else "thumb_" + file
    assert catalog.resolve_pandascore_logo(125063, "Sengoku Gaming", path=path).endswith("/" + expected)


@pytest.mark.parametrize("url", [
    "http://cdn.pandascore.co/images/team/image/125063/team.png",
    "https://evil.example/images/team/image/125063/team.png",
    "https://cdn.pandascore.co.evil.example/images/team/image/125063/team.png",
    "https://user@cdn.pandascore.co/images/team/image/125063/team.png",
    "https://cdn.pandascore.co:443/images/team/image/125063/team.png",
    "https://cdn.pandascore.co/images/team/image/125063/team.png?key=secret",
    "https://cdn.pandascore.co/images/team/image/125063/team.png#fragment",
    "https://cdn.pandascore.co/images/team/image/125064/team.png",
    "https://cdn.pandascore.co/images/player/image/125063/team.png",
    "https://cdn.pandascore.co/images/team/image/125063/team.svg",
    "https://cdn.pandascore.co/images/team/image/125063/../team.png",
    "https://cdn.pandascore.co/images/team/image/125063/%2e%2e-team.png",
    "https://cdn.pandascore.co/images/team/image/125063/normal_team.png",
    "https://cdn.pandascore.co/images/team/image/125063/team\n.png",
    "\x00https://cdn.pandascore.co/images/team/image/125063/team.png",
    "data:image/png;base64,aGVsbG8=",
])
def test_invalid_or_misbound_source_never_persists(tmp_path, url):
    path = tmp_path / "logos.json"
    raw = opponent()
    raw["image_url"] = url
    assert not catalog.remember_pandascore_logos([raw], path=path)
    assert not path.exists()


@pytest.mark.parametrize("team_id", [True, False, 0, -1, 1.5, None, [], "1.0", "0125063", 2**63])
def test_invalid_identity_ids_are_not_saved_or_resolved(tmp_path, team_id):
    path = tmp_path / "logos.json"
    raw = opponent()
    raw["id"] = team_id
    assert not catalog.remember_pandascore_logos([raw], path=path)
    assert catalog.resolve_pandascore_logo(team_id, "Sengoku Gaming", path=path) is None


@pytest.mark.parametrize("name", [None, False, "", " \t ", "Team\x00Name", "Team\u202eName", "n" * 161])
def test_invalid_identity_names_do_not_persist(tmp_path, name):
    raw = opponent()
    raw["name"] = name
    assert not catalog.remember_pandascore_logos([raw], path=tmp_path / "logos.json")


def test_repeat_scan_deduplicates_without_file_rewrite(tmp_path, monkeypatch):
    path = tmp_path / "logos.json"
    raw = opponent()
    assert catalog.remember_pandascore_logos([raw, raw], path=path)
    before = path.read_bytes(), path.stat().st_mtime_ns
    monkeypatch.setattr(catalog, "atomic_write_text", lambda *a, **k: pytest.fail("duplicate batch rewritten"))
    assert catalog.remember_pandascore_logos([raw], path=path)
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before


def test_conflicting_provider_identity_in_same_batch_is_not_guessed(tmp_path):
    path = tmp_path / "logos.json"
    assert not catalog.remember_pandascore_logos([opponent(), opponent(name="Another Team")], path=path)
    assert not path.exists()


def test_catalog_count_and_utf8_byte_limits_are_enforced(tmp_path):
    path = tmp_path / "logos.json"
    raws = [opponent(i, "Sport " + "界" * 154, "x" * 170 + ".png") for i in range(1, 800)]
    assert catalog.remember_pandascore_logos(raws, path=path)
    data = json.loads(path.read_bytes())
    assert len(data["teams"]) <= 256
    assert path.stat().st_size <= 128 * 1024
    assert data["teams"][-1]["id"] == 799
    assert catalog.resolve_pandascore_logo(799, "Sport " + "界" * 154, path=path)


@pytest.mark.parametrize("payload", [b"not json", b"[]", b"{}", b"\xff",
    b'{"schema":"participant-logos-v1","schema":"participant-logos-v1","source":"pandascore","teams":[]}',
    b'{"schema":"participant-logos-v1","source":"pandascore","teams":[{}]}',
    b"x" * (128 * 1024 + 1),
], ids=["not-json", "array", "empty", "invalid-utf8", "duplicate-key", "missing-row-fields", "oversized"])
def test_malformed_catalog_fails_closed_without_overwrite(tmp_path, payload):
    path = tmp_path / "logos.json"
    path.write_bytes(payload)
    assert catalog.resolve_pandascore_logo(125063, "Sengoku Gaming", path=path) is None
    assert not catalog.remember_pandascore_logos([opponent()], path=path)
    assert path.read_bytes() == payload


def test_valid_catalog_rejects_duplicate_ids_and_extra_fields(tmp_path):
    path = tmp_path / "logos.json"
    assert catalog.remember_pandascore_logos([opponent()], path=path)
    data = json.loads(path.read_text())
    row = deepcopy(data["teams"][0])
    data["teams"].append(row)
    path.write_text(json.dumps(data))
    assert catalog.resolve_pandascore_logo(125063, "Sengoku Gaming", path=path) is None
    data["teams"] = [row]
    row["provider_secret"] = "forbidden"
    path.write_text(json.dumps(data))
    assert catalog.resolve_pandascore_logo(125063, "Sengoku Gaming", path=path) is None


def test_optional_write_failure_does_not_escape(tmp_path, monkeypatch):
    monkeypatch.setattr(catalog, "atomic_write_text", lambda *a, **k: (_ for _ in ()).throw(OSError("read-only")))
    assert not catalog.remember_pandascore_logos([opponent()], path=tmp_path / "logos.json")


def test_missing_catalog_returns_none_without_creating_state(tmp_path):
    path = tmp_path / "missing" / "logos.json"
    assert catalog.resolve_pandascore_logo(125063, "Sengoku Gaming", path=path) is None
    assert not path.parent.exists()


def test_atomic_writer_rejects_leaf_and_parent_symlinks(tmp_path):
    target = tmp_path / "real.json"
    assert catalog.remember_pandascore_logos([opponent()], path=target)
    link = tmp_path / "link.json"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Symlink creation is unavailable on this Windows account")
    before = target.read_bytes()
    assert catalog.resolve_pandascore_logo(125063, "Sengoku Gaming", path=link) is None
    assert not catalog.remember_pandascore_logos([opponent(2, "Other Team")], path=link)
    assert target.read_bytes() == before
    directory = tmp_path / "folder"
    directory.mkdir()
    parent_link = tmp_path / "folder-link"
    parent_link.symlink_to(directory, target_is_directory=True)
    assert not catalog.remember_pandascore_logos([opponent()], path=parent_link / "logos.json")
    assert not (directory / "logos.json").exists()


def test_functions_perform_no_network_or_image_download(tmp_path, monkeypatch):
    import requests
    import socket
    monkeypatch.setattr(requests, "get", lambda *a, **k: pytest.fail("HTTP requested"))
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("socket opened"))
    path = tmp_path / "logos.json"
    assert catalog.remember_pandascore_logos([opponent()], path=path)
    assert catalog.resolve_pandascore_logo(125063, "Sengoku Gaming", path=path)


def _scanner():
    from scanners.esports_scanner import EsportsScanner
    scanner = EsportsScanner.__new__(EsportsScanner)
    scanner.errors = {}
    scanner.headers = {}
    scanner.pandascore_base = "https://api.pandascore.co"
    return scanner


def test_scanner_harvests_successful_scoped_opponents_once_and_leaves_matches_unchanged(monkeypatch):
    import scanners.esports_scanner as provider
    scanner = _scanner()
    raw = [
        {"id": 1, "opponents": [{"opponent": opponent()}, {"opponent": opponent(2, "Other Team")} ]},
        {"id": 2, "opponents": [{"opponent": opponent(3, "Rejected Team")} ]},
    ]
    original = deepcopy(raw)
    formatted = {"id": 1, "probability": .65, "analysis_hash": "untouched"}
    requests_seen, batches = [], []
    def get(*args, **kwargs):
        requests_seen.append((args, kwargs))
        return SimpleNamespace(status_code=200, json=lambda: raw)
    monkeypatch.setattr(provider.requests, "get", get)
    monkeypatch.setattr(scanner, "_format_match", lambda match, *a, **k: formatted if match["id"] == 1 else None)
    monkeypatch.setattr(catalog, "remember_pandascore_logos", lambda values: batches.append(deepcopy(values)))
    result = scanner._fetch_endpoint("csgo", "CS2", "upcoming", "upcoming", "cs2")
    assert result == [formatted] and result[0] is formatted
    assert raw == original
    assert len(requests_seen) == 1
    assert batches == [[raw[0]["opponents"][0]["opponent"], raw[0]["opponents"][1]["opponent"]]]


def test_scanner_optional_catalog_failure_cannot_fail_model_result(monkeypatch):
    import scanners.esports_scanner as provider
    scanner = _scanner()
    raw = {"id": 1, "opponents": [{"opponent": opponent()}]}
    formatted = {"id": 1, "model": "unchanged"}
    monkeypatch.setattr(provider.requests, "get", lambda *a, **k: SimpleNamespace(status_code=200, json=lambda: [raw]))
    monkeypatch.setattr(scanner, "_format_match", lambda *a, **k: formatted)
    monkeypatch.setattr(catalog, "remember_pandascore_logos", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("optional metadata")))
    assert scanner._fetch_endpoint("csgo", "CS2", "upcoming", "upcoming", "cs2") == [formatted]


def test_scanner_catalog_does_not_harvest_unselected_window_or_history(monkeypatch):
    import scanners.esports_scanner as provider
    scanner = _scanner()
    raw = [
        {"id": 1, "begin_at": "2026-09-30T12:00:00Z", "opponents": [{"opponent": opponent()}]},
        {"id": 2, "begin_at": "2026-10-01T12:00:00Z", "opponents": [{"opponent": opponent(2, "Outside Team")}]},
    ]
    monkeypatch.setattr(provider.requests, "get", lambda *a, **k: SimpleNamespace(status_code=200, json=lambda: raw))
    formatted_ids, batches = [], []
    def format_match(match, *args, **kwargs):
        formatted_ids.append(match["id"])
        return {"id": match["id"], "team1_history": [{"opponents": [opponent(3, "Historical Team")]}]}
    monkeypatch.setattr(scanner, "_format_match", format_match)
    monkeypatch.setattr(catalog, "remember_pandascore_logos", lambda values: batches.append(deepcopy(values)))
    result = scanner._fetch_endpoint(
        "csgo", "CS2", "upcoming", "upcoming", "cs2",
        window=(datetime(2026, 9, 30, tzinfo=timezone.utc), datetime(2026, 10, 1, tzinfo=timezone.utc)),
    )
    assert formatted_ids == [1]
    assert result[0]["team1_history"] == [{"opponents": [opponent(3, "Historical Team")]}]
    assert batches == [[raw[0]["opponents"][0]["opponent"]]]
