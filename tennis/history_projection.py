"""Worker-local index of an already selected, completely validated history.

This changes neither stored receipts nor the complete snapshot reference list.
Every row is validated before indexing. All revisions of any event ever linked
to either participant are kept, including corrections removing that participant.
No caller-owned mutable row, validation flag or cross-worker cache is retained.
"""
import json
import sys
from contextlib import contextmanager
from types import MappingProxyType

from context_models.contracts import ContextContractError
from context_sources.tennis_status import (STATUS_SCHEMA, validate_selected_tennis_receipt,
    _feature_receipt_scope, _FeatureReceiptScope)
from model_artifacts import canonical_bytes


class PreparedTennisHistory:
    def __init__(self, observations):
        if type(observations) is not tuple:
            raise ContextContractError("prepared history requires the complete selected tuple")
        self._build(observations)

    @classmethod
    def from_selected_rows(cls, observations):
        """Own a streaming selection; every row still passes full validation."""
        result = cls.__new__(cls)
        result._build(observations, chronological=True)
        return result

    @classmethod
    def from_physical_rows(cls, stored_rows, *, cutoff, tour):
        return cls.from_physical_tours(stored_rows, cutoff=cutoff, tours=(tour,))[tour]

    @classmethod
    def _from_case_physical_rows(cls, stored_rows, *, cutoff, tour, memberships=(), budget):
        """One bounded case, with B1/native/index proof in the same reader.

        Index membership headers are checked against their actual selected
        physical receipt here, not through a second source decode. Every
        revision remains present, including later participant corrections.
        """
        from context_observations import _decode_receipt
        from context_sources.tennis_status import SOURCE_SCHEMA, _tour, _validate_tennis_source_tail
        from context_models.contracts import ContextIntegrityError, canonical_timestamp
        _tour(tour)
        decision = canonical_timestamp(cutoff)
        expected = {}
        for member in memberships:
            expected.setdefault(member[4], set()).add(tuple(member))
        builder = _IndexBuilder(chronological=True)
        seen = set()
        encoded_bytes = 0
        for stored in stored_rows:
            budget.check()
            row = _decode_receipt(stored)
            if (row['source'] != 'espn' or row['sport'] != 'tennis'
                    or row['kind'] not in ('event_status', 'workload')
                    or row['source_schema'] not in (STATUS_SCHEMA, SOURCE_SCHEMA)
                    or row['observed_at'] > decision):
                raise ContextIntegrityError('streamed tennis source is outside its frozen case')
            _validate_tennis_source_tail(row, stored[8])
            if row['payload']['tour'] != tour or row['digest'] in seen:
                raise ContextIntegrityError('streamed tennis source crosses tours or repeats a physical receipt')
            seen.add(row['digest'])
            participants = (row['payload']['participant_ids'] if row['source_schema'] == STATUS_SCHEMA
                            else (row['payload']['player_id'], row['payload']['opponent_id']))
            for member in expected.pop(row['digest'], ()):
                if (member[0] != tour or member[1] not in participants
                        or member[2] != row['event_key'] or member[3] != row['observed_at']):
                    raise ContextIntegrityError('streamed tennis membership differs from physical native receipt')
            row.update(evidence_class='prospective', effective_at=row['observed_at'], publication_resolution=None)
            entry = cls._index_entry(row)
            encoded_bytes += len(entry[0])
            # Retain the immutable encoding, feature-scope decoded objects,
            # indexes and Python bookkeeping together, not merely wire bytes.
            budget.retain_case(encoded_bytes, len(seen))
            builder.append(entry)
        if expected:
            raise ContextIntegrityError('streamed tennis membership has no physical native receipt')
        result = cls.__new__(cls)
        builder.finish(result)
        return result

    @classmethod
    def _from_physical_case_batch(cls, stored_rows, *, cases, budget):
        """Full physical negative proof when no verified index is available.

        One actual native pass, grouped only by event. Participant removal or
        correction cannot discard an earlier revision of that event. No
        caller-provided validation flag or reusable source cache is accepted.
        """
        from context_observations import _decode_receipt
        from context_sources.tennis_status import SOURCE_SCHEMA, _validate_tennis_source_tail
        from context_models.contracts import ContextIntegrityError
        builders = [_IndexBuilder(chronological=True) for _ in cases]
        charges = [0 for _ in cases]
        current, pending, pending_size, last_order = None, [], 0, None

        def finish_event():
            nonlocal pending_size
            for index, (event, cutoff) in enumerate(cases):
                eligible = [entry for tour, entry, _ in pending if tour == event['tour'] and entry[4] <= cutoff]
                if not (current == event['event_key'] or any(
                        player in (event['home_id'], event['away_id']) for entry in eligible for player in entry[2])):
                    continue
                physical_bytes = sum(size for tour, entry, size in pending
                                     if tour == event['tour'] and entry[4] <= cutoff)
                budget.admit_case_raw(index, len(eligible), physical_bytes)
                for entry in eligible:
                    cost = len(entry[0])+512
                    budget.charge_metadata(cost)
                    charges[index] += cost
                    builders[index].append(entry)
            budget.metadata_bytes -= pending_size
            pending.clear()
            pending_size = 0

        for stored in stored_rows:
            budget.check()
            # A single work row is finite before crossing the SQL/Python
            # decoder boundary; the source owner validates its full bytes.
            if type(stored[8]) is not bytes or len(stored[8]) > budget.chunk_bytes:
                raise ValueError('global tennis source work row exceeds chunk admission')
            row = _decode_receipt(stored)
            _validate_tennis_source_tail(row, stored[8])
            if (row['source'] != 'espn' or row['sport'] != 'tennis'
                    or row['source_schema'] not in (STATUS_SCHEMA, SOURCE_SCHEMA)
                    or row['kind'] not in ('event_status', 'workload')):
                raise ContextIntegrityError('global tennis stream is outside native source scope')
            order = (row['event_key'], row['observed_at'], row['digest'])
            if last_order is not None and order <= last_order:
                raise ContextIntegrityError('global tennis physical stream is not strictly ordered')
            if current is not None and row['event_key'] != current:
                finish_event()
            current, last_order = row['event_key'], order
            budget.global_raw_rows += 1
            budget.global_raw_payload_bytes += len(stored[8])
            row.update(evidence_class='prospective', effective_at=row['observed_at'], publication_resolution=None)
            entry = cls._index_entry(row)
            cost = len(entry[0])+512
            budget.charge_metadata(cost)
            pending_size += cost
            pending.append((row['payload']['tour'], entry, len(stored[8])))
        if current is not None:
            finish_event()
        results = []
        for builder, cost in zip(builders, charges):
            result = cls.__new__(cls)
            builder.finish(result)
            result._stream_charge = cost
            results.append(result)
        return results

    @classmethod
    def from_physical_tours(cls, stored_rows, *, cutoff, tours):
        """Fixed physical/source co-owner; never accepts a validation flag.

        Decode every frozen SQL row with B1, then validate its complete native
        source tail in the same frame, before any tour projection. The ordinary
        selected-row constructor remains independently fully validating.
        """
        from context_observations import _decode_receipt
        from context_sources.tennis_status import SOURCE_SCHEMA, _tour, _validate_tennis_source_tail
        from context_models.contracts import canonical_timestamp
        if type(tours) is not tuple or not tours:
            raise ContextContractError("history tours require a nonempty explicit tuple")
        for tour in tours:
            _tour(tour)
        if len(set(tours)) != len(tours):
            raise ContextContractError("history tours must be unique")
        decision = canonical_timestamp(cutoff)
        builders = {tour: _IndexBuilder(chronological=True) for tour in tours}
        for stored in stored_rows:
            row = _decode_receipt(stored)
            if row["observed_at"] > decision or row["source_schema"] not in (STATUS_SCHEMA, SOURCE_SCHEMA):
                continue
            # B1 just checked these exact canonical content bytes, receipt
            # identity and every outer index. No callback sees this row
            # between physical validation and the complete source tail.
            _validate_tennis_source_tail(row, stored[8])
            builder = builders.get(row["payload"]["tour"])
            if builder is not None:
                row.update(evidence_class="prospective", effective_at=row["observed_at"],
                           publication_resolution=None)
                builder.append(cls._index_entry(row))
        results = {}
        for tour, builder in builders.items():
            result = cls.__new__(cls)
            builder.finish(result)
            results[tour] = result
        return results

    @staticmethod
    def _index_entry(row):
        payload = row["payload"]
        participants = (payload["participant_ids"] if row["source_schema"] == STATUS_SCHEMA
                        else (payload["player_id"], payload["opponent_id"]))
        return canonical_bytes(row), row["event_key"], tuple(participants), row["digest"], row["observed_at"]

    def _build(self, observations, *, chronological=False):
        def entries():
            for row in observations:
                validate_selected_tennis_receipt(row)
                yield self._index_entry(row)
        self._build_entries(entries(), chronological=chronological)

    def _build_entries(self, entries, *, chronological=False):
        builder = _IndexBuilder(chronological=chronological)
        for entry in entries:
            builder.append(entry)
        builder.finish(self)

    @property
    def observation_refs(self):
        return list(self._refs)

    def _event_ordinals(self, event):
        keys = {event["event_key"]}
        for player in (event["home_id"], event["away_id"]):
            keys.update(self._players.get(player, ()))
        ordinals = sorted({ordinal for key in keys for ordinal in self._events.get(key, ())},
                          key=None if self._rank is None else self._rank.__getitem__)
        return ordinals

    def for_event(self, event):
        return tuple(json.loads(self._rows[index]) for index in self._event_ordinals(event))

    @contextmanager
    def feature_scope(self, event):
        """Reuse completed validation only while actual row bytes still match.

        Neither dict identity nor a caller-supplied digest grants acceptance.
        Mutations, aliases, detached copies and uses after exit go cold again.
        This does not prune any event revision or the complete reference list.
        """
        if type(self) is not PreparedTennisHistory or self._rows is not self._validated_rows:
            yield self.for_event(event)
            return
        encoded = tuple(self._rows[index] for index in self._event_ordinals(event))
        rows = tuple(json.loads(raw) for raw in encoded)
        scope = _FeatureReceiptScope(rows, encoded)
        token = _feature_receipt_scope.set(scope)
        try:
            yield rows
        finally:
            scope.rows.clear()
            _feature_receipt_scope.reset(token)

    @contextmanager
    def _stream_feature_scope(self, event, budget):
        """Charge actual decoded rows alongside all retained encoded owners."""
        rows, encoded = [], []
        budget.selected_bytes = 0
        def size(value):
            result = sys.getsizeof(value)
            if type(value) is dict:
                result += sum(size(key)+size(item) for key, item in value.items())
            elif type(value) in (tuple, list):
                result += sum(size(item) for item in value)
            return result
        try:
            for index in self._event_ordinals(event):
                raw = self._rows[index]
                row = json.loads(raw)
                # Dict keys/strings are conservatively charged even if the
                # JSON decoder internally shares their object identities.
                budget.selected_bytes += size(row)+32
                budget.check()
                rows.append(row)
                encoded.append(raw)
            rows = tuple(rows)
            scope = _FeatureReceiptScope(rows, encoded)
            token = _feature_receipt_scope.set(scope)
            try:
                yield rows
            finally:
                scope.rows.clear()
                _feature_receipt_scope.reset(token)
        finally:
            budget.selected_bytes = 0


