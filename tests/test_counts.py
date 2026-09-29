"""The two death counts stay in separate tables, and the 29 Sep 2026 pull stays honest."""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "tableau" / "exports"


def table(name: str) -> pd.DataFrame:
    return pd.read_csv(EXPORTS / f"{name}.csv")


def test_extracts_exist():
    for name in ("yearly", "reported", "claims", "chart_deaths", "chart_ped", "quality_checks"):
        assert (EXPORTS / f"{name}.csv").exists()


def test_quality_checks_pass():
    assert table("quality_checks")["passed"].all()


def test_snapshot_of_the_29_sep_2026_pull():
    """If this fails, the open file changed. Reread the claims before updating the post."""
    yearly = table("yearly").set_index("year")
    assert int(yearly.loc[2025, "file_deaths"]) == 41
    assert int(yearly.loc[2025, "file_ped_deaths"]) == 0
    assert int(yearly.loc[2025, "file_ped_crashes"]) == 463
    assert bool(yearly.loc[2026, "partial_year"])


def test_reported_figures_are_not_added_into_the_file():
    yearly = table("yearly")
    assert "value" not in yearly.columns
    reported = table("reported")
    assert set(reported["source"]).issuperset({"Denver Gazette, 2026-02-03"})
    deaths_2025 = set(reported.query("metric == 'traffic_deaths' and year == 2025")["value"])
    assert deaths_2025 == {93, 94}
    assert 41 not in deaths_2025


def test_tableau_xml_matches_the_workbook_schema():
    import xml.etree.ElementTree as ET

    from twocounts.tableau_workbook import workbook_xml

    root = ET.fromstring(workbook_xml())
    manifest = root.find("document-format-change-manifest")
    assert manifest is not None
    assert manifest.find("WindowsPersistSimpleIdentifiers") is not None
    for style in root.iter("style"):
        for child in list(style):
            assert child.tag == "style-rule"
    xml = workbook_xml()
    assert "[none:series:nk]" in xml
    claims = root.find("worksheets/worksheet[@name='Claims']")
    assert claims is not None
    assert claims.find(".//color") is None


def test_claims_name_both_counts_and_refuse_a_score():
    claims = table("claims").set_index("claim_id")
    assert "score" not in claims.columns
    assert "41" in claims.loc["two_death_counts", "evidence"]
    assert "94" in claims.loc["two_death_counts", "evidence"]
    assert "35" in claims.loc["pedestrian_outcomes_blank", "evidence"]
    assert "0" in claims.loc["pedestrian_outcomes_blank", "evidence"]
    assert "falsified" in claims.loc["two_death_counts", "caveat"]
