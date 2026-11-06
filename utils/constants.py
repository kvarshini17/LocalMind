"""
constants.py
============
Centralized configuration and constant values for the application.
Keeping these in one place avoids hardcoded values scattered across modules
and makes the app easy to reconfigure.
"""

import os
from pathlib import Path

# --------------------------------------------------------------------------
# Base paths (all relative to project root, no hardcoded absolute paths)
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_DIR = BASE_DIR / "database"
UPLOADS_DIR = BASE_DIR / "uploads"
EXPORTS_DIR = BASE_DIR / "exports"
VECTORSTORE_DIR = BASE_DIR / "database" / "vectorstore"
SETTINGS_FILE = BASE_DIR / "database" / "settings.json"

DATABASE_PATH = DATABASE_DIR / "chats.db"

# Ensure required directories exist at import time
for _dir in (DATABASE_DIR, UPLOADS_DIR, EXPORTS_DIR, VECTORSTORE_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------
# Ollama configuration
# --------------------------------------------------------------------------
# 127.0.0.1 rather than "localhost": on Windows, localhost tries IPv6 (::1)
# first, which Ollama doesn't listen on, adding ~2s to every request.
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.environ.get("DEFAULT_OLLAMA_MODEL", "llama3.2:3b")
# How long Ollama keeps the model in memory after a request. The default
# (5m) means the first message after a short break pays a full reload.
OLLAMA_KEEP_ALIVE = os.environ.get("OLLAMA_KEEP_ALIVE", "30m")
# Only the most recent messages are sent as context, so long chats stay fast
# and the system prompt never gets truncated out of the context window.
MAX_HISTORY_MESSAGES = 12

# --------------------------------------------------------------------------
# RAG / PDF chat configuration
# --------------------------------------------------------------------------
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # sentence-transformers model
MAX_PDF_SIZE_MB = 50
TOP_K_RESULTS = 4
NO_ANSWER_MESSAGE = (
    "I couldn't find relevant information inside the uploaded documents."
)

# --------------------------------------------------------------------------
# UI / theme configuration
# --------------------------------------------------------------------------
APP_TITLE = "LocalMind"
APP_TAGLINE = "Your Intelligence. Your Device. Your Privacy."
APP_ICON = "🤖"

COLOR_USER_BUBBLE = "#2563EB"
COLOR_ACCENT_GRADIENT = "linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%)"

# Colors for the custom CSS, keyed by Streamlit's theme type. Page and sidebar
# backgrounds live in .streamlit/config.toml; keep the two files in sync.
THEME_COLORS = {
    "dark": {
        "card": "#1E1E1E",
        "assistant_bubble": "#262B33",
        "text": "#E6EDF3",
        "muted_text": "#8B949E",
        "border": "#30363D",
        "row_hover": "#2A2B32",
        "row_text": "#D1D5DB",
        "row_text_hover": "#FFFFFF",
        "shadow": "rgba(0,0,0,0.25)",
        "shadow_hover": "rgba(0,0,0,0.35)",
    },
    "light": {
        "card": "#F6F8FA",
        "assistant_bubble": "#F1F3F5",
        "text": "#1F2328",
        "muted_text": "#57606A",
        "border": "#D0D7DE",
        "row_hover": "#E8EBEF",
        "row_text": "#24292F",
        "row_text_hover": "#000000",
        "shadow": "rgba(0,0,0,0.08)",
        "shadow_hover": "rgba(0,0,0,0.14)",
    },
}

DEFAULT_TYPING_SPEED_MS = 0  # extra delay per word; 0 = show text as fast as it arrives
DEFAULT_FONT_SIZE = "Medium"

# --------------------------------------------------------------------------
# Default generation settings
# --------------------------------------------------------------------------
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 2048
DEFAULT_TOP_P = 0.9

# --------------------------------------------------------------------------
# History grouping labels
# --------------------------------------------------------------------------
GROUP_TODAY = "Today"
GROUP_YESTERDAY = "Yesterday"
GROUP_LAST_7_DAYS = "Last 7 Days"
GROUP_OLDER = "Older"

# --------------------------------------------------------------------------
# Export formats
# --------------------------------------------------------------------------
EXPORT_FORMATS = ["TXT", "Markdown", "PDF", "JSON"]

# --------------------------------------------------------------------------
# Fallback model list (used if Ollama isn't reachable when populating the
# settings dropdown for the first time)
# --------------------------------------------------------------------------
FALLBACK_MODELS = ["llama3.2", "mistral", "gemma", "phi", "deepseek"]
