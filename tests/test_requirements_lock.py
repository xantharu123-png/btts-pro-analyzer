"""requirements.lock must stay the exact, complete pin set of requirements.txt (Audit 25.10.2026 D7).

CI installs the lock, so a requirement that is missing from it or pinned outside its range would
make CI test a different environment than the one requirements.txt declares.
"""
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]


def _entries(path):
    lines = (line.strip() for line in path.read_text(encoding="utf-8").splitlines())
    return [line for line in lines if line and not line.startswith("#")]


def test_lock_pins_every_requirement_inside_its_declared_range():
    pins = {}
    for entry in _entries(ROOT / "requirements.lock"):
        requirement = Requirement(entry)
        specifiers = list(requirement.specifier)
        assert len(specifiers) == 1 and specifiers[0].operator == "==", entry
        name = canonicalize_name(requirement.name)
        assert name not in pins, f"duplicate pin {entry}"
        pins[name] = specifiers[0].version

    for entry in _entries(ROOT / "requirements.txt"):
        requirement = Requirement(entry)
        name = canonicalize_name(requirement.name)
        assert name in pins, f"{requirement.name} is not pinned in requirements.lock"
        assert requirement.specifier.contains(pins[name], prereleases=True), (entry, pins[name])


def test_ci_installs_the_lock():
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")

    assert "-r requirements.txt" not in workflow
    assert workflow.count("python -m pip install -r requirements.lock") == workflow.count("actions/setup-python")
    assert "cache-dependency-path: requirements.txt" not in workflow
