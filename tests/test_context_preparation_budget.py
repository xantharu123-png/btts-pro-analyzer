"""Pure accounting and real portable FD I/O; native Linux claims are separate."""
from dataclasses import replace
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

import pytest

import context_preparation_budget as budget


NS = 10**9
BOOT = "11111111-2222-3333-4444-555555555555"


@pytest.fixture
def identity():
    return budget.BudgetIdentity(*(char * 64 for char in "abcde"))


class ProtocolClock:
    """Explicit simulated OS observations, not native clock evidence."""
    def __init__(self):
        self.boot, self.now, self.offset, self.width = BOOT, 100 * NS, 1700000000 * NS, 0

    def sample(self):
        return budget.ClockSample(self.boot, self.now, self.now + self.offset, self.now + self.width)


@pytest.fixture
def clock(monkeypatch):
    clock = ProtocolClock()
    monkeypatch.setattr(budget, "_system_clock", clock.sample)
    return clock


def attach_local(path, identity, *, create):
    """Actual local file/fsync, NO native flock or parent-directory assurance."""
    flags = os.O_RDWR | getattr(os, "O_BINARY", 0)
    if create:
        flags |= os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    try:
        store = budget._FileJournal(fd)
    except BaseException:
        os.close(fd)
        raise
    return budget.PreparationBudget._attach(store, identity, create=create)


@pytest.fixture
def local(tmp_path, identity, clock):
    path = tmp_path / "portable-accounting.jsonl"
    handle = attach_local(path, identity, create=True)
    try:
        yield path, handle
    finally:
        handle.close()


def test_local_reservation_is_synced_before_ticket_return_and_claim_settles_once(local, identity, monkeypatch):
    path, handle = local
    events = []
    original = os.fsync
    def synced(fd):
        events.append(path.read_bytes())
        original(fd)
    monkeypatch.setattr(os, "fsync", synced)
    ticket = handle.reserve("1" * 64, 300 * NS)
    assert events and b'"event":"reserve"' in events[-1]
    state = budget._replay(path.read_bytes(), identity)
    assert state.pending == ticket
    assert handle.snapshot().charged_cpu_ns == 300 * NS
    outcome = handle.settle_claim(ticket, cumulative_cpu_ns=25 * NS, measurement_digest="2" * 64)
    assert outcome.settled_cpu_ns == 25 * NS
    assert outcome.charged_cpu_ns == 25 * NS
    assert outcome.remaining_cpu_ns == 1775 * NS
    before = path.read_bytes()
    with pytest.raises(budget.BudgetIntegrityError):
        handle.settle_claim(ticket, cumulative_cpu_ns=25 * NS, measurement_digest="2" * 64)
    assert path.read_bytes() == before


def test_retry_and_reopen_keep_original_deadline_and_cumulative_cpu(local, identity, clock):
    path, handle = local
    deadline = handle.snapshot().deadline_boot_ns
    first = handle.reserve("1" * 64, 300 * NS)
    handle.settle_claim(first, cumulative_cpu_ns=200 * NS, measurement_digest="2" * 64)
    handle.close()
    clock.now += 1700 * NS
    with attach_local(path, identity, create=False) as reopened:
        assert reopened.snapshot().deadline_boot_ns == deadline
        assert reopened.snapshot().settled_cpu_ns == 200 * NS
        retry = reopened.reserve("1" * 64, 300 * NS)
        assert retry.reservation_digest != first.reservation_digest
        result = reopened.settle_claim(retry, cumulative_cpu_ns=450 * NS, measurement_digest="3" * 64)
        assert result.remaining_cpu_ns == 1350 * NS
        assert result.deadline_boot_ns == deadline


def test_pending_crash_retains_full_charge_and_refuses_recovered_settlement(local, identity):
    path, handle = local
    ticket = handle.reserve("1" * 64, 300 * NS)
    handle.close()
    with attach_local(path, identity, create=False) as recovered:
        snapshot = recovered.snapshot()
        assert snapshot.status == "stopped"
        assert snapshot.charged_cpu_ns == 300 * NS
        assert snapshot.pending == ticket
        before = path.read_bytes()
        with pytest.raises(budget.BudgetStopped):
            recovered.reserve("3" * 64, NS)
        with pytest.raises(budget.BudgetStopped):
            recovered.settle_claim(ticket, cumulative_cpu_ns=NS, measurement_digest="4" * 64)
        assert path.read_bytes() == before


