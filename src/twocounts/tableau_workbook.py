"""Build tableau/two_death_counts.twbx from the extracts.

Open it in Tableau Public, check the sheets, then File > Save to Tableau Public As.
The workbook is generated, not committed. Palette fields use the local instance
name. A federated prefix is ignored, and Tableau then paints the default
palette, which includes red and orange.
"""

from __future__ import annotations

import csv
import hashlib
import tempfile
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from tableauhyperapi import (
    Connection,
    CreateMode,
    HyperProcess,
    Inserter,
    SqlType,
    TableDefinition,
    TableName,
    Telemetry,
)

from twocounts import EXPORTS, ROOT

OUT = ROOT / "tableau" / "two_death_counts.twbx"
BUILD = "2026.2.3 (20262.26.0912.1023)"
NAVY, TEAL, BLUE, SLATE = "#1e3a5f", "#0f766e", "#2563eb", "#64748b"
INK = "#0f172a"
DIMENSIONS = {"year"}


def a(value: object) -> str:
    s = str(value)
    for old, new in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"), ("'", "&apos;"), ('"', "&quot;")):
        s = s.replace(old, new)
    return s


def t(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def member(value: str) -> str:
    return a(f'"{value}"')


def ident(seed: str) -> str:
    digest = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while len(out) < 28:
        digest, r = divmod(digest, 36)
        out += alphabet[r]
    return out


def simple_id(seed: str) -> str:
    return "{" + str(uuid.uuid5(uuid.NAMESPACE_URL, "two-counts/" + seed)).upper() + "}"


def infer_type(values: list[str]) -> str:
    if values and all(v.lower() in ("true", "false") for v in values):
        return "boolean"
    try:
        [int(v) for v in values]
        return "integer"
    except ValueError:
        pass
    try:
        [float(v) for v in values]
        return "real"
    except ValueError:
        return "string"


def infer_columns(path: Path) -> list[tuple[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    header, body = rows[0], rows[1:]
    out = []
    for i, col in enumerate(header):
        values = [r[i] for r in body if i < len(r) and r[i] != ""]
        out.append((col, infer_type(values)))
    return out


def parse_value(raw: str, dtype: str):
    if raw == "":
        return None
    if dtype == "integer":
        return int(float(raw)) if "." in raw else int(raw)
    if dtype == "real":
        return float(raw)
    if dtype == "boolean":
        return raw.lower() == "true"
    return raw


def role_of(col: str, dtype: str) -> tuple[str, str]:
    if col in DIMENSIONS:
        return "dimension", "ordinal"
    if dtype in ("integer", "real"):
        return "measure", "quantitative"
    return "dimension", "nominal"


@dataclass
class Datasource:
    caption: str
    filename: str
    formats: dict[str, str] = field(default_factory=dict)
    styles: str = ""

    def __post_init__(self) -> None:
        self.name = "federated." + ident(self.caption)
        self.conn = "hyper." + ident(self.filename)
        self.columns = infer_columns(EXPORTS / self.filename)

    def ref(self, instance: str) -> str:
        return f"[{self.name}].[{instance}]"

    def column_decls(self) -> str:
        out = []
        for col, dtype in self.columns:
            role, kind = role_of(col, dtype)
            fmt = self.formats.get(col)
            fmt_attr = f" default-format='{a(fmt)}'" if fmt else ""
            out.append(
                f"<column datatype='{dtype}'{fmt_attr} name='[{a(col)}]' role='{role}' type='{kind}' />"
            )
        return "\n        ".join(out)

    @property
    def hyper_path(self) -> str:
        return f"Data/Extracts/{Path(self.filename).stem}.hyper"

    def write_hyper(self, target: Path) -> int:
        types = {
            "integer": SqlType.big_int(),
            "real": SqlType.double(),
            "string": SqlType.text(),
            "boolean": SqlType.bool(),
        }
        table = TableDefinition(
            TableName("Extract", "Extract"),
            [TableDefinition.Column(col, types[dtype]) for col, dtype in self.columns],
        )
        with (EXPORTS / self.filename).open(newline="", encoding="utf-8") as fh:
            records = [
                [parse_value(row.get(col, ""), dtype) for col, dtype in self.columns]
                for row in csv.DictReader(fh)
            ]
        target.parent.mkdir(parents=True, exist_ok=True)
        with (
            HyperProcess(
                telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU,
                parameters={"log_config": ""},
            ) as hyper,
            Connection(hyper.endpoint, target, CreateMode.CREATE_AND_REPLACE) as conn,
        ):
            conn.catalog.create_schema("Extract")
            conn.catalog.create_table(table)
            with Inserter(conn, table) as inserter:
                inserter.add_rows(records)
                inserter.execute()
        return len(records)

    def xml(self) -> str:
        return f"""
    <datasource caption='{a(self.caption)}' inline='true' name='{self.name}' version='18.1'>
      <connection class='federated'>
        <named-connections>
          <named-connection caption='{a(Path(self.filename).stem)}' name='{self.conn}'>
            <connection authentication='auth-none' author-locale='en_US' class='hyper' dbname='{a(self.hyper_path)}' default-settings='yes' port='' sslmode='' username='tableau_internal_user' />
          </named-connection>
        </named-connections>
        <relation connection='{self.conn}' name='Extract' table='[Extract].[Extract]' type='table' />
      </connection>
      <aliases enabled='yes' />
        {self.column_decls()}
      <layout dim-ordering='alphabetic' dim-percentage='0.5' measure-ordering='alphabetic' measure-percentage='0.4' show-structure='true' />
      <style><style-rule element='mark'>{self.styles}</style-rule></style>
    </datasource>"""


def color_map(field_name: str, pairs: list[tuple[str, str]]) -> str:
    maps = "".join(f"<map to='{c}'><bucket>{member(v)}</bucket></map>" for v, c in pairs)
    return f"<encoding attr='color' field='{a(field_name)}' type='palette'>{maps}</encoding>"


deaths = Datasource("Two counts", "chart_deaths.csv", formats={"deaths": "#,##0"})
deaths.styles = color_map(
    "[none:series:nk]",
    [("City reported", NAVY), ("Open crash file", TEAL)],
)
walking = Datasource("People walking", "chart_ped.csv", formats={"value": "#,##0"})
walking.styles = color_map(
    "[none:series:nk]",
    [
        ("Pedestrian crashes in the file", TEAL),
        ("Pedestrian deaths in the file", SLATE),
        ("Pedestrian deaths reported by DOTI", NAVY),
    ],
)
neighborhoods = Datasource("Neighborhoods", "neighborhoods.csv", formats={"ped_crashes": "#,##0"})
streets = Datasource("Street mentions", "streets.csv", formats={"mentions": "#,##0"})
claims = Datasource("Claims", "claims.csv")
SOURCES = [deaths, walking, neighborhoods, streets, claims]


@dataclass
class Sheet:
    name: str
    title: str
    ds: Datasource
    rows: str
    cols: str
    mark: str
    encodings: list[tuple[str, str]] = field(default_factory=list)
    instances: list[str] = field(default_factory=list)
    filters: str = ""
    sorts: str = ""
    style: str = ""

    def xml(self) -> str:
        inst = []
        for item in self.instances:
            prefix, col, tk = item.split(":")
            derivation = {"none": "None", "sum": "Sum"}[prefix]
            kind = {"nk": "nominal", "ok": "ordinal", "qk": "quantitative"}[tk]
            inst.append(
                f"<column-instance column='[{a(col)}]' derivation='{derivation}' "
                f"name='[{a(item)}]' pivot='key' type='{kind}' />"
            )
        enc = "".join(f"<{kind} column='{a(ref)}' />" for kind, ref in self.encodings)
        style = self.style.strip()
        if style and not style.startswith("<style-rule"):
            style = f"<style-rule element='mark'>{style}</style-rule>"
        return f"""
    <worksheet name='{a(self.name)}'>
      <layout-options><title><formatted-text>
        <run bold='true' fontcolor='{INK}' fontsize='12'>{t(self.title)}</run>
      </formatted-text></title></layout-options>
      <table>
        <view>
          <datasources><datasource caption='{a(self.ds.caption)}' name='{self.ds.name}' /></datasources>
          <datasource-dependencies datasource='{self.ds.name}'>
            {self.ds.column_decls()}
            {" ".join(inst)}
          </datasource-dependencies>
          {self.filters}
          {self.sorts}
          <aggregation value='true' />
        </view>
        <style>{style}</style>
        <panes><pane>
          <view><breakdown value='auto' /></view>
          <mark class='{self.mark}' />
          <encodings>{enc}</encodings>
        </pane></panes>
        <rows>{a(self.rows)}</rows>
        <cols>{a(self.cols)}</cols>
      </table>
      <simple-id uuid='{simple_id("sheet/" + self.name)}' />
    </worksheet>"""


def member_filter(ds: Datasource, level: str, values: list[str]) -> str:
    items = "".join(
        f"<groupfilter function='member' level='[{a(level)}]' member='{member(v)}' />" for v in values
    )
    marker = "user:ui-domain='database' user:ui-enumeration='inclusive' user:ui-marker='enumerate'"
    return (
        f"<filter class='categorical' column='{a(ds.ref(level))}'>"
        f"<groupfilter function='union' {marker}>{items}</groupfilter></filter>"
    )


DEATH_SERIES = ["Pedestrian deaths in the file", "Pedestrian deaths reported by DOTI"]
CRASH_SERIES = ["Pedestrian crashes in the file"]

sheets = [
    Sheet(
        "Two counts",
        "2024 is the Gazette figure of 80. 2025 and 2026 are the city page. The Gazette's 2025 figure is 93.",
        deaths,
        deaths.ref("sum:deaths:qk"),
        deaths.ref("none:year:ok"),
        "Bar",
        encodings=[("color", deaths.ref("none:series:nk"))],
        instances=["sum:deaths:qk", "none:year:ok", "none:series:nk"],
    ),
    Sheet(
        "Walking deaths",
        "DOTI's pedestrian death count, beside the pedestrian deaths the open file still records.",
        walking,
        walking.ref("sum:value:qk"),
        walking.ref("none:year:ok"),
        "Bar",
        encodings=[("color", walking.ref("none:series:nk"))],
        instances=["sum:value:qk", "none:year:ok", "none:series:nk"],
        filters=member_filter(walking, "none:series:nk", DEATH_SERIES),
    ),
    Sheet(
        "Walking crashes",
        "Pedestrian crashes stay in the file after the death field goes blank.",
        walking,
        walking.ref("sum:value:qk"),
        walking.ref("none:year:ok"),
        "Bar",
        encodings=[("color", walking.ref("none:series:nk"))],
        instances=["sum:value:qk", "none:year:ok", "none:series:nk"],
        filters=member_filter(walking, "none:series:nk", CRASH_SERIES),
    ),
    Sheet(
        "Neighborhoods",
        "2025 pedestrian crashes by neighborhood. Five Points leads. 17 crashes have no neighborhood.",
        neighborhoods,
        neighborhoods.ref("none:neighborhood:nk"),
        neighborhoods.ref("sum:ped_crashes:qk"),
        "Bar",
        instances=["none:neighborhood:nk", "sum:ped_crashes:qk"],
        sorts=(
            f"<computed-sort column='{a(neighborhoods.ref('none:neighborhood:nk'))}' direction='DESC' "
            f"using='{a(neighborhoods.ref('sum:ped_crashes:qk'))}' />"
        ),
    ),
    Sheet(
        "Streets",
        "Street mentions in 2025 pedestrian-crash addresses. An intersection names two streets, so this is mentions, not crashes on a street.",
        streets,
        streets.ref("none:street:nk"),
        streets.ref("sum:mentions:qk"),
        "Bar",
        instances=["none:street:nk", "sum:mentions:qk"],
        sorts=(
            f"<computed-sort column='{a(streets.ref('none:street:nk'))}' direction='DESC' "
            f"using='{a(streets.ref('sum:mentions:qk'))}' />"
        ),
    ),
    Sheet(
        "Claims",
        "Verdicts are labels. Hover a row for the evidence and the caveat.",
        claims,
        claims.ref("none:statement:nk"),
        "",
        "Text",
        encodings=[
            ("text", claims.ref("none:verdict:nk")),
            ("tooltip", claims.ref("none:evidence:nk")),
            ("tooltip", claims.ref("none:caveat:nk")),
        ],
        instances=["none:statement:nk", "none:verdict:nk", "none:evidence:nk", "none:caveat:nk"],
    ),
]


def zone(sheet: str, zid: int, x: int, y: int, w: int, h: int) -> str:
    return (
        f"<zone h='{h}' id='{zid}' name='{a(sheet)}' w='{w}' x='{x}' y='{y}'>"
        f"<layout-cache minheight='180' type-h='fixed' type-w='fixed' /></zone>"
    )


def legend_zone(zid: int, sheet: str, field: str, x: int, y: int, w: int, h: int) -> str:
    return (
        f"<zone h='{h}' id='{zid}' name='{a(sheet)}' pane-specification-id='0' "
        f"param='{a(field)}' type-v2='color' w='{w}' x='{x}' y='{y}' />"
    )


def dashboard_xml() -> str:
    title = (
        "<zone h='4000' id='3' type-v2='text' w='100000' x='0' y='0'><formatted-text>"
        f"<run bold='true' fontcolor='{INK}' fontsize='18'>Denver's two traffic-death counts</run>"
        "</formatted-text></zone>"
    )
    note = (
        "<zone h='5000' id='4' type-v2='text' w='100000' x='0' y='4000'><formatted-text>"
        "<run fontcolor='#334155' fontsize='10'>Navy is a figure the city or the Gazette published. "
        "Teal is the open crash file. The two are not added together. "
        "2026 is year to date. The file records pedestrian crashes after it stops recording "
        "pedestrian deaths.</run></formatted-text></zone>"
    )
    zones = "\n".join(
        [
            title,
            note,
            zone("Two counts", 5, 0, 9000, 62000, 28000),
            legend_zone(6, "Two counts", deaths.ref("none:series:nk"), 62000, 9000, 16000, 12000),
            zone("Walking deaths", 7, 78000, 9000, 22000, 28000),
            zone("Walking crashes", 8, 0, 38000, 100000, 18000),
            zone("Neighborhoods", 9, 0, 57000, 50000, 20000),
            zone("Streets", 10, 50000, 57000, 50000, 20000),
            zone("Claims", 11, 0, 78000, 100000, 21000),
        ]
    )
    return f"""
    <dashboard name='Two Death Counts'>
      <style />
      <size maxheight='1500' maxwidth='1200' minheight='1500' minwidth='1200' />
      <zones>
        <zone h='100000' id='2' type-v2='layout-basic' w='100000' x='0' y='0'>
          {zones}
        </zone>
      </zones>
      <simple-id uuid='{simple_id("dashboard")}' />
    </dashboard>"""


def window(sheet: Sheet) -> str:
    return f"""
    <window class='worksheet' name='{a(sheet.name)}'>
      <cards>
        <edge name='left'><strip size='160'><card type='pages' /><card type='filters' /><card type='marks' /></strip></edge>
        <edge name='top'>
          <strip size='2147483647'><card type='columns' /></strip>
          <strip size='2147483647'><card type='rows' /></strip>
          <strip size='31'><card type='title' /></strip>
        </edge>
      </cards>
      <simple-id uuid='{simple_id("window/" + sheet.name)}' />
    </window>"""


def workbook_xml() -> str:
    return f"""<?xml version='1.0' encoding='utf-8' ?>
<workbook source-build='{BUILD}' source-platform='mac' version='18.1' xmlns:user='http://www.tableausoftware.com/xml/user'>
  <document-format-change-manifest>
    <SheetIdentifierTracking />
    <SortTagCleanup />
    <WindowsPersistSimpleIdentifiers />
  </document-format-change-manifest>
  <preferences>
    <color-palette name='Two counts' type='regular'>
      <color>{NAVY}</color><color>{TEAL}</color><color>{BLUE}</color><color>{SLATE}</color>
    </color-palette>
  </preferences>
  <datasources>{"".join(ds.xml() for ds in SOURCES)}</datasources>
  <worksheets>{"".join(s.xml() for s in sheets)}</worksheets>
  <dashboards>{dashboard_xml()}</dashboards>
  <windows source-height='30'>
    {"".join(window(s) for s in sheets)}
    <window class='dashboard' maximized='true' name='Two Death Counts'>
      <viewpoints>{"".join(f"<viewpoint name='{a(s.name)}'><zoom type='entire-view' /></viewpoint>" for s in sheets)}</viewpoints>
      <active id='-1' />
      <device-preview>
        <device is-portrait='true' name='Generic Phone' type='Phone' />
      </device-preview>
      <simple-id uuid='{simple_id("window/dashboard")}' />
    </window>
  </windows>
</workbook>
"""


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as twbx:
        twbx.writestr(OUT.with_suffix(".twb").name, workbook_xml())
        for ds in SOURCES:
            hyper = Path(tmp) / Path(ds.hyper_path).name
            rows = ds.write_hyper(hyper)
            twbx.write(hyper, ds.hyper_path)
            print(f"{ds.filename}: {rows} rows")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
