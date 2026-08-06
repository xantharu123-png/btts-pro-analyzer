"""Streamlit bridge and downloadable package for the local N1Bet importer."""

from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any, Sequence
import zipfile

import streamlit.components.v1 as components


ROOT = Path(__file__).resolve().parent
COMPONENT_DIR = ROOT / "n1_import_component"
EXTENSION_DIR = ROOT / "browser_extension" / "n1bet_importer"

_bridge = components.declare_component(
    "betboy_n1_import_bridge",
    path=str(COMPONENT_DIR),
)


def render_bridge(
    *,
    targets: Sequence[dict[str, Any]],
    sync_nonce: int,
    force_sync: bool,
    last_seen: str,
    key: str,
) -> Any:
    return _bridge(
        targets=list(targets),
        syncNonce=int(sync_nonce),
        forceSync=bool(force_sync),
        lastSeen=str(last_seen or ""),
        default=None,
        key=key,
    )


@lru_cache(maxsize=1)
def extension_archive() -> bytes:
    """Build the unpacked-extension ZIP without writing runtime artifacts."""
    if not EXTENSION_DIR.is_dir():
        raise FileNotFoundError("N1Bet importer extension directory is missing")
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(EXTENSION_DIR.rglob("*")):
            if not path.is_file() or path.name.startswith("."):
                continue
            relative = path.relative_to(EXTENSION_DIR)
            archive.write(path, Path("betboy-n1bet-importer") / relative)
    return output.getvalue()


__all__ = ["EXTENSION_DIR", "extension_archive", "render_bridge"]
