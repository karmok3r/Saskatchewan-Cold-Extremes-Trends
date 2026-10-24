"""Compute annual cold-extreme indices for every downloaded station."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from coldtrends.config import DAILY_DIR, DATA_PROCESSED, DATA_RAW, INDICES, NORTH_LAT
from coldtrends.indices import station_indices


def composite_daily(members):
    """Merge member stations' daily records; earlier members take priority on overlap."""
    frames = []
    for climate_id in members.split(";"):
        path = DAILY_DIR / f"{climate_id}.csv"
        if path.exists() and path.stat().st_size > 0:
            df = pd.read_csv(path)
            if not df.empty:
                df["LOCAL_DATE"] = pd.to_datetime(df["LOCAL_DATE"]).dt.normalize()
                frames.append(df.dropna(subset=["MIN_TEMPERATURE", "MAX_TEMPERATURE"], how="all")
                              .drop_duplicates("LOCAL_DATE").set_index("LOCAL_DATE"))
    if not frames:
        return pd.DataFrame()
    merged = frames[0]
    for df in frames[1:]:
        merged = merged.combine_first(df)
    return merged.reset_index()


def main():
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    stations = pd.read_csv(DATA_RAW / "stations_selected.csv", dtype={"composite_id": str, "members": str})
    frames = []
    for loc_id, st in enumerate(stations.itertuples(), 1):
        daily = composite_daily(st.members)
        if daily.empty:
            continue
        idx = station_indices(daily)
        if idx.empty:
            continue
        # loc_id is an integer key; ArcGIS space-time cubes require one.
        idx.insert(0, "loc_id", loc_id)
        idx.insert(1, "station_id", st.composite_id)
        idx.insert(2, "station_name", st.STATION_NAME)
        idx.insert(3, "lon", st.lon)
        idx.insert(4, "lat", st.lat)
        idx.insert(5, "region", "North (boreal)" if st.lat >= NORTH_LAT else "South (prairie)")
        frames.append(idx)
        print(f"{st.STATION_NAME}: {idx['TNn'].notna().sum()} valid cold seasons")

    out = pd.concat(frames, ignore_index=True).sort_values(["loc_id", "year"])
    out["date"] = pd.to_datetime(out["year"].astype(str) + "-01-01").dt.strftime("%Y-%m-%d")
    cols = ["loc_id", "station_id", "station_name", "lon", "lat", "region", "year", "date", *INDICES]
    out[cols].to_csv(DATA_PROCESSED / "station_indices.csv", index=False)
    print(f"Wrote {len(out)} station-years for {out['loc_id'].nunique()} stations.")


if __name__ == "__main__":
    main()
