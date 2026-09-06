"""Analytical / behavioral verification tests for the transient conduction
model.

Section letters correspond to the Milestone 2 verification plan in the
project brief / README.
"""

import math

import pytest

from tps_trade import (
    TPSMaterial,
    HeatingPulse,
    square_pulse,
    max_stable_time_step,
    solve_transient_conduction,
    size_thickness_transient,
)


@pytest.fixture
def material():
    return TPSMaterial(
        name="Illustrative Reusable TPS",
        density=350.0,
        conductivity=0.06,
        max_service_temperature=2000.0,
        specific_heat=1050.0,
    )


@pytest.fixture
def material_no_cp():
    return TPSMaterial(
        name="Illustrative Reusable TPS (no cp)",
        density=350.0,
        conductivity=0.06,
        max_service_temperature=2000.0,
    )


# --- A. Thermal diffusivity --------------------------------------------------


def test_thermal_diffusivity_hand_calc(material):
    expected = material.conductivity / (material.density * material.specific_heat)
    assert material.thermal_diffusivity() == pytest.approx(expected)
    assert material.thermal_diffusivity() == pytest.approx(0.06 / (350.0 * 1050.0))


def test_thermal_diffusivity_requires_specific_heat(material_no_cp):
    with pytest.raises(ValueError):
        material_no_cp.thermal_diffusivity()


# --- B. Uniform-temperature equilibrium -------------------------------------


def test_uniform_initial_stays_uniform_when_hot_equals_initial(material):
    thickness = 0.03
    n_nodes = 21
    alpha = material.thermal_diffusivity()
    dx = thickness / (n_nodes - 1)
    dt = max_stable_time_step(alpha, dx, fourier_limit=0.4)

    result = solve_transient_conduction(
        material,
        thickness=thickness,
        t_initial=300.0,
        hot_side_temperature=300.0,
        total_time=50.0,
        dt=dt,
        n_nodes=n_nodes,
        backface="insulated",
    )

    for row in result.temperature_field:
        for temperature in row:
            assert temperature == pytest.approx(300.0, abs=1e-9)


# --- C. Stability rejection ---------------------------------------------------


def test_rejects_fourier_number_above_half(material):
    thickness = 0.03
    n_nodes = 21
    alpha = material.thermal_diffusivity()
    dx = thickness / (n_nodes - 1)
    unstable_dt = max_stable_time_step(alpha, dx, fourier_limit=0.9)

    with pytest.raises(ValueError, match="[Ss]tability"):
        solve_transient_conduction(
            material,
            thickness=thickness,
            t_initial=300.0,
            hot_side_temperature=1200.0,
            total_time=10.0,
            dt=unstable_dt,
            n_nodes=n_nodes,
        )


def test_accepts_fourier_number_at_half(material):
    thickness = 0.03
    n_nodes = 21
    alpha = material.thermal_diffusivity()
    dx = thickness / (n_nodes - 1)
    stable_dt = max_stable_time_step(alpha, dx, fourier_limit=0.5)

    result = solve_transient_conduction(
        material,
        thickness=thickness,
        t_initial=300.0,
        hot_side_temperature=1200.0,
        total_time=10.0,
        dt=stable_dt,
        n_nodes=n_nodes,
    )
    assert result.fourier_number == pytest.approx(0.5, rel=1e-6)


# --- D. Constant boundary behavior --------------------------------------------


def test_constant_hot_boundary_monotonic_and_bounded(material):
    thickness = 0.03
    n_nodes = 21
    alpha = material.thermal_diffusivity()
    dx = thickness / (n_nodes - 1)
    dt = max_stable_time_step(alpha, dx, fourier_limit=0.4)
    t_hot = 1200.0

    result = solve_transient_conduction(
        material,
        thickness=thickness,
        t_initial=300.0,
        hot_side_temperature=t_hot,
        total_time=300.0,
        dt=dt,
        n_nodes=n_nodes,
        backface="insulated",
    )

    # index 0 is the t=0 initial condition (uniform T_initial); the Dirichlet
    # hot-side BC is applied for every step thereafter.
    assert all(h == pytest.approx(t_hot) for h in result.hot_side_history[1:])
    assert all(b <= t_hot + 1e-6 for b in result.backface_history)
    assert all(
        result.backface_history[i] <= result.backface_history[i + 1] + 1e-9
        for i in range(len(result.backface_history) - 1)
    )


# --- E. Short-time penetration -------------------------------------------------


