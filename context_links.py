"""Immutable consumer identity only; not evidence of a sporting advantage."""
from dataclasses import dataclass

from context_models.contracts import require_digest, require_object


@dataclass(frozen=True, slots=True)
class ContextReference:
    key: str
    payload_digest: str

    def __post_init__(self):
        require_digest(self.key, "context input key")
        require_digest(self.payload_digest, "context payload digest")

    @classmethod
    def from_dict(cls, value):
        require_object(value, {"schema", "kind", "key", "payload_digest"},
                       label="immutable context reference")
        if (type(value["schema"]) is not int or value["schema"] != 1
                or value["kind"] != "context-consumer-reference-v1"):
            raise ValueError("unknown immutable context reference version")
        return cls(value["key"], value["payload_digest"])

    def to_dict(self):
        return {"schema": 1, "kind": "context-consumer-reference-v1",
                "key": self.key, "payload_digest": self.payload_digest}
