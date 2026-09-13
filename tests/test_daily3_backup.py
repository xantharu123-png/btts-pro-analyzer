import sqlite3
import zipfile

import pytest

from daily3_store import Daily3Store, day_balance
from scripts import backup_runtime_databases as backup
from test_daily3_store import NOW, DAY, SCOPE, command, placed


def test_daily3_only_backup_requires_existing_key_and_restores_actual_open_stake(tmp_path):
    root = tmp_path/'app'
    path = root/'runtime_state'/'daily3.db'
    store = Daily3Store(path, key=b'k'*32, clock=lambda: NOW)
    command(store, 'start')
    placed(store, 3000)
    with pytest.raises(RuntimeError, match='Daily3.*key'):
        backup.create_archive(tmp_path/'without-key', root=root, now=NOW)
    key_path = root/backup.LOCAL_INTEGRITY_KEY_RELATIVE_PATH
    key_path.parent.mkdir(parents=True)
    key_path.write_bytes((b'k'*32).hex().encode()+b'\n')
    archive, count = backup.create_archive(tmp_path/'with-key', root=root, now=NOW)
    assert count == backup.verify_archive(archive) == 1
    with zipfile.ZipFile(archive) as zipped:
        restored = tmp_path/'restored.db'
        restored.write_bytes(zipped.read('runtime_state/daily3.db'))
        restored_key = bytes.fromhex(zipped.read(backup.INTEGRITY_KEY_ARCHIVE_PATH).decode().strip())
    restored_store = Daily3Store(restored, key=restored_key, clock=lambda: NOW)
    assert restored_store.history(SCOPE) == store.history(SCOPE)
    assert day_balance(restored_store.history(SCOPE)[DAY]).available_cents == 2000
    with sqlite3.connect(restored) as con:
        con.execute('DELETE FROM daily3_events WHERE sequence=3')
    with pytest.raises(RuntimeError, match='checkpoint'):
        backup.verify_daily3_database(restored, (b'k'*32).hex().encode()+b'\n')


def test_default_key_uses_existing_backup_key_namespace(tmp_path, monkeypatch):
    import challenge_store
    calls = []
    monkeypatch.setattr(challenge_store, '_load_ledger_hmac_key', lambda path: (calls.append(path) or (b'k'*32, path)))
    Daily3Store(tmp_path/'daily3.db')
    assert calls[0].parent == challenge_store.DEFAULT_CHALLENGE_DB.parent/'challenge_sessions'