def test_short_heating_leaves_thick_backface_near_initial(material):
    thickness = 0.05
    n_nodes = 41
    alpha = material.thermal_diffusivity()
    dx = thickness / (n_nodes - 1)
    dt = max_stable_time_step(alpha, dx, fourier_limit=0.4)
    t_initial = 300.0

    result = solve_transient_conduction(
        material,
        thickness=thickness,
        t_initial=t_initial,
        hot_side_temperature=1500.0,
        total_time=5.0,
        dt=dt,
        n_nodes=n_nodes,
        backface="insulated",
    )
    assert result.peak_backface_temperature == pytest.approx(t_initial, abs=0.5)


# --- F. Thickness effect -------------------------------------------------------


def test_greater_thickness_reduces_peak_backface(material):
    n_nodes = 21
    alpha = material.thermal_diffusivity()
    pulse = square_pulse(t_initial=300.0, t_hot=1200.0, tau_heat=60.0)

    def peak_for(thickness):
        dx = thickness / (n_nodes - 1)
        dt = max_stable_time_step(alpha, dx, fourier_limit=0.4)
        return solve_transient_conduction(
            material,
            thickness=thickness,
            t_initial=300.0,
            hot_side_temperature=pulse,
            total_time=300.0,
            dt=dt,
            n_nodes=n_nodes,
        ).peak_backface_temperature

    assert peak_for(0.02) < peak_for(0.01)


# --- G. Conductivity effect ----------------------------------------------------


def test_higher_conductivity_increases_peak_backface_for_finite_pulse():
    n_nodes = 21
    thickness = 0.01
    pulse = square_pulse(t_initial=300.0, t_hot=1200.0, tau_heat=60.0)

    def peak_for(conductivity):
        mat = TPSMaterial(
            "variant", density=350.0, conductivity=conductivity,
            max_service_temperature=2000.0, specific_heat=1050.0,
        )
        alpha = mat.thermal_diffusivity()
        dx = thickness / (n_nodes - 1)
        dt = max_stable_time_step(alpha, dx, fourier_limit=0.4)
        return solve_transient_conduction(
            mat, thickness=thickness, t_initial=300.0, hot_side_temperature=pulse,
            total_time=300.0, dt=dt, n_nodes=n_nodes,
        ).peak_backface_temperature

    assert peak_for(0.15) > peak_for(0.06)


# --- H. Heat-capacity effect ----------------------------------------------------


def test_higher_specific_heat_reduces_transient_rise():
    n_nodes = 21
    thickness = 0.01
    pulse = square_pulse(t_initial=300.0, t_hot=1200.0, tau_heat=60.0)

    def peak_for(cp):
        mat = TPSMaterial(
            "variant", density=350.0, conductivity=0.06,
            max_service_temperature=2000.0, specific_heat=cp,
        )
        alpha = mat.thermal_diffusivity()
        dx = thickness / (n_nodes - 1)
        dt = max_stable_time_step(alpha, dx, fourier_limit=0.4)
        return solve_transient_conduction(
            mat, thickness=thickness, t_initial=300.0, hot_side_temperature=pulse,
            total_time=300.0, dt=dt, n_nodes=n_nodes,
        ).peak_backface_temperature

    assert peak_for(2100.0) < peak_for(1050.0)


# --- I. Density effect ----------------------------------------------------------


def test_higher_density_reduces_transient_rise():
    n_nodes = 21
    thickness = 0.01
    pulse = square_pulse(t_initial=300.0, t_hot=1200.0, tau_heat=60.0)

    def peak_for(density):
        mat = TPSMaterial(
            "variant", density=density, conductivity=0.06,
            max_service_temperature=2000.0, specific_heat=1050.0,
        )
        alpha = mat.thermal_diffusivity()
        dx = thickness / (n_nodes - 1)
        dt = max_stable_time_step(alpha, dx, fourier_limit=0.4)
        return solve_transient_conduction(
            mat, thickness=thickness, t_initial=300.0, hot_side_temperature=pulse,
            total_time=300.0, dt=dt, n_nodes=n_nodes,
        ).peak_backface_temperature

    assert peak_for(700.0) < peak_for(350.0)


# --- J. Energy/maximum sanity ----------------------------------------------------


