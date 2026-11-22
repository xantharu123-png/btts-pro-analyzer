import pytest

from challenge_engine import MARKET_BY_KEY


def label(sport, key, selection, **kwargs):
    from editorial_rail_labels import rail_selection_label

    return rail_selection_label(sport=sport, market_key=key, selection=selection, **kwargs)


@pytest.mark.parametrize(("key", "expected"), [
    ("RESULT_HOME", "Sieg 1. FC Köln (90 Minuten)"),
    ("RESULT_AWAY", "Sieg Mainz 05 (90 Minuten)"),
    ("RESULT_DRAW", "Unentschieden (90 Minuten)"),
    ("DC_1X", "1. FC Köln oder Unentschieden (90 Minuten)"),
    ("DC_X2", "Mainz 05 oder Unentschieden (90 Minuten)"),
    ("DC_12", "Kein Unentschieden (90 Minuten)"),
    ("BTTS_YES", "Beide Teams treffen: Ja"),
    ("BTTS_NO", "Beide Teams treffen: Nein"),
    ("HOME_UNDER_2_5", "1. FC Köln: Unter 2,5 Tore"),
    ("AWAY_OVER_0_5", "Mainz 05: Über 0,5 Tore"),
    ("TOTAL_OVER_2_5", "Gesamttore im Spiel: Über 2,5"),
    ("TOTAL_RANGE_2_4", "Gesamttore im Spiel: 2–4 Tore"),
    ("AWAY_RANGE_2_4", "Mainz 05: 2–4 Tore"),
    ("CORNERS_UNDER_9_5", "Eckbälle im Spiel: Unter 9,5"),
    ("HOME_CORNERS_OVER_4_5", "1. FC Köln: Über 4,5 Eckbälle"),
    ("YELLOW_OVER_2_5", "Gelbe Karten im Spiel: Über 2,5"),
    ("AWAY_YELLOW_UNDER_1_5", "Mainz 05: Unter 1,5 gelbe Karten"),
    ("RESULT_TOTAL_1X_UNDER_3_5", "1. FC Köln verliert nicht und im Spiel fallen unter 3,5 Tore"),
    ("RESULT_TOTAL_X2_UNDER_3_5", "Mainz 05 verliert nicht und im Spiel fallen unter 3,5 Tore"),
    ("RESULT_TOTAL_12_OVER_1_5", "Kein Unentschieden und im Spiel fallen über 1,5 Tore"),
    ("MIXED_BTTS_OR_OVER_2_5", "Beide Teams treffen oder im Spiel fallen über 2,5 Tore"),
    ("MIXED_HOME_OR_OVER_2_5", "1. FC Köln gewinnt oder im Spiel fallen über 2,5 Tore"),
    ("MIXED_AWAY_OR_OVER_2_5", "Mainz 05 gewinnt oder im Spiel fallen über 2,5 Tore"),
])
def test_fussball_rail_explains_subject_relation_and_line(key, expected):
    spec = MARKET_BY_KEY[key]
    assert label("Fußball", key, spec.selection, home="1. FC Köln", away="Mainz 05",
                 market=spec.market) == expected


def test_every_published_football_line_has_its_unit_and_subject():
    team_units = {"team_total": "Tore", "team_range": "Tore", "team_yellow": "gelbe Karten",
                  "team_corners": "Eckbälle"}
    match_subjects = {"total": "Gesamttore im Spiel", "total_range": "Gesamttore im Spiel",
                      "corner_total": "Eckbälle im Spiel", "yellow_total": "Gelbe Karten im Spiel"}
    for key, spec in MARKET_BY_KEY.items():
        value = label("football", key, spec.selection, home="Club 1.2", away="Mainz 05")
        assert value not in {spec.selection, spec.selection.replace(".", ",")}, key
        if spec.threshold is not None:
            assert str(spec.threshold).replace(".", ",") in value, key
        if spec.kind in team_units:
            assert value.startswith("Club 1.2:" if spec.side.startswith("home") else "Mainz 05:"), key
            assert value.endswith(team_units[spec.kind]), key
        if spec.kind in match_subjects:
            assert value.startswith(match_subjects[spec.kind]), key


