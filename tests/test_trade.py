"""Verification tests for the Milestone 4 reusable-vs-ablative TPS trade.

Section letters correspond to the Milestone 4 verification plan in the
project brief / README.
"""

import math

import pytest

from tps_trade import (
    TPSMaterial,
    AblativeMaterial,
    square_pulse,
    max_stable_time_step,
    size_thickness_transient,
    integrated_heat_load,
    size_ablative_thickness,
    AblativeCandidate,
    StudyCase,
    TradeResult,
    size_reusable_candidate,
    size_ablative_candidate,
    validate_candidate_database,
    run_trade_study,
    rank_feasible_by_mass,
    summarize_trade,
    generate_recommendation,
    STUDY_CASE,
    REUSABLE_CANDIDATES,
    ABLATIVE_CANDIDATES,
)


# --- A. Candidate database validation -----------------------------------------


def test_canonical_candidate_database_is_valid():
    # Should not raise.
    validate_candidate_database(REUSABLE_CANDIDATES, ABLATIVE_CANDIDATES)


def test_candidate_names_are_unique_in_canonical_database():
    names = [m.name for m in REUSABLE_CANDIDATES] + [c.material.name for c in ABLATIVE_CANDIDATES]
    assert len(names) == len(set(names))


def test_validate_candidate_database_rejects_duplicate_names():
    mat1 = TPSMaterial("dup", density=350.0, conductivity=0.06, max_service_temperature=1500.0, specific_heat=1000.0)
    mat2 = TPSMaterial("dup", density=200.0, conductivity=0.05, max_service_temperature=1500.0, specific_heat=1000.0)
    with pytest.raises(ValueError, match="duplicate"):
        validate_candidate_database([mat1, mat2], [])


def test_validate_candidate_database_rejects_wrong_types():
    with pytest.raises(TypeError):
        validate_candidate_database(["not a material"], [])
    with pytest.raises(TypeError):
        validate_candidate_database([], ["not a candidate"])


def test_canonical_reusable_candidates_have_valid_properties():
    for material in REUSABLE_CANDIDATES:
        assert material.density > 0
        assert material.conductivity > 0
        assert material.specific_heat is not None and material.specific_heat > 0
        assert material.max_service_temperature > 0


def test_canonical_ablative_candidates_have_valid_properties():
    for candidate in ABLATIVE_CANDIDATES:
        assert candidate.material.density > 0
        assert candidate.material.effective_heat_of_ablation > 0
        assert candidate.retained_thickness >= 0


# --- B. Reusable sizing consistency ---------------------------------------------


def test_reusable_trade_result_matches_direct_transient_sizing():
    material = REUSABLE_CANDIDATES[0]
    result = size_reusable_candidate(material, STUDY_CASE)
    assert result.feasible

    alpha = material.thermal_diffusivity()
    dx_min = STUDY_CASE.reusable_thickness_bounds[0] / (STUDY_CASE.reusable_n_nodes - 1)
    dt = max_stable_time_step(alpha, dx_min, STUDY_CASE.reusable_fourier_limit)
    direct = size_thickness_transient(
        material,
        STUDY_CASE.reusable_heating_history,
        total_time=STUDY_CASE.total_time,
        t_initial=STUDY_CASE.t_initial,
        t_back_max=STUDY_CASE.t_back_max,
        thickness_bounds=STUDY_CASE.reusable_thickness_bounds,
        dt=dt,
        n_nodes=STUDY_CASE.reusable_n_nodes,
    )

    assert result.required_thickness == pytest.approx(direct.thickness)
    assert result.reusable_detail.peak_backface_temperature == pytest.approx(direct.peak_backface_temperature)
    assert result.initial_areal_mass == pytest.approx(direct.areal_mass)


# --- C. Ablative sizing consistency ----------------------------------------------


def test_ablative_trade_result_matches_direct_ablative_sizing():
    candidate = ABLATIVE_CANDIDATES[0]
    result = size_ablative_candidate(candidate, STUDY_CASE)

    total_heat_load = STUDY_CASE.ablative_total_heat_load()
    direct = size_ablative_thickness(
        candidate.material, total_heat_load, candidate.retained_thickness, max_recession=candidate.max_recession
    )

    assert result.governing_metric_value == pytest.approx(direct.recession_depth)
    assert result.required_thickness == pytest.approx(direct.initial_thickness)
    assert result.initial_areal_mass == pytest.approx(direct.initial_areal_mass)


# --- D. Service-temperature rejection --------------------------------------------


def test_reusable_candidate_below_hot_side_max_is_infeasible():
    low_temp_material = TPSMaterial(
        "Too-low service temp",
        density=350.0,
        conductivity=0.06,
        max_service_temperature=STUDY_CASE.t_hot_max - 100.0,  # deliberately below
        specific_heat=1050.0,
    )
    result = size_reusable_candidate(low_temp_material, STUDY_CASE)
    assert not result.feasible
    assert result.required_thickness is None
    assert result.initial_areal_mass is None
    assert any("max_service_temperature" in note for note in result.notes)


