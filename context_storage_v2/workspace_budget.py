"""Closed, whole-job allocation accounting for the explicit C preparation.

Every possible new file (including archives, journals and failed attempts) has
one predeclared ceiling. Deleting a file does NOT release that reservation.
The complete active input set additionally includes all declared external inputs.

This is the accounting/admission component, NOT a filesystem sandbox or quota.
The native owner must hold the exclusive job lock, seal external inputs, limit
each writer to its exact file slots and enforce their ceilings BEFORE writing.
In particular SQLite TEMP/open-unlinked files cannot be made safe by a disk walk:
the separately reviewed native writer profile must exclude them from disk or
account for them. A returned observation is neither B authority nor a certificate
of an unobserved interval. Scans require quiescent writers; free-space sampling
is also required during execution. No files are created, deleted or resized here.
"""
from dataclasses import dataclass, fields
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat

from .contracts import DEFAULT_LIMITS, StorageIntegrityError, StorageLimitError, StorageLimits


FORMAT = "context-whole-workspace-plan-v2"
MAX_FILES = 4096
MAX_ENTRIES = 100000
MAX_DEPTH = 32


@dataclass(frozen=True)
class FileSlot:
    """An exact workspace-relative POSIX name, never a prefix or wildcard."""
    name: str
    ceiling_bytes: int
    active_input: bool = False


@dataclass(frozen=True)
class ExternalInput:
    """A separately sealed, existing regular input outside this new workspace."""
    path: Path


@dataclass(frozen=True)
class SpaceObservation:
    plan_digest: str
    workspace_bytes: int
    workspace_ceiling_bytes: int
    active_input_bytes: int
    active_input_ceiling_bytes: int
    remaining_reserved_bytes: int
    free_bytes: int
    existing_files: int


def _positive_integer(value, name):
    if type(value) is not int or value <= 0:
        raise StorageLimitError(name + " must be a positive integer")


def _regular(path):
    value = path.lstat()
    if (not stat.S_ISREG(value.st_mode) or value.st_nlink != 1
            or getattr(value, "st_file_attributes", 0) & 0x400):
        raise StorageIntegrityError("workspace budget requires single-link regular files")
    return value


def _size(value):
    return max(value.st_size, getattr(value, "st_blocks", 0) * 512)


def _file_identity(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_nlink, value.st_size,
            value.st_mtime_ns, value.st_ctime_ns, _size(value))


def _directory(path):
    if not path.is_absolute() or ".." in path.parts:
        raise StorageIntegrityError("workspace budget requires an absolute unambiguous path")
    # Check the supplied path before resolving it: resolve() would erase a link.
    for component in reversed((path, *path.parents)):
        value = component.lstat()
        if (not stat.S_ISDIR(value.st_mode)
                or getattr(value, "st_file_attributes", 0) & 0x400):
            raise StorageIntegrityError("workspace budget directory contains a link or reparse point")
    value = path.lstat()
    return value.st_dev, value.st_ino, value.st_mode


def _slot_name(name):
    if (type(name) is not str or not name or len(name) > 240
            or re.fullmatch(r"[A-Za-z0-9._/-]+", name) is None):
        raise StorageIntegrityError("workspace slot has an ambiguous name")
    parts = name.split("/")
    if (len(parts) > MAX_DEPTH or any(not part or part in {".", ".."}
            or part.endswith((" ", ".")) for part in parts)
            or PurePosixPath(name).is_absolute()):
        raise StorageIntegrityError("workspace slot must be an exact relative file path")
    devices = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
               *(f"LPT{i}" for i in range(1, 10))}
    if any(part.split(".", 1)[0].upper() in devices for part in parts):
        raise StorageIntegrityError("workspace slot names a platform device")
    return name


