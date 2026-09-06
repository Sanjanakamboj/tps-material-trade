"""Milestone 1 illustrative sanity case.

Sizes a single, illustrative reusable-TPS-style material against a prescribed
hot-surface temperature and steady heat flux, for a chosen backface
temperature limit. Also evaluates 80% and 120% of the required thickness to
show that the model behaves sensibly on either side of the sizing point.

Run with:

    python examples/sanity_case.py

NOTE: This is a deliberately simplified, illustrative case -- see the README
and tps_trade.conduction module docstring for the physical caveats of
prescribing T_hot and q'' independently.
"""

from tps_trade import TPSMaterial, backface_temperature, size_thickness_for_backface_limit


def main() -> None:
    # Illustrative reusable-TPS-style rigid tile material.
    # Properties are illustrative (order-of-magnitude representative of a
    # low-density ceramic tile insulator), NOT sourced from a specific
    # material data sheet, and must not be treated as design allowables.
    material = TPSMaterial(
        name="Illustrative Reusable TPS Tile (rigid ceramic insulator, illustrative properties)",
        density=350.0,  # kg/m^3
        conductivity=0.06,  # W/(m*K)
        max_service_temperature=1650.0,  # K
    )

    t_hot = 1400.0  # K, prescribed hot-surface temperature
    heat_flux = 3000.0  # W/m^2, prescribed steady heat flux
    t_back_max = 450.0  # K, backface temperature limit (e.g. bondline limit)

    result = size_thickness_for_backface_limit(
        material, t_hot=t_hot, heat_flux=heat_flux, t_back_max=t_back_max
    )

    print("=== Milestone 1 illustrative TPS sanity case ===")
    print(f"Material:                 {result.material.name}")
    print(f"  density (rho):          {result.material.density:.1f} kg/m^3")
    print(f"  conductivity (k):       {result.material.conductivity:.4f} W/(m*K)")
    print(f"T_hot:                    {result.t_hot:.1f} K")
    print(f"Heat flux (q''):          {result.heat_flux:.1f} W/m^2")
    print(f"T_back,max:               {result.t_back_max:.1f} K")
    print(f"Required thickness:       {result.thickness * 100:.2f} cm ({result.thickness:.4f} m)")
    print(f"Thermal resistance (R''): {result.thermal_resistance:.4f} m^2*K/W")
    print(f"Areal mass (m_A):         {result.areal_mass:.2f} kg/m^2")
    print(f"Predicted T_back:         {result.t_back_predicted:.2f} K")
    print(f"Temperature margin:       {result.margin_temperature:+.4f} K")
    print(f"Normalized margin:        {result.normalized_margin:+.6f}")

    print()
    print("--- Off-nominal thickness checks ---")
    for label, fraction in (("80% of required (undersized)", 0.8), ("120% of required (oversized)", 1.2)):
        thickness = fraction * result.thickness
        t_back = backface_temperature(t_hot, heat_flux, thickness, material.conductivity)
        margin = t_back_max - t_back
        status = "EXCEEDS limit" if t_back > t_back_max else "within limit"
        print(
            f"{label}: t = {thickness * 100:.2f} cm -> T_back = {t_back:.2f} K, "
            f"margin = {margin:+.4f} K ({status})"
        )

    undersized_thickness = 0.8 * result.thickness
    oversized_thickness = 1.2 * result.thickness
    t_back_under = backface_temperature(t_hot, heat_flux, undersized_thickness, material.conductivity)
    t_back_over = backface_temperature(t_hot, heat_flux, oversized_thickness, material.conductivity)
    assert t_back_under > t_back_max, "undersized case should exceed the backface limit"
    assert t_back_over <= t_back_max, "oversized case should have non-negative margin"
    print()
    print("Sanity checks passed: undersized case exceeds T_back,max; oversized case has positive margin.")


if __name__ == "__main__":
    main()
