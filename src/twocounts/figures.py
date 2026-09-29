"""Cover and two charts. Navy, teal, slate, blue. No red, no orange."""

from __future__ import annotations

import pandas as pd
from matplotlib import pyplot as plt

from twocounts import EXPORTS, REPORTS

NAVY, TEAL, SLATE, BLUE = "#1e3a5f", "#0f766e", "#64748b", "#2563eb"
INK = "#0f172a"
PAPER = "#f8fafc"


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "text.color": INK,
            "axes.labelcolor": INK,
            "xtick.color": INK,
            "ytick.color": INK,
            "axes.edgecolor": "#cbd5e1",
        }
    )


def cover(deaths: pd.DataFrame, ped: pd.DataFrame) -> None:
    sub = deaths[deaths["year"] == 2025]
    city = int(sub.loc[sub["series"] == "City reported", "deaths"].iloc[0])
    file_deaths = int(sub.loc[sub["series"] == "Open crash file", "deaths"].iloc[0])
    crashes = int(
        ped[(ped["year"] == 2025) & (ped["series"] == "Pedestrian crashes in the file")]["value"].iloc[0]
    )
    ped_deaths = int(
        ped[(ped["year"] == 2025) & (ped["series"] == "Pedestrian deaths in the file")]["value"].iloc[0]
    )
    doti = int(
        ped[(ped["year"] == 2025) & (ped["series"] == "Pedestrian deaths reported by DOTI")]["value"].iloc[0]
    )
    fig = plt.figure(figsize=(12, 6.3), dpi=100, facecolor=NAVY)
    ax = fig.add_axes((0.04, 0.08, 0.48, 0.84))
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.text(0, 0.92, "TWO DEATH COUNTS", color="#93c5fd", fontsize=13, fontweight="bold")
    ax.text(0, 0.78, "Denver traffic deaths, 2025", color="white", fontsize=22, fontweight="bold")
    ax.text(0, 0.62, str(city), color="white", fontsize=54, fontweight="bold")
    ax.text(0.22, 0.66, "on the city's Vision Zero page", color="#cbd5e1", fontsize=12)
    ax.text(0, 0.42, str(file_deaths), color="#5eead4", fontsize=54, fontweight="bold")
    ax.text(0.22, 0.46, "in the open crash file", color="#cbd5e1", fontsize=12)
    ax.text(0, 0.24, str(ped_deaths), color="#5eead4", fontsize=42, fontweight="bold")
    ax.text(0.16, 0.28, "pedestrian deaths in that file", color="#cbd5e1", fontsize=12)
    ax.text(
        0,
        0.08,
        f"DOTI reported {doti} people killed while walking. {crashes} pedestrian crashes are still in the file.",
        color="#94a3b8",
        fontsize=10,
    )

    ax2 = fig.add_axes((0.58, 0.22, 0.36, 0.58))
    ax2.set_facecolor(NAVY)
    labels = ["City page", "Open file"]
    values = [city, file_deaths]
    bars = ax2.barh(labels[::-1], values[::-1], color=[TEAL, "white"][::-1], height=0.55)
    ax2.tick_params(colors="white", labelsize=11)
    ax2.set_xlabel("Deaths in 2025", color="#cbd5e1")
    for spine in ax2.spines.values():
        spine.set_visible(False)
    ax2.xaxis.label.set_color("#cbd5e1")
    ax2.tick_params(axis="x", colors="#cbd5e1")
    for bar, value in zip(bars, values[::-1], strict=True):
        ax2.text(
            value + 1.5,
            bar.get_y() + bar.get_height() / 2,
            str(value),
            va="center",
            color="white",
            fontsize=12,
        )
    ax2.set_title(f"{crashes} pedestrian crashes still recorded", color="white", loc="left", fontsize=11)
    fig.savefig(REPORTS / "figures" / "cover.png", facecolor=fig.get_facecolor())
    plt.close(fig)


def pedestrian(ped: pd.DataFrame) -> None:
    crashes = ped[ped["series"] == "Pedestrian crashes in the file"].sort_values("year")
    file_deaths = ped[ped["series"] == "Pedestrian deaths in the file"].sort_values("year")
    reported = ped[ped["series"] == "Pedestrian deaths reported by DOTI"].sort_values("year")
    fig, ax = plt.subplots(figsize=(10, 5.2), dpi=120, facecolor=PAPER)
    ax.set_facecolor(PAPER)
    ax.bar(
        crashes["year"],
        crashes["value"],
        color=TEAL,
        width=0.7,
        label="Pedestrian crashes in the open file",
    )
    ax2 = ax.twinx()
    ax2.plot(
        file_deaths["year"],
        file_deaths["value"],
        color=NAVY,
        marker="o",
        linewidth=2,
        label="Pedestrian deaths in the file",
    )
    ax2.plot(
        reported["year"],
        reported["value"],
        color=BLUE,
        marker="s",
        linewidth=2,
        label="Pedestrian deaths reported by DOTI",
    )
    ax.set_ylabel("Crashes in the open file")
    ax2.set_ylabel("Deaths")
    ax.set_xlabel("")
    ax.set_title("People walking are still hit. The file stopped recording when they are killed.")
    lines, labels = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines + lines2, labels + labels2, frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(REPORTS / "figures" / "pedestrian_gap.png", facecolor=PAPER)
    plt.close(fig)


def two_counts(deaths: pd.DataFrame) -> None:
    full = deaths[deaths["year"].between(2024, 2025)]
    fig, ax = plt.subplots(figsize=(8, 4.6), dpi=120, facecolor=PAPER)
    ax.set_facecolor(PAPER)
    years = [2024, 2025]
    width = 0.36
    file_vals = [int(full[(full.year == y) & (full.series == "Open crash file")]["deaths"].iloc[0]) for y in years]
    city_vals = [int(full[(full.year == y) & (full.series == "City reported")]["deaths"].iloc[0]) for y in years]
    ax.bar([y - width / 2 for y in years], city_vals, width=width, color=NAVY, label="City reported")
    ax.bar([y + width / 2 for y in years], file_vals, width=width, color=TEAL, label="Open crash file")
    ax.set_xticks(years)
    ax.set_ylabel("Traffic deaths")
    ax.set_title("2024 uses the Gazette figure of 80. 2025 uses the city page, 94. The Gazette said 93.")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(REPORTS / "figures" / "two_counts.png", facecolor=PAPER)
    plt.close(fig)


def main() -> None:
    _style()
    out = REPORTS / "figures"
    out.mkdir(parents=True, exist_ok=True)
    deaths = pd.read_csv(EXPORTS / "chart_deaths.csv")
    ped = pd.read_csv(EXPORTS / "chart_ped.csv")
    cover(deaths, ped)
    pedestrian(ped)
    two_counts(deaths)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
