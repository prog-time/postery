from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "change-me-in-production"

TEMPLATES_DIR = str(BASE_DIR / "admin" / "templates")
STATICS_DIR   = str(BASE_DIR / "admin" / "statics")
