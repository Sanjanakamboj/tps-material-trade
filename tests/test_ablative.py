"""Analytical verification tests for the first-order ablative sizing model.

Section letters correspond to the Milestone 3 verification plan in the
project brief / README.
"""

import math

import pytest

from tps_trade import (
    AblativeMaterial,
    HeatFluxSegment,
    total_heat_load_constant,
    total_heat_load_piecewise,
    total_heat_load_sampled,
    integrated_heat_load,
    consumed_areal_mass,
    recession_depth,
    size_ablative_thickness,
    evaluate_trial_thickness,
)


@pytest.fixture
def material():
    return AblativeMaterial(
        name="Illustrative Ablative TPS",
        density=1400.0,
        effective_heat_of_ablation=1.0e7,
    )


# --- A. Constant heat-flux heat load -----------------------------------------


def test_constant_heat_load_exact():
    q, tau = 500_000.0, 60.0
    assert total_heat_load_constant(q, tau) == pytest.approx(q * tau)
    assert total_heat_load_constant(q, tau) == pytest.approx(30_000_000.0)


# --- B. Piecewise heat-load hand calculation ---------------------------------


def test_piecewise_heat_load_hand_calc():
    segments = [
        HeatFluxSegment(heat_flux=1_000_000.0, duration=10.0),
        HeatFluxSegment(heat_flux=500_000.0, duration=20.0),
        HeatFluxSegment(heat_flux=0.0, duration=5.0),
    ]
    expected = 1_000_000.0 * 10.0 + 500_000.0 * 20.0 + 0.0 * 5.0
    assert total_heat_load_piecewise(segments) == pytest.approx(expected)
    assert integrated_heat_load(segments) == pytest.approx(expected)


def test_sampled_heat_load_trapezoidal_hand_calc():
    times = [0.0, 10.0, 20.0]
    flux = [0.0, 1000.0, 0.0]
    # trapezoid: 0.5*(0+1000)*10 + 0.5*(1000+0)*10 = 5000 + 5000 = 10000
    assert total_heat_load_sampled(times, flux) == pytest.approx(10_000.0)
    assert integrated_heat_load((times, flux)) == pytest.approx(10_000.0)


# --- C. Consumed areal mass ---------------------------------------------------


def test_consumed_areal_mass_identity():
    q_total, h_eff = 3.0e7, 1.0e7
    assert consumed_areal_mass(q_total, h_eff) == pytest.approx(q_total / h_eff)
    assert consumed_areal_mass(q_total, h_eff) == pytest.approx(3.0)


# --- D. Recession depth --------------------------------------------------------


def test_recession_depth_identity():
    q_total, rho, h_eff = 3.0e7, 1400.0, 1.0e7
    delta = recession_depth(q_total, rho, h_eff)
    assert delta == pytest.approx(q_total / (rho * h_eff))
    assert delta == pytest.approx(3.0 / 1400.0)


# --- E. Density scaling ---------------------------------------------------------


def test_recession_depth_scales_inversely_with_density():
    q_total, h_eff = 3.0e7, 1.0e7
    delta_1 = recession_depth(q_total, 1000.0, h_eff)
    delta_2 = recession_depth(q_total, 2000.0, h_eff)
    assert delta_2 == pytest.approx(delta_1 / 2.0)


# --- F. Heat-of-ablation scaling -------------------------------------------------


def test_recession_depth_scales_inversely_with_heat_of_ablation():
    q_total, rho = 3.0e7, 1400.0
    delta_1 = recession_depth(q_total, rho, 1.0e7)
    delta_2 = recession_depth(q_total, rho, 2.0e7)
    assert delta_2 == pytest.approx(delta_1 / 2.0)


# --- G. Heat-load scaling --------------------------------------------------------


def test_doubling_heat_load_doubles_consumed_mass_and_recession(material):
    q1, q2 = 2.0e7, 4.0e7
    m1 = consumed_areal_mass(q1, material.effective_heat_of_ablation)
    m2 = consumed_areal_mass(q2, material.effective_heat_of_ablation)
    assert m2 == pytest.approx(2.0 * m1)

    d1 = recession_depth(q1, material.density, material.effective_heat_of_ablation)
    d2 = recession_depth(q2, material.density, material.effective_heat_of_ablation)
    assert d2 == pytest.approx(2.0 * d1)


# --- H. Initial thickness identity -----------------------------------------------


def test_initial_thickness_identity(material):
    result = size_ablative_thickness(
        material, total_heat_load=2.5e7, retained_thickness=0.005
    )
    assert result.initial_thickness == pytest.approx(result.recession_depth + result.retained_thickness)


# --- I. Mass decomposition ---------------------------------------------------------


def test_mass_decomposition(material):
    result = size_ablative_thickness(
        material, total_heat_load=2.5e7, retained_thickness=0.005
    )
    assert result.initial_areal_mass == pytest.approx(
        result.remaining_areal_mass + result.consumed_areal_mass
    )


# --- J. Trial-thickness exact boundary -------------------------------------------


def test_trial_thickness_exact_boundary_margin_zero(material):
    total_heat_load = 2.5e7
    retained_thickness = 0.005
    sizing = size_ablative_thickness(material, total_heat_load, retained_thickness)

    trial = evaluate_trial_thickness(
        material, sizing.initial_thickness, total_heat_load, retained_thickness
    )
    assert trial.margin_thickness == pytest.approx(0.0, abs=1e-12)
    assert trial.passed


# --- K. Over-thickness -------------------------------------------------------------


