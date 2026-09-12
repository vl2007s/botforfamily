"""Central configuration, loaded once at import time.

Secrets come exclusively from the environment (.env via python-dotenv) —
nothing sensitive is hardcoded, and .env is gitignored. Missing required
values fail fast at startup instead of half-configured."""

import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set. Copy .env.example to .env and fill in your values.")

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
if not ADMIN_ID:
    raise ValueError("ADMIN_ID is not set. Copy .env.example to .env and fill in your Telegram user ID.")

KINOPOISK_API_KEY = os.getenv("KINOPOISK_API_KEY", "")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
DB_PATH = os.path.join(BASE_DIR, "users.db")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
