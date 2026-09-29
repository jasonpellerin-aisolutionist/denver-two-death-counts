# Tableau

`make tableau` writes `two_death_counts.twbx` (gitignored).

Open it in Tableau Public 2026.2. The workbook uses the same schema that loads in that build: a format-change manifest with `WindowsPersistSimpleIdentifiers`, `<style>` that contains only `<style-rule>`, and color palettes bound to the local field `[none:series:nk]`.

Navy is a figure the city or the Gazette published. Teal is the open crash file. Slate is the pedestrian-death field inside that file, which is zero from 2023 on.

Check the six sheets, then File > Save to Tableau Public As. The public URL is not claimed until that save succeeds.

The point map of 2025 pedestrian crashes is in the Streamlit app. Path marks for the High Injury Network lines were left out of the workbook on purpose.