class WorkspaceBudget:
    """A fixed allocation plan; there is deliberately no release/reset API.

    directory_metadata_bytes reserves all directories and their filesystem
    allocation. File ceilings must include allocation rounding, not only payload
    bytes. This conservative fixed plan remains charged for the whole job,
    including closed/failed/retried attempts and already-created QA files.
    """
    def __init__(self, directory, slots, *, external_inputs=(),
                 directory_metadata_bytes=1024**2, limits=DEFAULT_LIMITS):
        if type(limits) is not StorageLimits:
            raise StorageLimitError("workspace budget needs exact C limits")
        StorageLimits.__post_init__(limits)
        self.directory = Path(directory)
        self._directory_id = _directory(self.directory)
        self.limits = limits
        self._limits_id = tuple(getattr(limits, item.name) for item in fields(StorageLimits))
        _positive_integer(directory_metadata_bytes, "directory metadata reserve")
        if directory_metadata_bytes > limits.workspace_bytes:
            raise StorageLimitError("directory metadata reserve exceeds the whole workspace")
        self.directory_metadata_bytes = directory_metadata_bytes
        # Reject an unbounded iterator; the complete plan itself is explicit.
        if type(slots) not in (tuple, list) or not 0 < len(slots) <= MAX_FILES:
            raise StorageLimitError("workspace needs a bounded complete slot plan")
        self.slots = tuple(slots)
        names, folders, active = set(), set(), 0
        reserved = directory_metadata_bytes
        for slot in self.slots:
            if type(slot) is not FileSlot or type(slot.active_input) is not bool:
                raise StorageIntegrityError("workspace needs typed file slots")
            name = _slot_name(slot.name)
            _positive_integer(slot.ceiling_bytes, "file reservation")
            # Casefold also prevents aliases on the Windows development host.
            folded = name.casefold()
            if folded in names:
                raise StorageIntegrityError("duplicate workspace slot")
            names.add(folded)
            folders.update(str(parent).casefold() for parent in PurePosixPath(name).parents
                           if str(parent) != ".")
            reserved += slot.ceiling_bytes
            active += slot.ceiling_bytes if slot.active_input else 0
        if names & folders:
            raise StorageIntegrityError("workspace file slot is another slot's directory")
        if reserved > limits.workspace_bytes:
            raise StorageLimitError("all file slots exceed the whole workspace allocation")
        if type(external_inputs) not in (tuple, list) or len(external_inputs) > MAX_FILES:
            raise StorageLimitError("external input set is not bounded")
        self.external_inputs = tuple(external_inputs)
        external = []
        seen_paths, seen_inodes = set(), set()
        for item in self.external_inputs:
            if type(item) is not ExternalInput or not isinstance(item.path, Path):
                raise StorageIntegrityError("external input requires an exact typed path")
            path = item.path
            _directory(path.parent)
            if path.is_relative_to(self.directory):
                raise StorageIntegrityError("workspace inputs must be counted as file slots")
            value = _regular(path)
            key, inode = str(path).casefold(), (value.st_dev, value.st_ino)
            if key in seen_paths or inode in seen_inodes:
                raise StorageIntegrityError("duplicate external input")
            seen_paths.add(key)
            seen_inodes.add(inode)
            external.append((str(path), _file_identity(value)))
            active += _size(value)
        if active > limits.input_bytes:
            raise StorageLimitError("entire active input set exceeds C admission")
        self._external = tuple(external)
        self._workspace_ceiling = reserved
        self._input_ceiling = active
        self._plan_bytes = self._encode_plan()
        self.plan_digest = hashlib.sha256(self._plan_bytes).hexdigest()
        self.check_quiescent()

    def _encode_plan(self):
        return json.dumps({"format": FORMAT, "directory": str(self.directory),
            "directory_id": self._directory_id, "metadata": self.directory_metadata_bytes,
            "slots": [(slot.name, slot.ceiling_bytes, slot.active_input) for slot in self.slots],
            "external_paths": [str(item.path) for item in self.external_inputs],
            "external_identities": self._external, "limits": self._limits_id,
            "workspace_ceiling": self._workspace_ceiling,
            "input_ceiling": self._input_ceiling},
            sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")

    def _check_plan(self):
        if type(self.limits) is not StorageLimits:
            raise StorageLimitError("workspace limits were replaced")
        StorageLimits.__post_init__(self.limits)
        if tuple(getattr(self.limits, item.name) for item in fields(StorageLimits)) != self._limits_id:
            raise StorageLimitError("workspace limits changed")
        if WorkspaceBudget._encode_plan(self) != self._plan_bytes:
            raise StorageIntegrityError("workspace allocation plan changed")
        if self.plan_digest != hashlib.sha256(self._plan_bytes).hexdigest():
            raise StorageIntegrityError("workspace allocation identity changed")
        if _directory(self.directory) != self._directory_id:
            raise StorageIntegrityError("workspace root identity changed")
        for name, expected in self._external:
            path = Path(name)
            _directory(path.parent)
            if _file_identity(_regular(path)) != expected:
                raise StorageIntegrityError("external sealed input changed")

    def sample_free_space(self):
        """Observe actual current free space; never stand in for a write quota."""
        WorkspaceBudget._check_plan(self)
        free = shutil.disk_usage(self.directory).free
        if type(free) is not int or free < self.limits.min_free_bytes:
            raise StorageLimitError("actual free-space reserve was lost")
        return free

    def check_quiescent(self) -> SpaceObservation:
        """Reconcile the complete workspace before/during quiescent job steps.

        The native owner must not run a writer concurrently with this scan. All
        unallocated future bytes must still fit ABOVE the actual free reserve.
        Unknown/extra files are errors, not silently assigned a new free budget.
        """
        WorkspaceBudget._check_plan(self)
        slots = {slot.name: slot for slot in self.slots}
        allowed_dirs = {str(parent) for name in slots for parent in PurePosixPath(name).parents}
        found, identities, directories, count, metadata = set(), [], [], 0, _size(self.directory.lstat())
        actual_files = active = 0

        def visit(path, depth):
            nonlocal count, metadata, actual_files, active
            if depth > MAX_DEPTH:
                raise StorageLimitError("workspace directory depth exceeded")
            directory_id = _directory(path)
            if directory_id[0] != self._directory_id[0]:
                raise StorageIntegrityError("workspace directory is on another filesystem")
            directory_epoch = _file_identity(path.lstat())
            directories.append((path, directory_epoch))
            with os.scandir(path) as entries:
                for entry in entries:
                    count += 1
                    if count > MAX_ENTRIES:
                        raise StorageLimitError("workspace entry count exceeded")
                    candidate = Path(entry.path)
                    relative = candidate.relative_to(self.directory).as_posix()
                    value = candidate.lstat()
                    if stat.S_ISDIR(value.st_mode) and not getattr(value, "st_file_attributes", 0) & 0x400:
                        if relative not in allowed_dirs:
                            raise StorageIntegrityError("workspace contains an undeclared directory")
                        metadata += _size(value)
                        visit(candidate, depth + 1)
                    else:
                        value = _regular(candidate)
                        if value.st_dev != self._directory_id[0]:
                            raise StorageIntegrityError("workspace file is on another filesystem")
                        if relative not in slots:
                            raise StorageIntegrityError("workspace contains an undeclared file")
                        size = _size(value)
                        if size > slots[relative].ceiling_bytes:
                            raise StorageLimitError("workspace file exceeded its fixed reservation")
                        found.add(relative)
                        identities.append((candidate, _file_identity(value)))
                        actual_files += size
                        active += size if slots[relative].active_input else 0
            if _directory(path) != directory_id:
                raise StorageIntegrityError("workspace directory changed during reconciliation")

        visit(self.directory, 0)
        if metadata > self.directory_metadata_bytes:
            raise StorageLimitError("workspace directory metadata exceeded its reservation")
        for path, expected in identities:
            if _file_identity(_regular(path)) != expected:
                raise StorageIntegrityError("workspace writer was not quiescent")
        for path, expected in directories:
            if _file_identity(path.lstat()) != expected:
                raise StorageIntegrityError("workspace directory changed during reconciliation")
        WorkspaceBudget._check_plan(self)
        external = sum(identity[-1] for _name, identity in self._external)
        actual = actual_files + metadata
        remaining = self._workspace_ceiling - actual
        free = WorkspaceBudget.sample_free_space(self)
        if free < self.limits.min_free_bytes + remaining:
            raise StorageLimitError("future whole-job allocations cannot retain the actual free reserve")
        return SpaceObservation(self.plan_digest, actual, self._workspace_ceiling,
            active + external, self._input_ceiling, remaining, free, len(found))
