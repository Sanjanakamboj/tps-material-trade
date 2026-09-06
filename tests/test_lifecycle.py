"""Verification tests for the Milestone 5 illustrative lifecycle trade.

Section letters correspond to the Milestone 5 verification plan in the
project brief / README.
"""

import math

import pytest

from tps_trade import (
    TradeResult,
    ReusableTradeDetail,
    AblativeTradeDetail,
    LifecycleConfig,
    compute_reusable_lifecycle,
    compute_ablative_lifecycle,
    compute_lifecycle,
    run_lifecycle_study,
    rank_lifecycle_by_burden,
    summarize_lifecycle,
    find_breakeven_mission_count,
    run_trade_study,
    STUDY_CASE,
    REUSABLE_CANDIDATES,
    ABLATIVE_CANDIDATES,
)


def _reusable_trade_result(name="reusable-x", installed_mass=5.0, feasible=True):
    detail = ReusableTradeDetail(
        peak_backface_temperature=450.0, thermal_diffusivity=1.6e-7, t_hot_max=1400.0, max_service_temperature=1650.0
    )
    return TradeResult(
        name=name,
        category="reusable",
        feasible=feasible,
        required_thickness=0.016,
        initial_areal_mass=installed_mass if feasible else None,
        governing_metric_name="peak_backface_temperature",
        governing_metric_value=450.0 if feasible else None,
        design_margin=0.1 if feasible else None,
        margin_units="K",
        key_capability_limit=1650.0,
        notes=() if feasible else ("infeasible",),
        reusable_detail=detail if feasible else None,
    )


def _ablative_trade_result(name="ablative-x", initial_mass=19.0, consumed_mass=12.0, feasible=True):
    detail = AblativeTradeDetail(
        total_heat_load=1.2e8,
        effective_heat_of_ablation=1.0e7,
        consumed_areal_mass=consumed_mass,
        remaining_areal_mass=initial_mass - consumed_mass,
        consumed_mass_fraction=consumed_mass / initial_mass,
        retained_thickness=0.005,
    )
    return TradeResult(
        name=name,
        category="ablative",
        feasible=feasible,
        required_thickness=0.0136,
        initial_areal_mass=initial_mass if feasible else None,
        governing_metric_name="recession_depth",
        governing_metric_value=0.0086 if feasible else None,
        design_margin=0.01 if feasible else None,
        margin_units="m",
        key_capability_limit=0.02,
        notes=() if feasible else ("infeasible",),
        ablative_detail=detail if feasible else None,
    )


# --- A. One-mission reusable identity --------------------------------------------


def test_one_mission_reusable_identity_zero_refurbishment():
    trade = _reusable_trade_result(installed_mass=5.67)
    config = LifecycleConfig(mission_count=1, reusable_service_life_missions=50, reusable_refurbishment_fraction=0.0)
    life = compute_reusable_lifecycle(trade, config)
    assert life.cumulative_lifecycle_burden == pytest.approx(5.67)
    assert life.replacements == 0


# --- B. One-mission ablative identity --------------------------------------------


def test_one_mission_ablative_identity():
    trade = _ablative_trade_result(initial_mass=19.0, consumed_mass=12.0)
    config = LifecycleConfig(mission_count=1, reusable_service_life_missions=50, reusable_refurbishment_fraction=0.0)
    life = compute_ablative_lifecycle(trade, config)
    assert life.cumulative_lifecycle_burden == pytest.approx(19.0)
    assert life.replacements == 0


# --- C. Ablative repeated-mission formula ----------------------------------------


def test_ablative_repeated_mission_formula_hand_calc():
    trade = _ablative_trade_result(initial_mass=19.0, consumed_mass=12.0)
    config = LifecycleConfig(mission_count=7, reusable_service_life_missions=50, reusable_refurbishment_fraction=0.0)
    life = compute_ablative_lifecycle(trade, config)
    expected = 19.0 + (7 - 1) * 12.0
    assert life.cumulative_lifecycle_burden == pytest.approx(expected)
    assert life.replacements == 6


# --- D. Reusable refurbishment scaling --------------------------------------------


def test_doubling_refurbishment_fraction_doubles_refurbishment_contribution():
    trade = _reusable_trade_result(installed_mass=5.67)
    cfg_1 = LifecycleConfig(mission_count=50, reusable_service_life_missions=50, reusable_refurbishment_fraction=0.01)
    cfg_2 = LifecycleConfig(mission_count=50, reusable_service_life_missions=50, reusable_refurbishment_fraction=0.02)
    life_1 = compute_reusable_lifecycle(trade, cfg_1)
    life_2 = compute_reusable_lifecycle(trade, cfg_2)
    assert life_2.reusable_detail.refurbishment_burden == pytest.approx(2.0 * life_1.reusable_detail.refurbishment_burden)
    # Installation burden (replacement-driven) must be unaffected by refurbishment fraction.
    assert life_1.reusable_detail.installation_burden == pytest.approx(life_2.reusable_detail.installation_burden)


# --- E. Reusable replacement count -------------------------------------------------


