"""Kompatibilitaets-Shim — die eigentliche App liegt in app.py.

Bleibt bestehen, damit alte Startkommandos und Imports nicht brechen:
- ``streamlit run btts_pro_app.py`` leitet auf app.py um.
- ``import btts_pro_app`` liefert das echte App-Modul.
"""
import sys as _sys

if __name__ == "__main__":
    import runpy

    runpy.run_module("app", run_name="__main__")
else:
    import app as _app

    _sys.modules[__name__] = _app
