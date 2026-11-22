"""An open tab must never take quota away from an already running scheduled worker."""
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest


UNITS = ('wettfinder', 'quotes', 'football-shadow', 'tennis', 'esports',
         'redcard-history', 'redcard-settlement')


def rows(*, busy=None, missing=None, load="loaded"):
    return "\n\n".join(f"Id=betboy-{name}.service\nLoadState={load}\nActiveState="
                       + ("activating" if name == busy else "inactive")
                       for name in UNITS if name != missing)


@pytest.mark.parametrize("output,allowed", [
    (rows(), True), (rows().replace("inactive", "failed", 1), True),
    (rows(busy="quotes"), False), (rows(busy="football-shadow"), False),
    (rows(missing="quotes"), False), (rows(load="not-found"), False),
    (rows() + "\n\n" + rows().split("\n\n")[0], False), ("", False)])
def test_all_regular_workers_must_be_known_and_idle(output, allowed):
    from live_football_readiness import jobs_idle
    with patch('live_football_readiness.subprocess.run', return_value=SimpleNamespace(
            stdout=output, returncode=0)) as run:
        assert jobs_idle() is allowed
        args, opts = run.call_args
        assert {a for a in args[0] if a.endswith('.service')} == {f'betboy-{name}.service' for name in UNITS}
        assert opts["timeout"] <= 2


@pytest.mark.parametrize("failure", [FileNotFoundError(), subprocess.TimeoutExpired("systemctl", 1)])
def test_no_service_manager_means_no_feed_requests(failure):
    from live_football_readiness import jobs_idle
    with patch('live_football_readiness.subprocess.run', side_effect=failure):
        assert not jobs_idle()
