from dotenv import load_dotenv
import os
import sys

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
WATCH_PATH = os.getenv("WATCH_PATH", "")
APP_TYPE = os.getenv("APP_TYPE", "python")
CONFIG_FILE = os.getenv("CONFIG_FILE", "agent_sources.json")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50"))
FLUSH_INTERVAL = float(os.getenv("FLUSH_INTERVAL", "5.0"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
DEAD_LETTER_FILE = os.getenv("DEAD_LETTER_FILE", "agent_dead_letter.jsonl")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
AGENT_USERNAME = os.getenv("AGENT_USERNAME", "")
AGENT_PASSWORD = os.getenv("AGENT_PASSWORD", "")

_VALID_APP_TYPES = {"python", "node", "windows"}
if APP_TYPE not in _VALID_APP_TYPES:
    print(
        f"[agent] WARNING: APP_TYPE='{APP_TYPE}' is not one of {sorted(_VALID_APP_TYPES)}",
        file=sys.stderr,
    )
