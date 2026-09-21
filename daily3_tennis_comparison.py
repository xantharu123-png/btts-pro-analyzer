"""Same-match surface ablation from the actually used, immutable tennis state.

This is selection evidence, not three independent models or an injury effect.
The producer is the native prediction worker; readers never fit or fetch data.
"""
from collections.abc import Mapping
from datetime import datetime
import math

SCHEMA = "tennis-same-match-surface-comparison-v1"


def build_tennis_comparison(state, origin, prediction):
    from context_models.tennis_live import original_base
    from tennis.backtest import MIN_ELO_MATCHES

    base = original_base(origin)
    inputs, event = origin["inputs"], origin["event"]
    a, b, surface = inputs["state_key_a"], inputs["state_key_b"], inputs["surface"]
    gates = [g for g in prediction.gates if g.name != "Quote/Risiko-EV"]
    table = state.elo.by_surface.get(surface)
    # WTA and unqualified legacy states must not acquire an implicit release.
    if (inputs["tour"] != "ATP" or state.tour_scope != "ATP"
            or state.artifact_hash != base["model_hash"]
            or {g.name for g in gates} != {'Belag', 'Erfahrung', 'Aufschlag-Daten', 'Spieler-Zuordnung'}
            or any(g.passed is not True for g in gates)
            or table is None or min(table.matches(a), table.matches(b)) < 8
            or min(state.elo.overall.matches(a), state.elo.overall.matches(b)) < MIN_ELO_MATCHES
            or type(state.cal_samples) is not int or state.cal_samples < 200):
        return None
    # Preserve the SAME serve weight, best-of, calibration and decision time.
    # Removing serve as well as surface would mislabel a serve advantage as a
    # surface effect. Third variant is the surface-Elo sensitivity comparison.
    from tennis.predict import predict_match
    captured = []
    predict_match(state, inputs['player_a'], inputs['player_b'], surface=None,
        best_of=inputs['best_of'], tour='ATP', indoor=inputs['indoor'],
        as_of=datetime.fromisoformat(base['cutoff']), workload_history=(), original_capture=captured.append)
    overall = captured[0]['values']['p_a_cal']
    surface_p = state.calibrate_match(state.elo.win_probability(a, b, surface), a, b, tour="ATP")
    return {
        "schema": SCHEMA, "event_key": event["event_key"],
        "scheduled_start": event["scheduled_start"], "modeled_at": base["cutoff"],
        "model_hash": base["model_hash"], "player_a": inputs["player_a"],
        "player_b": inputs["player_b"], "surface": surface, "tour": "ATP",
        "market_key": "H2H", "model_gates_passed": True,
        "overall_matches": [state.elo.overall.matches(a), state.elo.overall.matches(b)],
        "surface_matches": [table.matches(a), table.matches(b)],
        "probabilities_a": [origin["values"]["p_a_cal"], overall, surface_p],
    }


def tennis_surface_comparison(signal, *, now, minimum_probability):
    from daily3_comparison import Comparison, MIN_FORM_CHANGE, _clock, _number
    from forecast_analysis import _tennis_inputs, _tennis_data_age
    if str(signal.sport or "").casefold() != "tennis" or signal.market_key != "H2H":
        return None
    context = signal.context_evidence
    if not isinstance(context, Mapping):
        return None
    raw = context.get("daily3_comparison")
    if not isinstance(raw, Mapping) or raw.get("schema") != SCHEMA:
        return None
    inputs = _tennis_inputs(signal)
    if not inputs or not _tennis_data_age(inputs, now)[1]:
        return None
    from context_models.tennis_live import validate_context_model
    from context_models.contracts import ContextContractError
    try:
        link = validate_context_model(context.get('context_model'))
    except (ContextContractError, TypeError, KeyError):
        return None
    event = link["event"]
    model_hash = raw.get("model_hash")
    if (signal.fixture_source != "ESPN" or not signal.provider_event_id
            or raw.get("event_key") != f"espn:tennis:ATP:match:{signal.provider_event_id}"
            or event.get("event_key") != raw.get("event_key") or event.get("tour") != "ATP"
            or raw.get("tour") != "ATP" or raw.get("market_key") != "H2H"
            or raw.get("model_gates_passed") is not True
            or raw.get("player_a") != signal.competitor_a or raw.get("player_b") != signal.competitor_b
            or not signal.competitor_a or signal.competitor_a == signal.competitor_b
            or raw.get("surface") not in ("Hard", "Clay", "Grass", "Carpet")
            or raw.get("surface") != inputs.get("surface") or inputs.get("surface_in_model") is not True
            or inputs.get("model_tour_scope") != "ATP"
            or not isinstance(model_hash, str) or len(model_hash) != 64
            or any(c not in "0123456789abcdef" for c in model_hash)
            or model_hash != inputs.get("model_artifact_hash")):
        return None
    decision, start = _clock(raw.get("modeled_at")), _clock(raw.get("scheduled_start"))
    if (decision is None or start is None or not decision <= now < start
            or decision != _clock(signal.modeled_at) or decision != _clock(signal.input_cutoff_at)
            or decision != _clock(link.get("cutoff"))
            or start != _clock(signal.scheduled_start) or start != _clock(event.get("scheduled_start"))):
        return None
    from tennis.backtest import MIN_ELO_MATCHES
    for key, floor in (("overall_matches", MIN_ELO_MATCHES), ("surface_matches", 8)):
        counts = raw.get(key)
        if not isinstance(counts, (list, tuple)) or len(counts) != 2 or any(type(n) is not int or n < floor for n in counts):
            return None
    values = raw.get("probabilities_a")
    if not isinstance(values, (tuple, list)) or len(values) != 3 or any(not _number(p) or not 0 < p < 1 for p in values):
        return None
    if signal.selected_competitor == signal.competitor_a:
        active, overall, surface = values
    elif signal.selected_competitor == signal.competitor_b:
        active, overall, surface = (1-p for p in values)
    else:
        return None
    # Shared context probabilities may eventually differ from this original.
    # Such a revision needs its own comparison, never this old ablation.
    if not _number(signal.probability) or not math.isclose(active, signal.probability, rel_tol=0, abs_tol=1e-12):
        return None
    floor, margin = min(active, overall, surface), round(min(active, surface)-overall, 12)
    if floor < minimum_probability or margin < MIN_FORM_CHANGE-1e-12:
        return None
    return Comparison(margin, floor, overall, min(raw["surface_matches"]), overall, active, "Belagsignal")
