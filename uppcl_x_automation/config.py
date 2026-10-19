"""Configuration Manager for UPPCL X Complaint Monitoring System.

Loads and validates settings from config.yaml and environment variables (.env).
Provides thread-safe access to configuration objects.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from dotenv import load_dotenv


@dataclass(frozen=True)
class MonitoredAccount:
    handle: str
    code: str
    name: str


@dataclass(frozen=True)
class DiscomInfo:
    code: str
    name: str
    handle: str
    headquarters: str
    region: str


@dataclass(frozen=True)
class DistrictInfo:
    name: str
    discom: str
    zone: str


@dataclass
class AppConfig:
    # System
    app_name: str = "UPPCL X Complaint Monitoring & Sheet Sync"
    version: str = "1.0.0"
    timezone: str = "Asia/Kolkata"
    polling_interval_minutes: int = 5
    dry_run: bool = True
    auto_post_enabled: bool = False
    emergency_stop: bool = False
    daily_post_cap: int = 50

    # API credentials
    x_bearer_token: Optional[str] = None
    x_api_key: Optional[str] = None
    x_api_secret: Optional[str] = None
    x_access_token: Optional[str] = None
    x_access_token_secret: Optional[str] = None

    # Google Sheets
    google_service_account_file: Optional[str] = None
    google_webhook_url: Optional[str] = None
    google_spreadsheet_id: str = "12smJ_xw3sRWPcCzDsh_hC44ac2NlpO9I_wDnXF-wFXU"
    google_sheet_tab_name: str = "Twitter Complaint List"

    # SQLite
    sqlite_db_path: str = "data/uppcl_monitor.db"

    # Reference Maps
    monitored_accounts: List[MonitoredAccount] = field(default_factory=list)
    discoms: Dict[str, DiscomInfo] = field(default_factory=dict)
    districts: Dict[str, DistrictInfo] = field(default_factory=dict)
    district_aliases: Dict[str, str] = field(default_factory=dict)
    allowed_discom_handles: List[str] = field(default_factory=list)
    reply_templates: Dict[str, Dict[str, str]] = field(default_factory=dict)


def _sanitize_url(url: Optional[str]) -> Optional[str]:
    """Clean URLs by removing accidental leading/trailing strings or booleans."""
    if not url:
        return url
    u = url.strip()
    # Strip accidental prepended values like 'falsehttps://' or quotes
    u = u.strip("\"'")
    if u.lower().startswith("falsehttp://"):
        u = "http://" + u[12:]
    elif u.lower().startswith("falsehttps://"):
        u = "https://" + u[13:]
    elif u.lower().startswith("truehttp://"):
        u = "http://" + u[11:]
    elif u.lower().startswith("truehttps://"):
        u = "https://" + u[12:]
    return u


def load_config(config_path: Optional[str] = None, env_path: Optional[str] = None) -> AppConfig:
    """Load configuration from YAML and environment variables."""
    # Find base directory
    base_dir = Path(__file__).resolve().parent.parent

    # Load environment variables
    env_file = Path(env_path) if env_path else base_dir / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    else:
        load_dotenv()  # Fallback to current working directory

    # Load YAML file
    yaml_file = Path(config_path) if config_path else base_dir / "config" / "config.yaml"
    raw_yaml: Dict[str, Any] = {}
    if yaml_file.exists():
        with open(yaml_file, "r", encoding="utf-8") as f:
            raw_yaml = yaml.safe_load(f) or {}

    sys_yaml = raw_yaml.get("system", {})

    # Build monitored accounts
    monitored: List[MonitoredAccount] = []
    for acc in raw_yaml.get("monitored_accounts", []):
        monitored.append(MonitoredAccount(
            handle=acc.get("handle", ""),
            code=acc.get("code", ""),
            name=acc.get("name", "")
        ))

    # Build DISCOM map
    discoms_map: Dict[str, DiscomInfo] = {}
    for code, info in raw_yaml.get("discoms", {}).items():
        discoms_map[code] = DiscomInfo(
            code=code,
            name=info.get("name", ""),
            handle=info.get("handle", ""),
            headquarters=info.get("headquarters", ""),
            region=info.get("region", "")
        )

    # Build Canonical District map
    districts_map: Dict[str, DistrictInfo] = {}
    for d_name, d_info in raw_yaml.get("districts", {}).items():
        districts_map[d_name] = DistrictInfo(
            name=d_name,
            discom=d_info.get("discom", ""),
            zone=d_info.get("zone", "")
        )

    # District aliases
    aliases_map: Dict[str, str] = raw_yaml.get("district_aliases", {})

    # Safety allowlist
    allowed_handles: List[str] = raw_yaml.get("allowed_discom_handles", [])

    # Reply templates
    templates: Dict[str, Dict[str, str]] = raw_yaml.get("reply_templates", {})

    # Resolve environment overrides
    def get_bool_env(key: str, default: bool) -> bool:
        val = os.getenv(key)
        if val is None:
            return default
        return val.strip().lower() in ("true", "1", "yes")

    def get_int_env(key: str, default: int) -> int:
        val = os.getenv(key)
        if val is None:
            return default
        try:
            return int(val.strip())
        except ValueError:
            return default

    dry_run = get_bool_env("DRY_RUN", sys_yaml.get("dry_run", True))
    auto_post = get_bool_env("AUTO_POST_ENABLED", sys_yaml.get("auto_post_enabled", False))
    emergency_stop = get_bool_env("EMERGENCY_STOP", sys_yaml.get("emergency_stop", False))
    daily_cap = get_int_env("DAILY_POST_CAP", sys_yaml.get("daily_post_cap", 50))
    poll_interval = get_int_env("POLLING_INTERVAL_MINUTES", sys_yaml.get("polling_interval_minutes", 5))

    return AppConfig(
        app_name=sys_yaml.get("app_name", "UPPCL X Complaint Monitoring & Sheet Sync"),
        version=sys_yaml.get("version", "1.0.0"),
        timezone=sys_yaml.get("timezone", "Asia/Kolkata"),
        polling_interval_minutes=poll_interval,
        dry_run=dry_run,
        auto_post_enabled=auto_post,
        emergency_stop=emergency_stop,
        daily_post_cap=daily_cap,
        x_bearer_token=os.getenv("X_BEARER_TOKEN"),
        x_api_key=os.getenv("X_API_KEY"),
        x_api_secret=os.getenv("X_API_SECRET"),
        x_access_token=os.getenv("X_ACCESS_TOKEN"),
        x_access_token_secret=os.getenv("X_ACCESS_TOKEN_SECRET"),
        google_service_account_file=os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE"),
        google_webhook_url=_sanitize_url(os.getenv("GOOGLE_WEBHOOK_URL") or sys_yaml.get("google_webhook_url")),
        google_spreadsheet_id=os.getenv("GOOGLE_SPREADSHEET_ID", "12smJ_xw3sRWPcCzDsh_hC44ac2NlpO9I_wDnXF-wFXU"),
        google_sheet_tab_name=os.getenv("GOOGLE_SHEET_TAB_NAME", "Twitter Complaint List"),
        sqlite_db_path=os.getenv("SQLITE_DB_PATH", "data/uppcl_monitor.db"),
        monitored_accounts=monitored,
        discoms=discoms_map,
        districts=districts_map,
        district_aliases=aliases_map,
        allowed_discom_handles=allowed_handles,
        reply_templates=templates,
    )