def test_all_six_full_portions_exhaust_one_lifecycle_budget(local):
    path, handle = local
    for number in range(6):
        ticket = handle.reserve("1" * 64, 300 * NS)
        handle.settle_claim(ticket, cumulative_cpu_ns=(number + 1) * 300 * NS,
                            measurement_digest=f"{number:064x}")
    assert handle.snapshot().remaining_cpu_ns == 0
    before = path.read_bytes()
    with pytest.raises(budget.BudgetExceeded):
        handle.reserve("2" * 64, 1)
    assert path.read_bytes() == before


@pytest.mark.parametrize("value", [True, False, 0, -1, 0.5, "100", None, budget.PORTION_CPU_NS + 1, 2**80])
def test_reservation_requires_exact_bounded_positive_integer_ns(local, value):
    path, handle = local
    before = path.read_bytes()
    with pytest.raises(budget.BudgetIntegrityError):
        handle.reserve("1" * 64, value)
    assert path.read_bytes() == before


@pytest.mark.parametrize("value", [True, False, -1, 0.5, "100", None, 301 * NS, 2**80])
def test_unmeasurable_or_overrun_claim_permanently_stops_without_refund(local, identity, value):
    path, handle = local
    ticket = handle.reserve("1" * 64, 300 * NS)
    with pytest.raises((budget.BudgetIntegrityError, budget.BudgetExceeded)):
        handle.settle_claim(ticket, cumulative_cpu_ns=value, measurement_digest="2" * 64)
    snapshot = handle.snapshot()
    assert snapshot.status == "stopped"
    assert snapshot.charged_cpu_ns == 300 * NS
    assert snapshot.settled_cpu_ns == 0
    handle.close()
    with attach_local(path, identity, create=False) as reopened:
        with pytest.raises(budget.BudgetStopped):
            reopened.reserve("3" * 64, 1)


def test_cumulative_measurement_cannot_roll_back_or_reuse_an_old_receipt(local):
    _path, handle = local
    first = handle.reserve("1" * 64, 100 * NS)
    handle.settle_claim(first, cumulative_cpu_ns=50 * NS, measurement_digest="2" * 64)
    second = handle.reserve("1" * 64, 100 * NS)
    with pytest.raises(budget.BudgetIntegrityError, match="already consumed"):
        handle.settle_claim(second, cumulative_cpu_ns=70 * NS, measurement_digest="2" * 64)
    assert handle.snapshot().charged_cpu_ns == 150 * NS
    with pytest.raises(budget.BudgetExceeded):
        handle.settle_claim(second, cumulative_cpu_ns=49 * NS, measurement_digest="3" * 64)
    assert handle.snapshot().status == "stopped"


@pytest.mark.parametrize("field,value", [
    ("identity_digest", "f" * 64), ("reservation_digest", "f" * 64),
    ("sequence", True), ("portion_digest", "f" * 64), ("cpu_ns", NS),
    ("deadline_boot_ns", 1),
])
def test_foreign_changed_or_stale_ticket_cannot_settle_current_reservation(local, field, value):
    path, handle = local
    ticket = handle.reserve("1" * 64, 100 * NS)
    before = path.read_bytes()
    with pytest.raises(budget.BudgetIntegrityError):
        handle.settle_claim(replace(ticket, **{field: value}), cumulative_cpu_ns=50 * NS, measurement_digest="2" * 64)
    assert path.read_bytes() == before


def test_returned_frozen_ticket_and_identity_are_not_internal_mutation_authority(local, identity):
    _path, handle = local
    original = identity.input_digest
    object.__setattr__(identity, "input_digest", "f" * 64)
    ticket = handle.reserve("1" * 64, 100 * NS)
    object.__setattr__(ticket, "cpu_ns", 300 * NS)
    with pytest.raises(budget.BudgetIntegrityError):
        handle.settle_claim(ticket, cumulative_cpu_ns=150 * NS, measurement_digest="2" * 64)
    state = handle.snapshot()
    assert state.pending.cpu_ns == 100 * NS
    assert state.identity_digest == budget._hash(budget._identity(replace(identity, input_digest=original)))


@pytest.mark.parametrize("field", [field.name for field in budget.fields(budget.BudgetIdentity)])
def test_every_exact_identity_dimension_is_required_on_reopen(local, identity, field):
    path, handle = local
    handle.close()
    before = path.read_bytes()
    with pytest.raises(budget.BudgetIntegrityError, match="identity mismatch"):
        attach_local(path, replace(identity, **{field: "f" * 64}), create=False)
    assert path.read_bytes() == before


