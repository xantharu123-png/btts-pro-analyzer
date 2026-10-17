"""The legacy analyzer must use the same local-artifact boundary as workers."""
import os
import pickle
import stat
from pathlib import Path

import advanced_analyzer as advanced


def _fixture(tmp_path, monkeypatch):
    path = tmp_path/'model.pkl'
    bundle = dict(version=advanced.ML_MODEL_VERSION, feature_names=advanced.ML_FEATURE_NAMES,
                  model='existing-model', scaler='existing-scaler',
                  metrics={'active': True, 'folds_beating_baseline': 3})
    path.write_bytes(pickle.dumps(bundle))
    monkeypatch.setattr(advanced, 'ML_MODEL_PATH', path)
    analyzer = advanced.AdvancedBTTSAnalyzer.__new__(advanced.AdvancedBTTSAnalyzer)
    analyzer.model_trained = False
    return path, bundle, analyzer


def test_ordinary_legacy_cache_load_keeps_versioned_bundle(tmp_path, monkeypatch):
    _, bundle, analyzer = _fixture(tmp_path, monkeypatch)
    assert analyzer.load_model() is True
    assert analyzer.ml_model == bundle['model'] and analyzer.scaler == bundle['scaler']
    assert analyzer.model_metrics == bundle['metrics'] and analyzer.model_trained


def test_symlink_model_is_rejected_before_pickle_deserialization(tmp_path, monkeypatch):
    path, _, analyzer = _fixture(tmp_path, monkeypatch)
    original_lstat = os.lstat
    original_load = pickle.load
    deserialized = []

    def symlink_metadata(candidate, *args, **kwargs):
        metadata = original_lstat(candidate, *args, **kwargs)
        if os.path.abspath(candidate) == str(path):
            return os.stat_result((stat.S_IFLNK | 0o600, *metadata[1:]))
        return metadata

    def record_load(*args, **kwargs):
        deserialized.append(True)
        return original_load(*args, **kwargs)

    monkeypatch.setattr(os, 'lstat', symlink_metadata)
    monkeypatch.setattr(pickle, 'load', record_load)
    assert analyzer.load_model() is False
    assert deserialized == [] and analyzer.model_trained is False


def test_rejected_symlink_cache_cannot_be_overwritten_by_training_save(tmp_path, monkeypatch):
    path, _, analyzer = _fixture(tmp_path, monkeypatch)
    assert analyzer.load_model() is True
    original = path.read_bytes()
    analyzer.ml_model = 'fresh-training-result'
    is_symlink = Path.is_symlink
    monkeypatch.setattr(Path, 'is_symlink', lambda candidate: True if candidate == path else is_symlink(candidate))
    analyzer.save_model()
    assert path.read_bytes() == original


def test_fresh_cache_save_and_load_preserve_qualified_model(tmp_path, monkeypatch):
    path, bundle, analyzer = _fixture(tmp_path, monkeypatch)
    assert analyzer.load_model() is True
    path.unlink()
    analyzer.save_model()
    fresh = advanced.AdvancedBTTSAnalyzer.__new__(advanced.AdvancedBTTSAnalyzer)
    fresh.model_trained = False
    assert fresh.load_model() is True
    assert fresh.ml_model == bundle['model'] and fresh.scaler == bundle['scaler']
    assert fresh.model_metrics == bundle['metrics']
