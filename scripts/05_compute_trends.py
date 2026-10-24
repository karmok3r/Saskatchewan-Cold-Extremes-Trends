"""Mann-Kendall / Sen's slope trends for station indices and AHCCD seasonal temperatures."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from coldtrends.config import (AHCCD_PERIODS, AHCCD_VARS, ALPHA, DATA_PROCESSED, DATA_RAW,
                               END_YEAR, INDICES, NORTH_LAT, START_YEAR, TABLES)
from coldtrends.trends import fdr_bh, has_coverage, mann_kendall_sen


def trend_rows(groups, metrics, start, end):
    """Long table of trends: one row per station and metric."""
    rows = []
    for key, g in groups:
        g = g.set_index("year").reindex(range(start, end + 1))
        for metric in metrics:
            years, vals = g.index.values, g[metric].values.astype(float)
            if not has_coverage(years, vals, start, end):
                continue
            n, slope, _, tau, p = mann_kendall_sen(years, vals)
            rows.append({"key": key, "metric": metric, "n_years": n,
                         "slope_decade": slope * 10, "tau": tau, "p": p})
    long = pd.DataFrame(rows)
    long["q"] = long.groupby("metric")["p"].transform(lambda s: fdr_bh(s.values))
    long["sig"] = (long["q"] < ALPHA).astype(int)
    return long


def widen(long, meta, key_col):
    wide = long.pivot(index="key", columns="metric", values=["slope_decade", "p", "q", "sig", "n_years"])
    prefix = {"slope_decade": "slope", "p": "p", "q": "q", "sig": "sig", "n_years": "n"}
    wide.columns = [f"{prefix[stat]}_{metric}" for stat, metric in wide.columns]
    return meta.merge(wide, left_on=key_col, right_index=True, how="inner")


def summarize(long, direction):
    rows = []
    for metric, g in long.groupby("metric"):
        warm = np.sign(g["slope_decade"]) == direction.get(metric, 1)
        rows.append({"metric": metric, "stations": len(g),
                     "median_slope_decade": g["slope_decade"].median(),
                     "pct_sig_warming": 100 * ((g["sig"] == 1) & warm).mean(),
                     "pct_sig_cooling": 100 * ((g["sig"] == 1) & ~warm & (g["slope_decade"] != 0)).mean()})
    return pd.DataFrame(rows)


def main():
    TABLES.mkdir(parents=True, exist_ok=True)

    # Daily-station cold indices.
    idx = pd.read_csv(DATA_PROCESSED / "station_indices.csv", dtype={"station_id": str})
    long = trend_rows(idx.groupby("loc_id"), list(INDICES), START_YEAR, END_YEAR)
    meta = idx[["loc_id", "station_id", "station_name", "lon", "lat", "region"]].drop_duplicates("loc_id")
    long.rename(columns={"key": "loc_id"}).merge(meta, on="loc_id") \
        .to_csv(TABLES / "station_trends_long.csv", index=False)
    widen(long, meta, "loc_id").to_csv(TABLES / "station_trends.csv", index=False)
    summarize(long, {k: v[2] for k, v in INDICES.items()}) \
        .to_csv(TABLES / "station_trend_summary.csv", index=False)

    # AHCCD homogenized seasonal/annual temperatures (records end ~2020).
    ah = pd.read_csv(DATA_RAW / "ahccd_values.csv", dtype={"station_id": str})
    ah_end = min(END_YEAR, int(ah["year"].max()))
    ah = ah[ah["period"].isin(AHCCD_PERIODS)]
    wide = ah.pivot_table(index=["station_id", "year"], columns="period", values=list(AHCCD_VARS))
    wide.columns = [f"{AHCCD_VARS[var]}_{period}" for var, period in wide.columns]
    wide = wide.reset_index()
    metrics = [c for c in wide.columns if c not in ("station_id", "year")]
    ah_long = trend_rows(wide.groupby("station_id"), metrics, START_YEAR, ah_end)

    ah_meta = pd.read_csv(DATA_RAW / "ahccd_stations.csv", dtype={"station_id": str})
    ah_meta["region"] = np.where(ah_meta["lat"] >= NORTH_LAT, "North (boreal)", "South (prairie)")
    ah_meta = ah_meta[["station_id", "station_name", "lon", "lat", "region"]]
    ah_long.rename(columns={"key": "station_id"}).merge(ah_meta, on="station_id") \
        .to_csv(TABLES / "ahccd_trends_long.csv", index=False)
    widen(ah_long, ah_meta, "station_id").to_csv(TABLES / "ahccd_trends.csv", index=False)
    summarize(ah_long, {}).to_csv(TABLES / "ahccd_trend_summary.csv", index=False)

    print(f"Station-index trends: {long['key'].nunique()} stations; "
          f"AHCCD trends ({START_YEAR}-{ah_end}): {ah_long['key'].nunique()} stations.")


if __name__ == "__main__":
    main()
