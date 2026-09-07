from __future__ import annotations

import importlib.util
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pandas as pd
import pytest

import runtime_paths
from tennis import data_loader


TOURNAMENTS = (
    b"id,name,year,indoor_outdoor,surface,series_category_id,start_dtm\n"
    b"2026-1,Test Open,2026,Outdoor,Hard,atp_250,20260901\n"
)
OLD_MATCHES = b"id,tournament_id,winner_name,loser_name\n1,2026-1,Old Player,Other Player\n"
NEW_MATCHES = b"id,tournament_id,winner_name,loser_name\n2,2026-1,New Player,Other Player\n"


def _xlsx(winner="Seed Woman"):
    output = BytesIO()
    pd.DataFrame([{"Date": "2026-09-01", "Winner": winner, "Loser": "Other Woman", "Surface": "Hard"}]).to_excel(output, index=False)
    return output.getvalue()


@pytest.fixture
def isolated_loader(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime_state" / "tennis" / "training_data"
    seed = tmp_path / "packaged" / "tennis" / "data"
    seed.mkdir(parents=True)
    monkeypatch.setattr(runtime_paths, "TENNIS_TRAINING_DATA_DIR", runtime, raising=False)
    monkeypatch.setattr(runtime_paths, "PACKAGED_TENNIS_TRAINING_DATA_DIR", seed, raising=False)
    spec = importlib.util.spec_from_file_location("training_cache_test_loader", data_loader.__file__)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # The explicit canonical destination also exercises default-seed matching
    # without allowing the RED implementation to write the real checkout.
    monkeypatch.setattr(module, "DEFAULT_CACHE_DIR", runtime)
    monkeypatch.setattr(module.requests, "get", lambda *_a, **_k: pytest.fail("unexpected HTTP request"))
    return module, runtime, seed


def _seed_atp(seed):
    (seed / "atp_tournaments.csv").write_bytes(TOURNAMENTS)
    (seed / "atp_matches_2026.csv").write_bytes(OLD_MATCHES)


def test_missing_default_cache_seeds_atp_without_http(isolated_loader):
    module, runtime, seed = isolated_loader
    _seed_atp(seed)
    rows = module.load_atp_stats((2026,), cache_dir=runtime)
    assert rows["winner_name"].tolist() == ["Old Player"]
    assert (runtime / "atp_tournaments.csv").read_bytes() == TOURNAMENTS
    assert (runtime / "atp_matches_2026.csv").read_bytes() == OLD_MATCHES
    assert (seed / "atp_matches_2026.csv").read_bytes() == OLD_MATCHES


def test_refresh_changes_only_mutable_cache_and_uses_seed_baseline(isolated_loader, monkeypatch):
    module, runtime, seed = isolated_loader
    _seed_atp(seed)
    monkeypatch.setattr(module.requests, "get", lambda url, **_: SimpleNamespace(
        content=TOURNAMENTS if url.endswith("tournaments.csv") else NEW_MATCHES,
        raise_for_status=lambda: None,
    ))
    rows = module.load_atp_stats((2026,), cache_dir=runtime, refresh_current=True, current_year=2026)
    assert rows["winner_name"].tolist() == ["New Player"]
    assert (runtime / "atp_matches_2026.csv").read_bytes() == NEW_MATCHES
    assert (seed / "atp_tournaments.csv").read_bytes() == TOURNAMENTS
    assert (seed / "atp_matches_2026.csv").read_bytes() == OLD_MATCHES


def test_seeded_completed_history_is_checked_before_metadata_refresh(isolated_loader, monkeypatch):
    module, runtime, seed = isolated_loader
    _seed_atp(seed)
    removed = TOURNAMENTS.replace(b"2026-1,Test", b"2026-2,Replacement")
    monkeypatch.setattr(module.requests, "get", lambda *_a, **_k: SimpleNamespace(
        content=removed, raise_for_status=lambda: None,
    ))
    with pytest.raises(ValueError):
        module.load_atp_stats((2026,), cache_dir=runtime, refresh_current=True, current_year=2026)
    assert (runtime / "atp_tournaments.csv").read_bytes() == TOURNAMENTS
    assert (runtime / "atp_matches_2026.csv").read_bytes() == OLD_MATCHES


def test_existing_mutable_cache_is_never_overwritten_by_packaged_seed(isolated_loader):
    module, runtime, seed = isolated_loader
    _seed_atp(seed)
    runtime.mkdir(parents=True)
    (runtime / "atp_tournaments.csv").write_bytes(TOURNAMENTS)
    (runtime / "atp_matches_2026.csv").write_bytes(NEW_MATCHES)
    rows = module.load_atp_stats((2026,), cache_dir=runtime)
    assert rows["winner_name"].tolist() == ["New Player"]
    assert (runtime / "atp_matches_2026.csv").read_bytes() == NEW_MATCHES


def test_seed_publication_never_overwrites_a_concurrent_fresh_cache(isolated_loader, monkeypatch):
    module, runtime, seed = isolated_loader
    _seed_atp(seed)
    write = module.atomic_write_bytes
    def publish_with_competing_writer(path, payload, **kwargs):
        if path.name == "atp_matches_2026.csv":
            write(path, NEW_MATCHES)
        return write(path, payload, **kwargs)
    monkeypatch.setattr(module, "atomic_write_bytes", publish_with_competing_writer)
    rows = module.load_atp_stats((2026,), cache_dir=runtime)
    assert rows["winner_name"].tolist() == ["New Player"]
    assert (runtime / "atp_matches_2026.csv").read_bytes() == NEW_MATCHES
    assert (seed / "atp_matches_2026.csv").read_bytes() == OLD_MATCHES


def test_explicit_other_cache_never_imports_packaged_seed(isolated_loader, tmp_path, monkeypatch):
    module, runtime, seed = isolated_loader
    _seed_atp(seed)
    explicit = tmp_path / "isolated"
    monkeypatch.setattr(module.requests, "get", lambda url, **_: SimpleNamespace(
        content=TOURNAMENTS if url.endswith("tournaments.csv") else NEW_MATCHES,
        raise_for_status=lambda: None,
    ))
    rows = module.load_atp_stats((2026,), cache_dir=explicit)
    assert rows["winner_name"].tolist() == ["New Player"]
    assert (explicit / "atp_matches_2026.csv").read_bytes() == NEW_MATCHES
    assert not runtime.exists()


@pytest.mark.parametrize("tour", ["atp", "wta"])
def test_market_calibration_sources_seed_without_http(isolated_loader, tour):
    module, runtime, seed = isolated_loader
    payload = _xlsx()
    (seed / f"{tour}_odds_2026.xlsx").write_bytes(payload)
    rows = module.load_market_odds((2026,), tour=tour, cache_dir=runtime)
    assert rows["Winner"].tolist() == ["Seed Woman"]
    assert (runtime / f"{tour}_odds_2026.xlsx").read_bytes() == payload


def test_wta_refresh_preserves_packaged_workbook(isolated_loader, monkeypatch):
    module, runtime, seed = isolated_loader
    seed_payload = _xlsx()
    fresh_payload = _xlsx("Fresh Woman")
    (seed / "wta_odds_2026.xlsx").write_bytes(seed_payload)
    monkeypatch.setattr(module.requests, "get", lambda *_a, **_k: SimpleNamespace(
        content=fresh_payload, raise_for_status=lambda: None,
    ))
    rows = module.load_market_odds((2026,), tour="wta", cache_dir=runtime, refresh_current=True, current_year=2026)
    assert rows["Winner"].tolist() == ["Fresh Woman"]
    assert (runtime / "wta_odds_2026.xlsx").read_bytes() == fresh_payload
    assert (seed / "wta_odds_2026.xlsx").read_bytes() == seed_payload


def test_tennis_abstract_sources_seed_without_http(isolated_loader):
    module, runtime, seed = isolated_loader
    row = [0] * 45
    for index, value in {0: "20260901", 1: "Test", 2: "Hard", 3: "G", 4: "W", 5: "Seed Woman", 12: "Other Woman"}.items():
        row[index] = value
    payload = ("var matchmx = " + repr([row]) + ";").encode()
    for tag in ("wta_top50", "wta_51_100"):
        (seed / f"{tag}_leadersource.js").write_bytes(payload)
    rows = module.load_wta_ta_stats(cache_dir=runtime)
    assert rows["winner_name"].tolist() == ["Seed Woman"]
    assert (runtime / "wta_top50_leadersource.js").read_bytes() == payload


def test_daily_surface_lookup_reads_seed_with_cold_runtime_cache(isolated_loader, monkeypatch):
    from scripts import tennis_daily

    module, runtime, seed = isolated_loader
    tournaments = TOURNAMENTS.replace(b"start_dtm\n", b"start_dtm,location,slug\n").replace(
        b"20260901\n", b"20260901,Test City,test-open\n",
    )
    (seed / "atp_tournaments.csv").write_bytes(tournaments)
    monkeypatch.setattr(tennis_daily, "DEFAULT_CACHE_DIR", runtime)
    monkeypatch.setattr(tennis_daily, "cached_training_file", module.cached_training_file, raising=False)
    assert tennis_daily.tournament_surface_map(2026)["test open"] == ("Hard", 3, "Test Open", False)
    assert (runtime / "atp_tournaments.csv").read_bytes() == tournaments
    assert (seed / "atp_tournaments.csv").read_bytes() == tournaments


@pytest.mark.parametrize("kind", ["seed", "runtime_file", "runtime_parent"])
def test_default_seed_transfer_rejects_symlinks(isolated_loader, tmp_path, kind):
    module, runtime, seed = isolated_loader
    _seed_atp(seed)
    other = tmp_path / "other"
    other.mkdir()
    external = other / "atp_tournaments.csv"
    external.write_bytes(TOURNAMENTS)
    try:
        if kind == "seed":
            (seed / "atp_tournaments.csv").unlink()
            (seed / "atp_tournaments.csv").symlink_to(external)
        elif kind == "runtime_file":
            runtime.mkdir(parents=True)
            (runtime / "atp_tournaments.csv").symlink_to(external)
        else:
            runtime.parent.mkdir(parents=True)
            runtime.symlink_to(other, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    with pytest.raises(runtime_paths.RuntimeArtifactTrustError):
        module.load_atp_stats((2026,), cache_dir=runtime)
    assert external.read_bytes() == TOURNAMENTS


def test_configured_runtime_root_controls_omitted_default_cache(tmp_path):
    runtime_root = tmp_path / "custom-runtime"
    seed = tmp_path / "seed"
    seed.mkdir()
    _seed_atp(seed)
    script = """
import json
from pathlib import Path
import sys
import runtime_paths
runtime_paths.PACKAGED_TENNIS_TRAINING_DATA_DIR = Path(sys.argv[1])
from tennis import data_loader
expected = Path(sys.argv[2]) / 'tennis' / 'training_data'
assert data_loader.DEFAULT_CACHE_DIR == expected
data_loader.requests.get = lambda *a, **k: (_ for _ in ()).throw(AssertionError('unexpected HTTP'))
rows = data_loader.load_atp_stats((2026,))
assert rows['winner_name'].tolist() == ['Old Player']
assert (expected / 'atp_matches_2026.csv').is_file()
print(json.dumps({'winner': rows['winner_name'].tolist()}))
"""
    environment = dict(os.environ, BETBOY_RUNTIME_STATE_DIR=str(runtime_root), PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([sys.executable, "-c", script, str(seed), str(runtime_root)],
                            cwd=Path(data_loader.__file__).resolve().parents[1], env=environment,
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"winner": ["Old Player"]}
