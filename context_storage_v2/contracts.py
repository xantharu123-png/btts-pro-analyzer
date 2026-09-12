"""Approved C resource envelope, separate from unchanged legacy admission."""
from dataclasses import dataclass

from model_artifacts import ArtifactIntegrityError
from runtime_paths import RuntimeArtifactTrustError


class StorageIntegrityError(ArtifactIntegrityError):
    """A complete v2 input/identity/lifetime could not be established."""


class StorageLimitError(RuntimeArtifactTrustError):
    """The explicit v2 envelope was exceeded; never a partial success."""


MAX_INPUT_BYTES = 4 * 1024**3
MAX_TOUR_HISTORY_BYTES = 1024**3
MAX_BLOCK_BYTES = 16 * 1024**2
MAX_WORKSPACE_BYTES = 8 * 1024**3
MIN_FREE_BYTES = 4 * 1024**3
# A manifest must itself remain bounded even for deliberately tiny blocks.
MAX_BLOCKS_PER_SET = 4096


@dataclass(frozen=True)
class StorageLimits:
    """Tests/callers may tighten admission, never silently widen the contract."""
    input_bytes: int = MAX_INPUT_BYTES
    tour_history_bytes: int = MAX_TOUR_HISTORY_BYTES
    block_bytes: int = MAX_BLOCK_BYTES
    workspace_bytes: int = MAX_WORKSPACE_BYTES
    min_free_bytes: int = MIN_FREE_BYTES
    blocks_per_set: int = MAX_BLOCKS_PER_SET

    def __post_init__(self):
        maxima = dict(input_bytes=MAX_INPUT_BYTES,
                      tour_history_bytes=MAX_TOUR_HISTORY_BYTES,
                      block_bytes=MAX_BLOCK_BYTES,
                      workspace_bytes=MAX_WORKSPACE_BYTES,
                      blocks_per_set=MAX_BLOCKS_PER_SET)
        for name, maximum in maxima.items():
            value = getattr(self, name)
            if type(value) is not int or not 0 < value <= maximum:
                raise StorageLimitError("invalid or widened v2 storage limit")
        if type(self.min_free_bytes) is not int or self.min_free_bytes < MIN_FREE_BYTES:
            raise StorageLimitError("v2 free-space reserve cannot be lowered")


DEFAULT_LIMITS = StorageLimits()
