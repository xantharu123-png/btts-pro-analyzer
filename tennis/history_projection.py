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

    def _build(self, observations, *, chronological=False):
        encoded, events, players, refs = [], {}, {}, set()
        order = []
        for row in observations:
            validate_selected_tennis_receipt(row)
            encoded.append(canonical_bytes(row))
            if chronological:
                order.append((row["observed_at"], row["digest"], len(encoded)-1))
            key = row["event_key"]
            events.setdefault(key, []).append(len(encoded)-1)
            payload = row["payload"]
            participants = (payload["participant_ids"] if row["source_schema"] == STATUS_SCHEMA
                            else (payload["player_id"], payload["opponent_id"]))
            for player in participants:
                if player is not None:
                    players.setdefault(player, set()).add(key)
            refs.add(row["digest"])
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
