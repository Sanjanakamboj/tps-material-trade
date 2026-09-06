"""Milestone 3 illustrative ablative sanity study.

Sizes one illustrative ablative TPS material against a simple constant
heat-flux pulse using the first-order lumped ablation model (see
tps_trade.ablative module docstring for the full list of assumptions and
what is intentionally NOT modeled: pyrolysis kinetics, moving-boundary
conduction, char-layer thermochemistry, surface chemistry, a coupled
surface energy balance, or blowing correction).

Also runs a small sensitivity study on the effective heat of ablation
(H_eff), and evaluates 80%/120% of the required initial thickness.

Run with:

    python examples/ablative_sanity_case.py

Does NOT compare this ablative concept against the Milestone 1/2 reusable
TPS concepts -- that reusable-vs-ablative trade is explicitly out of scope
for this milestone.
"""

from tps_trade import (
    AblativeMaterial,
    HeatFluxSegment,
    integrated_heat_load,
    size_ablative_thickness,
    evaluate_trial_thickness,
)


def main() -> None:
    # Illustrative charring-ablator-style material. Properties are
    # illustrative (order-of-magnitude representative of a mid-density
    # charring ablator), NOT sourced from a specific material data sheet,
    # and must not be treated as design allowables.
    material = AblativeMaterial(
        name="Illustrative Charring Ablative TPS (illustrative properties)",
        density=1400.0,  # kg/m^3
        effective_heat_of_ablation=1.0e7,  # J/kg (10 MJ/kg)
    )

    # A simple constant heat-flux pulse -- NOT a real entry heat-rate trace.
    heat_flux = 2.0e6  # W/m^2
    duration = 60.0  # s
    pulse = [HeatFluxSegment(heat_flux=heat_flux, duration=duration)]
    total_heat_load = integrated_heat_load(pulse)

    retained_thickness = 0.005  # m, explicit engineering input (NOT derived/certified here)

    result = size_ablative_thickness(material, total_heat_load, retained_thickness)

    print("=== Milestone 3 illustrative ablative sanity study ===")
    print(f"Material:                 {result.material.name}")
    print(f"  density (rho):          {result.material.density:.1f} kg/m^3")
    print(f"  H_eff:                  {result.effective_heat_of_ablation:.3e} J/kg")
    print(f"Heat-flux pulse:          {heat_flux:.3e} W/m^2 for {duration:.1f} s")
    print(f"Total heat load (Q''):    {total_heat_load:.3e} J/m^2")
    print(f"Consumed areal mass:      {result.consumed_areal_mass:.3f} kg/m^2")
    print(f"Recession depth:          {result.recession_depth * 1000:.2f} mm ({result.recession_depth:.5f} m)")
    print(f"Retained thickness req.:  {result.retained_thickness * 1000:.2f} mm")
    print(f"Initial required thick.:  {result.initial_thickness * 1000:.2f} mm ({result.initial_thickness:.5f} m)")
    print(f"Initial areal mass:       {result.initial_areal_mass:.3f} kg/m^2")
    print(f"Remaining areal mass:     {result.remaining_areal_mass:.3f} kg/m^2")
    print(f"Consumed mass fraction:   {result.consumed_mass_fraction:.3f}")
    print(
        f"Mass check (init = remain + consumed): "
        f"{result.initial_areal_mass:.3f} = {result.remaining_areal_mass:.3f} + {result.consumed_areal_mass:.3f}"
    )

    print()
    print("--- Off-nominal initial-thickness checks ---")
    for label, fraction in (("80% of required (undersized)", 0.8), ("120% of required (oversized)", 1.2)):
        trial_thickness = fraction * result.initial_thickness
        trial = evaluate_trial_thickness(material, trial_thickness, total_heat_load, retained_thickness)
        status = "PASS" if trial.passed else "FAIL"
        print(
            f"{label}: t_initial = {trial_thickness * 1000:.2f} mm -> "
            f"remaining after recession = {trial.remaining_thickness * 1000:.2f} mm, "
            f"margin = {trial.margin_thickness * 1000:+.2f} mm ({status})"
        )

    undersized = evaluate_trial_thickness(material, 0.8 * result.initial_thickness, total_heat_load, retained_thickness)
    oversized = evaluate_trial_thickness(material, 1.2 * result.initial_thickness, total_heat_load, retained_thickness)
    assert not undersized.passed, "undersized case should fail the retained-thickness requirement"
    assert oversized.passed and oversized.margin_thickness > 0.0, "oversized case should pass with positive margin"
    print()
    print("Sanity checks passed: undersized case fails the retained-thickness requirement;")
    print("oversized case passes with positive margin.")

    # --- Sensitivity study: effective heat of ablation (H_eff) -----------
    print()
    print("--- Sensitivity: effective heat of ablation (H_eff) ---")
    print(f"{'H_eff variant':<18}{'H_eff [J/kg]':>16}{'recession [mm]':>18}{'t_initial [mm]':>18}{'areal mass [kg/m2]':>20}")
    for label, h_eff_factor in (("-25%", 0.75), ("baseline", 1.0), ("+25%", 1.25)):
        variant = AblativeMaterial(
            name="H_eff sensitivity variant",
            density=material.density,
            effective_heat_of_ablation=material.effective_heat_of_ablation * h_eff_factor,
        )
        variant_result = size_ablative_thickness(variant, total_heat_load, retained_thickness)
        print(
            f"{label:<18}{variant_result.effective_heat_of_ablation:>16.3e}"
            f"{variant_result.recession_depth * 1000:>18.2f}"
            f"{variant_result.initial_thickness * 1000:>18.2f}"
            f"{variant_result.initial_areal_mass:>20.3f}"
        )
    print(
        "Higher H_eff means more net absorbed energy is required to remove "
        "the same areal mass, so recession depth (and therefore required "
        "initial thickness and areal mass) scales INVERSELY with H_eff at "
        "fixed heat load and density -- a higher-H_eff material is more "
        "efficient per unit mass sacrificed, but H_eff alone does not "
        "determine overall TPS system quality (e.g. it says nothing about "
        "retained-thickness insulation performance)."
    )


if __name__ == "__main__":
    main()
