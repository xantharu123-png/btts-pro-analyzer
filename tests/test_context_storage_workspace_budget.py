"""Real local namespace accounting; no native quota/free-interval claims."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import os

import pytest

from context_storage_v2 import workspace_budget as owner
from context_storage_v2.contracts import DEFAULT_LIMITS, StorageIntegrityError, StorageLimitError


META = 1024**2
UNIT = 1024**2


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    directory = tmp_path / "whole-job"
    directory.mkdir()
    # Deterministic admission clock for disk-space faults, not a VPS measurement.
    space = SimpleNamespace(free=64 * 1024**3)
    monkeypatch.setattr(owner.shutil, "disk_usage", lambda _path: space)
    return directory, space


def plan(directory, slots=None, **kwargs):
    return owner.WorkspaceBudget(directory,
        [owner.FileSlot("build/main.sqlite", 4*UNIT, True),
         owner.FileSlot("build/main.sqlite-journal", 4*UNIT),
         owner.FileSlot("code.tar.gz", UNIT)] if slots is None else slots,
        directory_metadata_bytes=META, **kwargs)


def test_complete_plan_charges_future_main_journal_archive_and_directories(workspace):
    directory, _space = workspace
    budget = plan(directory)
    initial = budget.check_quiescent()
    assert initial.workspace_ceiling_bytes == 10*UNIT
    assert initial.active_input_ceiling_bytes == 4*UNIT
    assert initial.existing_files == initial.active_input_bytes == 0
    (directory / "build").mkdir()
    (directory / "build/main.sqlite").write_bytes(b"main" * 2048)
    (directory / "build/main.sqlite-journal").write_bytes(b"journal" * 1024)
    (directory / "code.tar.gz").write_bytes(b"archive")
    later = budget.check_quiescent()
    assert later.plan_digest == initial.plan_digest
    assert later.existing_files == 3
    assert later.workspace_bytes + later.remaining_reserved_bytes == 10*UNIT
    assert later.active_input_bytes == owner._size((directory / "build/main.sqlite").stat())


def test_file_deletion_does_not_release_reservation_or_permit_new_attempt(workspace):
    directory, _space = workspace
    budget = plan(directory)
    archive = directory / "code.tar.gz"
    archive.write_bytes(b"partial failed archive")
    populated = budget.check_quiescent()
    archive.unlink()  # Only this test-owned, exact fixture; not an owner operation.
    removed = budget.check_quiescent()
    assert populated.workspace_ceiling_bytes == removed.workspace_ceiling_bytes
    assert removed.remaining_reserved_bytes > populated.remaining_reserved_bytes
    (directory / "retry.tar.gz").write_bytes(b"unreserved")
    with pytest.raises(StorageIntegrityError, match="undeclared"):
        budget.check_quiescent()


def test_all_retry_slots_are_charged_together_before_any_writer(workspace):
    directory, _space = workspace
    limits = replace(DEFAULT_LIMITS, workspace_bytes=4*UNIT)
    with pytest.raises(StorageLimitError, match="whole workspace"):
        plan(directory, [owner.FileSlot(f"attempt{number}/main", UNIT) for number in range(4)], limits=limits)
    assert list(directory.iterdir()) == []


def test_entire_active_input_includes_external_source_and_all_own_indices(workspace, tmp_path):
    directory, _space = workspace
    original = tmp_path / "original.sqlite"
    original.write_bytes(b"retained outside new QA" * 200)
    external_size = owner._size(original.stat())
    inputs = [owner.ExternalInput(original)]
    budget = plan(directory, [owner.FileSlot("index", UNIT, True)], external_inputs=inputs)
    result = budget.check_quiescent()
    assert result.active_input_bytes == external_size
    assert result.active_input_ceiling_bytes == UNIT + external_size
    with pytest.raises(StorageLimitError, match="entire active"):
        plan(directory, [owner.FileSlot("index", UNIT, True)], external_inputs=inputs,
             limits=replace(DEFAULT_LIMITS, input_bytes=UNIT))


@pytest.mark.parametrize("kind", ["different-bytes", "extra-byte", "replacement"])
def test_external_input_must_remain_bound(workspace, tmp_path, kind):
    directory, _space = workspace
    original = tmp_path / "input"
    original.write_bytes(b"original")
    budget = plan(directory, external_inputs=[owner.ExternalInput(original)])
    if kind == "replacement":
        original.rename(tmp_path / "preserved-original")
        original.write_bytes(b"original")
    else:
        original.write_bytes(b"changed!" if kind == "different-bytes" else b"original!")
    with pytest.raises(StorageIntegrityError, match="external"):
        budget.check_quiescent()


def test_workspace_input_cannot_be_hidden_as_external(workspace):
    directory, _space = workspace
    path = directory / "code.tar.gz"
    path.write_bytes(b"payload")
    with pytest.raises(StorageIntegrityError, match="counted as file slots"):
        plan(directory, external_inputs=[owner.ExternalInput(path)])


def test_duplicate_external_source_not_counted_as_two_independent_inputs(workspace, tmp_path):
    directory, _space = workspace
    path = tmp_path / "input"
    path.write_bytes(b"payload")
    with pytest.raises(StorageIntegrityError, match="duplicate external"):
        plan(directory, external_inputs=[owner.ExternalInput(path), owner.ExternalInput(path)])


@pytest.mark.parametrize("name", ["../outside", "/absolute", "a//b", "a/./b", "a/../b",
    "a\\b", "*.db", "a\0b", "C:drive", "a\nb", "a\tb", "a b", "bad.", "NUL",
    "nested/CON.txt", "LPT1", "COM9.txt", "", "a/", "x"*241, 1, None])
def test_ambiguous_or_device_file_slots_fail_before_writes(workspace, name):
    directory, _space = workspace
    with pytest.raises(StorageIntegrityError):
        plan(directory, [owner.FileSlot(name, UNIT)])
    assert list(directory.iterdir()) == []


@pytest.mark.parametrize("slots", [[], (owner.FileSlot("x", UNIT) for _ in range(2)),
    [owner.FileSlot("x", UNIT)] * 4097])
def test_plan_cannot_be_unbounded_or_empty(workspace, slots):
    directory, _space = workspace
    with pytest.raises(StorageLimitError):
        plan(directory, slots)


@pytest.mark.parametrize("slots", [
    [owner.FileSlot("x", UNIT), owner.FileSlot("x", UNIT)],
    [owner.FileSlot("X", UNIT), owner.FileSlot("x", UNIT)],
    [owner.FileSlot("x", UNIT), owner.FileSlot("x/inside", UNIT)],
    [owner.FileSlot("X", UNIT), owner.FileSlot("x/inside", UNIT)],
])
def test_aliases_and_file_directory_collisions_fail(workspace, slots):
    directory, _space = workspace
    with pytest.raises(StorageIntegrityError):
        plan(directory, slots)


@pytest.mark.parametrize("amount", [0, -1, True, False, 1.5, "100", None])
def test_file_ceiling_uses_strict_positive_integers(workspace, amount):
    directory, _space = workspace
    with pytest.raises(StorageLimitError):
        plan(directory, [owner.FileSlot("x", amount)])


@pytest.mark.parametrize("flag", [0, 1, "yes", None])
def test_active_input_membership_is_explicit_boolean(workspace, flag):
    directory, _space = workspace
    with pytest.raises(StorageIntegrityError):
        plan(directory, [owner.FileSlot("x", UNIT, flag)])


@pytest.mark.parametrize("kind", ["file", "directory", "hidden", "extra-journal"])
def test_all_unexpected_workspace_entries_are_failures(workspace, kind):
    directory, _space = workspace
    budget = plan(directory)
    if kind == "directory":
        (directory / "unexpected").mkdir()
    else:
        (directory / (".hidden" if kind == "hidden" else "other-journal" if kind == "extra-journal" else "other")).write_bytes(b"x")
    with pytest.raises(StorageIntegrityError, match="undeclared"):
        budget.check_quiescent()


def test_main_and_journal_have_separate_hard_declared_ceilings(workspace):
    directory, _space = workspace
    budget = plan(directory, [owner.FileSlot("db", UNIT), owner.FileSlot("db-journal", UNIT)])
    (directory / "db-journal").write_bytes(b"j" * (UNIT+1))
    with pytest.raises(StorageLimitError, match="file exceeded"):
        budget.check_quiescent()


def test_admission_uses_all_future_bytes_above_actual_free_reserve(workspace):
    directory, space = workspace
    budget = plan(directory)
    observation = budget.check_quiescent()
    space.free = DEFAULT_LIMITS.min_free_bytes + observation.remaining_reserved_bytes
    assert budget.check_quiescent().free_bytes == space.free
    space.free -= 1
    with pytest.raises(StorageLimitError, match="future whole-job"):
        budget.check_quiescent()


def test_reserve_loss_during_execution_fails_without_writing_or_deleting(workspace):
    directory, space = workspace
    budget = plan(directory)
    space.free = DEFAULT_LIMITS.min_free_bytes-1
    with pytest.raises(StorageLimitError, match="actual free-space"):
        budget.sample_free_space()
    assert list(directory.iterdir()) == []


@pytest.mark.parametrize("field,value", [("directory_metadata_bytes", 4*UNIT),
    ("_workspace_ceiling", 1), ("_input_ceiling", 1), ("plan_digest", "0"*64),
    ("slots", (owner.FileSlot("x", 1),))])
def test_plan_fields_are_bound_after_admission(workspace, field, value):
    directory, _space = workspace
    budget = plan(directory)
    setattr(budget, field, value)
    with pytest.raises(StorageIntegrityError, match="allocation"):
        budget.check_quiescent()


def test_fixed_limits_validator_cannot_be_replaced(workspace):
    directory, _space = workspace
    limits = replace(DEFAULT_LIMITS)
    budget = plan(directory, limits=limits)
    object.__setattr__(limits, "__post_init__", lambda: None)
    object.__setattr__(limits, "workspace_bytes", 100*1024**3)
    with pytest.raises(StorageLimitError):
        budget.check_quiescent()


def test_limits_tightening_during_lifetime_is_still_a_changed_plan(workspace):
    directory, _space = workspace
    limits = replace(DEFAULT_LIMITS)
    budget = plan(directory, limits=limits)
    object.__setattr__(limits, "block_bytes", 4096)
    with pytest.raises(StorageLimitError, match="changed"):
        budget.check_quiescent()


def test_hardlink_is_not_a_new_budget_slot(workspace, tmp_path):
    directory, _space = workspace
    original = tmp_path / "other"
    original.write_bytes(b"unrelated")
    os.link(original, directory / "code.tar.gz")
    with pytest.raises(StorageIntegrityError, match="single-link"):
        plan(directory)
    assert original.read_bytes() == b"unrelated"


def test_workspace_root_replacement_invalidates_observation(workspace, tmp_path):
    directory, _space = workspace
    budget = plan(directory)
    directory.rename(tmp_path / "retained-old-job")
    directory.mkdir()
    with pytest.raises(StorageIntegrityError, match="root identity"):
        budget.check_quiescent()


def test_real_stat_accounting_includes_physical_allocation(workspace):
    directory, _space = workspace
    budget = plan(directory, [owner.FileSlot("x", UNIT)])
    (directory / "x").write_bytes(b"x")
    measured = budget.check_quiescent()
    assert measured.workspace_bytes >= owner._size((directory / "x").stat())
    assert measured.workspace_bytes >= 1


@pytest.mark.parametrize("foreign_directory", [False, True])
def test_other_filesystem_cannot_borrow_root_free_space(workspace, monkeypatch, foreign_directory):
    directory, _space = workspace
    budget = plan(directory)
    nested = directory / "build"
    nested.mkdir()
    database = nested / "main.sqlite"
    database.write_bytes(b"fixture")
    actual_lstat = Path.lstat
    def observed_lstat(path, *args, **kwargs):
        value = actual_lstat(path, *args, **kwargs)
        if path == database or (foreign_directory and path == nested):
            # Explicit device-counter simulation on real Windows fixture
            # files, not an actual native mount or filesystem quota test.
            names = ("st_mode", "st_nlink", "st_size", "st_dev", "st_ino",
                     "st_mtime_ns", "st_ctime_ns", "st_blocks", "st_file_attributes")
            result = {name: getattr(value, name, 0) for name in names}
            result["st_dev"] += 1
            return SimpleNamespace(**result)
        return value
    monkeypatch.setattr(Path, "lstat", observed_lstat)
    with pytest.raises(StorageIntegrityError, match="another filesystem"):
        budget.check_quiescent()