@pytest.mark.parametrize("change", ["boot", "boot_rollback", "wall_rollback", "wall_forward", "too_wide", "deadline"])
def test_clock_or_deadline_violation_is_persistent_stop_not_a_new_open_budget(local, identity, clock, change):
    path, handle = local
    old = clock.boot, clock.now, clock.offset, clock.width
    if change == "boot":
        clock.boot = "66666666-2222-3333-4444-555555555555"
    elif change == "boot_rollback":
        clock.now -= 1
    elif change == "wall_rollback":
        clock.offset -= 1
    elif change == "wall_forward":
        clock.offset += 1
    elif change == "too_wide":
        clock.width = budget.MAX_CLOCK_SAMPLE_NS + 1
    else:
        clock.now += budget.TOTAL_ELAPSED_NS
    with pytest.raises(budget.BudgetError):
        handle.reserve("1" * 64, NS)
    clock.boot, clock.now, clock.offset, clock.width = old
    assert handle.snapshot().status == "stopped"
    handle.close()
    with attach_local(path, identity, create=False) as reopened:
        with pytest.raises(budget.BudgetStopped):
            reopened.reserve("1" * 64, NS)


def test_deadline_crossed_while_syncing_reservation_never_returns_ticket(local, identity, clock, monkeypatch):
    path, handle = local
    original = os.fsync
    def delayed_sync(fd):
        original(fd)
        clock.now += budget.TOTAL_ELAPSED_NS
    monkeypatch.setattr(os, "fsync", delayed_sync)
    with pytest.raises(budget.BudgetExceeded):
        handle.reserve("1" * 64, 300 * NS)
    state = budget._replay(path.read_bytes(), identity)
    assert state.pending.cpu_ns == 300 * NS
    assert state.stopped


def test_nonjournalized_post_sync_clock_observation_cannot_roll_back(local, clock, monkeypatch):
    _path, handle = local
    original = os.fsync
    def delayed_sync(fd):
        original(fd)
        clock.now += 10 * NS
    monkeypatch.setattr(os, "fsync", delayed_sync)
    ticket = handle.reserve("1" * 64, NS)
    clock.now -= NS  # Still later than the durable reservation's clock.
    with pytest.raises(budget.BudgetStopped, match="rollback"):
        handle.settle_claim(ticket, cumulative_cpu_ns=1, measurement_digest="2" * 64)
    assert handle.snapshot().charged_cpu_ns == NS
    assert handle.snapshot().status == "stopped"


@pytest.mark.parametrize("field,value", [
    ("boot_before_ns", True), ("realtime_ns", 1.0), ("boot_after_ns", "100"),
    ("boot_id", "A" + BOOT[1:]), ("boot_id", BOOT + "\x00"),
])
def test_clock_observations_require_exact_bounded_identity_and_integer_types(local, monkeypatch, field, value):
    _path, handle = local
    sample = budget.ClockSample(BOOT, 100 * NS, (1700000000 + 100) * NS, 100 * NS)
    monkeypatch.setattr(budget, "_system_clock", lambda: replace(sample, **{field: value}))
    with pytest.raises(budget.BudgetIntegrityError):
        handle.reserve("1" * 64, NS)
    assert handle.snapshot().status == "stopped"


def test_same_handle_parallel_operations_refuse_before_second_write(local, monkeypatch):
    path, handle = local
    entered, release, outcomes = threading.Event(), threading.Event(), []
    original = os.fsync
    def paused_sync(fd):
        entered.set()
        assert release.wait(timeout=10)
        original(fd)
    def reserve_once():
        try:
            outcomes.append(handle.reserve("1" * 64, NS))
        except BaseException as exc:
            outcomes.append(exc)
    monkeypatch.setattr(os, "fsync", paused_sync)
    worker = threading.Thread(target=reserve_once)
    worker.start()
    try:
        assert entered.wait(timeout=10)
        before = path.read_bytes()
        for operation in (lambda: handle.reserve("2" * 64, NS), handle.close, handle.snapshot):
            with pytest.raises(budget.BudgetBusy, match="operation"):
                operation()
        assert path.read_bytes() == before
    finally:
        release.set()
        worker.join(timeout=10)
    assert not worker.is_alive()
    assert len(outcomes) == 1 and type(outcomes[0]) is budget.Reservation
    assert handle.snapshot().pending == outcomes[0]