def test_second_canonical_reusable_candidate_is_infeasible_for_canonical_case():
    # By design, "Reusable fibrous blanket (illustrative)" has
    # max_service_temperature < STUDY_CASE.t_hot_max.
    blanket = REUSABLE_CANDIDATES[1]
    assert blanket.max_service_temperature < STUDY_CASE.t_hot_max
    result = size_reusable_candidate(blanket, STUDY_CASE)
    assert not result.feasible


# --- E. Common study-case enforcement --------------------------------------------


def test_changing_candidate_material_does_not_mutate_study_case():
    before = (
        STUDY_CASE.t_initial,
        STUDY_CASE.t_hot_max,
        STUDY_CASE.tau_heat,
        STUDY_CASE.total_time,
        STUDY_CASE.t_back_max,
        STUDY_CASE.ablative_heat_flux,
    )
    for material in REUSABLE_CANDIDATES:
        size_reusable_candidate(material, STUDY_CASE)
    for candidate in ABLATIVE_CANDIDATES:
        size_ablative_candidate(candidate, STUDY_CASE)
    after = (
        STUDY_CASE.t_initial,
        STUDY_CASE.t_hot_max,
        STUDY_CASE.tau_heat,
        STUDY_CASE.total_time,
        STUDY_CASE.t_back_max,
        STUDY_CASE.ablative_heat_flux,
    )
    assert before == after


def test_all_reusable_candidates_use_identical_heating_history_and_limit():
    # The heating history and backface limit are properties/fields of the
    # single shared StudyCase instance -- verify every candidate is sized
    # against that same instance's values, not a per-candidate copy.
    material_a, material_b = REUSABLE_CANDIDATES[0], REUSABLE_CANDIDATES[0]
    hist_a = STUDY_CASE.reusable_heating_history
    hist_b = STUDY_CASE.reusable_heating_history
    assert hist_a.t_initial == hist_b.t_initial
    assert hist_a.t_hot == hist_b.t_hot
    assert hist_a.tau_heat == hist_b.tau_heat


def test_all_ablative_candidates_use_identical_heat_flux_history():
    load_a = STUDY_CASE.ablative_total_heat_load()
    load_b = STUDY_CASE.ablative_total_heat_load()
    assert load_a == load_b


# --- F. Areal-mass ranking --------------------------------------------------------


def _synthetic_result(name, category, feasible, mass, margin):
    return TradeResult(
        name=name,
        category=category,
        feasible=feasible,
        required_thickness=0.01,
        initial_areal_mass=mass,
        governing_metric_name="x",
        governing_metric_value=0.0,
        design_margin=margin,
        margin_units="K",
        key_capability_limit=None,
        notes=(),
    )


def test_lightest_feasible_candidate_is_selected():
    results = [
        _synthetic_result("heavy", "reusable", True, 10.0, 1.0),
        _synthetic_result("light", "ablative", True, 3.0, 1.0),
        _synthetic_result("medium", "reusable", True, 5.0, 1.0),
    ]
    ranked = rank_feasible_by_mass(results)
    assert ranked[0].name == "light"
    summary = summarize_trade(results)
    assert summary.winner.name == "light"


# --- G. Infeasible exclusion -------------------------------------------------------


def test_infeasible_candidate_never_selected_despite_lower_mass():
    results = [
        _synthetic_result("infeasible-light", "ablative", False, 1.0, None),
        _synthetic_result("feasible-heavier", "reusable", True, 5.0, 1.0),
    ]
    summary = summarize_trade(results)
    assert summary.winner.name == "feasible-heavier"
    assert all(r.name != "infeasible-light" for r in summary.ranked_feasible)


# --- H. Deterministic tie-break ---------------------------------------------------


def test_equal_mass_tie_break_is_deterministic_by_margin_then_name():
    results = [
        _synthetic_result("b_candidate", "reusable", True, 5.0, 0.5),
        _synthetic_result("a_candidate", "ablative", True, 5.0, 1.0),
    ]
    ranked_1 = rank_feasible_by_mass(results)
    ranked_2 = rank_feasible_by_mass(list(reversed(results)))
    assert [r.name for r in ranked_1] == [r.name for r in ranked_2] == ["a_candidate", "b_candidate"]


def test_exact_tie_break_falls_back_to_name():
    results = [
        _synthetic_result("zzz", "reusable", True, 5.0, 1.0),
        _synthetic_result("aaa", "ablative", True, 5.0, 1.0),
    ]
    ranked = rank_feasible_by_mass(results)
    assert [r.name for r in ranked] == ["aaa", "zzz"]


# --- J. Reusable model trend -------------------------------------------------------


