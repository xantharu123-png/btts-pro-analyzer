from tennis.surface_evidence import format_surface_evidence


def test_surface_evidence_shows_real_sample_and_actual_model_use():
    evidence = {
        "surface": "Hard",
        "players": {
            "a": {"matches": 23, "elo": 1634.2},
            "b": {"matches": 19, "elo": 1490.8},
        },
        "surface_elo_applied": True,
        "stats_through": "2026-09-23",
    }
    text = format_surface_evidence(evidence, "Spieler A", "Spieler B")
    assert text == (
        "Hartplatz: Spieler A 1.634 Elo (23 Spiele) · "
        "Spieler B 1.491 Elo (19 Spiele) · "
        "Belag-Elo berücksichtigt · Daten bis 23.09.2026"
    )


def test_surface_evidence_marks_too_small_sample_without_default_rating():
    evidence = {
        "surface": "Clay",
        "players": {
            "a": {"matches": 0, "elo": None},
            "b": {"matches": 7, "elo": 1458.2},
        },
        "surface_elo_applied": False,
    }
    text = format_surface_evidence(evidence, "A", "B")
    assert "A keine Belagspiele" in text
    assert "Gesamt-Elo verwendet" in text
    assert "1.500" not in text


def test_malformed_or_claimed_surface_use_is_not_displayed():
    evidence = {
        "surface": "Hard",
        "players": {
            "a": {"matches": 7, "elo": 1600.0},
            "b": {"matches": 9, "elo": 1400.0},
        },
        "surface_elo_applied": True,
    }
    assert format_surface_evidence(evidence, "A", "B") is None
    evidence["players"]["a"]["matches"] = True
    assert format_surface_evidence(evidence, "A", "B") is None
    assert format_surface_evidence({}, "A", "B") is None
    assert format_surface_evidence(evidence, "A" * 121, "B") is None
    evidence["surface"] = []
    assert format_surface_evidence(evidence, "A", "B") is None
