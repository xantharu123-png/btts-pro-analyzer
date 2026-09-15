"""Worker-local index of an already selected, completely validated history.

This changes neither stored receipts nor the complete snapshot reference list.
Every row is validated before indexing. All revisions of any event ever linked
to either participant are kept, including corrections removing that participant.
No caller-owned mutable row, validation flag or cross-worker cache is retained.
"""
import json
from types import MappingProxyType

from context_models.contracts import ContextContractError
from context_sources.tennis_status import STATUS_SCHEMA, validate_selected_tennis_receipt
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

    def for_event(self, event):
        keys = {event["event_key"]}
        for player in (event["home_id"], event["away_id"]):
            keys.update(self._players.get(player, ()))
        ordinals = sorted({ordinal for key in keys for ordinal in self._events.get(key, ())},
                          key=None if self._rank is None else self._rank.__getitem__)
        return tuple(json.loads(self._rows[index]) for index in ordinals)


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
