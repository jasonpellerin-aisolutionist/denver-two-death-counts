"""Turn the open file and the reported city figures into separate tables.

The two death counts are never added together. A test fails the build if they are.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

import pandas as pd
from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.ops import transform, unary_union

from twocounts import APP_DATA, COMPLETE_YEAR, EXPORTS, HIN_BUFFER_M, RAW, REPORTS

# Figures printed by DOTI or by the city's Vision Zero page. They are not
# computed from the open file. Each one names the place it was read.
REPORTED = [
    {
        "metric": "traffic_deaths",
        "year": 2024,
        "value": 80,
        "partial_year": False,
        "source": "Denver Gazette, 2026-02-03",
        "note": "The article's newest data: fatalities increased from 80 to 93.",
    },
    {
        "metric": "traffic_deaths",
        "year": 2025,
        "value": 93,
        "partial_year": False,
        "source": "Denver Gazette, 2026-02-03",
        "note": "Same article. Denver Streets Partnership also said 93, the deadliest year since 2013.",
    },
    {
        "metric": "traffic_deaths",
        "year": 2025,
        "value": 94,
        "partial_year": False,
        "source": "denvergov.org Vision Zero statistics, read 2026-09-29",
        "note": "The page says some dashboard connections may not be current, and points readers to the open data catalog.",
    },
    {
        "metric": "traffic_deaths",
        "year": 2026,
        "value": 47,
        "partial_year": True,
        "source": "denvergov.org Vision Zero statistics, read 2026-09-29",
        "note": "Year to date on the day the page was read. Not a full year.",
    },
    {
        "metric": "pedestrian_deaths",
        "year": 2021,
        "value": 23,
        "partial_year": False,
        "source": "DOTI, via Denver Gazette, 2026-02-03",
        "note": "Pedestrian deaths climbed from 23 in 2021 to 26 in 2024, then 35 in 2025.",
    },
    {
        "metric": "pedestrian_deaths",
        "year": 2024,
        "value": 26,
        "partial_year": False,
        "source": "DOTI, via Denver Gazette, 2026-02-03",
        "note": "One of the 2024 pedestrian deaths was on a freeway, the spokesperson said.",
    },
    {
        "metric": "pedestrian_deaths",
        "year": 2025,
        "value": 35,
        "partial_year": False,
        "source": "DOTI, via Denver Gazette, 2026-02-03",
        "note": "Eight of the 35 were on a freeway. Around half of those eight involved someone who had pulled over.",
    },
    {
        "metric": "cyclist_deaths",
        "year": 2021,
        "value": 4,
        "partial_year": False,
        "source": "DOTI, via Denver Gazette, 2026-02-03",
        "note": "Cyclist deaths rose from four in 2021 to five in 2025.",
    },
    {
        "metric": "cyclist_deaths",
        "year": 2025,
        "value": 5,
        "partial_year": False,
        "source": "DOTI, via Denver Gazette, 2026-02-03",
        "note": "Electric stand-up scooter deaths were eight in 2025 and zero in 2024, in the same DOTI account. A moped was one more.",
    },
    {
        "metric": "serious_injuries",
        "year": 2024,
        "value": 410,
        "partial_year": False,
        "source": "Denver Gazette, 2026-02-03",
        "note": "The article's newest data: serious injuries fell from 410 to 356. This may not be the file's SERIOUSLY_INJURED field.",
    },
    {
        "metric": "serious_injuries",
        "year": 2025,
        "value": 356,
        "partial_year": False,
        "source": "Denver Gazette, 2026-02-03",
        "note": "Reported drop. The open file's serious-injury sum did not drop. They are kept as different series.",
    },
]


def _records(path) -> pd.DataFrame:
    payload = json.loads(path.read_text())
    rows = []
    for feature in payload["features"]:
        attrs = feature.get("attributes") or feature
        rows.append(attrs)
    frame = pd.DataFrame(rows)
    frame["occurred"] = pd.to_datetime(frame["first_occurrence_date"], unit="ms", utc=True)
    frame["year"] = frame["occurred"].dt.year
    return frame


def _mode(row: pd.Series) -> str:
    text = " ".join(
        str(row.get(col) or "") for col in ("FATALITY_MODE_1", "FATALITY_MODE_2")
    ).upper()
    if "PEDESTRIAN" in text:
        return "pedestrian"
    if "BICYCLE" in text or "MOTORIZED BICYCLE" in text:
        return "bicycle"
    if "MOTORCYCLE" in text or "AUTOCYCLE" in text:
        return "motorcycle"
    if not text.strip():
        return "unspecified"
    return "motor vehicle"


def _street(address: object) -> list[str]:
    if not isinstance(address, str) or not address.strip():
        return []
    parts = re.split(r"\s*/\s*", address.upper())
    names = []
    for part in parts:
        part = re.sub(r"^\d+\s+", "", part.strip())
        part = re.sub(r"^(N|S|E|W|NB|SB|EB|WB)\s+", "", part)
        part = re.sub(r"\s+(N|S|E|W|NB|SB|EB|WB)$", "", part)
        if part and not part.startswith(("I25", "I70")):
            names.append(part)
        elif part.startswith(("I25", "I70")):
            names.append(part[:3] + " " + part[3:] if part[1].isdigit() else part)
    # Keep highway names readable: I25 HWYNB -> I-25
    cleaned = []
    for name in names:
        if name.startswith("I25"):
            cleaned.append("I-25")
        elif name.startswith("I70"):
            cleaned.append("I-70")
        else:
            cleaned.append(name)
    return cleaned


def _hin_union():
    payload = json.loads((RAW / "hin.geojson").read_text())
    lines = []
    for feature in payload["features"]:
        geom = feature.get("geometry")
        if not geom:
            continue
        lines.append(shape(geom))
    if not lines:
        raise RuntimeError("High Injury Network download has no lines")
    to_feet = Transformer.from_crs(4326, 2877, always_xy=True)
    projected = [shapely_project(geom, to_feet) for geom in lines]
    return unary_union(projected), to_feet


def shapely_project(geom, transformer):
    return transform(transformer.transform, geom)


def _on_network(frame: pd.DataFrame, network, to_feet) -> pd.Series:
    threshold_ft = HIN_BUFFER_M * 3.280833333
    prepared = network.buffer(threshold_ft)
    flags = []
    for lon, lat in zip(frame["geo_lon"], frame["geo_lat"], strict=True):
        if pd.isna(lon) or pd.isna(lat):
            flags.append(pd.NA)
            continue
        x, y = to_feet.transform(float(lon), float(lat))
        flags.append(bool(prepared.covers(Point(x, y))))
    return pd.Series(flags, index=frame.index)


def _yearly_from_file(detail: pd.DataFrame, yearly_all: pd.DataFrame) -> pd.DataFrame:
    ped = detail[detail["pedestrian_ind"] == 1]
    bike = detail[detail["bicycle_ind"] == 1]
    fatal = detail[detail["FATALITIES"].fillna(0) > 0]
    rows = []
    for year, total in yearly_all.set_index("year").iterrows():
        rows.append(
            {
                "year": int(year),
                "partial_year": int(year) > COMPLETE_YEAR,
                "file_crashes": int(total["crashes"] or 0),
                "file_deaths": int(total["deaths"] or 0),
                "file_serious": int(total["serious"] or 0),
                "file_ped_crashes": int((ped["year"] == year).sum()),
                "file_ped_deaths": int(ped.loc[ped["year"] == year, "FATALITIES"].fillna(0).sum()),
                "file_ped_serious": int(ped.loc[ped["year"] == year, "SERIOUSLY_INJURED"].fillna(0).sum()),
                "file_bike_crashes": int((bike["year"] == year).sum()),
                "file_bike_deaths": int(bike.loc[bike["year"] == year, "FATALITIES"].fillna(0).sum()),
                "file_death_rows": int((fatal["year"] == year).sum()),
            }
        )
    return pd.DataFrame(rows)


def _claims(yearly: pd.DataFrame, reported: pd.DataFrame, hin_share: float, modes: pd.DataFrame) -> pd.DataFrame:
    y2025 = yearly.set_index("year").loc[COMPLETE_YEAR]
    ped_doti = int(
        reported.query("metric == 'pedestrian_deaths' and year == 2025")["value"].iloc[0]
    )
    page_94 = int(
        reported.query("metric == 'traffic_deaths' and year == 2025 and value == 94")["value"].iloc[0]
    )
    gazette_93 = int(
        reported.query("metric == 'traffic_deaths' and year == 2025 and value == 93")["value"].iloc[0]
    )
    mode_2025 = modes[modes["year"] == COMPLETE_YEAR]
    ped_mode = int(mode_2025.loc[mode_2025["death_mode"] == "pedestrian", "deaths"].sum())
    return pd.DataFrame(
        [
            {
                "claim_id": "two_death_counts",
                "statement": "Denver's Vision Zero count and the open crash file do not count the same 2025 deaths.",
                "verdict": "counts_do_not_match",
                "evidence": (
                    f"Open file, sum of FATALITIES in {COMPLETE_YEAR}: {int(y2025['file_deaths'])}. "
                    f"Denver Gazette, 2026-02-03: {gazette_93}. "
                    f"Vision Zero statistics page, read 2026-09-29: {page_94}. "
                    "The two reported figures differ by one. The file is about half of either."
                ),
                "caveat": (
                    "These are different publications, not two extracts of one table. "
                    "The gap is the finding. It is not a claim that either office falsified a number."
                ),
            },
            {
                "claim_id": "pedestrian_outcomes_blank",
                "statement": "The open file still records pedestrian crashes, and it stopped recording pedestrian deaths.",
                "verdict": "outcome_fields_blank",
                "evidence": (
                    "Pedestrian-involved crashes in the file: "
                    + ", ".join(
                        f"{int(r.year)}: {int(r.file_ped_crashes)}"
                        for r in yearly.itertuples()
                        if r.year >= 2021
                    )
                    + ". Pedestrian deaths in that file (FATALITIES on pedestrian_ind rows, and fatality mode): "
                    + ", ".join(
                        f"{int(r.year)}: {int(r.file_ped_deaths)}" for r in yearly.itertuples()
                    )
                    + f". Fatality-mode pedestrian deaths in {COMPLETE_YEAR}: {ped_mode}. "
                    f"DOTI, via the Gazette: {ped_doti} pedestrian deaths in {COMPLETE_YEAR}."
                ),
                "caveat": (
                    "A blank outcome field is not evidence that the death did not happen. "
                    "DOTI's 35 is the reported count. The file's zero is a coding result."
                ),
            },
            {
                "claim_id": "hin_still_sees_the_crashes",
                "statement": "Pedestrian crashes are still mappable. Under half of the 2025 crashes sit within 30 meters of the High Injury Network.",
                "verdict": "descriptive_support",
                "evidence": (
                    f"{hin_share:.0%} of {COMPLETE_YEAR} pedestrian crashes with coordinates "
                    f"fall within {HIN_BUFFER_M} meters of a High Injury Network street."
                ),
                "caveat": (
                    "The network was drawn from earlier death and serious-injury crashes. "
                    "A crash near the line is not a death, and the buffer is a choice."
                ),
            },
            {
                "claim_id": "serious_injury_series",
                "statement": "The file's serious-injury sum and the Gazette's serious-injury drop are not the same series.",
                "verdict": "not_the_same_series",
                "evidence": (
                    f"File, sum of SERIOUSLY_INJURED: {int(yearly.set_index('year').loc[2024, 'file_serious'])} in 2024, "
                    f"{int(y2025['file_serious'])} in 2025. "
                    "Gazette, 2026-02-03: 410 in 2024, 356 in 2025."
                ),
                "caveat": "Do not subtract one series from the other. The definitions are not documented as identical.",
            },
        ]
    )


def _checks(yearly: pd.DataFrame, claims: pd.DataFrame, detail: pd.DataFrame) -> pd.DataFrame:
    y2025 = yearly.set_index("year").loc[COMPLETE_YEAR]
    checks = [
        ("every_year_from_2021", set(yearly["year"]) >= set(range(2021, 2027))),
        ("2026_marked_partial", bool(yearly.loc[yearly["year"] == 2026, "partial_year"].iloc[0])),
        ("file_has_2025_deaths", int(y2025["file_deaths"]) > 0),
        ("pedestrian_crashes_continue", int(y2025["file_ped_crashes"]) > 100),
        ("no_score_column", "score" not in claims.columns and "weight" not in claims.columns),
        ("reported_not_in_file_table", "value" not in yearly.columns),
        ("coordinates_present", detail["geo_lat"].notna().mean() > 0.9),
    ]
    return pd.DataFrame(
        [{"check": name, "passed": bool(ok)} for name, ok in checks]
    )


def main() -> None:
    detail = _records(RAW / "ksi_and_vulnerable.json")
    yearly_all = pd.DataFrame(json.loads((RAW / "yearly.json").read_text()))
    network, to_feet = _hin_union()
    detail["on_hin"] = _on_network(detail, network, to_feet)
    detail["death_mode"] = detail.apply(_mode, axis=1)

    yearly = _yearly_from_file(detail, yearly_all)
    reported = pd.DataFrame(REPORTED)
    ped_2025 = detail[(detail["year"] == COMPLETE_YEAR) & (detail["pedestrian_ind"] == 1)]
    located = ped_2025[ped_2025["on_hin"].notna()]
    hin_share = float(located["on_hin"].mean()) if len(located) else float("nan")

    modes = (
        detail[detail["FATALITIES"].fillna(0) > 0]
        .groupby(["year", "death_mode"], as_index=False)["FATALITIES"]
        .sum()
        .rename(columns={"FATALITIES": "deaths"})
    )
    claims = _claims(yearly, reported, hin_share, modes)
    checks = _checks(yearly, claims, detail)
    if not checks["passed"].all():
        failed = checks.loc[~checks["passed"], "check"].tolist()
        raise SystemExit(f"quality checks failed: {failed}")

    neighborhoods = (
        ped_2025.groupby(ped_2025["neighborhood_id"].fillna("(no neighborhood)"), as_index=False)
        .size()
        .rename(columns={"neighborhood_id": "neighborhood", "size": "ped_crashes"})
        .sort_values("ped_crashes", ascending=False)
    )
    mentions: dict[str, int] = {}
    for address in ped_2025["incident_address"]:
        for street in _street(address):
            mentions[street] = mentions.get(street, 0) + 1
    streets = (
        pd.DataFrame([{"street": k, "mentions": v} for k, v in mentions.items()])
        .sort_values("mentions", ascending=False)
        .head(15)
    )
    comparison_rows = []
    for _, row in yearly.iterrows():
        comparison_rows.append(
            {"year": int(row["year"]), "source": "Open crash file", "metric": "traffic_deaths", "value": int(row["file_deaths"]), "partial_year": bool(row["partial_year"])}
        )
        comparison_rows.append(
            {"year": int(row["year"]), "source": "Open crash file", "metric": "pedestrian_deaths", "value": int(row["file_ped_deaths"]), "partial_year": bool(row["partial_year"])}
        )
    for _, row in reported.iterrows():
        comparison_rows.append(
            {
                "year": int(row["year"]),
                "source": "City reported",
                "metric": row["metric"],
                "value": int(row["value"]),
                "partial_year": bool(row["partial_year"]),
            }
        )
    comparison = pd.DataFrame(comparison_rows)
    # One reported figure per year for the chart. 2025 keeps the city-page 94;
    # the Gazette's 93 stays in `reported` and is named in the caption.
    reported_for_chart = {
        2024: ("Gazette, 2026-02-03", 80),
        2025: ("City page, 2026-09-29", 94),
        2026: ("City page, 2026-09-29", 47),
    }
    chart_rows = []
    for _, row in yearly.iterrows():
        chart_rows.append(
            {
                "year": int(row["year"]),
                "series": "Open crash file",
                "deaths": int(row["file_deaths"]),
                "partial_year": bool(row["partial_year"]),
            }
        )
        if int(row["year"]) in reported_for_chart:
            label, value = reported_for_chart[int(row["year"])]
            chart_rows.append(
                {
                    "year": int(row["year"]),
                    "series": "City reported",
                    "deaths": value,
                    "partial_year": bool(row["partial_year"]),
                    "reported_as": label,
                }
            )
    chart_deaths = pd.DataFrame(chart_rows)
    ped_rows = []
    reported_ped = {2021: 23, 2024: 26, 2025: 35}
    for _, row in yearly.iterrows():
        ped_rows.append(
            {
                "year": int(row["year"]),
                "series": "Pedestrian crashes in the file",
                "value": int(row["file_ped_crashes"]),
                "partial_year": bool(row["partial_year"]),
            }
        )
        ped_rows.append(
            {
                "year": int(row["year"]),
                "series": "Pedestrian deaths in the file",
                "value": int(row["file_ped_deaths"]),
                "partial_year": bool(row["partial_year"]),
            }
        )
        if int(row["year"]) in reported_ped:
            ped_rows.append(
                {
                    "year": int(row["year"]),
                    "series": "Pedestrian deaths reported by DOTI",
                    "value": reported_ped[int(row["year"])],
                    "partial_year": False,
                }
            )
    chart_ped = pd.DataFrame(ped_rows)

    points = ped_2025[
        ["year", "geo_lon", "geo_lat", "neighborhood_id", "LIGHT_CONDITION", "ROAD_DESCRIPTION", "on_hin", "incident_address"]
    ].copy()
    points["on_hin"] = points["on_hin"].map({True: "on network", False: "off network"})

    meta = {
        "retrieved": json.loads((RAW / "retrieved.json").read_text())["retrieved"],
        "built": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "file_deaths_2025": int(yearly.set_index("year").loc[2025, "file_deaths"]),
        "file_ped_deaths_2025": int(yearly.set_index("year").loc[2025, "file_ped_deaths"]),
        "file_ped_crashes_2025": int(yearly.set_index("year").loc[2025, "file_ped_crashes"]),
        "hin_share_2025_ped": round(hin_share, 4),
        "hin_buffer_m": HIN_BUFFER_M,
    }
    tables = {
        "yearly": yearly,
        "reported": reported,
        "comparison": comparison,
        "claims": claims,
        "modes": modes,
        "neighborhoods": neighborhoods,
        "streets": streets,
        "ped_points": points,
        "chart_deaths": chart_deaths,
        "chart_ped": chart_ped,
        "quality_checks": checks,
    }
    for folder in (EXPORTS, APP_DATA):
        folder.mkdir(parents=True, exist_ok=True)
        for name, frame in tables.items():
            frame.to_csv(folder / f"{name}.csv", index=False)
        (folder / "meta.json").write_text(json.dumps(meta, indent=2))
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
