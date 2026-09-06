"""Milestone 5 canonical illustrative lifecycle trade study.

Extends the Milestone 4 single-event trade
(examples/tps_material_trade.py) into a simple, transparent multi-mission
mass-equivalent lifecycle comparison, using the SAME canonical candidates
and study case. See tps_trade.lifecycle module docstring and the README
for the full lifecycle methodology and its limitations -- this is an
ILLUSTRATIVE LIFECYCLE MASS-EQUIVALENT TRADE, not a real operations-cost or
reliability model.

Run with:

    python examples/tps_lifecycle_trade.py
"""

from dataclasses import replace

from tps_trade import (
    LifecycleConfig,
    run_lifecycle_study,
    summarize_lifecycle,
    find_breakeven_mission_count,
    run_trade_study,
    STUDY_CASE,
    REUSABLE_CANDIDATES,
    ABLATIVE_CANDIDATES,
)

# Baseline illustrative lifecycle assumptions -- NOT sourced from any real
# vehicle's tile lifetime or maintenance program.
BASELINE_SERVICE_LIFE_MISSIONS = 50
BASELINE_REFURBISHMENT_FRACTION = 0.01  # 1% of installed areal mass per mission
MISSION_COUNTS = (1, 5, 10, 25, 50, 100)


def print_lifecycle_table(life_results, mission_count) -> None:
    print(f"--- Mission count = {mission_count} ---")
    header = (
        f"{'Name':<46}{'Category':<10}{'Feasible':>9}{'Init.mass':>11}"
        f"{'Cum.burden':>12}{'Avg/mission':>13}{'Repl./Replen.':>15}"
    )
    print(header)
    for r in life_results:
        init_mass = f"{r.initial_areal_mass:.2f}" if r.initial_areal_mass is not None else "--"
        cum = f"{r.cumulative_lifecycle_burden:.2f}" if r.cumulative_lifecycle_burden is not None else "--"
        avg = f"{r.mission_averaged_burden:.3f}" if r.mission_averaged_burden is not None else "--"
        repl = str(r.replacements) if r.replacements is not None else "--"
        print(f"{r.name:<46}{r.category:<10}{str(r.feasible):>9}{init_mass:>11}{cum:>12}{avg:>13}{repl:>15}")


