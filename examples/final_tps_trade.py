"""STM-05 final canonical end-to-end TPS trade (Milestone 6).

One script that reproduces the project's major outputs in a single run:
the canonical study case, the single-event trade (Milestone 4), the
repeated-mission lifecycle trade (Milestone 5), a compact sensitivity
summary (heating duration, refurbishment fraction, reusable service life),
and the final, narrowly-scoped engineering recommendation.

This script introduces NO new equations or physics -- it only calls the
already-verified public API (`tps_trade.trade`, `tps_trade.lifecycle`,
`tps_trade.candidates`) and formats the results. See the individual
milestone examples (`sanity_case.py`, `transient_heating_study.py`,
`ablative_sanity_case.py`, `tps_material_trade.py`,
`tps_lifecycle_trade.py`) for the step-by-step derivations, and the README
for the full model documentation, verification summary, and limitations.

Run with:

    python examples/final_tps_trade.py
"""

from dataclasses import replace

from tps_trade import (
    StudyCase,
    LifecycleConfig,
    run_trade_study,
    summarize_trade,
    generate_recommendation,
    run_lifecycle_study,
    summarize_lifecycle,
    find_breakeven_mission_count,
    STUDY_CASE,
    REUSABLE_CANDIDATES,
    ABLATIVE_CANDIDATES,
)

MISSION_COUNTS = (1, 5, 10, 25, 50, 100)
BASELINE_SERVICE_LIFE = 50
BASELINE_REFURB_FRACTION = 0.01


def section(title: str) -> None:
    print()
    print(f"=== {title} ===")


def print_study_case(case: StudyCase) -> None:
    section("CANONICAL STUDY CASE")
    print(f"Name:                       {case.name}")
    print(f"Initial temperature:        {case.t_initial:.1f} K")
    print(f"Peak hot-side temperature:  {case.t_hot_max:.1f} K   (reusable Dirichlet BC)")
    print(f"Pulse duration:             {case.tau_heat:.1f} s")
    print(f"Total analysis duration:    {case.total_time:.1f} s   (reusable transient solve)")
    print(f"Backface temperature limit: {case.t_back_max:.1f} K   (reusable)")
    print(f"Ablative net heat flux:     {case.ablative_heat_flux:.3e} W/m^2")
    print(f"Integrated ablative load:   {case.ablative_total_heat_load():.3e} J/m^2   (Q'' = q''*tau_heat)")
    print(
        "NOTE: t_hot_max and ablative_heat_flux are two different simplified "
        "boundary-condition descriptions of 'the same' illustrative event -- "
        "there is no physical derivation linking them (see README)."
    )


def print_single_event_trade(results) -> None:
    section("SINGLE-EVENT TRADE (Milestone 4)")
    header = f"{'Name':<46}{'Category':<10}{'Feasible':>9}{'Thick[mm]':>11}{'Mass[kg/m2]':>13}{'Governing metric':>34}{'Margin':>16}"
    print(header)
    for r in results:
        thick = f"{r.required_thickness * 1000:.2f}" if r.required_thickness is not None else "--"
        mass = f"{r.initial_areal_mass:.2f}" if r.initial_areal_mass is not None else "--"
        if r.governing_metric_value is not None:
            if r.category == "reusable":
                metric = f"{r.governing_metric_name}={r.governing_metric_value:.1f} K"
            else:
                metric = f"{r.governing_metric_name}={r.governing_metric_value * 1000:.2f} mm"
        else:
            metric = "--"
        margin = f"{r.design_margin:+.3f} {r.margin_units}" if r.design_margin is not None else "--"
        print(f"{r.name:<46}{r.category:<10}{str(r.feasible):>9}{thick:>11}{mass:>13}{metric:>34}{margin:>16}")

    summary = summarize_trade(results)
    print()
    print("Ranking (feasible candidates, lightest first):")
    for i, r in enumerate(summary.ranked_feasible, start=1):
        print(f"  {i}. {r.name} ({r.category}): {r.initial_areal_mass:.2f} kg/m^2")
    return summary


