"""Environment settings. Importing this module has no network side effects."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CATALOG_PATH = ROOT / "catalog.json"


def allowed_users():
    raw = os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "")
    return {int(value.strip()) for value in raw.split(",") if value.strip()}


def dashboard_url():
    return os.environ.get("DASHBOARD_URL", "").strip()
