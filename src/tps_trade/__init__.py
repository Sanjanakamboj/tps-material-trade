"""tps_trade: TPS (thermal protection system) material/system trade toolkit.

Milestone 1 scope
------------------
This package currently provides ONLY a verified one-dimensional, steady-state
conduction sizing foundation for a single homogeneous TPS slab. It does not
yet model ablation, pyrolysis, transient response, radiation, or perform any
multi-material trade/scoring. See the project README for the full milestone
scope and the physical caveats of the simplified boundary-value problem
implemented here.
"""

from .materials import TPSMaterial
from .conduction import (
    SizingResult,
    thermal_resistance,
    thickness_from_resistance,
    backface_temperature,
    heat_flux_from_temperatures,
    areal_mass,
    size_thickness_for_backface_limit,
)
from .transient import (
    HeatingPulse,
    TransientResult,
    TransientSizingResult,
    square_pulse,
    max_stable_time_step,
    solve_transient_conduction,
    size_thickness_transient,
)
from .ablative import (
    AblativeMaterial,
    HeatFluxSegment,
    AblativeSizingResult,
    AblativeTrialResult,
    total_heat_load_constant,
    total_heat_load_piecewise,
    total_heat_load_sampled,
    integrated_heat_load,
    consumed_areal_mass,
    recession_depth,
    size_ablative_thickness,
    evaluate_trial_thickness,
)
from .trade import (
    AblativeCandidate,
    StudyCase,
    ReusableTradeDetail,
    AblativeTradeDetail,
    TradeResult,
    TradeSummary,
    size_reusable_candidate,
    size_ablative_candidate,
    validate_candidate_database,
    run_trade_study,
    rank_feasible_by_mass,
    summarize_trade,
    generate_recommendation,
)
from .candidates import (
    STUDY_CASE,
    REUSABLE_CANDIDATES,
    ABLATIVE_CANDIDATES,
)
from .lifecycle import (
    LifecycleConfig,
    ReusableLifecycleDetail,
    AblativeLifecycleDetail,
    LifecycleResult,
    LifecycleSummary,
    BreakevenResult,
    compute_reusable_lifecycle,
    compute_ablative_lifecycle,
    compute_lifecycle,
    run_lifecycle_study,
    rank_lifecycle_by_burden,
    summarize_lifecycle,
    find_breakeven_mission_count,
)

__all__ = [
    "TPSMaterial",
    "SizingResult",
    "thermal_resistance",
    "thickness_from_resistance",
    "backface_temperature",
    "heat_flux_from_temperatures",
    "areal_mass",
    "size_thickness_for_backface_limit",
    "HeatingPulse",
    "TransientResult",
    "TransientSizingResult",
    "square_pulse",
    "max_stable_time_step",
    "solve_transient_conduction",
    "size_thickness_transient",
    "AblativeMaterial",
    "HeatFluxSegment",
    "AblativeSizingResult",
    "AblativeTrialResult",
    "total_heat_load_constant",
    "total_heat_load_piecewise",
    "total_heat_load_sampled",
    "integrated_heat_load",
    "consumed_areal_mass",
    "recession_depth",
    "size_ablative_thickness",
    "evaluate_trial_thickness",
    "AblativeCandidate",
    "StudyCase",
    "ReusableTradeDetail",
    "AblativeTradeDetail",
    "TradeResult",
    "TradeSummary",
    "size_reusable_candidate",
    "size_ablative_candidate",
    "validate_candidate_database",
    "run_trade_study",
    "rank_feasible_by_mass",
    "summarize_trade",
    "generate_recommendation",
    "STUDY_CASE",
    "REUSABLE_CANDIDATES",
    "ABLATIVE_CANDIDATES",
    "LifecycleConfig",
    "ReusableLifecycleDetail",
    "AblativeLifecycleDetail",
    "LifecycleResult",
    "LifecycleSummary",
    "BreakevenResult",
    "compute_reusable_lifecycle",
    "compute_ablative_lifecycle",
    "compute_lifecycle",
    "run_lifecycle_study",
    "rank_lifecycle_by_burden",
    "summarize_lifecycle",
    "find_breakeven_mission_count",
]

__version__ = "0.1.0"
