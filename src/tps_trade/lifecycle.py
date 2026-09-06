"""Milestone 5: illustrative mission-lifecycle TPS trade.

This module extends the Milestone 4 single-event trade
(:mod:`tps_trade.trade`) into a simple, transparent MULTI-MISSION mass
bookkeeping model. It introduces **no new thermal physics** -- every
lifecycle calculation here starts from an already-sized, single-event
``TradeResult`` (thermal feasibility and initial areal mass) and applies an
explicit, illustrative accounting convention on top of it.

Call this what it is: an **illustrative lifecycle mass-equivalent trade**,
not a real operations-cost or reliability model. It does NOT represent
monetary cost, actual maintenance labor hours, probabilistic damage or
degradation, detailed material aging, coating erosion, impact damage,
oxidation kinetics, ablative chemistry, or trajectory simulation.

Lifecycle philosophy
-----------------------
- **Reusable TPS**: the installed TPS is retained between missions. It may
  require a small refurbishment-equivalent mass penalty each mission
  (inspection, minor repair, coating touch-up, handling), and it has a
  finite service life in missions, after which the ENTIRE installation is
  replaced.
- **Ablative TPS**: the modeled sacrificial (consumed) material is
  replenished before each subsequent mission; the retained substrate
  thickness is NOT treated as newly consumed each mission.

Neither category is assumed superior in advance -- the numbers decide.

Reusable lifecycle formula
------------------------------
For an installed areal mass ``m''_installed``, a service life of
``N_service`` missions per installation, and a refurbishment-equivalent
fraction ``f_refurb`` (applied once per mission, every mission, against the
fixed installed mass), for a total mission count ``M >= 1``::

    installation_count = ceil(M / N_service)
    replacement_count   = installation_count - 1

    installation_burden  = installation_count * m''_installed
    refurbishment_burden = f_refurb * m''_installed * M

    cumulative_burden = installation_burden + refurbishment_burden

Convention for WHEN a replacement occurs: one installation is good for
EXACTLY ``N_service`` missions (missions 1..N_service fly on installation
#1, missions N_service+1..2*N_service fly on installation #2, etc.) -- so
the first replacement is required before mission ``N_service + 1``, not at
mission ``N_service`` itself. This is why ``installation_count`` uses a
ceiling: at ``M == N_service`` exactly, only 1 installation has been used
(0 replacements); at ``M == N_service + 1``, a 2nd installation is required
(1 replacement).

If ``reusable_replace_at_end_of_service_life`` is False, this module does
NOT model flying a reusable candidate past its stated service life without
replacement -- a mission count exceeding the service life is instead
reported as lifecycle-infeasible for that candidate (this is a modeling
choice, documented, not a silent default).

``cumulative_burden`` here is a **mass-equivalent lifecycle burden**, not
actual mass physically flown on every mission -- the refurbishment term in
particular is an illustrative penalty, not a claim about real removed/
replaced material.

Ablative lifecycle formula
------------------------------
For an initial areal mass ``m''_initial`` and consumed areal mass per
mission ``m''_consumed`` (both from the Milestone 3 single-event sizing),
assuming the first mission requires the full initial mass and every
subsequent mission requires replenishing only the consumed mass, for
``M >= 1``::

    replenishment_count  = M - 1
    replenishment_burden = (M - 1) * m''_consumed

    cumulative_burden = m''_initial + replenishment_burden

No additional ablative refurbishment penalty is introduced in this
milestone.

Both conventions reduce to the single-event Milestone 4 result at ``M=1``
with zero refurbishment: ``cumulative_burden == initial_areal_mass``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import List, Optional, Sequence, Tuple

from .trade import TradeResult
from ._validation import require_nonnegative_finite


# --- Lifecycle configuration ---------------------------------------------------


@dataclass(frozen=True)
class LifecycleConfig:
    """Explicit, illustrative lifecycle-analysis assumptions.

    Attributes
    ----------
    mission_count:
        Total number of missions to accumulate burden over, M >= 1.
    reusable_service_life_missions:
        N_service: missions per reusable installation before a full
        replacement is required, >= 1. Illustrative (e.g. 25/50/100
        missions) -- NOT a claim about any real vehicle's tile lifetime
        unless separately sourced.
    reusable_refurbishment_fraction:
        f_refurb: illustrative mass-EQUIVALENT refurbishment penalty per
        mission, as a fraction of installed areal mass (e.g. 0.01 for 1%).
        Represents inspection/minor repair/coating touch-up/handling, NOT
        actual removed and replaced material, unless separately justified.
        Must be >= 0 and finite.
    reusable_replace_at_end_of_service_life:
        If True (default), a reusable candidate flown for more than
        ``reusable_service_life_missions`` missions incurs explicit
        replacement installations (see module docstring formula). If
        False, flying a candidate past its service life is NOT modeled --
        such a case is reported as lifecycle-infeasible instead of
        silently ignoring the service-life limit.
    ablative_replenishment_convention:
        Documentation-only tag naming the ablative convention in effect.
        Only ``"consumed_mass_only"`` (the convention described in the
        module docstring) is implemented in this milestone.
    """

    mission_count: int
    reusable_service_life_missions: int
    reusable_refurbishment_fraction: float
    reusable_replace_at_end_of_service_life: bool = True
    ablative_replenishment_convention: str = "consumed_mass_only"

    def __post_init__(self) -> None:
        if not isinstance(self.mission_count, int) or self.mission_count < 1:
            raise ValueError(f"mission_count must be an integer >= 1, got {self.mission_count!r}")
        if not isinstance(self.reusable_service_life_missions, int) or self.reusable_service_life_missions < 1:
            raise ValueError(
                "reusable_service_life_missions must be an integer >= 1, got "
                f"{self.reusable_service_life_missions!r}"
            )
        f_refurb = require_nonnegative_finite(
            self.reusable_refurbishment_fraction, "reusable_refurbishment_fraction"
        )
        object.__setattr__(self, "reusable_refurbishment_fraction", f_refurb)
        if self.ablative_replenishment_convention != "consumed_mass_only":
            raise ValueError(
                "ablative_replenishment_convention must be 'consumed_mass_only' "
                "in this milestone, got "
                f"{self.ablative_replenishment_convention!r}"
            )


# --- Structured lifecycle result -----------------------------------------------


@dataclass(frozen=True)
class ReusableLifecycleDetail:
    """Reusable-category-specific lifecycle breakdown."""

    installed_areal_mass: float
    service_life_missions: int
    refurbishment_fraction: float
    installation_count: int
    replacement_count: int
    installation_burden: float
    refurbishment_burden: float


@dataclass(frozen=True)
class AblativeLifecycleDetail:
    """Ablative-category-specific lifecycle breakdown."""

    initial_areal_mass: float
    consumed_areal_mass_per_mission: float
    consumed_mass_fraction_per_mission: float
    replenishment_count: int
    replenishment_burden: float


@dataclass(frozen=True)
class LifecycleResult:
    """Common multi-mission lifecycle result for one candidate.

    ``replacements`` counts REPLACEMENT-OR-REPLENISHMENT EVENTS, but this
    means something different per category (see ``reusable_detail`` /
    ``ablative_detail`` for the precise breakdown): for reusable candidates
    it is the number of FULL installation replacements over the service
    life; for ablative candidates it is the number of REPLENISHMENT events
    (topping up consumed mass), which is always ``mission_count - 1`` under
    this milestone's convention. These are not the same physical event and
    should not be compared directly across categories.
    """

    name: str
    category: str  # "reusable" or "ablative"
    mission_count: int
    feasible: bool  # thermal feasibility (from the underlying TradeResult) AND lifecycle applicability
    initial_areal_mass: Optional[float]
    cumulative_lifecycle_burden: Optional[float]  # kg/m^2-equivalent
    mission_averaged_burden: Optional[float]  # kg/m^2-equivalent per mission
    replacements: Optional[int]
    notes: Tuple[str, ...]
    reusable_detail: Optional[ReusableLifecycleDetail] = None
    ablative_detail: Optional[AblativeLifecycleDetail] = None


# --- Reusable lifecycle computation ---------------------------------------------


def compute_reusable_lifecycle(trade_result: TradeResult, config: LifecycleConfig) -> LifecycleResult:
    """Compute the cumulative mass-equivalent lifecycle burden for one
    reusable candidate's already-sized single-event ``TradeResult``.
    """
    if trade_result.category != "reusable":
        raise ValueError(f"trade_result.category must be 'reusable', got {trade_result.category!r}")

    if not trade_result.feasible:
        return LifecycleResult(
            name=trade_result.name,
            category="reusable",
            mission_count=config.mission_count,
            feasible=False,
            initial_areal_mass=None,
            cumulative_lifecycle_burden=None,
            mission_averaged_burden=None,
            replacements=None,
            notes=("excluded: thermally infeasible for the single-event study case",),
        )

    m_installed = trade_result.initial_areal_mass
    n_service = config.reusable_service_life_missions
    mission_count = config.mission_count

    if mission_count > n_service and not config.reusable_replace_at_end_of_service_life:
        return LifecycleResult(
            name=trade_result.name,
            category="reusable",
            mission_count=mission_count,
            feasible=False,
            initial_areal_mass=m_installed,
            cumulative_lifecycle_burden=None,
            mission_averaged_burden=None,
            replacements=None,
            notes=(
                f"excluded: mission_count={mission_count} exceeds service life "
                f"{n_service} and reusable_replace_at_end_of_service_life=False",
            ),
        )

    installation_count = math.ceil(mission_count / n_service)
    replacement_count = installation_count - 1
    installation_burden = installation_count * m_installed
    refurbishment_burden = config.reusable_refurbishment_fraction * m_installed * mission_count
    cumulative_burden = installation_burden + refurbishment_burden

    detail = ReusableLifecycleDetail(
        installed_areal_mass=m_installed,
        service_life_missions=n_service,
        refurbishment_fraction=config.reusable_refurbishment_fraction,
        installation_count=installation_count,
        replacement_count=replacement_count,
        installation_burden=installation_burden,
        refurbishment_burden=refurbishment_burden,
    )
    return LifecycleResult(
        name=trade_result.name,
        category="reusable",
        mission_count=mission_count,
        feasible=True,
        initial_areal_mass=m_installed,
        cumulative_lifecycle_burden=cumulative_burden,
        mission_averaged_burden=cumulative_burden / mission_count,
        replacements=replacement_count,
        notes=(),
        reusable_detail=detail,
    )


# --- Ablative lifecycle computation ---------------------------------------------


def compute_ablative_lifecycle(trade_result: TradeResult, config: LifecycleConfig) -> LifecycleResult:
    """Compute the cumulative mass-equivalent lifecycle burden for one
    ablative candidate's already-sized single-event ``TradeResult``.
    """
    if trade_result.category != "ablative":
        raise ValueError(f"trade_result.category must be 'ablative', got {trade_result.category!r}")

    if not trade_result.feasible:
        return LifecycleResult(
            name=trade_result.name,
            category="ablative",
            mission_count=config.mission_count,
            feasible=False,
            initial_areal_mass=None,
            cumulative_lifecycle_burden=None,
            mission_averaged_burden=None,
            replacements=None,
            notes=("excluded: thermally/recession infeasible for the single-event study case",),
        )

    mission_count = config.mission_count
    m_initial = trade_result.initial_areal_mass
    ablative_detail_src = trade_result.ablative_detail
    m_consumed = ablative_detail_src.consumed_areal_mass

    replenishment_count = mission_count - 1
    replenishment_burden = replenishment_count * m_consumed
    cumulative_burden = m_initial + replenishment_burden

    detail = AblativeLifecycleDetail(
        initial_areal_mass=m_initial,
        consumed_areal_mass_per_mission=m_consumed,
        consumed_mass_fraction_per_mission=ablative_detail_src.consumed_mass_fraction,
        replenishment_count=replenishment_count,
        replenishment_burden=replenishment_burden,
    )
    return LifecycleResult(
        name=trade_result.name,
        category="ablative",
        mission_count=mission_count,
        feasible=True,
        initial_areal_mass=m_initial,
        cumulative_lifecycle_burden=cumulative_burden,
        mission_averaged_burden=cumulative_burden / mission_count,
        replacements=replenishment_count,
        notes=(),
        ablative_detail=detail,
    )


def compute_lifecycle(trade_result: TradeResult, config: LifecycleConfig) -> LifecycleResult:
    """Dispatch to :func:`compute_reusable_lifecycle` or
    :func:`compute_ablative_lifecycle` based on ``trade_result.category``.
    """
    if trade_result.category == "reusable":
        return compute_reusable_lifecycle(trade_result, config)
    if trade_result.category == "ablative":
        return compute_ablative_lifecycle(trade_result, config)
    raise ValueError(f"unrecognized TradeResult.category: {trade_result.category!r}")


def run_lifecycle_study(trade_results: Sequence[TradeResult], config: LifecycleConfig) -> List[LifecycleResult]:
    """Compute the lifecycle result for every candidate's ``TradeResult``,
    using the SAME ``config`` for all of them (fairness by construction,
    mirroring :func:`tps_trade.trade.run_trade_study`)."""
    return [compute_lifecycle(result, config) for result in trade_results]


# --- Lifecycle ranking ---------------------------------------------------------


def rank_lifecycle_by_burden(results: Sequence[LifecycleResult]) -> List[LifecycleResult]:
    """Deterministic lifecycle ranking: exclude infeasible candidates, rank
    ascending by ``cumulative_lifecycle_burden``, tie-break by name.

    This ranking is intentionally SEPARATE from
    :func:`tps_trade.trade.rank_feasible_by_mass` -- a lifecycle ranking
    never overwrites the Milestone 4 single-event minimum-initial-mass
    result.
    """
    feasible = [r for r in results if r.feasible and r.cumulative_lifecycle_burden is not None]
    return sorted(feasible, key=lambda r: (r.cumulative_lifecycle_burden, r.name))


@dataclass(frozen=True)
class LifecycleSummary:
    """Summary of a ranked lifecycle study at one mission count."""

    mission_count: int
    ranked_feasible: Tuple[LifecycleResult, ...]
    winner: Optional[LifecycleResult]
    burden_gap_to_next: Optional[float]  # kg/m^2-equivalent


def summarize_lifecycle(results: Sequence[LifecycleResult]) -> LifecycleSummary:
    """Rank ``results`` (all assumed to share the same mission_count) and
    summarize the lowest-cumulative-burden feasible candidate."""
    ranked = rank_lifecycle_by_burden(results)
    winner = ranked[0] if ranked else None
    gap = None
    if winner is not None and len(ranked) > 1:
        gap = ranked[1].cumulative_lifecycle_burden - winner.cumulative_lifecycle_burden
    mission_count = results[0].mission_count if results else 0
    return LifecycleSummary(
        mission_count=mission_count, ranked_feasible=tuple(ranked), winner=winner, burden_gap_to_next=gap
    )


# --- Break-even / crossover analysis --------------------------------------------


@dataclass(frozen=True)
class BreakevenResult:
    """Result of searching for a lifecycle ranking crossover between two
    candidates over a finite mission-count range."""

    candidate_a_name: str
    candidate_b_name: str
    mission_range: Tuple[int, int]
    crossover_found: bool
    crossover_mission_count: Optional[int]
    burden_a_at_crossover: Optional[float]
    burden_b_at_crossover: Optional[float]
    leader_at_range_start: Optional[str]
    leader_at_range_end: Optional[str]
    notes: Tuple[str, ...]


def find_breakeven_mission_count(
    candidate_a: TradeResult,
    candidate_b: TradeResult,
    base_config: LifecycleConfig,
    mission_range: Tuple[int, int] = (1, 500),
) -> BreakevenResult:
    """Deterministically search ``mission_range`` (inclusive, both ends
    integers, ``mission_range[0] >= 1``) for the first mission count at
    which the lower-cumulative-burden candidate between ``candidate_a`` and
    ``candidate_b`` changes, using ``base_config`` for every other lifecycle
    assumption (only ``mission_count`` is varied).

    Never extrapolates beyond ``mission_range`` -- if no crossover is found
    within the searched bound, ``crossover_found=False`` and
    ``crossover_mission_count=None`` are returned rather than silently
    assuming one exists beyond the search.
    """
    lo, hi = mission_range
    if not isinstance(lo, int) or not isinstance(hi, int) or lo < 1 or hi < lo:
        raise ValueError(f"mission_range must be (lo, hi) integers with 1 <= lo <= hi, got {mission_range!r}")

    def burdens(mission_count: int) -> Tuple[Optional[float], Optional[float]]:
        cfg = replace(base_config, mission_count=mission_count)
        life_a = compute_lifecycle(candidate_a, cfg)
        life_b = compute_lifecycle(candidate_b, cfg)
        return life_a.cumulative_lifecycle_burden, life_b.cumulative_lifecycle_burden

    burden_a_start, burden_b_start = burdens(lo)
    if burden_a_start is None or burden_b_start is None:
        return BreakevenResult(
            candidate_a_name=candidate_a.name,
            candidate_b_name=candidate_b.name,
            mission_range=(lo, hi),
            crossover_found=False,
            crossover_mission_count=None,
            burden_a_at_crossover=None,
            burden_b_at_crossover=None,
            leader_at_range_start=None,
            leader_at_range_end=None,
            notes=("one or both candidates are infeasible at the start of mission_range; no comparison possible",),
        )

    def leader(a: float, b: float) -> str:
        return candidate_a.name if a < b else (candidate_b.name if b < a else "tie")

    initial_leader = leader(burden_a_start, burden_b_start)
    burden_a_end, burden_b_end = burden_a_start, burden_b_start
    final_leader = initial_leader

    for mission_count in range(lo + 1, hi + 1):
        burden_a, burden_b = burdens(mission_count)
        if burden_a is None or burden_b is None:
            continue
        current_leader = leader(burden_a, burden_b)
        burden_a_end, burden_b_end = burden_a, burden_b
        final_leader = current_leader
        if current_leader != initial_leader and current_leader != "tie":
            return BreakevenResult(
                candidate_a_name=candidate_a.name,
                candidate_b_name=candidate_b.name,
                mission_range=(lo, hi),
                crossover_found=True,
                crossover_mission_count=mission_count,
                burden_a_at_crossover=burden_a,
                burden_b_at_crossover=burden_b,
                leader_at_range_start=initial_leader,
                leader_at_range_end=current_leader,
                notes=(),
            )

    return BreakevenResult(
        candidate_a_name=candidate_a.name,
        candidate_b_name=candidate_b.name,
        mission_range=(lo, hi),
        crossover_found=False,
        crossover_mission_count=None,
        burden_a_at_crossover=burden_a_end,
        burden_b_at_crossover=burden_b_end,
        leader_at_range_start=initial_leader,
        leader_at_range_end=final_leader,
        notes=(f"no ranking crossover found within mission_range={mission_range}",),
    )
