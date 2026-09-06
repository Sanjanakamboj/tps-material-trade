"""Analytical verification tests for the steady 1-D conduction sizing model.

Section letters (A, B, C, ...) correspond to the verification plan in the
Milestone 1 project brief / README.
"""

import math

import pytest

from tps_trade import (
    TPSMaterial,
    thermal_resistance,
    thickness_from_resistance,
    backface_temperature,
    heat_flux_from_temperatures,
    areal_mass,
    size_thickness_for_backface_limit,
)


@pytest.fixture
def material():
    return TPSMaterial(
        name="Illustrative Reusable TPS",
        density=350.0,
        conductivity=0.06,
        max_service_temperature=1500.0,
    )


# --- A. Thermal resistance hand calculation ---------------------------------


def test_thermal_resistance_hand_calc():
    t = 0.05  # m
    k = 0.1  # W/(m*K)
    assert thermal_resistance(t, k) == pytest.approx(0.5)


def test_thickness_from_resistance_is_inverse():
    r = 0.5
    k = 0.1
    assert thickness_from_resistance(r, k) == pytest.approx(0.05)


# --- B. Conductive heat-flux identity ---------------------------------------


def test_heat_flux_identity():
    t_hot, t_back, k, t = 1200.0, 500.0, 0.05, 0.02
    q = heat_flux_from_temperatures(t_hot, t_back, t, k)
    assert q == pytest.approx(k * (t_hot - t_back) / t)
    assert q == pytest.approx(1750.0)


# --- C. Backface-temperature calculation ------------------------------------


def test_backface_temperature_calc():
    t_hot, q, t, k = 1200.0, 1750.0, 0.02, 0.05
    t_back = backface_temperature(t_hot, q, t, k)
    assert t_back == pytest.approx(t_hot - q * t / k)
    assert t_back == pytest.approx(500.0)


# --- D. Thickness inversion round-trip --------------------------------------


def test_thickness_inversion_round_trip(material):
    t_hot = 1400.0
    q = 1200.0
    known_thickness = 0.03

    t_back_at_known = backface_temperature(t_hot, q, known_thickness, material.conductivity)

    result = size_thickness_for_backface_limit(
        material, t_hot=t_hot, heat_flux=q, t_back_max=t_back_at_known
    )
    assert result.thickness == pytest.approx(known_thickness)
    assert result.t_back_predicted == pytest.approx(t_back_at_known)


# --- E. Conductivity scaling: t_req proportional to k -----------------------


def test_thickness_scales_linearly_with_conductivity():
    t_hot, q, t_back_max = 1400.0, 8000.0, 500.0

    mat_k1 = TPSMaterial("mat_k1", density=300.0, conductivity=0.05, max_service_temperature=2000.0)
    mat_k2 = TPSMaterial("mat_k2", density=300.0, conductivity=0.10, max_service_temperature=2000.0)

    r1 = size_thickness_for_backface_limit(mat_k1, t_hot, q, t_back_max)
    r2 = size_thickness_for_backface_limit(mat_k2, t_hot, q, t_back_max)

    assert r2.thickness == pytest.approx(2.0 * r1.thickness)


# --- F. Heat-flux scaling: t_req proportional to 1/q'' ----------------------


def test_thickness_scales_inversely_with_heat_flux(material):
    t_hot, t_back_max = 1400.0, 500.0

    r1 = size_thickness_for_backface_limit(material, t_hot, heat_flux=4000.0, t_back_max=t_back_max)
    r2 = size_thickness_for_backface_limit(material, t_hot, heat_flux=8000.0, t_back_max=t_back_max)

    assert r2.thickness == pytest.approx(r1.thickness / 2.0)


# --- G. Areal-mass scaling ---------------------------------------------------


def test_areal_mass_scales_with_density():
    t = 0.02
    assert areal_mass(400.0, t) == pytest.approx(2.0 * areal_mass(200.0, t))


def test_areal_mass_scales_with_thickness():
    rho = 400.0
    assert areal_mass(rho, 0.04) == pytest.approx(2.0 * areal_mass(rho, 0.02))


# --- H. Exact-boundary margin ------------------------------------------------