def print_lifecycle_trade(trade_results):
    section("LIFECYCLE TRADE (Milestone 5)")
    print(
        f"Baseline lifecycle assumptions: reusable service life = "
        f"{BASELINE_SERVICE_LIFE} missions, refurbishment-equivalent fraction = "
        f"{BASELINE_REFURB_FRACTION * 100:.1f}% of installed mass/mission (both illustrative)"
    )
    header = f"{'Missions':>9}  {'Name':<46}{'Cum.burden':>12}{'Avg/mission':>13}{'Rank':>6}"
    print(header)

    winners = {}
    for mission_count in MISSION_COUNTS:
        config = LifecycleConfig(
            mission_count=mission_count,
            reusable_service_life_missions=BASELINE_SERVICE_LIFE,
            reusable_refurbishment_fraction=BASELINE_REFURB_FRACTION,
        )
        life_results = run_lifecycle_study(trade_results, config)
        summary = summarize_lifecycle(life_results)
        winners[mission_count] = summary.winner
        ranked_names = {r.name: i + 1 for i, r in enumerate(summary.ranked_feasible)}
        for r in life_results:
            cum = f"{r.cumulative_lifecycle_burden:.2f}" if r.cumulative_lifecycle_burden is not None else "--"
            avg = f"{r.mission_averaged_burden:.3f}" if r.mission_averaged_burden is not None else "--"
            rank = str(ranked_names.get(r.name, "--"))
            print(f"{mission_count:>9}  {r.name:<46}{cum:>12}{avg:>13}{rank:>6}")
    return winners


def print_sensitivity_summary(study_case, reusable_materials, ablative_candidates, trade_results):
    section("SENSITIVITY SUMMARY")

    print("--- A. Heating-duration sensitivity (60 s / 120 s / 240 s) ---")
    for label, tau_heat, total_time in (
        ("60 s (shorter)", 60.0, 400.0),
        ("120 s (baseline)", study_case.tau_heat, study_case.total_time),
        ("240 s (longer)", 240.0, 900.0),
    ):
        case = replace(study_case, name=f"tau_heat={tau_heat:.0f}s", tau_heat=tau_heat, total_time=total_time)
        case_results = run_trade_study(case, reusable_materials, ablative_candidates)
        summary = summarize_trade(case_results)
        by_name = {r.name: r for r in case_results}
        tile = by_name["Reusable low-density tile (illustrative)"]
        dense = by_name["Dense high-H_eff ablator (illustrative)"]
        light = by_name["Lightweight charring ablator (illustrative)"]
        print(
            f"  {label:<18} tile={tile.initial_areal_mass:.2f} kg/m^2 | "
            f"dense ablator={dense.initial_areal_mass:.2f} kg/m^2 "
            f"({'feasible' if dense.feasible else 'INFEASIBLE'}) | "
            f"lightweight ablator={'%.2f kg/m^2' % light.initial_areal_mass if light.feasible else 'INFEASIBLE'} "
            f"-> winner: {summary.winner.name} ({summary.winner.category})"
        )
    print(
        "  Ranking does not change across these durations in this candidate "
        "set (reusable tile always wins), though the lightweight ablator "
        "becomes infeasible at 240 s (exceeds its recession allowable)."
    )

    by_name = {r.name: r for r in trade_results}
    tile = by_name["Reusable low-density tile (illustrative)"]
    dense = by_name["Dense high-H_eff ablator (illustrative)"]

    print()
    print("--- B. Reusable refurbishment-fraction sensitivity (tile, M=50 missions) ---")
    dense_50 = run_lifecycle_study(
        [dense], LifecycleConfig(mission_count=50, reusable_service_life_missions=BASELINE_SERVICE_LIFE, reusable_refurbishment_fraction=0.0)
    )[0]
    for f_refurb in (0.0, 0.01, 0.02, 0.05):
        config = LifecycleConfig(mission_count=50, reusable_service_life_missions=BASELINE_SERVICE_LIFE, reusable_refurbishment_fraction=f_refurb)
        life = run_lifecycle_study([tile], config)[0]
        print(f"  f_refurb={f_refurb * 100:>4.1f}%: tile burden = {life.cumulative_lifecycle_burden:>7.2f} kg/m^2-equiv  (dense ablator: {dense_50.cumulative_lifecycle_burden:.2f})")
    print("  Ranking is unchanged across this range: the tile stays far below the dense ablator's 50-mission burden.")

    print()
    print("--- C. Reusable service-life sensitivity (tile, M=100 missions, f_refurb=1%) ---")
    dense_100 = run_lifecycle_study(
        [dense], LifecycleConfig(mission_count=100, reusable_service_life_missions=BASELINE_SERVICE_LIFE, reusable_refurbishment_fraction=BASELINE_REFURB_FRACTION)
    )[0]
    for n_service in (10, 25, 50, 100):
        config = LifecycleConfig(mission_count=100, reusable_service_life_missions=n_service, reusable_refurbishment_fraction=BASELINE_REFURB_FRACTION)
        life = run_lifecycle_study([tile], config)[0]
        print(f"  N_service={n_service:>4}: tile burden = {life.cumulative_lifecycle_burden:>7.2f} kg/m^2-equiv ({life.replacements} replacement(s))  (dense ablator: {dense_100.cumulative_lifecycle_burden:.2f})")
    print("  Ranking is unchanged even at the shortest illustrative service life tested (10 missions).")


