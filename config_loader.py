"""Central configuration loading for local, Streamlit, and environment secrets."""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class AppConfig:
    api_key: Optional[str] = None
    api_football_key: Optional[str] = None
    weather_key: Optional[str] = None
    supabase_db_url: Optional[str] = None
    odds_api_key: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    pandascore_key: Optional[str] = None
    rapidapi_key: Optional[str] = None
    cricket_api_key: Optional[str] = None
    source: str = "empty"


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper().startswith("YOUR_") or text.upper().startswith("DEIN_"):
        return None
    return text


def _secret_get(secrets: Any, *path: str) -> Optional[str]:
    current = secrets
    try:
        for key in path:
            if key not in current:
                return None
            current = current[key]
        return _clean(current)
    except Exception:
        return None


def _load_streamlit_config(st_module: Any = None) -> tuple[dict, list[str]]:
    if st_module is None or not hasattr(st_module, "secrets"):
        return {}, []

    secrets = st_module.secrets
    values = {
        "api_key": _secret_get(secrets, "api", "api_key"),
        "api_football_key": _secret_get(secrets, "api", "api_football_key"),
        "weather_key": _secret_get(secrets, "api", "weather_key"),
        "supabase_db_url": (
            _secret_get(secrets, "SUPABASE_DB_URL")
            or _secret_get(secrets, "database", "supabase_db_url")
            or _secret_get(secrets, "api", "supabase_db_url")
        ),
        "odds_api_key": _secret_get(secrets, "odds", "api_key"),
        "telegram_bot_token": _secret_get(secrets, "telegram", "bot_token"),
        "telegram_chat_id": _secret_get(secrets, "telegram", "chat_id"),
        "pandascore_key": _secret_get(secrets, "esports", "pandascore_key"),
        "rapidapi_key": _secret_get(secrets, "cricket", "rapidapi_key"),
        "cricket_api_key": _secret_get(secrets, "cricket", "api_key"),
    }
    return values, ["Streamlit secrets"] if any(values.values()) else []


def _load_env_config() -> tuple[dict, list[str]]:
    values = {
        "api_key": _clean(os.environ.get("FOOTBALL_DATA_API_KEY") or os.environ.get("API_KEY")),
        "api_football_key": _clean(os.environ.get("API_FOOTBALL_KEY")),
        "weather_key": _clean(os.environ.get("OPENWEATHER_API_KEY") or os.environ.get("WEATHER_API_KEY")),
        "supabase_db_url": _clean(os.environ.get("SUPABASE_DB_URL")),
        "odds_api_key": _clean(os.environ.get("ODDS_API_KEY")),
        "telegram_bot_token": _clean(os.environ.get("TELEGRAM_BOT_TOKEN")),
        "telegram_chat_id": _clean(os.environ.get("TELEGRAM_CHAT_ID")),
        "pandascore_key": _clean(os.environ.get("PANDASCORE_KEY")),
        "rapidapi_key": _clean(os.environ.get("RAPIDAPI_KEY")),
        "cricket_api_key": _clean(os.environ.get("CRICKET_API_KEY")),
    }
    return values, ["environment"] if any(values.values()) else []


def _load_ini_config(config_path: str | Path = "config.ini") -> tuple[dict, list[str]]:
    path = Path(config_path)
    if not path.exists():
        return {}, []

    parser = configparser.ConfigParser()
    try:
        parser.read(path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        parser.read(path, encoding="latin-1")

    def get(section: str, option: str) -> Optional[str]:
        if parser.has_option(section, option):
            return _clean(parser.get(section, option))
        return None

    values = {
        "api_key": get("api", "api_key"),
        "api_football_key": get("api", "api_football_key"),
        "weather_key": get("api", "weather_key"),
        "supabase_db_url": get("database", "supabase_db_url"),
        "odds_api_key": get("odds", "api_key"),
        "telegram_bot_token": get("telegram", "bot_token"),
        "telegram_chat_id": get("telegram", "chat_id"),
        "pandascore_key": get("esports", "pandascore_key"),
        "rapidapi_key": get("cricket", "rapidapi_key"),
        "cricket_api_key": get("cricket", "api_key"),
    }
    return values, ["config.ini"] if any(values.values()) else []


def load_app_config(st_module: Any = None, config_path: str | Path = "config.ini") -> AppConfig:
    """Load config with precedence: Streamlit secrets, environment, config.ini."""
    merged: dict[str, Optional[str]] = {}
    sources: list[str] = []

    for values, found_sources in (
        _load_ini_config(config_path),
        _load_env_config(),
        _load_streamlit_config(st_module),
    ):
        sources.extend(found_sources)
        for key, value in values.items():
            if value:
                merged[key] = value

    return AppConfig(**merged, source=", ".join(dict.fromkeys(sources)) or "not configured")