@pytest.mark.parametrize(
    "mission_count,n_service,expected_installations,expected_replacements",
    [
        (5, 10, 1, 0),  # M < N_service
        (10, 10, 1, 0),  # M == N_service exactly: no replacement yet
        (11, 10, 2, 1),  # M == N_service + 1: first replacement required
        (25, 10, 3, 2),  # multiple replacement intervals
        (20, 10, 2, 1),  # M == 2*N_service exactly: still only 2 installations
        (21, 10, 3, 2),  # M == 2*N_service + 1: 3rd installation required
    ],
)
def test_reusable_replacement_count_convention(mission_count, n_service, expected_installations, expected_replacements):
    trade = _reusable_trade_result(installed_mass=5.0)
    config = LifecycleConfig(
        mission_count=mission_count, reusable_service_life_missions=n_service, reusable_refurbishment_fraction=0.0
    )
    life = compute_reusable_lifecycle(trade, config)
    assert life.reusable_detail.installation_count == expected_installations
    assert life.replacements == expected_replacements


# --- F. Zero refurbishment ---------------------------------------------------------


def test_zero_refurbishment_and_long_service_life_equals_installed_mass():
    trade = _reusable_trade_result(installed_mass=5.67)
    config = LifecycleConfig(mission_count=30, reusable_service_life_missions=100, reusable_refurbishment_fraction=0.0)
    life = compute_reusable_lifecycle(trade, config)
    assert life.cumulative_lifecycle_burden == pytest.approx(5.67)


# --- G. Mission-average identity ---------------------------------------------------


def test_mission_averaged_burden_identity():
    trade = _ablative_trade_result(initial_mass=19.0, consumed_mass=12.0)
    config = LifecycleConfig(mission_count=10, reusable_service_life_missions=50, reusable_refurbishment_fraction=0.0)
    life = compute_ablative_lifecycle(trade, config)
    assert life.mission_averaged_burden == pytest.approx(life.cumulative_lifecycle_burden / 10)


# --- H. Thermally infeasible exclusion ----------------------------------------------


def test_infeasible_reusable_candidate_excluded_from_lifecycle():
    infeasible_trade = _reusable_trade_result(feasible=False)
    config = LifecycleConfig(mission_count=50, reusable_service_life_missions=50, reusable_refurbishment_fraction=0.01)
    life = compute_reusable_lifecycle(infeasible_trade, config)
    assert not life.feasible
    assert life.cumulative_lifecycle_burden is None


def test_canonical_fibrous_blanket_excluded_from_lifecycle_ranking():
    results = run_trade_study(STUDY_CASE, REUSABLE_CANDIDATES, ABLATIVE_CANDIDATES)
    config = LifecycleConfig(mission_count=50, reusable_service_life_missions=50, reusable_refurbishment_fraction=0.01)
    life_results = run_lifecycle_study(results, config)
    ranked = rank_lifecycle_by_burden(life_results)
    assert all(r.name != "Reusable fibrous blanket (illustrative)" for r in ranked)
    blanket_life = next(r for r in life_results if r.name == "Reusable fibrous blanket (illustrative)")
    assert not blanket_life.feasible


# --- I. Lifecycle ranking -----------------------------------------------------------


def test_lifecycle_ranking_can_differ_from_single_event_mass_ranking():
    # Candidate A has lower initial mass but a much higher per-mission burden
    # (e.g. very high ablative consumption), so it should lose the lifecycle
    # ranking despite winning on single-event mass.
    light_but_costly = _ablative_trade_result(name="light-but-costly", initial_mass=2.0, consumed_mass=50.0)
    heavier_but_efficient = _reusable_trade_result(name="heavier-but-efficient", installed_mass=6.0)

    config_one_mission = LifecycleConfig(mission_count=1, reusable_service_life_missions=50, reusable_refurbishment_fraction=0.0)
    life_one = run_lifecycle_study([light_but_costly, heavier_but_efficient], config_one_mission)
    assert rank_lifecycle_by_burden(life_one)[0].name == "light-but-costly"  # single-event: lighter wins

    config_many_missions = LifecycleConfig(mission_count=10, reusable_service_life_missions=50, reusable_refurbishment_fraction=0.0)
    life_many = run_lifecycle_study([light_but_costly, heavier_but_efficient], config_many_missions)
    assert rank_lifecycle_by_burden(life_many)[0].name == "heavier-but-efficient"  # lifecycle: efficient wins


# --- J. Break-even helper -----------------------------------------------------------


def test_breakeven_helper_finds_known_analytical_crossover():
    # Reusable: cumulative = installation_count*5.0 + 0 (zero refurb, service
    # life 1000 so installation_count stays 1 across the whole search range).
    # -> constant burden = 5.0 for all M in range.
    # Ablative: cumulative = 1.0 + (M-1)*1.0 = M.
    # Crossover: ablative starts lower (M=1: 1.0 < 5.0) and overtakes once
    # M > 5, i.e. at M=6 (6.0 > 5.0).
    reusable = _reusable_trade_result(name="reusable-flat", installed_mass=5.0)
    ablative = _ablative_trade_result(name="ablative-linear", initial_mass=1.0, consumed_mass=1.0)

    base_config = LifecycleConfig(mission_count=1, reusable_service_life_missions=1000, reusable_refurbishment_fraction=0.0)
    result = find_breakeven_mission_count(ablative, reusable, base_config, mission_range=(1, 50))

    assert result.crossover_found
    assert result.crossover_mission_count == 6
    assert result.leader_at_range_start == "ablative-linear"
    assert result.leader_at_range_end == "reusable-flat"


