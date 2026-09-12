# Task57 preparation — existing QA package names, read-only observation

Status: preparation only; no native chain execution or runtime-closure proof.
Task54 is the sole implementation writer. This note does not activate another
writer or authorize a dependency installation, application update or deletion.

At2026-09-12T16:37:57Z Root successfully ran one read-only SSH command as the
ordinary `betboy-vps` login, with no sudo. The only filesystem query was:

```sh
find /tmp/betboy-context-qa.9xr68INa/venv/lib/python3.12/site-packages \
  -mindepth 1 -maxdepth 1 -printf "%f\n" | sort
```

Exact observed top-level names (not imported or recursively hashed):

```text
__pycache__
_pytest
certifi
certifi-2026.7.22.dist-info
charset_normalizer
charset_normalizer-3.5.1.dist-info
dateutil
et_xmlfile
et_xmlfile-2.0.0.dist-info
idna
idna-3.19.dist-info
iniconfig
iniconfig-2.3.0.dist-info
joblib
joblib-1.5.3.dist-info
narwhals
narwhals-2.26.0.dist-info
numpy
numpy-2.5.1.dist-info
numpy.libs
openpyxl
openpyxl-3.1.5.dist-info
packaging
packaging-26.3.dist-info
pandas
pandas-3.0.5.dist-info
pip
pip-24.0.dist-info
pluggy
pluggy-1.6.0.dist-info
py.py
pygments
pygments-2.21.0.dist-info
pytest
pytest-9.1.1.dist-info
python_dateutil-2.9.0.post0.dist-info
requests
requests-2.34.2.dist-info
scikit_learn-1.9.0.dist-info
scikit_learn.libs
scipy
scipy-1.18.0.dist-info
scipy.libs
six-1.17.0.dist-info
six.py
sklearn
threadpoolctl-3.6.0.dist-info
threadpoolctl.py
urllib3
urllib3-2.7.0.dist-info
xlrd
xlrd-2.0.2.dist-info
```

Directory names are not authenticated package versions or dependency closure.
They establish no Python import, native ELF load, runtime-data read, performance,
allocated-space or guard result. No package is implicitly admitted because its
name occurs here; the next reviewed fixed catalogue must bind actual selected
files and the finalized Task54 route. Root's prior space/selected-apparent-size
observation is recorded separately in task-56-vps-package-observation.md.

The proposed callable is currently
`run_small_corpus_consumer_acceptance(tmp_path, monkeypatch, tour, *, record_property=None)`
inside the new Task54 test module. Its bytes and final interface must be bound
only after Task54's independent review. Direct invocation avoids pytest.main,
collection and plugin startup; importing its explicit pytest helper is still a
real dependency. Legacy fixture/oracle setup and all retained attempts must be
charged together with the C phase, code/dependency copies and parent costs;
separate local phase budgets are not separate whole-job allowances.