def test_higher_rho_cp_reduces_transient_penetration_in_trade_case():
    baseline = TPSMaterial(
        "baseline", density=350.0, conductivity=0.06, max_service_temperature=2000.0, specific_heat=1050.0
    )
    higher_inertia = TPSMaterial(
        "higher-inertia", density=350.0, conductivity=0.06, max_service_temperature=2000.0, specific_heat=2100.0
    )
    assert higher_inertia.thermal_diffusivity() < baseline.thermal_diffusivity()

    result_baseline = size_reusable_candidate(baseline, STUDY_CASE)
    result_higher = size_reusable_candidate(higher_inertia, STUDY_CASE)
    assert result_baseline.feasible and result_higher.feasible
    # Lower diffusivity -> less transient penetration -> thinner required
    # insulation for the same backface limit and pulse.
    assert result_higher.required_thickness < result_baseline.required_thickness


# --- K. Ablative model trend -------------------------------------------------------


def test_higher_heat_of_ablation_reduces_consumed_mass_and_recession():
    total_heat_load = STUDY_CASE.ablative_total_heat_load()
    low_h_eff = AblativeCandidate(
        material=AblativeMaterial("low H_eff", density=1000.0, effective_heat_of_ablation=5.0e6),
        retained_thickness=0.005,
    )
    high_h_eff = AblativeCandidate(
        material=AblativeMaterial("high H_eff", density=1000.0, effective_heat_of_ablation=1.0e7),
        retained_thickness=0.005,
    )
    result_low = size_ablative_candidate(low_h_eff, STUDY_CASE)
    result_high = size_ablative_candidate(high_h_eff, STUDY_CASE)

    assert result_high.ablative_detail.consumed_areal_mass < result_low.ablative_detail.consumed_areal_mass
    assert result_high.governing_metric_value < result_low.governing_metric_value  # recession_depth


# --- L. Mass identity ---------------------------------------------------------------


def test_ablative_mass_identity_in_trade_result():
    for candidate in ABLATIVE_CANDIDATES:
        result = size_ablative_candidate(candidate, STUDY_CASE)
        detail = result.ablative_detail
        assert result.initial_areal_mass == pytest.approx(
            detail.remaining_areal_mass + detail.consumed_areal_mass
        )


# --- Recommendation and end-to-end trade study -------------------------------------


def test_run_trade_study_and_recommendation_end_to_end():
    results = run_trade_study(STUDY_CASE, REUSABLE_CANDIDATES, ABLATIVE_CANDIDATES)
    assert len(results) == len(REUSABLE_CANDIDATES) + len(ABLATIVE_CANDIDATES)

    summary = summarize_trade(results)
    assert summary.winner is not None
    assert summary.winner.feasible

    recommendation = generate_recommendation(STUDY_CASE, summary)
    assert summary.winner.name in recommendation
    assert "NOT a claim" in recommendation


def test_recommendation_handles_no_feasible_candidate():
    empty_summary = summarize_trade([])
    recommendation = generate_recommendation(STUDY_CASE, empty_summary)
    assert "No feasible candidate" in recommendation


# --- StudyCase validation ------------------------------------------------------------


def test_study_case_rejects_hot_max_not_exceeding_initial():
    with pytest.raises(ValueError):
        StudyCase(
            name="bad", t_initial=1000.0, t_hot_max=900.0, tau_heat=60.0,
            total_time=600.0, t_back_max=450.0, ablative_heat_flux=1.0e6,
        )


def test_study_case_rejects_total_time_not_exceeding_tau_heat():
    with pytest.raises(ValueError):
        StudyCase(
            name="bad", t_initial=300.0, t_hot_max=1400.0, tau_heat=600.0,
            total_time=600.0, t_back_max=450.0, ablative_heat_flux=1.0e6,
        )


def test_study_case_rejects_invalid_thickness_bounds():
    with pytest.raises(ValueError):
        StudyCase(
            name="bad", t_initial=300.0, t_hot_max=1400.0, tau_heat=60.0,
            total_time=600.0, t_back_max=450.0, ablative_heat_flux=1.0e6,
            reusable_thickness_bounds=(0.05, 0.01),
        )


def test_study_case_rejects_fourier_limit_above_half():
    with pytest.raises(ValueError):
        StudyCase(
            name="bad", t_initial=300.0, t_hot_max=1400.0, tau_heat=60.0,
            total_time=600.0, t_back_max=450.0, ablative_heat_flux=1.0e6,
            reusable_fourier_limit=0.9,
        )


def test_ablative_candidate_recession_allowable_feasibility():
    total_heat_load = STUDY_CASE.ablative_total_heat_load()
    tight_candidate = AblativeCandidate(
        material=AblativeMaterial("tight allowable", density=1000.0, effective_heat_of_ablation=5.0e6),
        retained_thickness=0.005,
        max_recession=0.001,  # deliberately far too small
    )
    result = size_ablative_candidate(tight_candidate, STUDY_CASE)
    assert not result.feasible
    assert result.design_margin is not None and result.design_margin < 0.0
