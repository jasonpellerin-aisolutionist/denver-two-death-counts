"""Denver publishes two traffic-death counts. This package keeps them apart."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
EXPORTS = ROOT / "tableau" / "exports"
APP_DATA = ROOT / "app" / "data"
REPORTS = ROOT / "reports"

# Last complete calendar year in the open file. 2026 is year-to-date.
COMPLETE_YEAR = 2025
# A crash counts as on the High Injury Network within this distance.
HIN_BUFFER_M = 30
