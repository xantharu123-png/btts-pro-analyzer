"""Yield to scheduled BetBoy workers before a discretionary viewer-driven call."""
import subprocess


_WORKERS = frozenset(f"betboy-{name}.service" for name in (
    "wettfinder", "tennis", "esports", "football-shadow", "quotes",
    "redcard-history", "redcard-settlement",
))


def jobs_idle() -> bool:
    """Local read-only probe. No manager or an ambiguous answer never permits HTTP."""
    try:
        result = subprocess.run(
            ["/usr/bin/systemctl", "show", "--no-pager", "-p", "Id", "-p", "LoadState",
             "-p", "ActiveState", *sorted(_WORKERS)],
            capture_output=True, text=True, timeout=1.5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        return False
    if result.returncode:
        return False
    seen = set()
    for block in result.stdout.strip().split("\n\n"):
        pairs = [line.partition("=") for line in block.splitlines()]
        fields = {key: value for key, sep, value in pairs if sep}
        unit = fields.get("Id")
        # A previous failed oneshot is not running; do not suppress the ticker
        # until that worker's next scheduled day. Activating/deactivating still block.
        if (len(pairs) != 3 or len(fields) != 3 or unit not in _WORKERS or unit in seen
                or fields.get("LoadState") != "loaded" or fields.get("ActiveState") not in {"inactive", "failed"}):
            return False
        seen.add(unit)
    return seen == _WORKERS
