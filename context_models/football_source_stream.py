"""Versioned, read-only native source transport for existing football inputs.

Every causal receipt is decoded and checked before a deterministic feature
projection is retained.  This is not a latest-only database query: correction,
withdrawal and simultaneous-conflict receipts remain in the audited inventory.
The original 4 MiB joint-source resolver is deliberately unchanged.

This transport changes resource processing, not a feature or probability law.
Its output must be rebuilt from the physical reader by its owning consumer;
the compact inventory hash alone is not proof that omitted sources are valid.
"""
from datetime import datetime, timedelta

import challenge_engine as engine
from context_models.contracts import ContextContractError, ContextIntegrityError, canonical_timestamp, digest
from model_artifacts import canonical_bytes
from context_models.football import _appearance_payload, _is_empty_collection, _native_causal_roster_row, _selected
from context_models.replay import ReplayUnavailable
from context_observations import _SELECT, _decode_receipt
from context_sources.football import _detail_event, normalize_football_context
from context_sources.outcomes import validate_football_base_input

SOURCE_TRANSPORT = "football-native-source-stream-v2"
MAX_RAW_BYTES = 128 * 1024 * 1024
MAX_RAW_RECEIPTS = 100_000
MAX_EXPANDED_SOURCE_BYTES = 128 * 1024 * 1024
MAX_BRANCH_BYTES = 4 * 1024 * 1024
MAX_BRANCH_RECEIPTS = 4096
MAX_EVENTS = 4096


class _Audit:
    def __init__(self, ledger=None, *, retain_full=False):
        self.refs, self.contents, self.bytes, self.ledger = set(), {}, 0, ledger
        self.expanded_bytes = 2  # Exact JSON-list brackets for a full row tuple.
        self.full_rows = [] if retain_full else None

    def decode(self, connection, ref, storage_type, length):
        if storage_type != "blob" or type(length) is not int or not 0 < length <= MAX_BRANCH_BYTES:
            raise ContextIntegrityError("stream source body is absent or outside its single-record envelope")
        if ref in self.refs or len(self.refs) >= MAX_RAW_RECEIPTS:
            raise ReplayUnavailable("stream_source_receipt_bound_exceeded")
        # Admission precedes body retrieval. One physical content is charged
        # once even if several genuine reception clocks point to its bytes.
        content = connection.execute("SELECT content_digest FROM context_observations WHERE digest=?", (ref,)).fetchone()
        if content is None:
            raise ContextIntegrityError("stream source header has no receipt")
        content = content[0]
        if content not in self.contents:
            if self.bytes + length > MAX_RAW_BYTES:
                raise ReplayUnavailable("stream_source_physical_byte_bound_exceeded")
            if self.ledger is not None:
                self.ledger.admit("context_contents", content)
            self.contents[content] = length
            self.bytes += length
        elif self.contents[content] != length:
            raise ContextIntegrityError("stream physical content changed in its reader image")
        raw = connection.execute(_SELECT + " WHERE r.digest=?", (ref,)).fetchone()
        if raw is None or type(raw[-1]) is not bytes or len(raw[-1]) != length:
            raise ContextIntegrityError("stream source bytes differ from their admitted header")
        # The owning decoder already checks exact canonical content, hashes,
        # native index fields and receipt clocks in-place. Do not copy/dump the
        # entire raw content again solely for an identical structural check.
        row = _decode_receipt(raw)
        extra = dict(digest=row['digest'], content_digest=row['content_digest'], observed_at=row['observed_at'],
                     evidence_class="prospective", effective_at=row["observed_at"], publication_resolution=None)
        row.update(extra)
        # Two nonempty JSON objects combine with one comma and without the
        # adjacent braces: exact full-row bytes, no second huge serialization.
        expanded = self.expanded_bytes + length + len(canonical_bytes(extra)) - 1 + int(bool(self.refs))
        if self.full_rows is not None and expanded > MAX_EXPANDED_SOURCE_BYTES:
            raise ReplayUnavailable("stream_source_expanded_byte_bound_exceeded")
        self.refs.add(ref)
        self.expanded_bytes = expanded
        if self.full_rows is not None:
            self.full_rows.append(row)
        return row


