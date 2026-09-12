"""Bounded canonical C2 bytes without changing the scalar reference reader.

This is a separate read interface, not a trust/approval token or a standalone
opener.  The caller keeps exclusive ownership of the same tracked connection and
transaction until exhaustion.  Whole-set validation precedes even the opening
bracket; every public chunk and the terminal boundary recheck that generation,
schema and the existing local resource envelope.  These checks do not establish
a global disk quota, native RSS/CPU acceptance, or B verification authority.
"""
from __future__ import annotations

from dataclasses import fields
import hashlib
import sqlite3
from typing import Iterator

from . import refs
from .contracts import DEFAULT_LIMITS, StorageIntegrityError, StorageLimitError


def _descriptor_values(descriptor):
    return tuple(getattr(descriptor, field.name) for field in fields(refs.RefSetDescriptor))


def _assert_boundary(connection, descriptor, values, generation, limits):
    # Check the tracked epoch before querying: a closed connection must fail as
    # an integrity error rather than leaking a sqlite ProgrammingError.
    refs._assert_reader(connection, generation)
    refs._validate_descriptor(descriptor, limits)
    if _descriptor_values(descriptor) != values:
        raise StorageIntegrityError("canonical reference descriptor changed during iteration")
    refs._check_schema(connection)
    # Includes attached/TEMP databases, physical/logical bytes and companions,
    # free reserve, page cap, negative bounded cache, and disabled mmap.  A
    # schema/data-version stamp alone cannot observe a changed free reserve.
    refs._check_footprint(connection, limits)
    refs._assert_reader(connection, generation)


def _canonical_pieces(connection, set_digest, limits):
    """Keep one bounded binary block plus at most one 67-byte JSON token."""
    yield b"["
    cursor = refs._members(connection, set_digest)
    first = True
    try:
        for _index, digest, _count, _size in cursor:
            content = refs._read_block(connection, digest, limits)
            for offset in range(0, len(content), 32):
                quoted = b'"' + content[offset:offset + 32].hex().encode("ascii") + b'"'
                yield quoted if first else b"," + quoted
                first = False
            # Do not retain the preceding block while materializing the next.
            del content
    finally:
        try:
            cursor.close()
        except sqlite3.ProgrammingError:
            # The public guard reports an already-closed owning connection;
            # cleanup must not replace that error (or make generator.close fail).
            pass
    yield b"]"


def _bounded_chunks(pieces, chunk_bytes):
    buffer = bytearray()
    try:
        for piece in pieces:
            offset = 0
            while offset < len(piece):
                take = min(chunk_bytes - len(buffer), len(piece) - offset)
                buffer.extend(piece[offset:offset + take])
                offset += take
                if len(buffer) == chunk_bytes:
                    chunk = bytes(buffer)
                    buffer.clear()
                    yield chunk
        if buffer:
            yield bytes(buffer)
    finally:
        pieces.close()


def iter_canonical_ref_chunks(
    connection,
    descriptor: refs.RefSetDescriptor,
    *,
    limits=DEFAULT_LIMITS,
    chunk_bytes=65536,
) -> Iterator[bytes]:
    """Yield the exact old canonical reference-array bytes in bounded chunks.

    ``chunk_bytes`` is an exact positive integer no larger than the passed block
    budget.  It affects only output segmentation, never reference membership,
    order, formatting or the canonical digest.  A fresh call is needed for each
    read.  Exhaust the iterator to establish its terminal checks; abandoning it
    grants no completed-read receipt.  No transaction or SQLite settings change.

    The existing complete C2 validation is reused unchanged.  Emission retains
    only a bounded binary block and O(chunk_bytes) buffering, not a Python list
    of references or the complete canonical array.  Public chunks, unlike the
    unchanged scalar interface, are the externally visible validation unit.
    """
    try:
        refs._require_connection(connection, limits)
        if type(chunk_bytes) is not int or not 0 < chunk_bytes <= limits.block_bytes:
            raise StorageLimitError("canonical reference chunk size exceeds its C block budget")
        refs._validate_descriptor(descriptor, limits)
        values = _descriptor_values(descriptor)
        generation = refs._generation(connection, limits)
        refs._check_schema(connection)
        refs._check_footprint(connection, limits)
        refs._check_shapes(connection)
        refs._verify_set(connection, descriptor, limits)
        _assert_boundary(connection, descriptor, values, generation, limits)
    except sqlite3.DatabaseError as exc:
        raise StorageIntegrityError("canonical reference admission or complete validation failed") from exc

    expected_bytes = descriptor.canonical_bytes
    expected_digest = descriptor.canonical_digest
    pieces = _canonical_pieces(connection, descriptor.set_digest, limits)
    chunks = _bounded_chunks(pieces, chunk_bytes)
    hasher = hashlib.sha256()
    emitted_bytes = 0
    try:
        while True:
            # This also runs immediately after resuming the last public yield,
            # before a successful StopIteration may escape to the consumer.
            _assert_boundary(connection, descriptor, values, generation, limits)
            try:
                chunk = next(chunks)
            except StopIteration:
                _assert_boundary(connection, descriptor, values, generation, limits)
                if emitted_bytes != expected_bytes or hasher.hexdigest() != expected_digest:
                    raise StorageIntegrityError("emitted canonical reference bytes do not match the complete set")
                return
            _assert_boundary(connection, descriptor, values, generation, limits)
            emitted_bytes += len(chunk)
            hasher.update(chunk)
            if emitted_bytes > expected_bytes:
                raise StorageIntegrityError("emitted canonical reference bytes exceed the complete set")
            yield chunk
    except sqlite3.DatabaseError as exc:
        raise StorageIntegrityError("canonical reference read failed") from exc
    finally:
        chunks.close()