def test_over_thickness_gives_positive_margin(material):
    total_heat_load = 2.5e7
    retained_thickness = 0.005
    sizing = size_ablative_thickness(material, total_heat_load, retained_thickness)

    oversized = 1.2 * sizing.initial_thickness
    trial = evaluate_trial_thickness(material, oversized, total_heat_load, retained_thickness)
    assert trial.margin_thickness > 0.0
    assert trial.passed


# --- L. Under-thickness --------------------------------------------------------------


def test_under_thickness_gives_negative_margin_and_fails(material):
    total_heat_load = 2.5e7
    retained_thickness = 0.005
    sizing = size_ablative_thickness(material, total_heat_load, retained_thickness)

    undersized = 0.8 * sizing.initial_thickness
    trial = evaluate_trial_thickness(material, undersized, total_heat_load, retained_thickness)
    assert trial.margin_thickness < 0.0
    assert not trial.passed


# --- M. Zero heat load ----------------------------------------------------------------


def test_zero_heat_load_gives_zero_recession(material):
    retained_thickness = 0.004
    result = size_ablative_thickness(material, total_heat_load=0.0, retained_thickness=retained_thickness)
    assert result.recession_depth == 0.0
    assert result.consumed_areal_mass == 0.0
    assert result.initial_thickness == pytest.approx(retained_thickness)


# --- N. Invalid material inputs ------------------------------------------------------


@pytest.mark.parametrize("bad_density", [0.0, -1.0, float("nan"), float("inf")])
def test_rejects_invalid_density(bad_density):
    with pytest.raises(ValueError):
        AblativeMaterial(name="bad", density=bad_density, effective_heat_of_ablation=1.0e7)


@pytest.mark.parametrize("bad_h_eff", [0.0, -1.0, float("nan"), float("inf")])
def test_rejects_invalid_heat_of_ablation(bad_h_eff):
    with pytest.raises(ValueError):
        AblativeMaterial(name="bad", density=1400.0, effective_heat_of_ablation=bad_h_eff)


# --- O. Invalid heat-history inputs --------------------------------------------------


def test_rejects_negative_duration():
    with pytest.raises(ValueError):
        HeatFluxSegment(heat_flux=1000.0, duration=-1.0)
    with pytest.raises(ValueError):
        HeatFluxSegment(heat_flux=1000.0, duration=0.0)


def test_rejects_non_monotonic_times():
    with pytest.raises(ValueError):
        total_heat_load_sampled([0.0, 5.0, 5.0], [0.0, 100.0, 200.0])
    with pytest.raises(ValueError):
        total_heat_load_sampled([0.0, 10.0, 5.0], [0.0, 100.0, 200.0])


def test_rejects_nan_and_inf_in_history():
    with pytest.raises(ValueError):
        total_heat_load_sampled([0.0, float("nan")], [0.0, 100.0])
    with pytest.raises(ValueError):
        total_heat_load_sampled([0.0, 10.0], [0.0, float("inf")])
    with pytest.raises(ValueError):
        HeatFluxSegment(heat_flux=float("nan"), duration=10.0)


def test_rejects_negative_heat_flux():
    with pytest.raises(ValueError):
        HeatFluxSegment(heat_flux=-100.0, duration=10.0)
    with pytest.raises(ValueError):
        total_heat_load_sampled([0.0, 10.0], [0.0, -100.0])


def test_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        total_heat_load_sampled([0.0, 10.0, 20.0], [0.0, 100.0])


def test_rejects_too_few_samples():
    with pytest.raises(ValueError):
        total_heat_load_sampled([0.0], [0.0])


def test_rejects_empty_segments():
    with pytest.raises(ValueError):
        total_heat_load_piecewise([])


# --- P. Numerical integration determinism ----------------------------------------------


def test_sampled_integration_is_deterministic():
    times = [0.0, 5.0, 15.0, 30.0]
    flux = [0.0, 800_000.0, 500_000.0, 0.0]
    result_1 = total_heat_load_sampled(times, flux)
    result_2 = total_heat_load_sampled(times, flux)
    assert result_1 == result_2


# --- Additional: recession margin (max_recession) ---------------------------------------


def test_recession_margin_reported_when_max_recession_given(material):
    result = size_ablative_thickness(
        material, total_heat_load=2.5e7, retained_thickness=0.005, max_recession=0.01
    )
    assert result.recession_margin == pytest.approx(0.01 - result.recession_depth)


def test_recession_margin_is_none_by_default(material):
    result = size_ablative_thickness(material, total_heat_load=2.5e7, retained_thickness=0.005)
    assert result.recession_margin is None


# --- Invalid sizing inputs ---------------------------------------------------------------


def test_size_ablative_thickness_rejects_negative_heat_load(material):
    with pytest.raises(ValueError):
        size_ablative_thickness(material, total_heat_load=-1.0, retained_thickness=0.005)


def test_size_ablative_thickness_rejects_negative_retained_thickness(material):
    with pytest.raises(ValueError):
        size_ablative_thickness(material, total_heat_load=1.0e7, retained_thickness=-0.001)


def test_evaluate_trial_thickness_rejects_nonpositive_trial_thickness(material):
    with pytest.raises(ValueError):
        evaluate_trial_thickness(material, trial_thickness=0.0, total_heat_load=1.0e7, retained_thickness=0.005)
    with pytest.raises(ValueError):
        evaluate_trial_thickness(material, trial_thickness=-0.01, total_heat_load=1.0e7, retained_thickness=0.005)


def test_integrated_heat_load_rejects_unrecognized_history():
    with pytest.raises(TypeError):
        integrated_heat_load("not a history")
    with pytest.raises(TypeError):
        integrated_heat_load([])