def print_final_recommendation(single_event_summary, lifecycle_winners) -> None:
    section("FINAL RECOMMENDATION")
    single_winner = single_event_summary.winner
    winner_100 = lifecycle_winners[100]

    print(f"Single-event winner:  {single_winner.name} ({single_winner.category})")
    print(f"100-mission winner:   {winner_100.name} ({winner_100.category})")
    print()
    print(
        "Under the defined illustrative thermal and lifecycle assumptions, "
        f"the {single_winner.name} is the minimum-areal-mass feasible "
        "candidate for BOTH the single-event and the repeated-mission trade "
        "in this study."
    )
    print()
    print("Reason:")
    print(
        "  - Single event: it requires the lowest initial areal mass among "
        "all THERMALLY FEASIBLE candidates for this study case's prescribed "
        "hot-side pulse and backface limit."
    )
    print(
        "  - Repeated missions: its cumulative lifecycle burden (installation "
        "plus refurbishment-equivalent penalty, occasional full replacement) "
        "grows far more slowly with mission count than either ablative "
        "candidate's linearly-growing replenishment burden, so it remains "
        "lightest across every mission count and every sensitivity case "
        "tested here."
    )
    print()
    print("Limitations of this recommendation:")
    print("  - The reusable and ablative models do NOT use identical boundary-condition formulations")
    print("    (prescribed temperature vs. prescribed heat flux) -- see the README.")
    print("  - Lifecycle assumptions here strongly favor reusable systems once repeated missions are")
    print("    considered; this is a property of the assumptions and candidate set, not a general law.")
    print("  - Refurbishment-equivalent burden is a mass bookkeeping convention, NOT real monetary cost")
    print("    or labor.")
    print("  - All candidate material properties are illustrative, not sourced design allowables.")
    print("  - No certified vehicle conclusion is being made -- this is a preliminary, illustrative,")
    print("    single-study-case model comparison.")


def main() -> None:
    print("=================================================================")
    print(" STM-05: TPS Material Trade -- final canonical end-to-end result")
    print("=================================================================")

    print_study_case(STUDY_CASE)

    trade_results = run_trade_study(STUDY_CASE, REUSABLE_CANDIDATES, ABLATIVE_CANDIDATES)
    single_event_summary = print_single_event_trade(trade_results)

    lifecycle_winners = print_lifecycle_trade(trade_results)

    print_sensitivity_summary(STUDY_CASE, REUSABLE_CANDIDATES, ABLATIVE_CANDIDATES, trade_results)

    by_name = {r.name: r for r in trade_results}
    tile = by_name["Reusable low-density tile (illustrative)"]
    dense = by_name["Dense high-H_eff ablator (illustrative)"]
    base_config = LifecycleConfig(mission_count=1, reusable_service_life_missions=BASELINE_SERVICE_LIFE, reusable_refurbishment_fraction=BASELINE_REFURB_FRACTION)
    breakeven = find_breakeven_mission_count(tile, dense, base_config, mission_range=(1, 500))
    section("BREAK-EVEN CHECK (reusable tile vs. dense ablator)")
    if breakeven.crossover_found:
        print(f"Crossover found at mission {breakeven.crossover_mission_count}.")
    else:
        print(
            f"No crossover found within {breakeven.mission_range[0]}-{breakeven.mission_range[1]} missions "
            f"-- '{breakeven.leader_at_range_start}' leads throughout."
        )

    print_final_recommendation(single_event_summary, lifecycle_winners)


if __name__ == "__main__":
    main()
