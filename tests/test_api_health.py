"""Regressionstests für _api_football_health (Sidebar-Systemstatus).

Deckt den Produktionsbefund ab: API-Football liefert ein errors-Objekt ohne
"access"-Schlüssel (z.B. Rate-Limit) und die Sidebar zeigte wörtlich "None".
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app  # noqa: E402


def _payload(errors):
    body = {"errors": errors, "response": {}}
    response = Mock()
    response.json.return_value = body
    response.status_code = 200
    return response


class ApiFootballHealthTest(unittest.TestCase):
    def _health(self, errors):
        with patch.object(app.requests, "get", return_value=_payload(errors)):
            # Cache der Streamlit-Funktion umgehen: undecorated Aufruf
            return app._api_football_health.__wrapped__("test-key")

    def test_errors_dict_without_access_never_shows_none_literal(self):
        health = self._health({"requests": "Limit erreicht"})
        self.assertNotEqual(health["detail"], "None")
        self.assertIn("requests", health["detail"])
        self.assertEqual(health["state"], "error")

    def test_access_error_is_used_verbatim(self):
        health = self._health({"access": "Account suspended"})
        self.assertEqual(health["detail"], "Account suspended")
        self.assertEqual(health["state"], "suspended")
        self.assertEqual(health["label"], "Live-API gesperrt")

    def test_rate_limit_gets_transient_label(self):
        health = self._health({"rateLimit": "Too many requests"})
        self.assertEqual(health["label"], "Live-API Kurzzeit-Limit")
        self.assertEqual(health["state"], "error")

    def test_empty_errors_means_active(self):
        with patch.object(app.requests, "get", return_value=_payload([])):
            payload_response = Mock()
            payload_response.json.return_value = {
                "errors": [],
                "response": {"subscription": {"active": True, "plan": "Pro"}},
            }
            payload_response.status_code = 200
        with patch.object(app.requests, "get", return_value=payload_response):
            health = app._api_football_health.__wrapped__("test-key")
        self.assertEqual(health["state"], "active")
        self.assertEqual(health["label"], "Live-API aktiv (Pro)")
        self.assertEqual(health["detail"], "")


if __name__ == "__main__":
    unittest.main()
