"""Download AHCCD homogenized seasonal and annual temperatures for Saskatchewan."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from coldtrends.config import DATA_RAW, PROVINCE
from coldtrends.eccc_api import get_features, to_frame

RENAME = {
    "station_id__id_station": "station_id",
    "period_value__valeur_periode": "period",
    "year__annee": "year",
    "temp_min__temp_min": "temp_min",
    "temp_mean__temp_moyenne": "temp_mean",
    "temp_max__temp_max": "temp_max",
}


def main():
    DATA_RAW.mkdir(parents=True, exist_ok=True)

    stations = to_frame(get_features("ahccd-stations", province__province=PROVINCE,
                                     measurement_type__type_mesure="temp_mean"))
    stations = stations.rename(columns={"station_id__id_station": "station_id",
                                        "station_name__nom_station": "station_name",
                                        "joined__rejoint": "joined",
                                        "start_date__date_debut": "start_date",
                                        "end_date__date_fin": "end_date"})
    stations[["station_id", "station_name", "lon", "lat", "joined", "start_date", "end_date"]] \
        .to_csv(DATA_RAW / "ahccd_stations.csv", index=False)

    frames = []
    for collection in ["ahccd-seasonal", "ahccd-annual"]:
        df = to_frame(get_features(collection, province__province=PROVINCE, skipGeometry="true"))
        frames.append(df.rename(columns=RENAME)[list(RENAME.values())])
    values = pd.concat(frames, ignore_index=True)
    for col in ["temp_min", "temp_mean", "temp_max"]:
        values[col] = values[col].where(values[col] > -9999)
    values = values.dropna(subset=["temp_min", "temp_mean", "temp_max"], how="all")
    values.to_csv(DATA_RAW / "ahccd_values.csv", index=False)
    print(f"{len(stations)} AHCCD temperature stations, {len(values)} station-period values.")


if __name__ == "__main__":
    main()
