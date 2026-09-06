"""Validation tests for TPSMaterial."""

import math

import pytest

from tps_trade import TPSMaterial


def test_valid_material_constructs():
    mat = TPSMaterial(
        name="Illustrative Reusable TPS",
        density=350.0,
        conductivity=0.06,
        max_service_temperature=1500.0,
    )
    assert mat.density == 350.0
    assert mat.conductivity == 0.06
    assert mat.max_service_temperature == 1500.0
    assert mat.specific_heat is None


def test_valid_material_with_specific_heat():
    mat = TPSMaterial(
        name="Illustrative Reusable TPS",
        density=350.0,
        conductivity=0.06,
        max_service_temperature=1500.0,
        specific_heat=1050.0,
    )
    assert mat.specific_heat == 1050.0


@pytest.mark.parametrize("bad_density", [0.0, -1.0, float("nan"), float("inf")])
def test_rejects_invalid_density(bad_density):
    with pytest.raises(ValueError):
        TPSMaterial(
            name="bad",
            density=bad_density,
            conductivity=0.06,
            max_service_temperature=1500.0,
        )


@pytest.mark.parametrize("bad_k", [0.0, -0.5, float("nan"), float("inf")])
def test_rejects_invalid_conductivity(bad_k):
    with pytest.raises(ValueError):
        TPSMaterial(
            name="bad",
            density=350.0,
            conductivity=bad_k,
            max_service_temperature=1500.0,
        )


@pytest.mark.parametrize("bad_t", [0.0, -100.0, float("nan"), float("inf")])
def test_rejects_invalid_max_service_temperature(bad_t):
    with pytest.raises(ValueError):
        TPSMaterial(
            name="bad",
            density=350.0,
            conductivity=0.06,
            max_service_temperature=bad_t,
        )


@pytest.mark.parametrize("bad_cp", [0.0, -1.0, float("nan"), float("inf")])
def test_rejects_invalid_specific_heat_when_provided(bad_cp):
    with pytest.raises(ValueError):
        TPSMaterial(
            name="bad",
            density=350.0,
            conductivity=0.06,
            max_service_temperature=1500.0,
            specific_heat=bad_cp,
        )


def test_rejects_empty_name():
    with pytest.raises(ValueError):
        TPSMaterial(
            name="   ",
            density=350.0,
            conductivity=0.06,
            max_service_temperature=1500.0,
        )