def test_temperatures_remain_bounded_by_initial_and_hot(material):
    thickness = 0.02
    n_nodes = 21
    alpha = material.thermal_diffusivity()
    dx = thickness / (n_nodes - 1)
    dt = max_stable_time_step(alpha, dx, fourier_limit=0.4)
    t_initial, t_hot = 300.0, 1200.0

    result = solve_transient_conduction(
        material, thickness=thickness, t_initial=t_initial, hot_side_temperature=t_hot,
        total_time=200.0, dt=dt, n_nodes=n_nodes, backface="insulated",
    )
    for row in result.temperature_field:
        for temperature in row:
            assert t_initial - 1e-6 <= temperature <= t_hot + 1e-6


# --- K. Backface insulated condition --------------------------------------------


def test_insulated_backface_zero_gradient_numerically(material):
    thickness = 0.02
    n_nodes = 21
    alpha = material.thermal_diffusivity()
    dx = thickness / (n_nodes - 1)
    dt = max_stable_time_step(alpha, dx, fourier_limit=0.4)

    result = solve_transient_conduction(
        material, thickness=thickness, t_initial=300.0, hot_side_temperature=1200.0,
        total_time=200.0, dt=dt, n_nodes=n_nodes, backface="insulated",
    )
    final_row = result.temperature_field[-1]
    # First-order one-sided gradient at the backface should be small relative
    # to the gradient near the hot side (the zero-gradient BC is exact in the
    # discrete update; this checks it is consistent with the resulting field).
    gradient_back = abs(final_row[-1] - final_row[-2]) / dx
    gradient_front = abs(final_row[1] - final_row[0]) / dx
    assert gradient_back < 0.1 * gradient_front


# --- L. Pulse duration effect -----------------------------------------------------


def test_longer_pulse_increases_peak_backface(material):
    thickness = 0.01
    n_nodes = 21
    alpha = material.thermal_diffusivity()
    dx = thickness / (n_nodes - 1)
    dt = max_stable_time_step(alpha, dx, fourier_limit=0.4)

    short_pulse = square_pulse(t_initial=300.0, t_hot=1200.0, tau_heat=30.0)
    long_pulse = square_pulse(t_initial=300.0, t_hot=1200.0, tau_heat=150.0)

    peak_short = solve_transient_conduction(
        material, thickness=thickness, t_initial=300.0, hot_side_temperature=short_pulse,
        total_time=300.0, dt=dt, n_nodes=n_nodes,
    ).peak_backface_temperature
    peak_long = solve_transient_conduction(
        material, thickness=thickness, t_initial=300.0, hot_side_temperature=long_pulse,
        total_time=300.0, dt=dt, n_nodes=n_nodes,
    ).peak_backface_temperature

    assert peak_long > peak_short


# --- M. Thickness-sizing boundary --------------------------------------------------


@pytest.fixture
def sizing_setup(material):
    n_nodes = 21
    alpha = material.thermal_diffusivity()
    t_lo, t_hi = 0.005, 0.02
    dx_min = t_lo / (n_nodes - 1)
    dt = max_stable_time_step(alpha, dx_min, fourier_limit=0.4)
    pulse = square_pulse(t_initial=300.0, t_hot=1200.0, tau_heat=60.0)
    return dict(
        material=material, heating_history=pulse, total_time=300.0, t_initial=300.0,
        t_back_max=400.0, thickness_bounds=(t_lo, t_hi), dt=dt, n_nodes=n_nodes,
    )


def test_sizing_meets_backface_limit_within_tolerance(sizing_setup):
    result = size_thickness_transient(**sizing_setup)
    assert result.converged
    assert result.peak_backface_temperature <= sizing_setup["t_back_max"] + 1.0


# --- N. Over-thickness ---------------------------------------------------------------


def test_over_thickness_gives_positive_margin(material, sizing_setup):
    result = size_thickness_transient(**sizing_setup)
    n_nodes = sizing_setup["n_nodes"]
    alpha = material.thermal_diffusivity()
    oversized = result.thickness * 1.3
    dx = oversized / (n_nodes - 1)
    dt = max_stable_time_step(alpha, dx, fourier_limit=0.4)

    peak_over = solve_transient_conduction(
        material, thickness=oversized, t_initial=300.0,
        hot_side_temperature=sizing_setup["heating_history"], total_time=300.0,
        dt=dt, n_nodes=n_nodes,
    ).peak_backface_temperature

    assert (sizing_setup["t_back_max"] - peak_over) > 0.0


# --- O. Under-thickness --------------------------------------------------------------