def test_margin_is_zero_at_sized_thickness(material):
    result = size_thickness_for_backface_limit(
        material, t_hot=1300.0, heat_flux=6000.0, t_back_max=600.0
    )
    assert result.margin_temperature == pytest.approx(0.0, abs=1e-9)


# --- I. Over-thickness --------------------------------------------------------


def test_over_thickness_reduces_backface_temp_and_gives_positive_margin(material):
    result = size_thickness_for_backface_limit(
        material, t_hot=1300.0, heat_flux=6000.0, t_back_max=600.0
    )
    oversized_thickness = 1.2 * result.thickness
    t_back_oversized = backface_temperature(
        result.t_hot, result.heat_flux, oversized_thickness, material.conductivity
    )
    margin_oversized = result.t_back_max - t_back_oversized

    assert t_back_oversized < result.t_back_predicted
    assert margin_oversized > 0.0


# --- J. Under-thickness --------------------------------------------------------


def test_under_thickness_increases_backface_temp_and_gives_negative_margin(material):
    result = size_thickness_for_backface_limit(
        material, t_hot=1300.0, heat_flux=6000.0, t_back_max=600.0
    )
    undersized_thickness = 0.8 * result.thickness
    t_back_undersized = backface_temperature(
        result.t_hot, result.heat_flux, undersized_thickness, material.conductivity
    )
    margin_undersized = result.t_back_max - t_back_undersized

    assert t_back_undersized > result.t_back_predicted
    assert margin_undersized < 0.0


# --- K. Invalid inputs --------------------------------------------------------


def test_rejects_nonpositive_conductivity_in_resistance():
    with pytest.raises(ValueError):
        thermal_resistance(0.02, 0.0)
    with pytest.raises(ValueError):
        thermal_resistance(0.02, -1.0)


def test_rejects_negative_thickness_in_resistance():
    with pytest.raises(ValueError):
        thermal_resistance(-0.01, 0.05)


def test_rejects_nonpositive_heat_flux_for_inverse_sizing(material):
    with pytest.raises(ValueError):
        size_thickness_for_backface_limit(material, t_hot=1300.0, heat_flux=0.0, t_back_max=600.0)
    with pytest.raises(ValueError):
        size_thickness_for_backface_limit(material, t_hot=1300.0, heat_flux=-500.0, t_back_max=600.0)


def test_rejects_nan_and_inf_inputs(material):
    with pytest.raises(ValueError):
        size_thickness_for_backface_limit(material, t_hot=float("nan"), heat_flux=6000.0, t_back_max=600.0)
    with pytest.raises(ValueError):
        size_thickness_for_backface_limit(material, t_hot=1300.0, heat_flux=float("inf"), t_back_max=600.0)
    with pytest.raises(ValueError):
        backface_temperature(float("inf"), 6000.0, 0.02, 0.05)


def test_rejects_nonphysical_absolute_temperatures(material):
    with pytest.raises(ValueError):
        size_thickness_for_backface_limit(material, t_hot=0.0, heat_flux=6000.0, t_back_max=600.0)
    with pytest.raises(ValueError):
        size_thickness_for_backface_limit(material, t_hot=1300.0, heat_flux=6000.0, t_back_max=-10.0)
    with pytest.raises(ValueError):
        backface_temperature(-300.0, 6000.0, 0.02, 0.05)


def test_rejects_negative_density_or_thickness_in_areal_mass():
    with pytest.raises(ValueError):
        areal_mass(-100.0, 0.02)
    with pytest.raises(ValueError):
        areal_mass(100.0, -0.02)


# --- L. Zero-required-thickness case ------------------------------------------


def test_zero_thickness_when_t_hot_at_or_below_limit(material):
    result = size_thickness_for_backface_limit(
        material, t_hot=500.0, heat_flux=5000.0, t_back_max=500.0
    )
    assert result.thickness == 0.0
    assert result.areal_mass == 0.0
    assert result.t_back_predicted == pytest.approx(500.0)
    assert result.margin_temperature == pytest.approx(0.0, abs=1e-9)

    result_below = size_thickness_for_backface_limit(
        material, t_hot=400.0, heat_flux=5000.0, t_back_max=500.0
    )
    assert result_below.thickness == 0.0
