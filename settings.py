"""Paths and settings. Reads .env automatically so the API key never goes in code."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env_file():
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()

SAMPLE_DIR = ROOT / "sample_data"
CASES_DIR = SAMPLE_DIR / "cases"
OUTPUT_DIR = ROOT / "outputs"
RESULTS_DIR = OUTPUT_DIR / "case_results"
AUDIT_LOG = OUTPUT_DIR / "audit_log.jsonl"
DECISIONS_FILE = OUTPUT_DIR / "decisions.json"
FRONTEND_DIST = ROOT / "frontend" / "dist"

MODEL = os.getenv("PA_MODEL", "claude-sonnet-5-5")


def use_claude() -> bool:
    """Claude runs when a key is set and offline mode is not forced (PA_OFFLINE=true)."""
    return bool(os.getenv("ANTHROPIC_API_KEY")) and os.getenv("PA_OFFLINE", "false").lower() != "true"


def coverage_rules() -> dict:
    return read_json(Path(__file__).parent / "coverage_rules.json")


def read_json(path: Path, default=None):
    import json
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_json(path: Path, data):
    import json
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