def test_under_thickness_reduces_or_violates_margin(material, sizing_setup):
    result = size_thickness_transient(**sizing_setup)
    n_nodes = sizing_setup["n_nodes"]
    alpha = material.thermal_diffusivity()
    undersized = result.thickness * 0.7
    dx = undersized / (n_nodes - 1)
    dt = max_stable_time_step(alpha, dx, fourier_limit=0.4)

    peak_under = solve_transient_conduction(
        material, thickness=undersized, t_initial=300.0,
        hot_side_temperature=sizing_setup["heating_history"], total_time=300.0,
        dt=dt, n_nodes=n_nodes,
    ).peak_backface_temperature

    margin_under = sizing_setup["t_back_max"] - peak_under
    assert margin_under < result.margin_temperature


# --- P. Bisection determinism -----------------------------------------------------


def test_sizing_is_deterministic(sizing_setup):
    result1 = size_thickness_transient(**sizing_setup)
    result2 = size_thickness_transient(**sizing_setup)
    assert result1.thickness == result2.thickness
    assert result1.iterations == result2.iterations
    assert result1.peak_backface_temperature == result2.peak_backface_temperature


def test_sizing_raises_when_infeasible(material):
    n_nodes = 21
    alpha = material.thermal_diffusivity()
    t_lo, t_hi = 0.001, 0.003
    dx_min = t_lo / (n_nodes - 1)
    dt = max_stable_time_step(alpha, dx_min, fourier_limit=0.4)
    pulse = square_pulse(t_initial=300.0, t_hot=1200.0, tau_heat=60.0)

    with pytest.raises(ValueError, match="[Nn]o feasible thickness"):
        size_thickness_transient(
            material, pulse, total_time=300.0, t_initial=300.0, t_back_max=310.0,
            thickness_bounds=(t_lo, t_hi), dt=dt, n_nodes=n_nodes,
        )


# --- Q. Missing cp -------------------------------------------------------------------


def test_transient_solver_rejects_material_without_specific_heat(material_no_cp):
    with pytest.raises(ValueError):
        solve_transient_conduction(
            material_no_cp, thickness=0.02, t_initial=300.0, hot_side_temperature=1200.0,
            total_time=10.0, dt=0.1, n_nodes=21,
        )


# --- R. Invalid inputs -----------------------------------------------------------------


def test_rejects_nonpositive_thickness(material):
    with pytest.raises(ValueError):
        solve_transient_conduction(
            material, thickness=0.0, t_initial=300.0, hot_side_temperature=1200.0,
            total_time=10.0, dt=0.1, n_nodes=21,
        )
    with pytest.raises(ValueError):
        solve_transient_conduction(
            material, thickness=-0.01, t_initial=300.0, hot_side_temperature=1200.0,
            total_time=10.0, dt=0.1, n_nodes=21,
        )


def test_rejects_too_few_nodes(material):
    with pytest.raises(ValueError):
        solve_transient_conduction(
            material, thickness=0.02, t_initial=300.0, hot_side_temperature=1200.0,
            total_time=10.0, dt=0.1, n_nodes=2,
        )


def test_rejects_nonpositive_dt(material):
    with pytest.raises(ValueError):
        solve_transient_conduction(
            material, thickness=0.02, t_initial=300.0, hot_side_temperature=1200.0,
            total_time=10.0, dt=0.0, n_nodes=21,
        )
    with pytest.raises(ValueError):
        solve_transient_conduction(
            material, thickness=0.02, t_initial=300.0, hot_side_temperature=1200.0,
            total_time=10.0, dt=-1.0, n_nodes=21,
        )


def test_rejects_nonpositive_total_time(material):
    with pytest.raises(ValueError):
        solve_transient_conduction(
            material, thickness=0.02, t_initial=300.0, hot_side_temperature=1200.0,
            total_time=0.0, dt=0.1, n_nodes=21,
        )


def test_rejects_invalid_temperatures(material):
    with pytest.raises(ValueError):
        solve_transient_conduction(
            material, thickness=0.02, t_initial=-300.0, hot_side_temperature=1200.0,
            total_time=10.0, dt=0.1, n_nodes=21,
        )
    with pytest.raises(ValueError):
        solve_transient_conduction(
            material, thickness=0.02, t_initial=300.0, hot_side_temperature=0.0,
            total_time=10.0, dt=0.1, n_nodes=21,
        )


def test_rejects_nan_and_inf(material):
    with pytest.raises(ValueError):
        solve_transient_conduction(
            material, thickness=float("nan"), t_initial=300.0, hot_side_temperature=1200.0,
            total_time=10.0, dt=0.1, n_nodes=21,
        )
    with pytest.raises(ValueError):
        solve_transient_conduction(
            material, thickness=0.02, t_initial=300.0, hot_side_temperature=1200.0,
            total_time=float("inf"), dt=0.1, n_nodes=21,
        )


