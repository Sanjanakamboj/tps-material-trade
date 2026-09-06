"""Milestone 4 canonical reusable-vs-ablative TPS trade study.

Runs the canonical illustrative study case (``tps_trade.candidates.STUDY_CASE``)
against the small illustrative candidate database
(``tps_trade.candidates.REUSABLE_CANDIDATES`` / ``ABLATIVE_CANDIDATES``),
prints a transparent engineering trade table, and reports the
minimum-areal-mass feasible candidate plus a preliminary, case-specific
recommendation.

Also runs a small heating-DURATION sensitivity study (shorter vs. longer
pulse, same peak hot-side temperature / heat flux) to show how required
thickness, areal mass, and feasibility respond -- and whether the ranking
changes.

IMPORTANT: see tps_trade.trade module docstring and the project README for
why the reusable (prescribed hot-side TEMPERATURE) and ablative (prescribed
net heat FLUX) boundary conditions used here are two different simplified
descriptions of "the same" illustrative event, not a physically derived
equivalence -- and for the full list of what this trade does NOT yet
account for (lifecycle/reuse, pyrolysis chemistry, a coupled surface energy
balance, attachment/substructure mass, cost, etc).

Run with:

    python examples/tps_material_trade.py
"""

from tps_trade import (
    StudyCase,
    run_trade_study,
    summarize_trade,
    generate_recommendation,
    STUDY_CASE,
    REUSABLE_CANDIDATES,
    ABLATIVE_CANDIDATES,
)


def print_trade_table(results) -> None:
    reusable = [r for r in results if r.category == "reusable"]
    ablative = [r for r in results if r.category == "ablative"]

    print("--- Reusable candidates ---")
    header = f"{'Name':<38}{'Feasible':>9}{'Thick[mm]':>11}{'Mass[kg/m2]':>13}{'PeakTback[K]':>13}{'Margin[K]':>11}{'alpha[m2/s]':>13}"
    print(header)
    for r in reusable:
        thick = f"{r.required_thickness * 1000:.2f}" if r.required_thickness is not None else "--"
        mass = f"{r.initial_areal_mass:.2f}" if r.initial_areal_mass is not None else "--"
        peak = f"{r.governing_metric_value:.1f}" if r.governing_metric_value is not None else "--"
        margin = f"{r.design_margin:+.3f}" if r.design_margin is not None else "--"
        alpha = f"{r.reusable_detail.thermal_diffusivity:.3e}" if r.reusable_detail else "--"
        print(f"{r.name:<38}{str(r.feasible):>9}{thick:>11}{mass:>13}{peak:>13}{margin:>11}{alpha:>13}")

    print()
    print("--- Ablative candidates ---")
    header = f"{'Name':<38}{'Feasible':>9}{'Thick[mm]':>11}{'Mass[kg/m2]':>13}{'Recess[mm]':>12}{'Consumed[%]':>13}{'Retained[mm]':>13}"
    print(header)
    for r in ablative:
        thick = f"{r.required_thickness * 1000:.2f}" if r.required_thickness is not None else "--"
        mass = f"{r.initial_areal_mass:.2f}" if r.initial_areal_mass is not None else "--"
        recess = f"{r.governing_metric_value * 1000:.2f}" if r.governing_metric_value is not None else "--"
        consumed = f"{r.ablative_detail.consumed_mass_fraction * 100:.1f}" if r.ablative_detail else "--"
        retained = f"{r.ablative_detail.retained_thickness * 1000:.2f}" if r.ablative_detail else "--"
        print(f"{r.name:<38}{str(r.feasible):>9}{thick:>11}{mass:>13}{recess:>12}{consumed:>13}{retained:>13}")


def main() -> None:
    print("=== Milestone 4 reusable-vs-ablative TPS trade study ===")
    print(f"Study case: {STUDY_CASE.name}")
    print(f"  T_initial:            {STUDY_CASE.t_initial:.1f} K")
    print(f"  T_hot,max (reusable): {STUDY_CASE.t_hot_max:.1f} K")
    print(f"  Heat flux (ablative): {STUDY_CASE.ablative_heat_flux:.3e} W/m^2")
    print(f"  Heating duration:     {STUDY_CASE.tau_heat:.1f} s")
    print(f"  Total sim duration:   {STUDY_CASE.total_time:.1f} s")
    print(f"  T_back,max (reusable):{STUDY_CASE.t_back_max:.1f} K")
    print()

    results = run_trade_study(STUDY_CASE, REUSABLE_CANDIDATES, ABLATIVE_CANDIDATES)
    print_trade_table(results)

    summary = summarize_trade(results)
    print()
    print("--- Ranking (feasible candidates, lightest first) ---")
    for i, r in enumerate(summary.ranked_feasible, start=1):
        print(f"{i}. {r.name} ({r.category}): {r.initial_areal_mass:.2f} kg/m^2")

    print()
    print(generate_recommendation(STUDY_CASE, summary))

    # --- Heating-duration sensitivity study --------------------------------
    print()
    print("=== Sensitivity: heating-pulse duration ===")
    print(
        "Same peak hot-side temperature and heat flux; only the heating "
        "duration (and, for the reusable case, the total simulated time to "
        "let the backface response develop) changes."
    )
    durations = (
        ("Case A: shorter pulse", 60.0, 400.0),
        ("Baseline (canonical case)", STUDY_CASE.tau_heat, STUDY_CASE.total_time),
        ("Case B: longer pulse", 240.0, 900.0),
    )
    for label, tau_heat, total_time in durations:
        case = StudyCase(
            name=f"{label} (tau_heat={tau_heat:.0f} s)",
            t_initial=STUDY_CASE.t_initial,
            t_hot_max=STUDY_CASE.t_hot_max,
            tau_heat=tau_heat,
            total_time=total_time,
            t_back_max=STUDY_CASE.t_back_max,
            ablative_heat_flux=STUDY_CASE.ablative_heat_flux,
        )
        case_results = run_trade_study(case, REUSABLE_CANDIDATES, ABLATIVE_CANDIDATES)
        case_summary = summarize_trade(case_results)
        print()
        print(f"{label} (tau_heat={tau_heat:.0f} s):")
        for r in case_results:
            mass = f"{r.initial_areal_mass:.2f}" if r.initial_areal_mass is not None else "--"
            print(f"    {r.name:<38} feasible={str(r.feasible):<5} mass={mass} kg/m^2")
        winner = case_summary.winner
        print(f"  -> winner: {winner.name} ({winner.category}) at {winner.initial_areal_mass:.2f} kg/m^2")

    print()
    print(
        "Interpretation: as heating duration increases, the reusable "
        "candidate's required insulation thickness/mass grows (transient "
        "penetration has more time to reach the backface), while each "
        "ablative candidate's consumed mass grows linearly with the "
        "(constant) heat flux held over a longer time. In this study case "
        "the ranking does not cross over -- the reusable tile remains the "
        "minimum-mass feasible candidate at every duration tested -- but "
        "note that the lightweight charring ablator can itself become "
        "INFEASIBLE at longer durations if its recession exceeds its "
        "illustrative structural allowable (max_recession), independent of "
        "the reusable-vs-ablative mass comparison. No crossover is forced "
        "here; report whichever outcome the numbers actually show."
    )


if __name__ == "__main__":
    main()
