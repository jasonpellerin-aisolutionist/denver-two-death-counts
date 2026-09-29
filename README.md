# Denver's two traffic-death counts

Denver's Vision Zero page, read on 29 September 2026, said 94 people died in traffic in 2025 and 47 had died so far in 2026. The same page points readers to the open data catalog as the more comprehensive source.

The open crash file records 41 deaths in 2025 and 26 so far in 2026. It records 463 pedestrian crashes in 2025 and 0 pedestrian deaths. The Denver Gazette, citing DOTI, reported 35 people killed while walking in 2025, and 93 traffic deaths in total. The page and the Gazette differ by one. Both are kept. Neither is added to the file.

The gap is the finding. It is not a claim that either office falsified a number.

## What you can open

- `reports/two_death_counts.xlsx` keeps the file and the reported figures on separate sheets.
- `reports/figures/` has the cover and the two charts.
- `app/streamlit_app.py` maps the 2025 pedestrian crashes and colors them by whether they fall within 30 meters of the High Injury Network (43% do).
- `make tableau` builds `tableau/two_death_counts.twbx`. Publish it from Tableau Public. The public URL is added here after that save.

## Rebuild

```bash
uv sync
make refresh
make build
make workbook
make figures
make tableau
make test
```

`make refresh` pages the ArcGIS layers. Raw responses stay in `data/raw/` and are not committed. The weekly GitHub Action rebuilds the extracts and fails the snapshot test if the 29 September 2026 relationship changes, so a fix in the city's file does not silently rewrite this write-up.

## Read this before quoting a number

`docs/METHODOLOGY.md` is the citation note. Short version:

- File deaths are the sum of `FATALITIES`. An offense label of fatal is not a death when that field is 0.
- 2026 is year to date.
- Street rankings are mentions. An intersection names two streets.
- Eight freeway pedestrian deaths, the share DOTI described to the Gazette, do not explain a file with 0 pedestrian deaths or a total gap of about 50.
- No score. No weights.

Data: City and County of Denver open geospatial catalog. Reported figures: Denver Gazette, 3 February 2026, and the Vision Zero statistics page as read on 29 September 2026.
