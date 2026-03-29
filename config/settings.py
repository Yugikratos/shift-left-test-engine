"""Application settings — loads from .env file or environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

# ── Paths ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
MOCK_DATA_DIR = BASE_DIR / "mock_data"
KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"
DML_DIR = MOCK_DATA_DIR / "dml"
DDL_DIR = MOCK_DATA_DIR / "ddl"
SAMPLE_DATA_DIR = MOCK_DATA_DIR / "sample_data"

# ── LLM Configuration ─────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-20250514")
LLM_ENABLED = bool(ANTHROPIC_API_KEY)

# ── Database ───────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'test_data_engine.db'}")
TARGET_DB_URL = os.getenv("TARGET_DB_URL", f"sqlite:///{BASE_DIR / 'target_test.db'}")

# ── Logging ────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ── API ────────────────────────────────────────────────
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# ── Agent Settings ─────────────────────────────────────
DEFAULT_RECORD_COUNT = 100
MAX_RECORD_COUNT = 10000
MASKING_ENABLED = True

# ── PII Detection Patterns ─────────────────────────────
PII_NAME_PATTERNS = [
    "_nm", "_name", "first_nm", "last_nm", "mid_init",
    "_prefix", "_suffix", "_title", "ceo_",
]
PII_ADDRESS_PATTERNS = [
    "_addr", "_street", "_city", "_state", "_zip",
    "_mail_", "_phys_", "str_addr", "cty_nm", "st_abbr",
]
PII_PHONE_PATTERNS = [
    "_phone", "_area_cd", "_exchng", "_ext_nbr",
    "bus_area", "bus_exchng",
]
PII_ID_PATTERNS = [
    "ssn", "tax_id", "ein", "passport",
]

# ── ETL Control Field Patterns ─────────────────────────
CONTROL_FIELD_PATTERNS = [
    "etl_", "dw_load", "dw_updt", "rec_seq",
    "cyc_dt", "proc_cd", "src_cd", "ctl_rec",
    "publ_id", "chkum", "newline",
]

# ── SCD-2 Detection Patterns ──────────────────────────
SCD2_PATTERNS = [
    "eff_sdt", "eff_edt", "eff_strt_dt", "eff_end_dt",
    "eff_start_date", "eff_end_date", "logc_del_ind",
]

# ── Relationship Key Patterns ─────────────────────────
RELATIONSHIP_KEY_PATTERNS = [
    "_id", "_nbr", "_number", "_cd", "_key",
]


def print_config():
    """Print current configuration for debugging."""
    print(f"  Base Dir:      {BASE_DIR}")
    print(f"  LLM Enabled:   {LLM_ENABLED}")
    print(f"  LLM Model:     {LLM_MODEL}")
    print(f"  Database:      {DATABASE_URL}")
    print(f"  Log Level:     {LOG_LEVEL}")
    print(f"  Mock Data Dir: {MOCK_DATA_DIR}")
