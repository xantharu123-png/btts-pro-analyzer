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
        """Fixed physical/source co-owner; never accepts a validation flag.

        Decode every frozen SQL row with B1, then validate its complete native
        source tail in the same frame, before any tour projection. The ordinary
        selected-row constructor remains independently fully validating.
        """
        from context_observations import _decode_receipt
        from context_sources.tennis_status import SOURCE_SCHEMA, _tour, _validate_tennis_source_tail
        from context_models.contracts import canonical_timestamp
        _tour(tour)
        decision = canonical_timestamp(cutoff)
        def entries():
            for stored in stored_rows:
                row = _decode_receipt(stored)
                if row["observed_at"] > decision or row["source_schema"] not in (STATUS_SCHEMA, SOURCE_SCHEMA):
                    continue
                # B1 just checked these exact canonical content bytes, receipt
                # identity and every outer index. No callback sees this row
                # between physical validation and the complete source tail.
                _validate_tennis_source_tail(row, stored[8])
                if row["payload"]["tour"] != tour:
                    continue
                row.update(evidence_class="prospective", effective_at=row["observed_at"],
                           publication_resolution=None)
                yield cls._index_entry(row)
        result = cls.__new__(cls)
        result._build_entries(entries(), chronological=True)
        return result

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
        encoded, events, players, refs = [], {}, {}, set()
        order = []
        for raw, key, participants, ref, clock in entries:
            encoded.append(raw)
            if chronological:
                order.append((clock, ref, len(encoded)-1))
            events.setdefault(key, []).append(len(encoded)-1)
            for player in participants:
                if player is not None:
                    players.setdefault(player, set()).add(key)
            refs.add(ref)
        self._rows = tuple(encoded)
        self._events = MappingProxyType({key: tuple(value) for key, value in events.items()})
        self._players = MappingProxyType({key: frozenset(value) for key, value in players.items()})
        self._refs = tuple(sorted(refs))
        self._rank = None
        if chronological:
            # Sort only small clock/hash/index records, not the full SQL payload
            # inventory. Event membership and every correction remain intact.
            rank = [0]*len(order)
            for position, (_, _, ordinal) in enumerate(sorted(order)):
                rank[ordinal] = position
            self._rank = tuple(rank)

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
