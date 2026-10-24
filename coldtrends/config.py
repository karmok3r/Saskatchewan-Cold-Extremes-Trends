"""Project-wide settings: paths, study period, quality thresholds."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DATA_RAW = ROOT / "data" / "raw"
DAILY_DIR = DATA_RAW / "daily"
DATA_PROCESSED = ROOT / "data" / "processed"
TABLES = ROOT / "outputs" / "tables"
FIGURES = ROOT / "outputs" / "figures"

API = "https://api.weather.gc.ca"
PROVINCE = "SK"

# Cold seasons run Jul-Jun and are labelled by the year they end in
# (winter 1999/2000 -> 2000). Frost-season indices use calendar years.
START_YEAR = 1951
END_YEAR = 2025

# ECCC often closes a station and opens a successor nearby under a new ID.
# Records are joined into composites when the successor is close, at a
# similar elevation, starts within a short gap, and extends the record.
JOIN_MAX_KM = 25
JOIN_MAX_ELEV_DIFF_M = 100
JOIN_MAX_GAP_YEARS = 2
JOIN_MIN_EXTENSION_YEARS = 5
MIN_ANCHOR_YEARS = 15

# A composite is kept only if it spans at least this many study-period years.
MIN_DAILY_YEARS = 40

# A season counts only if this fraction of days is present, both over the
# whole season and over the core cold months.
SEASON_COMPLETENESS = 0.85
CORE_COLD_MONTHS = [11, 12, 1, 2, 3]
CORE_COMPLETENESS = 0.90

# Trend tests need this many valid years, with coverage at both ends of
# the record so a trend isn't fitted to half the period.
MIN_VALID_YEARS = 30
EDGE_WINDOW = 15
MIN_EDGE_YEARS = 5

ALPHA = 0.05
BASELINE = (1961, 1990)

# Stations north of this latitude are grouped as "North (boreal)".
NORTH_LAT = 54.0

# Index metadata: label, units, and whether a positive trend means warming.
INDICES = {
    "TNn":    ("Coldest night of the season", "°C", +1),
    "TXn":    ("Coldest day of the season", "°C", +1),
    "DJF_TN": ("Winter (DJF) mean minimum temperature", "°C", +1),
    "DJF_TX": ("Winter (DJF) mean maximum temperature", "°C", +1),
    "FD":     ("Frost days (Tmin < 0 °C)", "days", -1),
    "ID":     ("Ice days (Tmax < 0 °C)", "days", -1),
    "CN30":   ("Nights at or below −30 °C", "days", -1),
    "CN40":   ("Nights at or below −40 °C", "days", -1),
    "LSF":    ("Last spring frost", "day of year", -1),
    "FFF":    ("First fall frost", "day of year", +1),
    "FFS":    ("Frost-free season length", "days", +1),
}

# AHCCD (homogenized) variables and periods to test.
AHCCD_VARS = {"temp_min": "Tmin", "temp_mean": "Tmean", "temp_max": "Tmax"}
AHCCD_PERIODS = ["Win", "Spr", "Sum", "Fal", "Ann"]