class _IndexBuilder:
    """Private accumulator; only final immutable indexes escape their reader."""
    def __init__(self, *, chronological):
        self.encoded, self.events, self.players, self.refs = [], {}, {}, set()
        self.order = [] if chronological else None

    def append(self, entry):
        raw, key, participants, ref, clock = entry
        ordinal = len(self.encoded)
        self.encoded.append(raw)
        if self.order is not None:
            self.order.append((clock, ref, ordinal))
        self.events.setdefault(key, []).append(ordinal)
        for player in participants:
            if player is not None:
                self.players.setdefault(player, set()).add(key)
        self.refs.add(ref)

    def finish(self, result):
        result._rows = tuple(self.encoded)
        result._validated_rows = result._rows
        result._events = MappingProxyType({key: tuple(value) for key, value in self.events.items()})
        result._players = MappingProxyType({key: frozenset(value) for key, value in self.players.items()})
        result._refs = tuple(sorted(self.refs))
        result._rank = None
        if self.order is not None:
            # Sort only small clock/hash/index records, not the full SQL payload
            # inventory. Event membership and every correction remain intact.
            rank = [0]*len(self.order)
            for position, (_, _, ordinal) in enumerate(sorted(self.order)):
                rank[ordinal] = position
            result._rank = tuple(rank)