def test_positive_clock_observation_width_remains_valid_across_durable_records(tmp_path, identity, monkeypatch):
    now = 100 * NS
    def bracketed_clock():
        nonlocal now
        now += 1_000_000
        return budget.ClockSample(BOOT, now, now + 500 + 1700000000 * NS, now + 1000)
    monkeypatch.setattr(budget, "_system_clock", bracketed_clock)
    path = tmp_path / "positive-width.jsonl"
    with attach_local(path, identity, create=True) as handle:
        deadline = handle.snapshot().deadline_boot_ns
        ticket = handle.reserve("1" * 64, NS)
        handle.settle_claim(ticket, cumulative_cpu_ns=1, measurement_digest="2" * 64)
    now += 1000 * NS
    with attach_local(path, identity, create=False) as reopened:
        assert reopened.snapshot().deadline_boot_ns == deadline
        ticket = reopened.reserve("1" * 64, NS)
        assert reopened.settle_claim(ticket, cumulative_cpu_ns=2, measurement_digest="3" * 64).settled_cpu_ns == 2


def test_failed_initialization_preserves_empty_file_and_releases_local_owner(tmp_path, identity, monkeypatch):
    path = tmp_path / "failed-init.jsonl"
    monkeypatch.setattr(budget, "_system_clock", lambda: budget.ClockSample(BOOT, True, 1, 1))
    with pytest.raises(budget.BudgetIntegrityError):
        attach_local(path, identity, create=True)
    assert path.exists() and path.read_bytes() == b""
    with pytest.raises(budget.BudgetIntegrityError, match="empty"):
        attach_local(path, identity, create=False)
    with pytest.raises(FileExistsError):
        attach_local(path, identity, create=True)
    assert path.read_bytes() == b""


def test_empty_missing_or_partial_existing_journal_is_never_initialized(tmp_path, identity, clock):
    missing = tmp_path / "missing.jsonl"
    with pytest.raises(FileNotFoundError):
        attach_local(missing, identity, create=False)
    assert not missing.exists()
    for index, data in enumerate((b"", b"{", b'{"record":{}}')):
        path = tmp_path / f"corrupt-{index}.jsonl"
        path.write_bytes(data)
        with pytest.raises(budget.BudgetIntegrityError):
            attach_local(path, identity, create=False)
        assert path.read_bytes() == data
        with pytest.raises(FileExistsError):
            attach_local(path, identity, create=True)


@pytest.mark.parametrize("mutation", ["truncated", "duplicate", "reordered", "wrong_hash", "extra_key", "float", "bool", "oversized_line", "too_many"])
def test_bounded_closed_journal_parser_rejects_corruption_without_repair(local, identity, mutation):
    path, handle = local
    ticket = handle.reserve("1" * 64, NS)
    handle.settle_claim(ticket, cumulative_cpu_ns=NS, measurement_digest="2" * 64)
    handle.close()
    original = path.read_bytes()
    lines = original.splitlines(keepends=True)
    if mutation == "truncated":
        changed = original[:-1]
    elif mutation == "duplicate":
        changed = original + lines[-1]
    elif mutation == "reordered":
        changed = lines[0] + lines[2] + lines[1]
    elif mutation == "oversized_line":
        changed = b" " * budget.MAX_RECORD_BYTES + b"\n"
    elif mutation == "too_many":
        changed = b"{}\n" * (budget.MAX_RECORDS + 1)
    else:
        value = json.loads(lines[0])
        if mutation == "wrong_hash":
            value["digest"] = "f" * 64
        elif mutation == "extra_key":
            value["record"]["native_verified"] = True
            value["digest"] = budget._hash(value["record"])
        else:
            value["record"]["version"] = 1.0 if mutation == "float" else True
            value["digest"] = budget._hash(value["record"])
        changed = budget._canonical(value) + b"\n" + b"".join(lines[1:])
    path.write_bytes(changed)
    with pytest.raises(budget.BudgetError):
        attach_local(path, identity, create=False)
    assert path.read_bytes() == changed


def test_partial_real_write_failure_preserves_bytes_and_blocks_any_recovery(local, identity, monkeypatch):
    path, handle = local
    before = path.read_bytes()
    original, calls = os.write, 0
    def failing(fd, data):
        nonlocal calls
        calls += 1
        if calls == 1:
            return original(fd, data[:17])
        raise OSError("injected failure after actual partial file write")
    monkeypatch.setattr(os, "write", failing)
    with pytest.raises(budget.BudgetIOError):
        handle.reserve("1" * 64, NS)
    damaged = path.read_bytes()
    assert damaged.startswith(before) and len(damaged) == len(before) + 17
    handle.close()
    with pytest.raises(budget.BudgetIntegrityError):
        attach_local(path, identity, create=False)
    assert path.read_bytes() == damaged


