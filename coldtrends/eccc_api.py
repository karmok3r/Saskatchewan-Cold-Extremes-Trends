"""Minimal client for the ECCC MSC GeoMet OGC API (api.weather.gc.ca)."""
import time

import pandas as pd
import requests

from .config import API

PAGE_SIZE = 10000

_session = requests.Session()
_session.headers["User-Agent"] = "saskatchewan-cold-extremes-trends"


def _get(url, params, retries=5):
    for attempt in range(retries):
        try:
            r = _session.get(url, params=params, timeout=180)
            if r.status_code < 500:
                r.raise_for_status()
                return r.json()
        except (requests.ConnectionError, requests.Timeout):
            pass
        time.sleep(2 ** attempt)
    raise RuntimeError(f"Request failed after {retries} attempts: {url} {params}")


def get_features(collection, **params):
    """Fetch every feature of a collection matching params, paging by offset."""
    url = f"{API}/collections/{collection}/items"
    features, offset = [], 0
    while True:
        page = _get(url, {"f": "json", "limit": PAGE_SIZE, "offset": offset, **params})
        batch = page.get("features", [])
        features.extend(batch)
        if len(batch) < PAGE_SIZE:
            return features
        offset += PAGE_SIZE


def to_frame(features):
    """Flatten GeoJSON features to a DataFrame with lon/lat columns."""
    rows = []
    for f in features:
        row = dict(f["properties"])
        geom = f.get("geometry")
        if geom and geom.get("type") == "Point":
            row["lon"], row["lat"] = geom["coordinates"][:2]
        rows.append(row)
    return pd.DataFrame(rows)
