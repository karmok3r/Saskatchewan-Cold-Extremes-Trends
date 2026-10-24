"""Download daily Tmin/Tmax for the selected stations (resumable)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from coldtrends.config import DAILY_DIR, DATA_RAW
from coldtrends.eccc_api import get_features, to_frame

FIELDS = "LOCAL_DATE,MIN_TEMPERATURE,MAX_TEMPERATURE"


def main():
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    composites = pd.read_csv(DATA_RAW / "stations_selected.csv", dtype=str)
    ids = sorted({m for members in composites["members"] for m in members.split(";")})
    for k, climate_id in enumerate(ids, 1):
        out = DAILY_DIR / f"{climate_id}.csv"
        if out.exists():
            continue
        feats = get_features("climate-daily", CLIMATE_IDENTIFIER=climate_id,
                             properties=FIELDS, skipGeometry="true", sortby="LOCAL_DATE")
        df = to_frame(feats)
        df.to_csv(out, index=False)
        print(f"[{k}/{len(ids)}] {climate_id}: {len(df)} days")


if __name__ == "__main__":
    main()
