"""Closed physical B3 schema must count hidden/generated columns too."""
import sqlite3

import pytest

from context_models.contracts import ContextIntegrityError
from test_context_consumers import saved, read


@pytest.mark.parametrize("storage,hidden", [("VIRTUAL", 2), ("STORED", 3)])
def test_generated_extra_column_cannot_hide_from_consumer_schema_validation(tmp_path, storage, hidden):
    path, reference, payload = saved(tmp_path)
    connection = sqlite3.connect(path)
    try:
        connection.execute("ALTER TABLE context_snapshots RENAME TO original_snapshots")
        connection.execute("CREATE TABLE context_snapshots (key TEXT PRIMARY KEY NOT NULL, payload BLOB NOT NULL, "
            "payload_digest TEXT NOT NULL, unexpected TEXT GENERATED ALWAYS AS ('outside-contract') " + storage + ")")
        connection.execute("INSERT INTO context_snapshots(key,payload,payload_digest) SELECT key,payload,payload_digest FROM original_snapshots")
        connection.execute("DROP TABLE original_snapshots")
        connection.commit()
        assert len(connection.execute("PRAGMA table_info(context_snapshots)").fetchall()) == 3
        assert connection.execute("PRAGMA table_xinfo(context_snapshots)").fetchall()[-1][-1] == hidden
    finally:
        connection.close()
    before = path.read_bytes()
    with pytest.raises(ContextIntegrityError, match="schema"):
        read(path, reference, payload)
    assert path.read_bytes() == before
