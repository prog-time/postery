import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

_secret_key = os.environ.get("SECRET_KEY")
if not _secret_key:
    raise RuntimeError(
        "SECRET_KEY is not set. "
        "Add SECRET_KEY=<random-hex-32> to your .env file or environment. "
        "Generate a key with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
SECRET_KEY = _secret_key

TEMPLATES_DIR = str(BASE_DIR / "admin" / "templates")
STATICS_DIR   = str(BASE_DIR / "admin" / "statics")

# Retry settings for the background publishing worker (TASK-002)
MAX_ATTEMPTS = 3          # maximum publish attempts before marking channel as FAILED
RETRY_DELAY_MINUTES = 5   # base delay between retries; actual delay = attempt * RETRY_DELAY_MINUTES
