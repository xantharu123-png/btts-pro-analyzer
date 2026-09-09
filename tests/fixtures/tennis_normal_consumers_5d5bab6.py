"""Exact pre-consumer functions from 5d5bab6; test-only with owning globals."""

def _tennis_context_summary(row):
    try:
        data = json.loads(row.get("context_json") or "{}")
    except (TypeError, ValueError):
        data = {}
    facts = []
    for side, name in (("a", row.get("player_a")), ("b", row.get("player_b"))):
        player = data.get("players", {}).get(side, {}) if isinstance(data, dict) else {}
        for fact in player.get("facts", ()) if isinstance(player, dict) else ():
            if isinstance(fact, str):
                facts.append(f"{name}: {fact}")
    return " · ".join([*facts[:2], "Belag modelliert; akute Fitness-/Belastungseffekte noch nicht numerisch validiert."])


def _tennis_model_clock(row):
    value = row.get("created_utc")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return datetime.fromtimestamp(value, timezone.utc).isoformat()
    return None


def tennis_signals(
    db_path: Union[str, Path] = TENNIS_DB,
    today: Optional[str] = None,
    now: Optional[datetime] = None,
) -> List[ModelSignal]:
    """Return open tennis Shadow signals from the current price policy."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    today = today or current.astimezone(ZURICH_TZ).date().isoformat()
    rows = [row for row in _latest_tennis_rows(db_path, today, current)
            if row.get("verdict") == "WETTE" and row.get("recommended_side") in {"A", "B"}]
    signals: List[ModelSignal] = []
    for row in rows:
        scheduled = _parse_iso(row["scheduled_start_utc"])
        if scheduled is None:
            continue
        if scheduled.tzinfo is None:
            scheduled = scheduled.replace(tzinfo=timezone.utc)
        if scheduled.astimezone(timezone.utc) <= current:
            continue
        if not _valid_probability(row["p_cal"]):
            continue
        p_a = float(row["p_cal"])
        detail = (
            f"Tennis-Shadow · {row['tour']} · {row['tournament']} · "
            f"{row['match_date']} · Policy {TENNIS_POLICY_VERSION}"
        )
        side = row["recommended_side"]
        player = row["player_a"] if side == "A" else row["player_b"]
        probability = p_a if side == "A" else 1.0 - p_a
        minimum_odds = _minimum_odds(
            probability,
            WINNER_PROBABILITY_HAIRCUT,
        )
        if minimum_odds is None:
            continue
        signals.append(
            ModelSignal(
                key=f"tennis-{row['id']}-{side}",
                label=(
                    f"🎾 {row['player_a']} vs {row['player_b']} · "
                    f"Sieg {player}"
                ),
                probability=probability,
                probability_haircut=WINNER_PROBABILITY_HAIRCUT,
                evidence_stage="SHADOW",
                policy_version=TENNIS_POLICY_VERSION,
                detail=detail,
                scheduled_start=scheduled.astimezone(timezone.utc).isoformat(),
                minimum_odds=minimum_odds,
                source="tennis_shadow",
                fixture_source=row.get("fixture_source"),
                provider_event_id=row.get("provider_event_id"),
                context_evidence=json.loads(row.get("context_json") or "{}"),
                modeled_at=_tennis_model_clock(row),
                input_cutoff_at=_tennis_model_clock(row),
                model_version=TENNIS_MODEL_VERSION,
                context_summary=_tennis_context_summary(row),
                sport="Tennis",
                event_label=f"{row['player_a']} vs {row['player_b']}",
                market="Match Winner",
                selection=f"Sieg {player}",
                market_key="H2H",
                competitor_a=str(row["player_a"]),
                competitor_b=str(row["player_b"]),
                selected_competitor=str(player),
                competition=f"{row['tour']} {row['tournament']}",
            )
        )
    return signals


def tennis_model_signals(
    db_path: Union[str, Path] = TENNIS_DB,
    today: Optional[str] = None,
    now: Optional[datetime] = None,
) -> List[ModelSignal]:
    """Return one local match day's tennis candidates with all model gates green."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    today = today or current.astimezone(ZURICH_TZ).date().isoformat()
    rows = _latest_tennis_rows(db_path, today, current)
    signals: List[ModelSignal] = []
    for row in rows:
        scheduled = _parse_iso(row["scheduled_start_utc"])
        if scheduled is None or scheduled.tzinfo is None:
            continue
        scheduled = scheduled.astimezone(timezone.utc)
        if scheduled <= current or not _valid_probability(row["p_cal"]):
            continue
        try:
            gates = json.loads(row["gates_json"])
        except (TypeError, ValueError):
            continue
        if not isinstance(gates, dict) or not gates:
            continue
        model_gates = {
            name: gate
            for name, gate in gates.items()
            if name != "Quote/Risiko-EV"
        }
        if (
            not model_gates
            or any(
                not isinstance(gate, dict) or gate.get("passed") is not True
                for gate in model_gates.values()
            )
        ):
            continue
        p_a = float(row["p_cal"])
        side = "A" if p_a > 0.5 else "B" if p_a < 0.5 else None
        if side is None:
            continue
        player = row["player_a"] if side == "A" else row["player_b"]
        probability = p_a if side == "A" else 1.0 - p_a
        minimum_odds = _minimum_odds(
            probability,
            WINNER_PROBABILITY_HAIRCUT,
        )
        if minimum_odds is None:
            continue
        signals.append(
            ModelSignal(
                key=f"tennis-model-{row['id']}-{side}",
                label=(
                    f"🎾 {row['player_a']} vs {row['player_b']} · "
                    f"Sieg {player}"
                ),
                probability=probability,
                probability_haircut=WINNER_PROBABILITY_HAIRCUT,
                evidence_stage="SHADOW",
                policy_version=TENNIS_POLICY_VERSION,
                detail=(
                    f"Tennis-Modell quotenfrei · {row['tour']} · "
                    f"{row['tournament']} · {row['match_date']}"
                ),
                scheduled_start=scheduled.isoformat(),
                minimum_odds=minimum_odds,
                source="tennis_model",
                fixture_source=row.get("fixture_source"),
                provider_event_id=row.get("provider_event_id"),
                context_evidence=json.loads(row.get("context_json") or "{}"),
                modeled_at=_tennis_model_clock(row),
                input_cutoff_at=_tennis_model_clock(row),
                model_version=TENNIS_MODEL_VERSION,
                context_summary=_tennis_context_summary(row),
                sport="Tennis",
                event_label=f"{row['player_a']} vs {row['player_b']}",
                market="Match Winner",
                selection=f"Sieg {player}",
                market_key="H2H",
                competitor_a=str(row["player_a"]),
                competitor_b=str(row["player_b"]),
                selected_competitor=str(player),
                competition=f"{row['tour']} {row['tournament']}",
            )
        )
    return signals