def main() -> None:
    print("=== Milestone 5 illustrative lifecycle trade study ===")
    print(f"Study case: {STUDY_CASE.name} (same as Milestone 4)")
    print(f"Baseline reusable service life: {BASELINE_SERVICE_LIFE_MISSIONS} missions (illustrative)")
    print(f"Baseline refurbishment-equivalent fraction: {BASELINE_REFURBISHMENT_FRACTION * 100:.1f}% of installed mass/mission (illustrative)")
    print()

    trade_results = run_trade_study(STUDY_CASE, REUSABLE_CANDIDATES, ABLATIVE_CANDIDATES)

    print("--- Single-event (Milestone 4) result, reproduced for reference ---")
    for r in trade_results:
        mass = f"{r.initial_areal_mass:.2f} kg/m^2" if r.initial_areal_mass is not None else "infeasible"
        print(f"  {r.name}: {mass}")
    print()

    winners_by_mission = {}
    for mission_count in MISSION_COUNTS:
        config = LifecycleConfig(
            mission_count=mission_count,
            reusable_service_life_missions=BASELINE_SERVICE_LIFE_MISSIONS,
            reusable_refurbishment_fraction=BASELINE_REFURBISHMENT_FRACTION,
        )
        life_results = run_lifecycle_study(trade_results, config)
        print_lifecycle_table(life_results, mission_count)
        summary = summarize_lifecycle(life_results)
        winners_by_mission[mission_count] = summary.winner
        print(f"  -> lifecycle winner: {summary.winner.name} ({summary.winner.category})")
        print()

    single_event_winner = min(
        (r for r in trade_results if r.feasible), key=lambda r: r.initial_areal_mass
    )
    print("=== Summary across mission counts ===")
    print(f"Single-event (M=1-equivalent, Milestone 4) winner: {single_event_winner.name}")
    print(f"50-mission lifecycle winner:  {winners_by_mission[50].name}")
    print(f"100-mission lifecycle winner: {winners_by_mission[100].name}")

    # --- Break-even analysis: reusable tile vs. dense ablator -------------
    print()
    print("=== Break-even analysis: Reusable low-density tile vs. Dense high-H_eff ablator ===")
    by_name = {r.name: r for r in trade_results}
    tile = by_name["Reusable low-density tile (illustrative)"]
    dense_ablator = by_name["Dense high-H_eff ablator (illustrative)"]
    base_config = LifecycleConfig(
        mission_count=1,
        reusable_service_life_missions=BASELINE_SERVICE_LIFE_MISSIONS,
        reusable_refurbishment_fraction=BASELINE_REFURBISHMENT_FRACTION,
    )
    breakeven = find_breakeven_mission_count(tile, dense_ablator, base_config, mission_range=(1, 500))
    if breakeven.crossover_found:
        print(
            f"Crossover found at mission {breakeven.crossover_mission_count}: leadership changes from "
            f"'{breakeven.leader_at_range_start}' to '{breakeven.leader_at_range_end}'."
        )
    else:
        print(
            f"No crossover found within {breakeven.mission_range[0]}-{breakeven.mission_range[1]} missions. "
            f"'{breakeven.leader_at_range_start}' leads throughout this range "
            f"(burden at {breakeven.mission_range[1]} missions: "
            f"tile={breakeven.burden_a_at_crossover:.2f} kg/m^2-equiv, "
            f"dense ablator={breakeven.burden_b_at_crossover:.2f} kg/m^2-equiv)."
        )

    # --- Service-life sensitivity (reusable tile) --------------------------
    print()
    print("=== Sensitivity: reusable service life (tile, M=100 missions, f_refurb=1%) ===")
    for n_service in (10, 25, 50, 100):
        config = replace(base_config, mission_count=100, reusable_service_life_missions=n_service)
        life = run_lifecycle_study([tile], config)[0]
        print(
            f"  N_service={n_service:>4}: cumulative burden = {life.cumulative_lifecycle_burden:.2f} kg/m^2-equiv "
            f"({life.replacements} replacement(s))"
        )
    print(
        "  For comparison, the Dense high-H_eff ablator's 100-mission burden is "
        f"{run_lifecycle_study([dense_ablator], replace(base_config, mission_count=100))[0].cumulative_lifecycle_burden:.2f} "
        "kg/m^2-equiv, regardless of reusable service life."
    )

    # --- Refurbishment-fraction sensitivity (reusable tile) -----------------
    print()
    print("=== Sensitivity: refurbishment-equivalent fraction (tile, M=50 missions) ===")
    for f_refurb in (0.0, 0.01, 0.02, 0.05):
        config = replace(base_config, mission_count=50, reusable_refurbishment_fraction=f_refurb)
        life = run_lifecycle_study([tile], config)[0]
        print(f"  f_refurb={f_refurb * 100:>4.1f}%: cumulative burden = {life.cumulative_lifecycle_burden:.2f} kg/m^2-equiv")
    print(
        "  For comparison, the Dense high-H_eff ablator's 50-mission burden is "
        f"{run_lifecycle_study([dense_ablator], replace(base_config, mission_count=50))[0].cumulative_lifecycle_burden:.2f} "
        "kg/m^2-equiv, unaffected by the reusable refurbishment fraction."
    )

    print()
    print(
        "Interpretation: neither the service-life nor refurbishment-fraction "
        "sensitivity changes the ranking in this candidate set -- the reusable "
        "tile remains far lighter over the mission counts and parameter ranges "
        "tested here, because the ablative candidates' PER-MISSION consumed "
        "mass is large relative to the reusable tile's installation and "
        "refurbishment burden. This is a property of THESE illustrative "
        "candidates and assumptions, not a general claim that reusable TPS "
        "always wins a lifecycle comparison -- a candidate set with a lower-"
        "consumption ablator or a much shorter reusable service life could "
        "show a different, or crossing, result."
    )


if __name__ == "__main__":
    main()
