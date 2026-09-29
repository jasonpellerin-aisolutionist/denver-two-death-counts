"""Pull Denver's open crash file and the High Injury Network. No credentials."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import requests

from twocounts import RAW

CRASHES = (
    "https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services/"
    "ODC_CRIME_TRAFFICACCIDENTS5YR_P/FeatureServer/325/query"
)
HIN = (
    "https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services/"
    "ODC_TRANS_HIN_L/FeatureServer/326/query"
)
FIELDS = (
    "object_id,incident_id,first_occurrence_date,incident_address,geo_lon,geo_lat,"
    "neighborhood_id,bicycle_ind,pedestrian_ind,ROAD_DESCRIPTION,LIGHT_CONDITION,"
    "SERIOUSLY_INJURED,FATALITIES,FATALITY_MODE_1,FATALITY_MODE_2,"
    "SERIOUSLY_INJURED_MODE_1,top_traffic_accident_offense"
)
# Outcome rows plus every pedestrian or bicycle crash. The full file is ~292,000
# property-damage crashes and is not needed for this question.
WHERE = "pedestrian_ind = 1 OR bicycle_ind = 1 OR FATALITIES > 0 OR SERIOUSLY_INJURED > 0"
PAGE = 2000


def session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "denver-two-death-counts/0.1 (research; jason@jasonpellerin.com)"
    return s


def _query(s: requests.Session, url: str, params: dict) -> dict:
    response = s.get(url, params=params, timeout=120)
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(payload["error"])
    return payload


def _pages(s: requests.Session, url: str, params: dict) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        page = _query(s, url, {**params, "resultOffset": offset, "resultRecordCount": PAGE})
        features = page.get("features") or []
        rows.extend(features)
        if not page.get("exceededTransferLimit") or not features:
            break
        offset += len(features)
    return rows


def yearly_totals(s: requests.Session) -> list[dict]:
    """One pass per year so a partial year cannot be mixed into a full one."""
    stats = json.dumps(
        [
            {"statisticType": "count", "onStatisticField": "object_id", "outStatisticFieldName": "crashes"},
            {"statisticType": "sum", "onStatisticField": "FATALITIES", "outStatisticFieldName": "deaths"},
            {"statisticType": "sum", "onStatisticField": "SERIOUSLY_INJURED", "outStatisticFieldName": "serious"},
        ]
    )
    out = []
    for year in range(2021, 2027):
        where = (
            f"first_occurrence_date >= timestamp '{year}-01-01 00:00:00' "
            f"AND first_occurrence_date < timestamp '{year + 1}-01-01 00:00:00'"
        )
        payload = _query(s, CRASHES, {"where": where, "outStatistics": stats, "f": "json"})
        row = payload["features"][0]["attributes"]
        row["year"] = year
        out.append(row)
    return out


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    s = session()
    crashes = _pages(
        s,
        CRASHES,
        {"where": WHERE, "outFields": FIELDS, "outSR": 4326, "f": "json"},
    )
    features = _pages(
        s,
        HIN,
        {
            "where": "1=1",
            "outFields": "StreetName,Tier,CrashRate",
            "outSR": 4326,
            "returnGeometry": "true",
            "f": "geojson",
        },
    )
    retrieved = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    (RAW / "ksi_and_vulnerable.json").write_text(json.dumps({"features": crashes}))
    (RAW / "hin.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    (RAW / "yearly.json").write_text(json.dumps(yearly_totals(s)))
    (RAW / "retrieved.json").write_text(
        json.dumps(
            {
                "retrieved": retrieved,
                "crash_service": CRASHES,
                "hin_service": HIN,
                "crash_rows": len(crashes),
                "hin_features": len(features),
            },
            indent=2,
        )
    )
    print(f"crashes {len(crashes)} hin {len(features)} retrieved {retrieved}")


if __name__ == "__main__":
    main()
