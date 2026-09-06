"""Milestone 2 representative transient heating study.

Uses the same illustrative-reusable-TPS material concept introduced in
Milestone 1 (examples/sanity_case.py), now with a specific heat (cp) added
so it can be used in the transient model, and exposes it to a finite-
duration square hot-side temperature pulse rather than an indefinitely
sustained steady boundary condition.

Compares:
  A. the Milestone 1 STEADY-sized thickness (assumes the hot-side condition
     is sustained indefinitely), against
  B. the Milestone 2 TRANSIENT-sized thickness (accounts for the pulse
     actually being finite-duration).

Run with:

    python examples/transient_heating_study.py

NOTE: This is a deliberately simplified, illustrative case -- see the
project README and tps_trade.transient module docstring for the physical
caveats of prescribing a hot-side TEMPERATURE history directly (no surface
energy balance, no ablation/pyrolysis, constant properties).
"""

from tps_trade import (
    TPSMaterial,
    size_thickness_for_backface_limit,
    square_pulse,
    max_stable_time_step,
    solve_transient_conduction,
    size_thickness_transient,
)


def main() -> None:
    # Same illustrative reusable-TPS-style rigid tile concept as Milestone 1,
    # now with an illustrative specific heat added for transient analysis.
    material = TPSMaterial(
        name="Illustrative Reusable TPS Tile (rigid ceramic insulator, illustrative properties)",
        density=350.0,  # kg/m^3
        conductivity=0.06,  # W/(m*K)
        max_service_temperature=1650.0,  # K
        specific_heat=1050.0,  # J/(kg*K)
    )
    alpha = material.thermal_diffusivity()

    t_initial = 300.0  # K
    t_hot = 1400.0  # K, hot-side temperature during the pulse
    tau_heat = 120.0  # s, pulse duration
    total_time = 600.0  # s, total simulated duration (well past the pulse)
    t_back_max = 450.0  # K, backface temperature limit

    pulse = square_pulse(t_initial=t_initial, t_hot=t_hot, tau_heat=tau_heat)

    print("=== Milestone 2 representative transient heating study ===")
    print(f"Material:                 {material.name}")
    print(f"  density (rho):          {material.density:.1f} kg/m^3")
    print(f"  conductivity (k):       {material.conductivity:.4f} W/(m*K)")
    print(f"  specific heat (cp):     {material.specific_heat:.1f} J/(kg*K)")
    print(f"  diffusivity (alpha):    {alpha:.3e} m^2/s")
    print(f"Initial temperature:      {t_initial:.1f} K")
    print(f"Hot-side temperature:     {t_hot:.1f} K")
    print(f"Pulse duration (tau):     {tau_heat:.1f} s")
    print(f"Backface limit:           {t_back_max:.1f} K")

    # --- A. Milestone 1 steady-sized thickness --------------------------
    # Uses the same T_hot / T_back_max, and the illustrative steady heat
    # flux from the Milestone 1 sanity case, purely as a reference point --
    # NOT a claim that this heat flux corresponds physically to the pulse
    # below.
    steady_heat_flux = 3000.0  # W/m^2, illustrative (Milestone 1 sanity case)
    steady = size_thickness_for_backface_limit(
        material, t_hot=t_hot, heat_flux=steady_heat_flux, t_back_max=t_back_max
    )
    print()
    print("--- A. Milestone 1 steady-state sizing (sustained indefinitely) ---")
    print(f"Prescribed heat flux:     {steady_heat_flux:.1f} W/m^2")
    print(f"Steady-sized thickness:   {steady.thickness * 100:.3f} cm")
    print(f"Areal mass:               {steady.areal_mass:.2f} kg/m^2")

    # --- B. Milestone 2 transient-sized thickness ------------------------
    n_nodes = 21
    thickness_bounds = (0.002, 0.03)  # m, search bracket
    dx_min = thickness_bounds[0] / (n_nodes - 1)
    dt = max_stable_time_step(alpha, dx_min, fourier_limit=0.4)

    sizing = size_thickness_transient(
        material,
        heating_history=pulse,
        total_time=total_time,
        t_initial=t_initial,
        t_back_max=t_back_max,
        thickness_bounds=thickness_bounds,
        dt=dt,
        n_nodes=n_nodes,
    )

    print()
    print("--- B. Milestone 2 transient sizing (finite-duration pulse) ---")
    print(f"Spatial nodes:            {n_nodes}")
    print(f"Time step (dt):           {dt:.5f} s")
    print(f"Search bracket:           {thickness_bounds[0]*100:.2f}-{thickness_bounds[1]*100:.2f} cm")
    print(f"Bisection iterations:     {sizing.iterations} ({sizing.status})")
    print(f"Transient-sized thickness:{sizing.thickness * 100:.3f} cm")
    print(f"Peak backface temp:       {sizing.peak_backface_temperature:.2f} K")
    print(f"Temperature margin:       {sizing.margin_temperature:+.4f} K")
    print(f"Areal mass:               {sizing.areal_mass:.2f} kg/m^2")

    # Full transient trace at the sized thickness, for reporting Fo and the
    # time of peak backface temperature.
    dx = sizing.thickness / (n_nodes - 1)
    dt_report = max_stable_time_step(alpha, dx, fourier_limit=0.4)
    result = solve_transient_conduction(
        material, sizing.thickness, t_initial, pulse, total_time, dt_report, n_nodes
    )
    print(f"Fourier number (Fo):      {result.fourier_number:.3f}")
    print(f"Time of peak T_back:      {result.time_of_peak_backface_temperature:.1f} s")

    print()
    print("--- Comparison: steady- vs transient-sized thickness -----------")
    print(f"Steady-sized:    {steady.thickness * 100:.3f} cm  (assumes indefinite exposure)")
    print(f"Transient-sized: {sizing.thickness * 100:.3f} cm  (accounts for {tau_heat:.0f} s pulse)")
    print(
        "The transient-sized thickness can be thinner than the steady-sized "
        "thickness because the heat pulse here is finite: the backface never "
        "has time to reach the temperature it would eventually reach under "
        "sustained heating, so less insulating material is needed to keep "
        "its PEAK transient temperature under the limit. This is a property "
        "of prescribing a short, finite-duration pulse -- it is NOT a "
        "general statement that transient sizing is always less conservative "
        "than steady sizing (a sufficiently long pulse converges toward the "
        "steady result), and this comparison is illustrative only, not a "
        "real reentry certification load case."
    )


if __name__ == "__main__":
    main()