@pytest.mark.parametrize(("sport", "key", "selection", "expected"), [
    ("football", "AWAY_UNDER_2_5", "Unter 2.5", "Auswärtsteam: Unter 2,5 Tore"),
    ("football", "HOME_RANGE_1_3", "1-3 Tore", "Heimteam: 1–3 Tore"),
    ("Tennis", "H2H", "Sieg V. Golubic", "Sieg V. Golubic"),
    ("tennis", "H2H", "V. Golubic", "Sieg V. Golubic"),
    ("E-Sport", "H2H", "Sieg Team 1.2", "Seriensieg Team 1.2"),
    ("ice_hockey", "H2H", "SC Bern", "Sieg SC Bern (inkl. Verlängerung und Penaltyschießen)"),
    ("Basketball", "H2H", "Dallas", "Sieg Dallas (inkl. Verlängerung)"),
])
def test_archived_labels_do_not_need_a_market_caption(sport, key, selection, expected):
    assert label(sport, key, selection) == expected


@pytest.mark.parametrize(("sport", "key", "selection", "market", "expected"), [
    ("tennis", None, "Sieg J. Doe", "Match Winner", "Sieg J. Doe"),
    ("Eishockey", None, "ZSC", "Sieger inklusive Verlängerung und Penaltyschießen",
     "Sieg ZSC (inkl. Verlängerung und Penaltyschießen)"),
    ("Basketball", "H2H", "Bulls", "Sieger inklusive Overtime", "Sieg Bulls (inkl. Verlängerung)"),
    ("ice_hockey", "AWAY_OVER_0_5", "Über 0.5", "", "Über 0.5"),
    ("tennis", "unknown", "A. Player 1.2", "Sondermarkt", "Sondermarkt · A. Player 1.2"),
    ("football", "RESULT_HOME", "Auswärtssieg", "Endergebnis", "Endergebnis · Auswärtssieg"),
    ("football", "HOME_UNDER_2_5", "Unter 2.5", "Team 2 Gesamttore", "Team 2 Gesamttore · Unter 2.5"),
    ("football", "TOTAL_OVER_1_5", "Über 2.5", "Gesamttore", "Gesamttore · Über 2.5"),
    ("football", "DC_12", "", "", ""),
    ("ice_hockey", "H2H", "SC Bern", "Sieger nach 60 Minuten", "Sieger nach 60 Minuten · SC Bern"),
    ("cricket", "match_winner", "India", "Außenseiter gewinnt das Match", "Außenseiter gewinnt das Match · India"),
])
def test_uncertain_input_is_not_reinterpreted_or_localized(sport, key, selection, market, expected):
    assert label(sport, key, selection, market=market) == expected


@pytest.mark.parametrize(("sport", "key", "choice", "expected"), [
    ("football", "HOME_UNDER_2_5", "Unter 2.5", "Heimteam: Unter 2,5 Tore"),
    ("Eishockey", "H2H", "SC Bern", "Sieg SC Bern (inkl. Verlängerung und Penaltyschießen)"),
])
def test_generic_loader_caption_does_not_hide_the_bound_market(sport, key, choice, expected):
    assert label(sport, key, choice, market="Auswahl") == expected


def test_h2h_does_not_assign_a_third_name_a_win():
    assert label("E-Sport", "H2H", "Sieg C", market="Match Winner", home="A", away="B") == "Match Winner · Sieg C"


@pytest.mark.parametrize(("choice", "bound", "away", "expected"), [
    ("Sieg Spieler B", "Spieler A", "Spieler B", "Siegauswahl nicht eindeutig"),
    ("Spieler B", "Dritter Spieler", "Spieler B", "Siegauswahl nicht eindeutig"),
    ("Sieg Dritter Spieler", "Spieler A", "Spieler B", "Siegauswahl nicht eindeutig"),
    ("Sieg Spieler B", "Spieler B", "Spieler B", "Sieg Spieler B"),
    ("Sieg Spieler B", None, "Spieler B", "Sieg Spieler B"),
    ("Sieg Spieler B", "Spieler A", "", "Sieg Spieler B"),
])
def test_compare_h2h_display_with_separate_native_identity_only_given_both_sides(choice, bound, away, expected):
    assert label("tennis", "H2H", choice, home="Spieler A", away=away, selected_competitor=bound) == expected