def _bounded_branch(name, rows, lengths):
    rows = tuple(sorted({row["digest"]: row for row in rows}.values(),
                        key=lambda row: (row["observed_at"], row["digest"])))
    if len(rows) > MAX_BRANCH_RECEIPTS:
        raise ReplayUnavailable("stream_feature_branch_receipt_bound_exceeded:" + name)
    if sum(lengths[row["content_digest"]] for row in rows) > MAX_BRANCH_BYTES:
        raise ReplayUnavailable("stream_feature_branch_byte_bound_exceeded:" + name)
    return rows


def _latest(groups, key, row, *, sizes, state):
    previous = groups.get(key)
    if previous is None or row["observed_at"] > previous[0]["observed_at"]:
        replacement = [row]
    elif row["observed_at"] == previous[0]["observed_at"]:
        replacement = previous + [row]
    else:
        return
    count = state[0] + len(replacement) - len(previous or ())
    size = state[1] + sum(sizes[item["content_digest"]] for item in replacement) - sum(
        sizes[item["content_digest"]] for item in previous or ())
    if count > MAX_BRANCH_RECEIPTS or size > MAX_BRANCH_BYTES:
        raise ReplayUnavailable("stream_feature_event_branch_bound_exceeded")
    groups[key], state[:] = replacement, [count, size]


class _BranchRows:
    def __init__(self, name, audit):
        self.name, self.audit, self.rows, self.size = name, audit, {}, 0

    def extend(self, rows):
        for row in rows:
            if row["digest"] in self.rows:
                continue
            length = self.audit.contents[row["content_digest"]]
            if len(self.rows) >= MAX_BRANCH_RECEIPTS:
                raise ReplayUnavailable("stream_feature_branch_receipt_bound_exceeded:" + self.name)
            if self.size + length > MAX_BRANCH_BYTES:
                raise ReplayUnavailable("stream_feature_branch_byte_bound_exceeded:" + self.name)
            self.rows[row["digest"]] = row
            self.size += length


def _event_pool(connection, key, cutoff, audit, *, frozen, target, include_player_load):
    """Validate one whole event, then apply the existing pure row selector."""
    roster, base, weather, proofs, binding_rows = {}, {}, {}, {}, []
    states = {name: [0, 0] for name in ("roster", "base", "weather", "proof")}
    headers = connection.execute(
        "SELECT r.digest,typeof(c.payload),length(CAST(c.payload AS BLOB)) "
        "FROM context_observations r LEFT JOIN context_contents c ON c.content_digest=r.content_digest "
        "WHERE r.event_key=? AND r.observed_at<=? AND r.kind!='match_outcome' "
        "ORDER BY r.observed_at,r.digest LIMIT ?", (key, cutoff, MAX_RAW_RECEIPTS-len(audit.refs)+1))
    for ref, storage_type, length in headers:
        row = audit.decode(connection, ref, storage_type, length)
        if row["event_key"] != key or row["observed_at"] > cutoff:
            raise ContextIntegrityError("stream index differs from its causal native event")
        if ref in frozen:
            binding_rows.append(row)
        if row["kind"] == "base_fixture":
            validate_football_base_input(row)
            _latest(base, key, row, sizes=audit.contents, state=states['base'])
        elif row["kind"] in {"appearance", "availability", "confirmed_lineup"}:
            _native_causal_roster_row(row, cutoff)
            _latest(roster, (row["event_key"], row["subject_id"], row["kind"], row["source"]), row,
                    sizes=audit.contents, state=states['roster'])
            if include_player_load and row["kind"] == "appearance" and not _is_empty_collection(row):
                payload = _appearance_payload(row, cutoff=datetime.fromisoformat(cutoff))
                if payload["minutes"] is not None and payload["minutes"] > 0:
                    identity = (row["event_key"], row["subject_id"], payload["team_id"], payload["scheduled_start"])
                    before = proofs.get(identity)
                    if before is None or (payload["result_observed_at"], row['observed_at'], row["digest"]) < (
                            before["payload"]["result_observed_at"], before['observed_at'], before["digest"]):
                        count = states['proof'][0] + int(before is None)
                        size = states['proof'][1] + audit.contents[row['content_digest']] - (
                            audit.contents[before['content_digest']] if before is not None else 0)
                        if count > MAX_BRANCH_RECEIPTS or size > MAX_BRANCH_BYTES:
                            raise ReplayUnavailable('stream_feature_recovery_branch_bound_exceeded')
                        proofs[identity] = row
                        states['proof'][:] = [count, size]
        elif row["kind"] == "weather" and key == target["event_key"]:
            from context_sources.openweather import SOURCE_SCHEMA, validate_record
            if row['source_schema'] == SOURCE_SCHEMA:
                # The city-weather owner validates every supported revision
                # before choosing its latest point. Older malformed inputs may
                # not be laundered by a later good point or unrelated schema.
                validate_record(row)
                _latest(weather, (key, row['source_schema']), row, sizes=audit.contents, state=states['weather'])
    latest_roster = _bounded_branch("event-selection", (row for group in roster.values() for row in group), audit.contents)
    selected = _selected(latest_roster, cutoff=datetime.fromisoformat(cutoff))
    # Validate selected foreign collections before projecting onto the target
    # team, exactly as the original roster feature owner does.
    for row in selected:
        if row["kind"] == "appearance" and not _is_empty_collection(row):
            _appearance_payload(row, cutoff=datetime.fromisoformat(cutoff))
    latest_base = tuple(row for group in base.values() for row in group)
    expected = set()
    for row in latest_base:
        detail = row["payload"]["detail"]
        event = _detail_event(detail)
        projected = normalize_football_context(event, injuries=[],
            lineups=[detail] if key == target["event_key"] and "lineups" in detail else [],
            appearances=[detail] if event["status"] == "completed" and "players" in detail else [],
            observed_at=datetime.fromisoformat(row["observed_at"]))
        expected.update(digest(value) for value in projected if value["kind"] in {"appearance", "confirmed_lineup"})
    # Keep incomplete/empty collection heads too. Passing only the selector's
    # usable output would let an old positive recovery proof resurrect a
    # collection that its newer empty or incomplete revision withdrew.
    return latest_roster, tuple(proofs.values()), latest_base, tuple(row for group in weather.values() for row in group), binding_rows, expected


