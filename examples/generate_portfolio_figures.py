"""Generate the STM-05 portfolio figures (Milestone 6).

Produces four deterministic static PNG figures under ``figures/`` directly
from the project's verified public API -- no new physics, no randomness,
no manual data entry. Re-running this script reproduces byte-for-byte
identical inputs each time (matplotlib's PNG encoding is deterministic for
a fixed environment/version, though exact bytes can vary across
matplotlib/font versions -- the underlying NUMBERS are always
deterministic and reproducible from the code).

Figures:
    1. figures/fig1_single_event_trade.png
       Single-event areal mass by candidate (Milestone 4), infeasible
       candidate called out explicitly.
    2. figures/fig2_thickness_recession.png
       Reusable required thickness vs. ablative initial thickness vs.
       ablative recession -- explicitly NOT the same physical quantity.
    3. figures/fig3_lifecycle_burden.png
       Cumulative lifecycle burden vs. mission count (Milestone 5),
       log-scaled y-axis (values span >2 orders of magnitude).
    4. figures/fig4_heating_duration_sensitivity.png
       Single-event areal mass vs. heating-pulse duration, showing the
       ranking holding steady and the lightweight ablator's feasibility
       gate.

Run with:

    python examples/generate_portfolio_figures.py

Requires the optional "figures" extra: pip install -e ".[figures]"
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # deterministic, headless backend
import matplotlib.pyplot as plt

from tps_trade import (
    LifecycleConfig,
    run_trade_study,
    run_lifecycle_study,
    STUDY_CASE,
    REUSABLE_CANDIDATES,
    ABLATIVE_CANDIDATES,
)

FIGURES_DIR = Path(__file__).resolve().parent.parent / "figures"

REUSABLE_COLOR = "#2E6F95"
ABLATIVE_COLOR = "#B0522D"
INFEASIBLE_COLOR = "#9E9E9E"
DPI = 150


def _short_label(name: str) -> str:
    return name.replace(" (illustrative)", "")


def figure_1_single_event_trade(trade_results) -> Path:
    names = [_short_label(r.name) for r in trade_results]
    masses = [r.initial_areal_mass if r.feasible else 0.0 for r in trade_results]
    colors = [
        (REUSABLE_COLOR if r.category == "reusable" else ABLATIVE_COLOR) if r.feasible else INFEASIBLE_COLOR
        for r in trade_results
    ]

    fig, ax = plt.subplots(figsize=(9, 5.5))
    bars = ax.bar(names, masses, color=colors, edgecolor="black", linewidth=0.6)

    for bar, r in zip(bars, trade_results):
        if r.feasible:
            ax.annotate(
                f"{r.initial_areal_mass:.2f}",
                xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                xytext=(0, 4),
                textcoords="offset points",
                ha="center",
                fontsize=9,
            )
        else:
            ax.annotate(
                "INFEASIBLE\n(exceeds max\nservice temp.)",
                xy=(bar.get_x() + bar.get_width() / 2, 0),
                xytext=(0, 6),
                textcoords="offset points",
                ha="center",
                fontsize=8,
                color="#333333",
            )

    ax.set_ylabel("Initial areal mass [kg/m$^2$]")
    ax.set_title(
        "Single-event TPS trade: initial areal mass by candidate\n"
        f"({STUDY_CASE.name})"
    )
    ax.set_ylim(0, max(masses) * 1.25 if max(masses) > 0 else 1.0)
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=REUSABLE_COLOR, label="Reusable (feasible)"),
        plt.Rectangle((0, 0), 1, 1, color=ABLATIVE_COLOR, label="Ablative (feasible)"),
        plt.Rectangle((0, 0), 1, 1, color=INFEASIBLE_COLOR, label="Infeasible"),
    ]
    ax.legend(handles=handles, loc="upper left")
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    fig.tight_layout()

    out_path = FIGURES_DIR / "fig1_single_event_trade.png"
    fig.savefig(out_path, dpi=DPI)
    plt.close(fig)
    return out_path


def figure_2_thickness_recession(trade_results) -> Path:
    feasible = [r for r in trade_results if r.feasible]
    names = [_short_label(r.name) for r in feasible]

    reusable_thickness = [
        r.required_thickness * 1000 if r.category == "reusable" else 0.0 for r in feasible
    ]
    ablative_initial_thickness = [
        r.required_thickness * 1000 if r.category == "ablative" else 0.0 for r in feasible
    ]
    ablative_recession = [
        r.governing_metric_value * 1000 if r.category == "ablative" else 0.0 for r in feasible
    ]

    x = range(len(feasible))
    width = 0.28

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.bar(
        [i - width for i in x], reusable_thickness, width=width,
        label="Reusable required insulation thickness", color=REUSABLE_COLOR, edgecolor="black", linewidth=0.5,
    )
    ax.bar(
        [i for i in x], ablative_initial_thickness, width=width,
        label="Ablative initial (installed) thickness", color=ABLATIVE_COLOR, edgecolor="black", linewidth=0.5,
    )
    ax.bar(
        [i + width for i in x], ablative_recession, width=width,
        label="Ablative recession (consumed thickness)", color="#E0A458", edgecolor="black", linewidth=0.5,
    )

    ax.set_xticks(list(x))
    ax.set_xticklabels(names, rotation=20, ha="right")
    ax.set_ylabel("Thickness [mm]")
    ax.set_title(
        "Thickness comparison by candidate (feasible candidates only)\n"
        "NOTE: reusable thickness (insulation) and ablative recession (consumed material)\n"
        "are NOT the same physical quantity -- see figure caption / README"
    )
    ax.legend(loc="upper left", fontsize=9)
    fig.tight_layout()

    out_path = FIGURES_DIR / "fig2_thickness_recession.png"
    fig.savefig(out_path, dpi=DPI)
    plt.close(fig)
    return out_path


def figure_3_lifecycle_burden(trade_results) -> Path:
    by_name = {r.name: r for r in trade_results}
    tile = by_name["Reusable low-density tile (illustrative)"]
    light_ablator = by_name["Lightweight charring ablator (illustrative)"]
    dense_ablator = by_name["Dense high-H_eff ablator (illustrative)"]

    mission_counts = list(range(1, 101))
    series = {}
    for candidate, color, marker in (
        (tile, REUSABLE_COLOR, "o"),
        (light_ablator, "#E0A458", "^"),
        (dense_ablator, ABLATIVE_COLOR, "s"),
    ):
        burdens = []
        for m in mission_counts:
            config = LifecycleConfig(mission_count=m, reusable_service_life_missions=50, reusable_refurbishment_fraction=0.01)
            life = run_lifecycle_study([candidate], config)[0]
            burdens.append(life.cumulative_lifecycle_burden)
        series[candidate.name] = (burdens, color, marker)

    fig, ax = plt.subplots(figsize=(9, 5.5))
    for name, (burdens, color, marker) in series.items():
        ax.plot(mission_counts, burdens, color=color, label=_short_label(name), linewidth=2, markevery=10, marker=marker, markersize=5)

    ax.set_yscale("log")
    ax.set_xlabel("Mission count")
    ax.set_ylabel("Cumulative lifecycle burden [kg/m$^2$-equivalent] (log scale)")
    ax.set_title(
        "Illustrative mission-lifecycle mass-equivalent burden\n"
        "(reusable service life = 50 missions, refurbishment = 1% of installed mass/mission)"
    )
    ax.legend(loc="upper left")
    ax.grid(True, which="both", linestyle=":", linewidth=0.5, alpha=0.6)
    fig.tight_layout()

    out_path = FIGURES_DIR / "fig3_lifecycle_burden.png"
    fig.savefig(out_path, dpi=DPI)
    plt.close(fig)
    return out_path


def figure_4_heating_duration_sensitivity() -> Path:
    durations = [60.0, 120.0, 180.0, 240.0]
    total_times = [400.0, 600.0, 750.0, 900.0]

    tile_masses = []
    dense_masses = []
    light_masses = []
    light_feasible = []

    for tau_heat, total_time in zip(durations, total_times):
        case = replace(STUDY_CASE, name=f"tau_heat={tau_heat:.0f}s", tau_heat=tau_heat, total_time=total_time)
        results = run_trade_study(case, REUSABLE_CANDIDATES, ABLATIVE_CANDIDATES)
        by_name = {r.name: r for r in results}
        tile_masses.append(by_name["Reusable low-density tile (illustrative)"].initial_areal_mass)
        dense_masses.append(by_name["Dense high-H_eff ablator (illustrative)"].initial_areal_mass)
        light = by_name["Lightweight charring ablator (illustrative)"]
        light_feasible.append(light.feasible)
        light_masses.append(light.initial_areal_mass if light.feasible else None)

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(durations, tile_masses, color=REUSABLE_COLOR, marker="o", linewidth=2, label="Reusable low-density tile")
    ax.plot(durations, dense_masses, color=ABLATIVE_COLOR, marker="s", linewidth=2, label="Dense high-H_eff ablator")

    feasible_durations = [d for d, f in zip(durations, light_feasible) if f]
    feasible_masses = [m for m, f in zip(light_masses, light_feasible) if f]
    infeasible_durations = [d for d, f in zip(durations, light_feasible) if not f]

    ax.plot(feasible_durations, feasible_masses, color="#E0A458", marker="^", linewidth=2, label="Lightweight charring ablator")
    for d in infeasible_durations:
        ax.axvline(d, color="#E0A458", linestyle="--", linewidth=1, alpha=0.7)
        ax.annotate(
            "lightweight ablator\nINFEASIBLE beyond\nthis duration\n(exceeds recession\nallowable)",
            xy=(d, ax.get_ylim()[1] if ax.get_ylim()[1] > 0 else 1),
            xytext=(d, max(tile_masses + dense_masses) * 0.6),
            ha="center", fontsize=8, color="#7a4a1e",
        )

    ax.set_xlabel("Heating pulse duration [s]")
    ax.set_ylabel("Required initial areal mass [kg/m$^2$]")
    ax.set_title(
        "Heating-duration sensitivity: single-event areal mass by candidate\n"
        "(peak hot-side temperature and heat flux held fixed)"
    )
    ax.legend(loc="upper left")
    ax.grid(True, linestyle=":", linewidth=0.5, alpha=0.6)
    fig.tight_layout()

    out_path = FIGURES_DIR / "fig4_heating_duration_sensitivity.png"
    fig.savefig(out_path, dpi=DPI)
    plt.close(fig)
    return out_path


def main() -> None:
    FIGURES_DIR.mkdir(exist_ok=True)
    trade_results = run_trade_study(STUDY_CASE, REUSABLE_CANDIDATES, ABLATIVE_CANDIDATES)

    paths = [
        figure_1_single_event_trade(trade_results),
        figure_2_thickness_recession(trade_results),
        figure_3_lifecycle_burden(trade_results),
        figure_4_heating_duration_sensitivity(),
    ]
    print("Generated portfolio figures:")
    for path in paths:
        print(f"  {path.relative_to(FIGURES_DIR.parent)}")


if __name__ == "__main__":
    main()
