# Methodology

Pulled 2026-09-29 from Denver's open geospatial catalog. The crash layer is `ODC_CRIME_TRAFFICACCIDENTS5YR_P`, layer id 325. The High Injury Network is `ODC_TRANS_HIN_L`, layer id 326. The catalog describes the crash layer as the previous five calendar years plus the current year to date.

## What is counted

`file_deaths` is the sum of the `FATALITIES` field on crash rows in that calendar year. `file_ped_deaths` is that sum on rows where `pedestrian_ind` is 1. `file_ped_crashes` is the count of those rows. A row labeled `TRAF - ACCIDENT - FATAL` is not treated as a death unless `FATALITIES` is greater than zero. In 2025, many rows with that offense label have `FATALITIES` of 0.

Reported figures live in `reported.csv` and are never added to a file total.

| Year | Source | Traffic deaths | Pedestrian deaths |
| --- | --- | --- | --- |
| 2024 | Denver Gazette, 2026-02-03, citing newer city data | 80 | 26, attributed to DOTI |
| 2025 | Same Gazette article | 93 | 35, attributed to DOTI |
| 2025 | Denver Vision Zero statistics page, read 2026-09-29 | 94 | not stated on the page read |
| 2026 | Same page, year to date on that read | 47 | not stated |

The Gazette and the page differ by one for 2025. Both are kept. The chart uses 94 for 2025 and names 93 in the caption.

## What is not claimed

The file recording 41 deaths in 2025, against 93 or 94 published, is the finding. It is not a claim that either office falsified a number. They are different publications.

The file records 0 pedestrian deaths in 2023, 2024, 2025, and 2026 year to date, while pedestrian crashes continue (463 in 2025). DOTI reported 35 pedestrian deaths in 2025. The fatality-mode field for pedestrians is also empty in those years. The hypothesis that a coding change, a different records system, or interstate crashes reported by Colorado State Patrol explains the gap is not tested here. DOTI told the Gazette that 8 of the 35 pedestrian deaths in 2025 were on the freeway. That share cannot account for a file that records 0 pedestrian deaths, or for a total gap of about 50 deaths.

Serious injuries are a second disagreement, not the same series. The file sums `SERIOUSLY_INJURED` to 420 in 2024 and 432 in 2025. The Gazette reported 410 and 356. They are not subtracted.

## High Injury Network

2025 pedestrian crashes with coordinates were projected from WGS84 to EPSG:2877 (Colorado State Plane, US survey feet). A crash is "on network" when its point falls inside a 30 meter buffer of the network lines. 30 meters is a choice, about 98 feet. The network was drawn from an earlier killed-or-serious-injury period. Being near the network is not a death, and it is not a claim that the street caused the crash.

Street names are parsed from `incident_address` by splitting on `/`, dropping a house number, and stripping a leading or trailing direction. An intersection names two streets, so the ranking is mentions, not crashes on a street.

## Left out

Driver contributing factors and offense identifiers are not published. Individual crash addresses are in the public source. The extracts used for the dashboard keep neighborhood, light, road type, and whether the point falls on the network. The map in the app does not label a victim.

No composite score is computed. No weights are applied.