def streamed_joint_sources(connection, packet, binding, base, *, feature_version, ledger=None, retain_full=False, latest=None):
    if canonical_timestamp(base["cutoff"]) != binding["decision_at"]:
        from football_context_inventory import rebuild_later_sources
        return rebuild_later_sources(connection, packet, binding, base, latest=latest,
            feature_version=feature_version, ledger=ledger, retain_full=retain_full)
    return _stream_joint_sources_at_cutoff(connection, packet, binding, base,
        feature_version=feature_version, ledger=ledger, retain_full=retain_full)


def _stream_joint_sources_at_cutoff(connection, packet, binding, base, *, feature_version, ledger=None, retain_full=False):
    """Audit all causal revisions and return lossless bounded feature branches.

    The compact branches are an explicit new transport, not legacy D1 evidence.
    The physical reader must own rebuilding and checking this output.
    """
    from context_models.football_joint_context import FEATURE_VERSION, POOLED_FEATURE_VERSION, PLAYER_LOAD_FEATURE_VERSION
    if not connection.in_transaction:
        raise ContextContractError('streamed football sources require one held physical reader transaction')
    if feature_version not in {FEATURE_VERSION, POOLED_FEATURE_VERSION, PLAYER_LOAD_FEATURE_VERSION}:
        raise ContextContractError("unknown streamed football feature version")
    if type(retain_full) is not bool:
        raise ContextContractError("stream full-source retention requires an explicit boolean")
    cutoff = canonical_timestamp(base["cutoff"])
    event = binding["native_event"]
    if event is None or event["event_key"] != base["event_key"]:
        raise ContextIntegrityError("stream source event differs from the original base")
    if not binding["decision_at"] <= cutoff < event["scheduled_start"]:
        raise ContextContractError("stream source cutoff must follow original and precede kickoff")
    original_rows = [packet["fixture"], *packet["league_history"], *(packet["team_history"] or [])]
    keys = ["api-football:football:" + str(native_id) for native_id in sorted({
        engine.football_base_history_record(raw)["fixture_id"] for raw in
        original_rows})]
    if len(keys) > MAX_EVENTS:
        raise ReplayUnavailable("stream_source_event_bound_exceeded")
    frozen = {ref for field in ("consumed_receipts", "inspected_receipts")
              for values in binding[field].values() for ref in values}
    audit, expected = _Audit(ledger, retain_full=retain_full), set()
    branches = {name: _BranchRows(name, audit) for name in ('binding', 'schedule', 'weather', 'roster.home', 'roster.away', 'load')}
    target_teams = {event["home_id"], event["away_id"]}
    original_target_keys = {own["event_key"] for own in map(_detail_event, original_rows)
                            if target_teams & {own["home_id"], own["away_id"]}}
    include_load = feature_version == PLAYER_LOAD_FEATURE_VERSION

    def consume(key, *, additional=False, players=frozenset()):
        chosen, proofs, native, forecasts, captured, projections = _event_pool(connection, key, cutoff, audit,
            frozen=frozen, target=event, include_player_load=include_load)
        expected.update(projections)
        branches['binding'].extend(captured)
        branches['weather'].extend(forecasts)
        teams = target_teams if not additional else {row["payload"]["team_id"] for row in chosen
            if row["kind"] == "appearance" and row["subject_id"] in players}
        if include_load:
            old_players = {row['subject_id'] for row in proofs if row['payload']['team_id'] in teams}
            # Retain the complete newer foreign-team collection that revokes
            # an old target-team player proof. Otherwise a second selector
            # would resurrect that old proof after a native team correction.
            teams = teams | {row['payload']['team_id'] for row in chosen
                if row['kind'] == 'appearance' and row['subject_id'] in old_players}
        relevant = tuple(row for row in chosen if
            (row["kind"] == "appearance" and row["payload"]["team_id"] in teams)
            or (row["kind"] in {"availability", "confirmed_lineup"} and key == event["event_key"]))
        for side in ('home', 'away'):
            branches['roster.'+side].extend(row for row in relevant if row['payload'].get('team_id') == event[side+'_id'])
        branches['load'].extend(row for row in relevant if row['payload'].get('team_id') not in target_teams)
        branches['load'].extend(row for row in proofs if row["payload"]["team_id"] in teams)
        native_events = [_detail_event(row["payload"]["detail"]) for row in native]
        if key in original_target_keys or any(target_teams & {value["home_id"], value["away_id"]} for value in native_events):
            branches['schedule'].extend(native)

    for key in keys:
        consume(key)
    if include_load:
        from context_sources.football_player_history import _target_players
        selected = tuple(row for name in ('roster.home', 'roster.away', 'load') for row in branches[name].rows.values())
        players = _target_players(selected, event=event, cutoff=datetime.fromisoformat(cutoff))
        if players:
            if len(players) > MAX_EVENTS:
                raise ReplayUnavailable('player_history_cohort_bound_exceeded')
            marks, known = ",".join("?" for _ in players), ",".join("?" for _ in keys)
            extra = connection.execute("SELECT DISTINCT event_key FROM context_observations "
                "WHERE source='api-football' AND kind='appearance' "
                f"AND subject_id IN ({marks}) AND observed_at>=? AND observed_at<=? "
                f"AND event_key NOT IN ({known}) ORDER BY event_key LIMIT ?",
                (*players, canonical_timestamp(datetime.fromisoformat(cutoff)-timedelta(days=14)), cutoff,
                 *keys, MAX_EVENTS-len(keys)+1)).fetchall()
            if len(extra) > MAX_EVENTS-len(keys):
                raise ReplayUnavailable("stream_source_event_bound_exceeded")
            for (key,) in extra:
                from context_models.football import _native_identity
                if not _native_identity(key, 'football'):
                    raise ContextIntegrityError('player history header has a nonnative event key')
                consume(key, additional=True, players=frozenset(players))
    if not frozen <= audit.refs:
        raise ContextIntegrityError("stream source lacks an exact frozen consumed or inspected receipt")
    if not expected <= set(audit.contents):
        raise ReplayUnavailable("native_context_projection_missing_or_superseded")
    # Transfer/international workload has its own full-collection branch,
    # never an invented club-role sample.
    branches = {name: _bounded_branch(name, branch.rows.values(), audit.contents) for name, branch in branches.items()}
    observed = {row["digest"]: row for rows in branches.values() for row in rows}
    projected = tuple(sorted(observed.values(), key=lambda row: (row["observed_at"], row["digest"])))
    return {"source_transport": SOURCE_TRANSPORT, "branches": branches,
        "feature_observations": projected,
        "observations": tuple(sorted(audit.full_rows, key=lambda row: (row["observed_at"], row["digest"]))) if retain_full else projected,
        "audit": {"receipt_count": len(audit.refs), "physical_content_bytes": audit.bytes,
                  "expanded_observation_bytes": audit.expanded_bytes,
                  "receipt_refs_hash": digest(sorted(audit.refs)), "content_refs_hash": digest(sorted(audit.contents)),
                  "retained_receipts": len(observed),
                  "branch_bytes": {name: sum(audit.contents[row["content_digest"]] for row in rows)
                                   for name, rows in branches.items()}}}