def test_rejects_mixed_backface_semantics(material):
    with pytest.raises(ValueError):
        solve_transient_conduction(
            material, thickness=0.02, t_initial=300.0, hot_side_temperature=1200.0,
            total_time=10.0, dt=0.1, n_nodes=21, backface="insulated",
            backface_temperature=300.0,
        )
    with pytest.raises(ValueError):
        solve_transient_conduction(
            material, thickness=0.02, t_initial=300.0, hot_side_temperature=1200.0,
            total_time=10.0, dt=0.1, n_nodes=21, backface="prescribed",
        )


def test_rejects_unknown_backface_condition(material):
    with pytest.raises(ValueError):
        solve_transient_conduction(
            material, thickness=0.02, t_initial=300.0, hot_side_temperature=1200.0,
            total_time=10.0, dt=0.1, n_nodes=21, backface="something_else",
        )


# --- Prescribed backface option (secondary boundary condition) -----------------


def test_prescribed_backface_matches_history(material):
    thickness = 0.02
    n_nodes = 21
    alpha = material.thermal_diffusivity()
    dx = thickness / (n_nodes - 1)
    dt = max_stable_time_step(alpha, dx, fourier_limit=0.4)

    result = solve_transient_conduction(
        material, thickness=thickness, t_initial=300.0, hot_side_temperature=1200.0,
        total_time=50.0, dt=dt, n_nodes=n_nodes, backface="prescribed",
        backface_temperature=300.0,
    )
    assert all(b == pytest.approx(300.0) for b in result.backface_history)


# --- Analytical reference: semi-infinite step-temperature erf solution ---------


def test_matches_semi_infinite_erf_solution_before_backface_effects(material):
    """Compare the FD solution against the classical semi-infinite,
    step-surface-temperature analytical solution:

        (T(x,t) - T_hot) / (T_initial - T_hot) = erf(x / (2*sqrt(alpha*t)))

    Valid only while the diffusion penetration depth is small relative to
    the slab thickness, i.e. the backface has not yet materially affected
    the interior point checked here.
    """
    thickness = 0.05  # thick relative to the diffusion depth reached below
    n_nodes = 101
    alpha = material.thermal_diffusivity()
    dx = thickness / (n_nodes - 1)
    dt = max_stable_time_step(alpha, dx, fourier_limit=0.4)
    total_time = 60.0
    t_initial, t_hot = 300.0, 1200.0

    penetration_depth = math.sqrt(4.0 * alpha * total_time)
    assert penetration_depth < 0.2 * thickness  # semi-infinite assumption check

    result = solve_transient_conduction(
        material, thickness=thickness, t_initial=t_initial, hot_side_temperature=t_hot,
        total_time=total_time, dt=dt, n_nodes=n_nodes, backface="insulated",
    )

    x_check = 0.01
    index = round(x_check / dx)
    t_numeric = result.temperature_field[-1][index]

    eta = x_check / (2.0 * math.sqrt(alpha * total_time))
    t_analytical = t_hot + (t_initial - t_hot) * math.erf(eta)

    assert t_numeric == pytest.approx(t_analytical, abs=2.0)


# --- Grid-convergence awareness --------------------------------------------------


def test_grid_refinement_converges_toward_a_stable_peak_value(material):
    """Refine spatial resolution at a fixed time step (small enough to stay
    stable at the finest grid), and check that the change in peak backface
    temperature shrinks as the grid is refined -- i.e. the result is
    converging, not just drifting arbitrarily with resolution.
    """
    thickness = 0.01
    pulse = square_pulse(t_initial=300.0, t_hot=1200.0, tau_heat=60.0)
    alpha = material.thermal_diffusivity()

    finest_n_nodes = 41
    dx_finest = thickness / (finest_n_nodes - 1)
    dt = max_stable_time_step(alpha, dx_finest, fourier_limit=0.4)

    def peak_for(n_nodes):
        return solve_transient_conduction(
            material, thickness=thickness, t_initial=300.0, hot_side_temperature=pulse,
            total_time=300.0, dt=dt, n_nodes=n_nodes,
        ).peak_backface_temperature

    peak_coarse = peak_for(11)
    peak_medium = peak_for(21)
    peak_fine = peak_for(finest_n_nodes)

    # Refinement should reduce the change in the result (converging), not
    # necessarily hit an exact fixed point at these modest resolutions.
    assert abs(peak_fine - peak_medium) < abs(peak_medium - peak_coarse)