def test_fsync_failure_after_complete_reserve_never_authorizes_execution(local, identity, monkeypatch):
    path, handle = local
    def failing(_fd):
        raise OSError("injected sync failure; not native durability evidence")
    monkeypatch.setattr(os, "fsync", failing)
    with pytest.raises(budget.BudgetIOError):
        handle.reserve("1" * 64, NS)
    assert budget._replay(path.read_bytes(), identity).pending.cpu_ns == NS
    handle.close()
    with attach_local(path, identity, create=False) as reopened:
        assert reopened.snapshot().status == "stopped"
        with pytest.raises(budget.BudgetStopped):
            reopened.reserve("2" * 64, NS)


def test_same_process_parallel_owners_and_foreign_descriptor_writes_are_rejected(local, identity):
    path, handle = local
    with pytest.raises(budget.BudgetBusy):
        attach_local(path, identity, create=False)
    before = path.read_bytes()
    with open(path, "ab") as outsider:
        outsider.write(b"\n")
    with pytest.raises(budget.BudgetIntegrityError):
        handle.reserve("1" * 64, NS)
    assert path.read_bytes() == before + b"\n"


def test_bounded_record_capacity_is_not_reset_or_compacted(local):
    path, handle = local
    for number in range(127):
        ticket = handle.reserve("1" * 64, 1)
        handle.settle_claim(ticket, cumulative_cpu_ns=number + 1, measurement_digest=f"{number:064x}")
    before = path.read_bytes()
    with pytest.raises(budget.BudgetExceeded, match="capacity"):
        handle.reserve("1" * 64, 1)
    assert path.read_bytes() == before
    assert handle.snapshot().record_count == 255


def test_stop_unknown_is_terminal_and_never_refunds_pending_charge(local):
    _path, handle = local
    handle.reserve("1" * 64, 300 * NS)
    result = handle.stop_unmeasured()
    assert result.status == "stopped"
    assert result.charged_cpu_ns == 300 * NS
    with pytest.raises(budget.BudgetStopped):
        handle.reserve("1" * 64, NS)


def test_public_api_has_no_root_or_measurement_attestation_boolean():
    for method in (budget.PreparationBudget.create, budget.PreparationBudget.open_existing,
                   budget.PreparationBudget.reserve, budget.PreparationBudget.settle_claim):
        assert not ({"verified", "root_verified", "complete", "measured", "native", "authorized"} & set(inspect.signature(method).parameters))
    assert "NOT measurement proof" in budget.PreparationBudget.settle_claim.__doc__


@pytest.mark.skipif(sys.platform == "linux", reason="non-Linux fail-closed entrypoint")
def test_native_api_does_not_silently_use_portable_test_assurance(identity):
    with pytest.raises(budget.NativeBudgetUnavailable):
        budget.PreparationBudget.create(0, identity)


@pytest.mark.skipif(sys.platform != "linux", reason="requires real Linux flock, directory fsync and boot clock")
def test_native_linux_locked_fd_roundtrip_and_cross_process_exclusion(tmp_path, identity):
    directory = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with budget.PreparationBudget.create(directory, identity) as handle:
            ticket = handle.reserve("1" * 64, NS)
            code = "import os,sys; import context_preparation_budget as b; d=os.open(sys.argv[1],os.O_RDONLY|os.O_DIRECTORY); i=b.BudgetIdentity(*[c*64 for c in 'abcde']);\ntry: b.PreparationBudget.open_existing(d,i)\nexcept b.BudgetBusy: sys.exit(7)\nsys.exit(2)"
            result = subprocess.run([sys.executable, "-c", code, str(tmp_path)],
                                    cwd=Path(budget.__file__).parent, timeout=15, capture_output=True)
            assert result.returncode == 7, result.stderr.decode("utf-8", errors="replace")
            handle.settle_claim(ticket, cumulative_cpu_ns=1, measurement_digest="2" * 64)
        with budget.PreparationBudget.open_existing(directory, identity) as reopened:
            assert reopened.snapshot().settled_cpu_ns == 1
    finally:
        os.close(directory)
