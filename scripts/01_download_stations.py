"""List Saskatchewan climate stations and build long composite station records.

Each composite starts from an anchor station and is extended forwards/backwards
with nearby successor or predecessor stations (see JOIN_* in config).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from coldtrends.config import (DATA_RAW, END_YEAR, JOIN_MAX_ELEV_DIFF_M, JOIN_MAX_GAP_YEARS,
                               JOIN_MAX_KM, JOIN_MIN_EXTENSION_YEARS, MIN_ANCHOR_YEARS,
                               MIN_DAILY_YEARS, PROVINCE, START_YEAR)
from coldtrends.eccc_api import get_features, to_frame

WINDOW_START = pd.Timestamp(f"{START_YEAR - 1}-07-01")
WINDOW_END = pd.Timestamp(f"{END_YEAR}-12-31")


def distance_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    h = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(h))


def span_years(start, end):
    return max((min(end, WINDOW_END) - max(start, WINDOW_START)).days / 365.25, 0)


def build_composites(stations):
    gap = pd.Timedelta(days=round(365.25 * JOIN_MAX_GAP_YEARS))
    extension = pd.Timedelta(days=round(365.25 * JOIN_MIN_EXTENSION_YEARS))
    used, composites = set(), []
    for _, anchor in stations.sort_values("overlap_years", ascending=False).iterrows():
        if anchor.CLIMATE_IDENTIFIER in used or anchor.overlap_years < MIN_ANCHOR_YEARS:
            continue
        members = [anchor.CLIMATE_IDENTIFIER]
        used.add(anchor.CLIMATE_IDENTIFIER)
        start, end = anchor["first"], anchor["last"]
        while True:
            c = stations[~stations.CLIMATE_IDENTIFIER.isin(used)].copy()
            c["km"] = distance_km(anchor.lat, anchor.lon, c.lat, c.lon)
            c = c[(c.km <= JOIN_MAX_KM) &
                  ((c.elev - anchor.elev).abs().fillna(0) <= JOIN_MAX_ELEV_DIFF_M)]
            forward = c[(end < WINDOW_END) & (c["first"] <= end + gap) & (c["last"] > end + extension)]
            backward = c[(start > WINDOW_START) & (c["last"] >= start - gap) & (c["first"] < start - extension)]
            candidates = pd.concat([forward, backward])
            if candidates.empty:
                break
            best = candidates.sort_values("km").iloc[0]
            members.append(best.CLIMATE_IDENTIFIER)
            used.add(best.CLIMATE_IDENTIFIER)
            start, end = min(start, best["first"]), max(end, best["last"])
        composites.append({
            "composite_id": anchor.CLIMATE_IDENTIFIER, "STATION_NAME": anchor.STATION_NAME,
            "lon": anchor.lon, "lat": anchor.lat, "ELEVATION": anchor.elev,
            "members": ";".join(members), "n_members": len(members),
            "first_year": max(start, WINDOW_START).year, "last_year": min(end, WINDOW_END).year,
            "span_years": round(span_years(start, end), 1),
        })
    return pd.DataFrame(composites)


def main():
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    stations = to_frame(get_features("climate-stations", PROV_STATE_TERR_CODE=PROVINCE))
    stations = stations.dropna(subset=["DLY_FIRST_DATE", "DLY_LAST_DATE"]).copy()
    stations["first"] = pd.to_datetime(stations["DLY_FIRST_DATE"])
    stations["last"] = pd.to_datetime(stations["DLY_LAST_DATE"])
    stations["elev"] = pd.to_numeric(stations["ELEVATION"], errors="coerce")
    stations["overlap_years"] = [round(span_years(a, b), 1) for a, b in zip(stations["first"], stations["last"])]

    keep = ["CLIMATE_IDENTIFIER", "STATION_NAME", "lon", "lat", "ELEVATION",
            "DLY_FIRST_DATE", "DLY_LAST_DATE", "overlap_years"]
    stations[keep].to_csv(DATA_RAW / "stations_all.csv", index=False)

    composites = build_composites(stations[stations["overlap_years"] > 0])
    selected = composites[composites["span_years"] >= MIN_DAILY_YEARS]
    selected = selected.sort_values("span_years", ascending=False)
    selected.to_csv(DATA_RAW / "stations_selected.csv", index=False)
    print(f"{len(stations)} SK stations with daily data -> {len(selected)} composites spanning "
          f">= {MIN_DAILY_YEARS} years ({(selected['n_members'] > 1).sum()} joined from several IDs, "
          f"{selected['n_members'].sum()} station records to download).")


if __name__ == "__main__":
    main()
