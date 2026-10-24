"""Annual cold-extreme indices from a daily Tmin/Tmax series."""
import numpy as np
import pandas as pd

from .config import (CORE_COLD_MONTHS, CORE_COMPLETENESS, END_YEAR,
                     SEASON_COMPLETENESS, START_YEAR)


def _complete(s, frac):
    return s.notna().mean() >= frac


def season_indices(tn, tx):
    """Indices for Jul-Jun cold seasons. tn/tx are daily Series on a full date index."""
    season = tn.index.year + (tn.index.month >= 7)
    core = tn.index.month.isin(CORE_COLD_MONTHS)
    djf = tn.index.month.isin([12, 1, 2])
    rows = []
    for year in range(START_YEAR, END_YEAR + 1):
        m = season == year
        if not m.any():
            continue
        tn_s, tx_s = tn[m], tx[m]
        row = {"year": year}
        if _complete(tn_s, SEASON_COMPLETENESS) and _complete(tn[m & core], CORE_COMPLETENESS):
            row.update(TNn=tn_s.min(), FD=int((tn_s < 0).sum()),
                       CN30=int((tn_s <= -30).sum()), CN40=int((tn_s <= -40).sum()))
            if _complete(tn[m & djf], CORE_COMPLETENESS):
                row["DJF_TN"] = tn[m & djf].mean()
        if _complete(tx_s, SEASON_COMPLETENESS) and _complete(tx[m & core], CORE_COMPLETENESS):
            row.update(TXn=tx_s.min(), ID=int((tx_s < 0).sum()))
            if _complete(tx[m & djf], CORE_COMPLETENESS):
                row["DJF_TX"] = tx[m & djf].mean()
        rows.append(row)
    return pd.DataFrame(rows, columns=["year", "TNn", "FD", "CN30", "CN40", "DJF_TN",
                                       "TXn", "ID", "DJF_TX"])


def frost_season_indices(tn):
    """Last spring frost, first fall frost and frost-free length per calendar year."""
    rows = []
    for year in range(START_YEAR, END_YEAR + 1):
        spring = tn[f"{year}-03-01":f"{year}-07-14"]
        fall = tn[f"{year}-07-15":f"{year}-11-30"]
        if len(spring) == 0 or len(fall) == 0:
            continue
        if not (_complete(spring, CORE_COMPLETENESS) and _complete(fall, CORE_COMPLETENESS)):
            continue
        spring_frosts = spring[spring <= 0]
        fall_frosts = fall[fall <= 0]
        lsf = spring_frosts.index[-1].dayofyear if len(spring_frosts) else np.nan
        fff = fall_frosts.index[0].dayofyear if len(fall_frosts) else np.nan
        rows.append({"year": year, "LSF": lsf, "FFF": fff, "FFS": fff - lsf - 1})
    return pd.DataFrame(rows, columns=["year", "LSF", "FFF", "FFS"])


def station_indices(daily):
    """All indices for one station. daily has LOCAL_DATE, MIN_TEMPERATURE, MAX_TEMPERATURE."""
    df = daily.copy()
    df["LOCAL_DATE"] = pd.to_datetime(df["LOCAL_DATE"]).dt.normalize()
    df = df.drop_duplicates("LOCAL_DATE").set_index("LOCAL_DATE").sort_index()
    full = pd.date_range(f"{START_YEAR - 1}-07-01", f"{END_YEAR}-12-31", freq="D")
    df = df.reindex(full)
    tn = pd.to_numeric(df["MIN_TEMPERATURE"], errors="coerce")
    tx = pd.to_numeric(df["MAX_TEMPERATURE"], errors="coerce")
    return season_indices(tn, tx).merge(frost_season_indices(tn), on="year", how="outer")
