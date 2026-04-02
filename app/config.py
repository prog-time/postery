import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")

TEMPLATES_DIR = str(BASE_DIR / "admin" / "templates")
STATICS_DIR   = str(BASE_DIR / "admin" / "statics")
