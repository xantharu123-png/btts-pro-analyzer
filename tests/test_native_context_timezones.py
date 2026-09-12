"""Task58 real reader binding QA; portable seams are not native acceptance."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from test_native_context_chain import HERE, entry, timezone_dependencies, tzif_fixture


def reader_fixture(tmp_path):
    seal = tmp_path / "seal"
    dependencies = timezone_dependencies(seal)
    values = []
    for key in ("Europe/Zurich", "UTC"):
        raw = tzif_fixture(key)
        target = seal / "runtime-data/zoneinfo" / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        target.chmod(0o444)
        values.append({**entry(key, raw), "source": str(tmp_path / "originals" / key)})
    for path in (seal / "runtime-data/zoneinfo/Europe", seal / "runtime-data/zoneinfo", seal / "runtime-data"):
        path.chmod(0o555)
    (tmp_path / "work").mkdir()
    return {"code": [], "dependencies": dependencies, "timezone_data": values}


BOOTSTRAP = r'''
import datetime, importlib, importlib.machinery, json, os, sys
from pathlib import Path
root = Path(sys.argv[3])
manifest = json.loads(sys.argv[4])
manifest["runtime"] = {"stdlib_search_path": list(sys.path)}
seal = root / "seal"
data = seal / "runtime-data/zoneinfo"
deps = seal / "dependencies"
c = {"__name__": "_reader_catalogue"}
exec(compile(Path(sys.argv[1]).read_bytes(), sys.argv[1], "exec"), c)
c["TIMEZONE_DATA"] = tuple((x["path"], x["source"], x["size"], x["sha256"]) for x in manifest["timezone_data"])
w = {"__name__": "_reader_worker"}
exec(compile(Path(sys.argv[2]).read_bytes(), sys.argv[2], "exec"), w)
if not hasattr(os, "O_DIRECTORY"):
    os.O_DIRECTORY = 0
'''


def run_reader(tmp_path, manifest, body):
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", BOOTSTRAP + body,
         str(HERE / "native_context_chain_catalogue.py"),
         str(HERE / "native_context_chain_worker.py"), str(tmp_path), json.dumps(manifest)],
        capture_output=True, text=True, timeout=20)
    retained = tmp_path / ("reader-result-%02d.json" % (len(list(tmp_path.glob("reader-result-*.json"))) + 1))
    retained.write_text(json.dumps({"command": result.args, "returncode": result.returncode,
                                    "stdout": result.stdout, "stderr": result.stderr}), encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_real_dateutil_retains_its_old_path_after_zoneinfo_only_binding(tmp_path):
    # Break caught: assuming reset_tzpath configures the independent gettz reader.
    result = run_reader(tmp_path, reader_fixture(tmp_path), r'''
(root / "old-system").mkdir()
(root / "old-system/UTC").write_bytes((data / "UTC").read_bytes())
sys.path.insert(0, str(deps))
import zoneinfo
from dateutil.tz import tz
observed = w["observe_python_files"](root / "code", seal, root / "work", manifest)
zoneinfo.reset_tzpath((str(data),))
zoneinfo.ZoneInfo.clear_cache()
assert zoneinfo.ZoneInfo("UTC").utcoffset(None) == datetime.timedelta(0)
# Windows ships no system TZPATHS. Give the actual reader an existing old
# fixture path, not a fabricated reader or mocked isfile/open/sys.audit call.
tz.TZPATHS = [str(root / "old-system")]
try:
    tz.gettz("UTC")
except w["ChainError"] as exc:
    assert Path(exc.file_context["path"]) == root / "old-system/UTC"
    print(json.dumps({"denied": exc.file_context["path"]}))
else:
    raise AssertionError("ZoneInfo-only binding unexpectedly bound dateutil")
''')
    assert result["denied"].endswith("UTC")


def test_real_dual_readers_use_same_seal_and_preserve_offsets_and_fold(tmp_path):
    # Break caught: missing TZPATHS/TZFILES/cache configuration or wrong order.
    result = run_reader(tmp_path, reader_fixture(tmp_path), r'''
observed = w["observe_python_files"](root / "code", seal, root / "work", manifest)
cache_calls = []
def profile(frame, event, arg):
    if event == "call" and frame.f_code.co_name == "cache_clear" and Path(frame.f_code.co_filename) == deps / "dateutil/tz/tz.py":
        cache_calls.append(frame.f_code.co_name)
sys.setprofile(profile)
w["bind_timezone_data"](c, seal, manifest)
sys.setprofile(None)
assert cache_calls == ["cache_clear"], "actual dateutil cache was not cleared"
import zoneinfo
from dateutil.tz import tz
assert zoneinfo.TZPATH == (str(data),)
assert list(tz.TZPATHS) == [str(data)] and list(tz.TZFILES) == []
assert Path(tz.__file__) == deps / "dateutil/tz/tz.py"
def opens(key):
    return sum(count for event, count in observed.items()
               if event.startswith("open:") and Path(event[5:]) == data / key)
for key in ("UTC", "Europe/Zurich"):
    before = opens(key)
    one, two = zoneinfo.ZoneInfo(key), tz.gettz(key)
    assert two is not None and Path(two._filename) == data / key
    # Windows readers preserve '/' inside the IANA key; compare actual path
    # identity, not the slash spelling or prior custody-validation opens.
    assert opens(key) - before == 2, observed
    for month, day, hour, fold, zurich_hours in (
            (1, 15, 12, 0, 1), (7, 15, 12, 0, 2),
            (10, 25, 2, 0, 2), (10, 25, 2, 1, 1)):
        want = datetime.timedelta(hours=0 if key == "UTC" else zurich_hours)
        for reader in (one, two):
            actual = datetime.datetime(2026, month, day, hour, 30, tzinfo=reader, fold=fold)
            assert actual.utcoffset() == want, (key, month, fold, actual)
            assert actual.astimezone(datetime.timezone.utc).astimezone(reader) == actual
assert "dateutil.zoneinfo" not in sys.modules
print(json.dumps({"observations": observed}))
''')
    assert result["observations"]


@pytest.mark.parametrize("route", ["missing-key", "importlib-module", "loader-resource", "relative-resource"])
def test_real_dateutil_bundled_fallback_is_denied_despite_catalogued_bytes(tmp_path, route):
    # Break caught: generic dependency/stdlib admission overrides fallback denial.
    manifest = reader_fixture(tmp_path)
    result = run_reader(tmp_path, manifest, r'''
sys.path.insert(0, str(deps))
# Prove actual otherwise-admitted bundle can answer the unknown sealed key,
# in this separate unguarded fixture subprocess before the audit. Binding is
# not called here: the preloaded state is tested for rejection separately.
from dateutil.zoneinfo import get_zonefile_instance
assert get_zonefile_instance().get("America/New_York") is not None
bundle = deps / "dateutil/zoneinfo/dateutil-zoneinfo.tar.gz"
assert bundle.is_file() and any(x["path"] == "dateutil/zoneinfo/dateutil-zoneinfo.tar.gz" for x in manifest["dependencies"])
# A new clean subprocess is used below for the protected paths.
print(json.dumps({"bundle_exists": True}))
''')
    assert result["bundle_exists"]
    body = r'''
observed = w["observe_python_files"](root / "code", seal, root / "work", manifest)
sys.path.insert(0, str(deps))
w["bind_timezone_data"](c, seal, manifest)
bundle = deps / "dateutil/zoneinfo/dateutil-zoneinfo.tar.gz"
try:
    ROUTE
except w["ChainError"] as exc:
    # Resource loader and importlib bypass import-event-only enforcement.
    if ROUTE_NAME != "missing-key":
        assert exc.file_context["event"] == "open", str(exc)
        assert "dateutil" in exc.file_context["path"] and "zoneinfo" in exc.file_context["path"]
    assert "dateutil.zoneinfo" not in sys.modules
    print(json.dumps({"denied": ROUTE_NAME, "message": str(exc)}))
else:
    raise AssertionError("catalogued fallback remained readable")
'''
    routes = {
        "missing-key": '__import__("dateutil.tz", fromlist=["gettz"]).gettz("America/New_York")',
        "importlib-module": 'importlib.import_module("dateutil.zoneinfo")',
        "loader-resource": 'importlib.machinery.SourceFileLoader("dateutil.zoneinfo", str(bundle.parent / "__init__.py")).get_data(str(bundle))',
        "relative-resource": 'os.chdir(root / "work"); importlib.machinery.SourceFileLoader("dateutil.zoneinfo", str(bundle.parent / "__init__.py")).get_data("../seal/dependencies/dateutil/zoneinfo/dateutil-zoneinfo.tar.gz")',
    }
    result = run_reader(tmp_path, manifest, body.replace("ROUTE_NAME", repr(route)).replace("ROUTE", routes[route]))
    assert result["denied"] == route


@pytest.mark.parametrize("preload", ["dateutil-reader", "dateutil-cache", "bundled-cache", "zoneinfo-cache"])
def test_real_binding_rejects_preloaded_reader_or_fallback_cache(tmp_path, preload):
    # Break caught: rebasing a reader leaves already-held timezone objects live.
    bodies = {
        "dateutil-reader": 'from dateutil import tz',
        "dateutil-cache": 'from dateutil import tz; retained = tz.gettz(str(data / "UTC"))',
        "bundled-cache": 'from dateutil.zoneinfo import get_zonefile_instance; retained = get_zonefile_instance()',
        "zoneinfo-cache": 'import zoneinfo; zoneinfo.reset_tzpath((str(data),)); retained = zoneinfo.ZoneInfo("UTC")',
    }
    result = run_reader(tmp_path, reader_fixture(tmp_path), r'''
sys.path.insert(0, str(deps))
PRELOAD
before = list(sys.path)
observed = w["observe_python_files"](root / "code", seal, root / "work", manifest)
try:
    w["bind_timezone_data"](c, seal, manifest)
except w["ChainError"] as exc:
    assert "preloaded" in str(exc)
    assert sys.path == before
    print(json.dumps({"rejected": True}))
else:
    raise AssertionError("preloaded actual reader/cache was silently rebound")
'''.replace("PRELOAD", bodies[preload]))
    assert result["rejected"]


def test_real_readers_reject_system_unknown_traversal_and_writes(tmp_path):
    # Break caught: rebinding permits an alternative file, alias or data write.
    result = run_reader(tmp_path, reader_fixture(tmp_path), r'''
(root / "old-system").mkdir()
(root / "old-system/UTC").write_bytes((data / "UTC").read_bytes())
observed = w["observe_python_files"](root / "code", seal, root / "work", manifest)
w["bind_timezone_data"](c, seal, manifest)
from dateutil import tz
import zoneinfo
attempts = [
    lambda: tz.gettz(str(root / "old-system/UTC")),
    lambda: tz.gettz("Europe/../UTC"),
    lambda: tz.gettz("Europe/Unlisted"),
    lambda: zoneinfo.ZoneInfo("Europe/Unlisted"),
    lambda: open("/usr/share/zoneinfo/UTC", "rb"),
    lambda: open("/usr/share/zoneinfo/Etc/UTC", "rb"),
    lambda: open("/usr/share/zoneinfo/Europe/Zurich", "rb"),
]
for attempt in attempts:
    try:
        attempt()
    except (w["ChainError"], zoneinfo.ZoneInfoNotFoundError):
        pass
    else:
        raise AssertionError("unplanned real timezone read admitted")
for mode in ("wb", "r+b", "ab"):
    try:
        open(data / "UTC", mode)
    except w["ChainError"]:
        pass
    else:
        raise AssertionError("timezone write admitted")
# Numeric offsets and normal UTC conversion require no fallback data source.
value = datetime.datetime(2026, 7, 15, 12, tzinfo=tz.tzoffset("numeric", 5400))
assert value.utcoffset() == datetime.timedelta(minutes=90)
assert value.astimezone(tz.UTC).hour == 10 and value.astimezone(tz.UTC).minute == 30
print(json.dumps({"denied": len(attempts) + 3, "numeric_minutes": 90}))
''')
    assert result == {"denied": 10, "numeric_minutes": 90}


def test_real_unprotected_run_stops_before_audit_or_dependency_import(tmp_path):
    # Break caught: dependency configuration moves before actual guard checks.
    result = run_reader(tmp_path, reader_fixture(tmp_path), r'''
events = []
def audit(event, args):
    if event == "import" and args[0].split(".", 1)[0] in ("dateutil", "pandas", "pytest"):
        events.append(args[0])
sys.addaudithook(audit)
try:
    w["run"]("ATP")
except w["ChainError"] as exc:
    assert "child required" in str(exc) or "identity drop missing" in str(exc)
    assert events == [] and "dateutil" not in sys.modules and "zoneinfo" not in sys.modules
    print(json.dumps({"guard_rejected": True}))
else:
    raise AssertionError("unguarded interpreter ran worker")
''')
    assert result["guard_rejected"]


def test_binding_requires_exact_reader_dependency_admission(tmp_path):
    # Break caught: importing an installed reader absent from the closed manifest.
    manifest = reader_fixture(tmp_path)
    manifest["dependencies"] = [x for x in manifest["dependencies"] if x["path"] != "dateutil/tz/tz.py"]
    result = run_reader(tmp_path, manifest, r'''
before = list(sys.path)
observed = w["observe_python_files"](root / "code", seal, root / "work", manifest)
try:
    w["bind_timezone_data"](c, seal, manifest)
except w["ChainError"] as exc:
    assert "dependency" in str(exc)
    assert "dateutil" not in sys.modules and "zoneinfo" not in sys.modules
    assert sys.path == before
    print(json.dumps({"rejected": True}))
else:
    raise AssertionError("uncatalogued reader binding admitted")
''')
    assert result["rejected"]
