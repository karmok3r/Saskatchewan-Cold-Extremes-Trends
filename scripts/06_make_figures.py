"""Provincial anomaly time series (south vs north) and quick-look station trend maps."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

from coldtrends.config import (ALPHA, BASELINE, DATA_PROCESSED, END_YEAR, FIGURES, INDICES,
                               START_YEAR, TABLES)
from coldtrends.trends import mann_kendall_sen

SURFACE, INK, INK_2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
REGION_COLORS = {"South (prairie)": "#2a78d6", "North (boreal)": "#eb6834"}
DIVERGING = LinearSegmentedColormap.from_list("cool_warm", ["#2a78d6", "#f0efec", "#e34948"])
MIN_BASELINE_YEARS = 15
MIN_STATIONS = 3

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK_2, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
})


def regional_anomalies(idx, metric):
    """Station anomalies vs each station's baseline mean, averaged by region and year."""
    base = idx[idx["year"].between(*BASELINE)].groupby("loc_id")[metric].agg(["mean", "count"])
    base = base[base["count"] >= MIN_BASELINE_YEARS]["mean"]
    d = idx[idx["loc_id"].isin(base.index)][["loc_id", "region", "year", metric]].dropna()
    d["anom"] = d[metric] - d["loc_id"].map(base)
    g = d.groupby(["region", "year"])["anom"].agg(["mean", "count"]).reset_index()
    return g[g["count"] >= MIN_STATIONS]


def plot_timeseries(idx, metric, rows):
    label, units, _ = INDICES[metric]
    anoms = regional_anomalies(idx, metric)
    if anoms.empty:
        return
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.axhline(0, color=AXIS, linewidth=1)
    for region, color in REGION_COLORS.items():
        r = anoms[anoms["region"] == region].set_index("year").reindex(range(START_YEAR, END_YEAR + 1))
        if r["mean"].notna().sum() < 10:
            continue
        ax.plot(r.index, r["mean"], color=color, linewidth=0.8, alpha=0.4)
        smooth = r["mean"].rolling(10, center=True, min_periods=6).mean()
        ax.plot(r.index, smooth, color=color, linewidth=2, label=f"{region} — 10-yr mean")
        n, slope, intercept, _, p = mann_kendall_sen(r.index.values, r["mean"].values)
        ax.plot(r.index, intercept + slope * r.index.values, color=color, linewidth=1.2, linestyle="--")
        last = smooth.dropna()
        ax.annotate(f"{region.split()[0]}  {slope * 10:+.2f} {units}/decade",
                    (last.index[-1], last.iloc[-1]), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=9, color=INK_2)
        rows.append({"metric": metric, "region": region, "years": n,
                     "slope_decade": slope * 10, "p": p})
    ax.set_title(f"{label}: Saskatchewan regional anomaly", loc="left")
    ax.set_ylabel(f"Anomaly vs {BASELINE[0]}–{BASELINE[1]} ({units})")
    ax.set_xlim(START_YEAR, END_YEAR + 14)
    ax.legend(frameon=False, loc="upper left", fontsize=9)
    fig.text(0.01, 0.01, "Thin: annual mean of station anomalies · Dashed: Sen's slope · "
             "Source: ECCC daily climate observations", fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(FIGURES / f"ts_{metric}.png", dpi=200)
    plt.close(fig)


def plot_station_map(trends, metric, label, units, warming_sign, source):
    col, sig = f"slope_{metric}", f"sig_{metric}"
    if col not in trends:
        return
    d = trends.dropna(subset=[col])
    lim = np.nanpercentile(np.abs(d[col]), 95) or 1
    cmap = DIVERGING if warming_sign > 0 else DIVERGING.reversed()
    norm = TwoSlopeNorm(0, -lim, lim)
    fig, ax = plt.subplots(figsize=(6, 7.5))
    s_ = d[d[sig] == 1]
    ns = d[d[sig] != 1]
    ax.scatter(ns["lon"], ns["lat"], s=60, facecolors="none", edgecolors=cmap(norm(ns[col])),
               linewidths=2, label=f"Not significant (FDR q ≥ {ALPHA})")
    sc = ax.scatter(s_["lon"], s_["lat"], s=70, c=s_[col], cmap=cmap, norm=norm,
                    edgecolors=SURFACE, linewidths=1.5, label=f"Significant (q < {ALPHA})")
    if s_.empty:
        sc = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    cb = fig.colorbar(sc, ax=ax, shrink=0.7, pad=0.02, extend="both")
    cb.set_label(f"Sen's slope ({units}/decade) — red = toward warmer", color=INK_2)
    cb.outline.set_visible(False)
    ax.set_aspect(1 / np.cos(np.radians(54)))
    ax.set_xlim(-110.2, -101.2)
    ax.set_ylim(48.8, 60.2)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title(f"{label}\nstation trends", loc="left")
    ax.legend(frameon=False, loc="upper right", fontsize=8)
    fig.text(0.01, 0.01, source, fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(FIGURES / f"map_{metric}.png", dpi=200)
    plt.close(fig)


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    idx = pd.read_csv(DATA_PROCESSED / "station_indices.csv", dtype={"station_id": str})
    trends = pd.read_csv(TABLES / "station_trends.csv", dtype={"station_id": str})
    rows = []
    for metric, (label, units, sign) in INDICES.items():
        plot_timeseries(idx, metric, rows)
        plot_station_map(trends, metric, label, units, sign,
                         f"ECCC daily observations, {START_YEAR}–{END_YEAR}")
    pd.DataFrame(rows).to_csv(TABLES / "regional_trends.csv", index=False)

    ahccd = pd.read_csv(TABLES / "ahccd_trends.csv", dtype={"station_id": str})
    plot_station_map(ahccd, "Tmin_Win", "Winter mean minimum temperature (AHCCD, homogenized)",
                     "°C", +1, "ECCC AHCCD homogenized seasonal data")
    print(f"Figures written to {FIGURES}")


if __name__ == "__main__":
    main()
