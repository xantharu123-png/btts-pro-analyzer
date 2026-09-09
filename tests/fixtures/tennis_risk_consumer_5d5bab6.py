"""Exact pre-consumer functions from 5d5bab6; test-only with owning globals."""

def adapt_tennis_shadow(
    db_path: str | Path,
    *,
    as_of: Optional[datetime] = None,
    window_end: Optional[datetime] = None,
    policy_version: str = RISKOBET_POLICY_VERSION,
) -> tuple[RiskAdapterResult, ...]:
    """Read causal, unsettled pre-match tennis model rows from shadow SQLite."""

    now = _parse_datetime(as_of or datetime.now(_UTC))
    end = _parse_datetime(window_end) if window_end is not None else None
    if now is None or (end is not None and end < now):
        raise ValueError("invalid tennis adapter time window")
    path = Path(db_path)
    if not path.is_file():
        return ()
    from tennis.shadow import latest_predictions
    rows = latest_predictions(path, pending_only=True, as_of=now)
    outputs: list[RiskAdapterResult] = []
    for row in rows:
        prediction_id = row["id"]
        if (
            not isinstance(prediction_id, int)
            or isinstance(prediction_id, bool)
            or prediction_id <= 0
        ):
            continue
        starts_at = _parse_datetime(row["scheduled_start_utc"])
        observed_at = _parse_datetime(row["created_utc"])
        if (
            starts_at is None
            or observed_at is None
            or observed_at > now
            or observed_at > starts_at
            or starts_at <= now
            or (end is not None and starts_at > end)
        ):
            continue
        p_a = _probability(row["p_cal"])
        player_a = _clean_text(row["player_a"])
        player_b = _clean_text(row["player_b"])
        if p_a is None or not player_a or not player_b or player_a.casefold() == player_b.casefold():
            continue
        p_b = 1.0 - p_a
        if math.isclose(p_a, p_b, abs_tol=1e-12):
            continue
        underdog_side = "home" if p_a < p_b else "away"
        underdog = player_a if underdog_side == "home" else player_b
        p_underdog = min(p_a, p_b)
        markets = _load_json_object(row["markets_json"])
        tournament = _clean_text(row["tournament"] if "tournament" in row.keys() else "")
        competition = tournament or _clean_text(row["tour"] if "tour" in row.keys() else "") or "Tennis"
        provider_id = _clean_text(
            row["provider_event_id"] if "provider_event_id" in row.keys() else ""
        ) or f"shadow-{row['id']}"
        provider = _clean_text(
            row["fixture_source"] if "fixture_source" in row.keys() else ""
        ) or "tennis-shadow"
        model_version = _clean_text(
            row["model_version"] if "model_version" in row.keys() else ""
        ) or TENNIS_FALLBACK_MODEL_VERSION
        event_key = stable_event_key("tennis", provider, provider_id)
        input_payload = {
            "prediction_id": prediction_id,
            "provider_event_id": provider_id,
            "created_utc": observed_at.isoformat(),
            "scheduled_start_utc": starts_at.isoformat(),
            "tour": _clean_text(row["tour"] if "tour" in row.keys() else ""),
            "tournament": tournament,
            "surface": _clean_text(row["surface"] if "surface" in row.keys() else ""),
            "best_of": row["best_of"] if "best_of" in row.keys() else None,
            "player_a": player_a,
            "player_b": player_b,
            "p_cal": p_a,
            "markets": _without_prices(markets),
            "gates": _without_prices(
                _load_json_object(row["gates_json"] if "gates_json" in row.keys() else None)
            ),
            "model_revision_id": row.get("model_revision_id"),
            "context": _without_prices(_load_json_object(row.get("context_json"))),
        }
        factor = _shadow_factor(
            key="tennis_calibrated_match_model",
            summary=(
                f"Kalibriertes Sieger-Modell plus Satzsimulation; Außenseiter {p_underdog:.1%}."
            ),
            source="tennis_shadow.predictions",
            observed_at=observed_at,
            imported_at=observed_at,
            starts_at=starts_at,
        )
        identity_factor = _shadow_identity_factor(
            key=f"tennis_prediction_id:{prediction_id}",
            summary=(
                f"Eingefrorene Tennis-Quellzeile {prediction_id}: "
                f"{player_a} vs {player_b}."
            ),
            source="tennis_shadow.predictions",
            observed_at=observed_at,
            imported_at=observed_at,
            starts_at=starts_at,
        )
        workload = _load_json_object(row.get("context_json"))
        workload_players = workload.get("players", {})
        workload_factors = []
        if isinstance(workload_players, Mapping):
            for side, player_name in (("a", player_a), ("b", player_b)):
                data = workload_players.get(side, {})
                if not isinstance(data, Mapping):
                    continue
                for index, fact in enumerate(data.get("facts", ())):
                    if not isinstance(fact, str) or not fact.strip():
                        continue
                    workload_factors.append(FactorEvidence(
                        factor_key=f"tennis_workload_{side}_{index}",
                        summary=f"{player_name}: {fact}"[:600],
                        source="tennis-shadow-observed-results",
                        observed_at=observed_at, imported_at=observed_at,
                        fresh_until=starts_at, role=FactorRole.DISPLAY_ONLY,
                    ))
        snapshot = EventModelSnapshot(
            event_key=event_key,
            sport="tennis",
            competition=competition,
            event_label=f"{player_a} vs {player_b}",
            starts_at=starts_at,
            modeled_at=observed_at,
            input_cutoff_at=observed_at,
            model_version=model_version,
            input_hash=canonical_input_hash(input_payload),
            factors=(factor, identity_factor, *workload_factors),
        )
        options: list[tuple[float, str, str, float, float, str, str]] = []
        # (weighted score, market key, label, p, haircut, pro, con)
        over_25 = _probability(markets.get("over_2_5_sets"))
        favorite_straight_key = (
            "set_handicap_b_minus_1_5"
            if underdog_side == "home"
            else "set_handicap_a_minus_1_5"
        )
        favorite_straight = _probability(markets.get(favorite_straight_key))
        at_least_one = 1.0 - favorite_straight if favorite_straight is not None else None
        # A simple 1+ set card needs an additional matchup signal.  The
        # independently simulated probability of a deciding set is that signal.
        if (
            at_least_one is not None
            and TENNIS_SIDE_MIN_PROBABILITY <= at_least_one <= TENNIS_SIMPLE_MAX_PROBABILITY
            and over_25 is not None
            and over_25 >= 0.40
        ):
            options.append(
                (
                    at_least_one * 0.45,
                    "plus_1_5_sets",
                    "Außenseiter gewinnt mindestens einen Satz (+1,5)",
                    at_least_one,
                    0.10,
                    f"Das Satzmodell sieht {over_25:.1%} Chance auf einen Entscheidungssatz.",
                    "Ein einzelner schwacher Aufschlagdurchgang kann den Satzmarkt kippen.",
                )
            )
        if (
            over_25 is not None
            and TENNIS_SIDE_MIN_PROBABILITY <= over_25 <= TENNIS_SIMPLE_MAX_PROBABILITY
        ):
            options.append(
                (
                    over_25 * 0.70,
                    "over_2_5_sets",
                    "Über 2,5 Sätze",
                    over_25,
                    0.10,
                    f"Die Serve-Simulation weist {over_25:.1%} für drei Sätze aus.",
                    "Das Modell setzt ein regulär beendetes Best-of-3-Match voraus.",
                )
            )
        chosen_side = max(options, key=lambda item: (item[0], item[1]), default=None)
        base_specs: list[tuple[str, str, float, float, str, str]] = []
        if p_underdog >= TENNIS_WIN_MIN_PROBABILITY:
            base_specs.append((
                "match_winner",
                "Außenseitersieg",
                p_underdog,
                0.15,
                f"Das kalibrierte Matchmodell gibt {underdog} {p_underdog:.1%} Siegchance.",
                "Belag ist modelliert. Akute Fitness, Verletzungen und Belastung sind noch nicht als numerischer Effekt validiert.",
            ))
        if chosen_side is not None:
            base_specs.append(chosen_side[1:])
        candidates = tuple(
            RiskCandidate(
                snapshot_id=snapshot.snapshot_id,
                event_key=event_key,
                sport="tennis",
                competition=competition,
                event_label=f"{player_a} vs {player_b}",
                starts_at=starts_at,
                market_key=spec[0],
                market_label=spec[1],
                selection_key=("over" if spec[0] == "over_2_5_sets" else underdog_side),
                selection_label=("Über 2,5 Sätze" if spec[0] == "over_2_5_sets" else underdog),
                model_probability=spec[2],
                cautious_probability=max(0.0, spec[2] - spec[3]),
                stage=EvidenceStage.SHADOW,
                context_state=ContextState.PARTIAL,
                policy_version=policy_version,
                pros=(spec[4],),
                cons=(spec[5],),
                settlement_contract=(
                    f"riskobet-settlement-v1:tennis:{spec[0]}:"
                    f"{'over' if spec[0] == 'over_2_5_sets' else underdog_side}"
                ),
            )
            for spec in base_specs
        )
        outputs.append(RiskAdapterResult(snapshot=snapshot, candidates=candidates))
    return tuple(outputs)