# --- K. No-crossover behavior --------------------------------------------------------


def test_breakeven_helper_reports_no_crossover_when_none_exists():
    reusable = _reusable_trade_result(name="reusable-cheap", installed_mass=1.0)
    ablative = _ablative_trade_result(name="ablative-expensive", initial_mass=100.0, consumed_mass=100.0)
    base_config = LifecycleConfig(mission_count=1, reusable_service_life_missions=1000, reusable_refurbishment_fraction=0.0)

    result = find_breakeven_mission_count(reusable, ablative, base_config, mission_range=(1, 50))
    assert not result.crossover_found
    assert result.crossover_mission_count is None
    assert result.leader_at_range_start == "reusable-cheap"
    assert result.leader_at_range_end == "reusable-cheap"


def test_canonical_tile_vs_dense_ablator_has_no_crossover_within_500_missions():
    results = run_trade_study(STUDY_CASE, REUSABLE_CANDIDATES, ABLATIVE_CANDIDATES)
    by_name = {r.name: r for r in results}
    tile = by_name["Reusable low-density tile (illustrative)"]
    dense = by_name["Dense high-H_eff ablator (illustrative)"]
    base_config = LifecycleConfig(mission_count=1, reusable_service_life_missions=50, reusable_refurbishment_fraction=0.01)

    result = find_breakeven_mission_count(tile, dense, base_config, mission_range=(1, 500))
    assert not result.crossover_found
    assert result.leader_at_range_start == tile.name


# --- L. Determinism -------------------------------------------------------------------


def test_lifecycle_computation_is_deterministic():
    trade = _ablative_trade_result()
    config = LifecycleConfig(mission_count=25, reusable_service_life_missions=50, reusable_refurbishment_fraction=0.02)
    life_1 = compute_ablative_lifecycle(trade, config)
    life_2 = compute_ablative_lifecycle(trade, config)
    assert life_1 == life_2


def test_breakeven_search_is_deterministic():
    reusable = _reusable_trade_result(installed_mass=5.0)
    ablative = _ablative_trade_result(initial_mass=1.0, consumed_mass=1.0)
    base_config = LifecycleConfig(mission_count=1, reusable_service_life_missions=1000, reusable_refurbishment_fraction=0.0)
    result_1 = find_breakeven_mission_count(ablative, reusable, base_config, mission_range=(1, 50))
    result_2 = find_breakeven_mission_count(ablative, reusable, base_config, mission_range=(1, 50))
    assert result_1 == result_2


# --- LifecycleConfig validation --------------------------------------------------------


def test_lifecycle_config_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        LifecycleConfig(mission_count=0, reusable_service_life_missions=50, reusable_refurbishment_fraction=0.0)
    with pytest.raises(ValueError):
        LifecycleConfig(mission_count=10, reusable_service_life_missions=0, reusable_refurbishment_fraction=0.0)
    with pytest.raises(ValueError):
        LifecycleConfig(mission_count=10, reusable_service_life_missions=50, reusable_refurbishment_fraction=-0.01)
    with pytest.raises(ValueError):
        LifecycleConfig(
            mission_count=10, reusable_service_life_missions=50, reusable_refurbishment_fraction=0.0,
            ablative_replenishment_convention="something_else",
        )


def test_reusable_replace_disabled_marks_overlong_mission_count_infeasible():
    trade = _reusable_trade_result(installed_mass=5.0)
    config = LifecycleConfig(
        mission_count=60, reusable_service_life_missions=50, reusable_refurbishment_fraction=0.0,
        reusable_replace_at_end_of_service_life=False,
    )
    life = compute_reusable_lifecycle(trade, config)
    assert not life.feasible
    assert life.cumulative_lifecycle_burden is None


def test_compute_lifecycle_dispatch_rejects_category_mismatch():
    reusable = _reusable_trade_result()
    ablative = _ablative_trade_result()
    config = LifecycleConfig(mission_count=1, reusable_service_life_missions=50, reusable_refurbishment_fraction=0.0)
    with pytest.raises(ValueError):
        compute_reusable_lifecycle(ablative, config)
    with pytest.raises(ValueError):
        compute_ablative_lifecycle(reusable, config)


# --- M. Regression is covered by the full test suite (see other test files) -----------


def test_run_lifecycle_study_end_to_end_on_canonical_database():
    results = run_trade_study(STUDY_CASE, REUSABLE_CANDIDATES, ABLATIVE_CANDIDATES)
    config = LifecycleConfig(mission_count=50, reusable_service_life_missions=50, reusable_refurbishment_fraction=0.01)
    life_results = run_lifecycle_study(results, config)
    assert len(life_results) == len(results)
    summary = summarize_lifecycle(life_results)
    assert summary.winner is not None
    assert summary.winner.feasible
