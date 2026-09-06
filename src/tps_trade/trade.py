"""Milestone 4: reusable-vs-ablative TPS engineering trade.

This module is the first place in the project that puts the Milestone 1/2
reusable-TPS transient conduction model and the Milestone 3 ablative
recession model side by side on a common areal-mass basis. It does not
introduce any new thermal physics -- every sizing call here delegates to
the already-verified functions in :mod:`tps_trade.transient` and
:mod:`tps_trade.ablative`.

IMPORTANT: the reusable and ablative models are NOT physically identical
formulations
------------------------------------------------------------------------
The reusable model is driven by a prescribed HOT-SIDE TEMPERATURE history
(a Dirichlet boundary condition on the conduction equation). The ablative
model is driven by a prescribed NET HEAT-FLUX history (an energy input
integrated directly into consumed mass). ``StudyCase`` picks one
illustrative peak temperature and one illustrative heat flux intended to
represent "the same" qualitative entry-like heating event, but there is NO
physical derivation here converting one into the other (that would require
a surface energy balance, which is explicitly out of scope through
Milestone 4). Treat the correspondence between ``t_hot_max`` and
``ablative_heat_flux`` as illustrative and qualitative, not as a derived
equivalence. This mismatch is fundamental to comparing these two
categories of TPS at this stage of the project and is called out
repeatedly (also see the README) rather than hidden.

Scope of this milestone
--------------------------
This module sizes and ranks a small, explicit set of illustrative reusable
and ablative TPS candidates against ONE canonical study case, and reports
a transparent trade table plus a preliminary, case-specific recommendation.
It does NOT implement lifecycle/refurbishment economics, reuse-cycle
degradation, ablative pyrolysis chemistry, a coupled radiative/convective
surface energy balance, or trajectory simulation, and the "recommendation"
it produces is explicitly scoped to "minimum-mass candidate under this
simplified model for this specific study case" -- not "best real spacecraft
TPS" (see ``generate_recommendation``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from .materials import TPSMaterial
from .ablative import (
    AblativeMaterial,
    HeatFluxSegment,
    integrated_heat_load,
    size_ablative_thickness,
)
from .transient import (
    HeatingPulse,
    square_pulse,
    max_stable_time_step,
    size_thickness_transient,
)
from ._validation import (
    require_finite_number,
    require_positive_finite,
    require_nonnegative_finite,
    require_positive_absolute_temperature,
)


# --- Ablative candidate wrapper ----------------------------------------------


@dataclass(frozen=True)
class AblativeCandidate:
    """An ablative material paired with its trade-specific engineering inputs.

    ``retained_thickness`` and ``max_recession`` are NOT material
    properties -- they are engineering inputs to a specific sizing case
    (see :mod:`tps_trade.ablative`), kept here so a small candidate
    database can carry them alongside the material itself.

    max_recession:
        Optional maximum allowable recession depth [m] -- an illustrative
        structural/char-layer allowable, analogous in spirit to the
        reusable model's ``max_service_temperature`` hard limit. If
        given, a candidate whose predicted recession exceeds it is marked
        infeasible by ``size_ablative_candidate``.
    """

    material: AblativeMaterial
    retained_thickness: float
    max_recession: Optional[float] = None

    def __post_init__(self) -> None:
        retained_thickness = require_nonnegative_finite(self.retained_thickness, "retained_thickness")
        object.__setattr__(self, "retained_thickness", retained_thickness)
        if self.max_recession is not None:
            object.__setattr__(
                self, "max_recession", require_positive_finite(self.max_recession, "max_recession")
            )


# --- Canonical study case ------------------------------------------------------


@dataclass(frozen=True)
class StudyCase:
    """One canonical, illustrative entry-like heating event shared by every
    candidate in a trade study.

    Attributes
    ----------
    name:
        Human-readable label for the case (e.g. what it is illustrating).
    t_initial:
        Initial/uniform starting temperature [K] for both models.
    t_hot_max:
        Peak hot-side temperature [K] imposed on REUSABLE candidates (a
        square pulse to this value for ``tau_heat`` seconds, then back to
        ``t_initial``; see ``reusable_heating_history``).
    tau_heat:
        Heating pulse duration [s], used by BOTH the reusable hot-side
        pulse and the ablative heat-flux pulse, so both models see an
        event of the same duration.
    total_time:
        Total simulated duration [s] for the reusable transient solve --
        must be long enough after the pulse ends to capture the peak
        backface temperature.
    t_back_max:
        Reusable backface-temperature limit [K].
    ablative_heat_flux:
        Net heat flux [W/m^2] imposed on ABLATIVE candidates for
        ``tau_heat`` seconds (see ``ablative_heat_flux_history``).
    reusable_thickness_bounds:
        Shared bisection search bracket [m] used for EVERY reusable
        candidate, so no candidate is given a more favorable search range
        than another.
    reusable_n_nodes, reusable_fourier_limit:
        Shared spatial discretization and stability-margin target used for
        EVERY reusable candidate (the actual `dt` still depends on each
        material's own diffusivity, since the stability limit does).

    This is a clearly labeled ILLUSTRATIVE, entry-like case -- it does NOT
    represent a certified vehicle trajectory or heat pulse.
    """

    name: str
    t_initial: float
    t_hot_max: float
    tau_heat: float
    total_time: float
    t_back_max: float
    ablative_heat_flux: float
    reusable_thickness_bounds: Tuple[float, float] = (0.002, 0.08)
    reusable_n_nodes: int = 21
    reusable_fourier_limit: float = 0.4

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string")

        t_initial = require_positive_absolute_temperature(self.t_initial, "t_initial")
        t_hot_max = require_positive_absolute_temperature(self.t_hot_max, "t_hot_max")
        tau_heat = require_positive_finite(self.tau_heat, "tau_heat")
        total_time = require_positive_finite(self.total_time, "total_time")
        t_back_max = require_positive_absolute_temperature(self.t_back_max, "t_back_max")
        ablative_heat_flux = require_nonnegative_finite(self.ablative_heat_flux, "ablative_heat_flux")

        if t_hot_max <= t_initial:
            raise ValueError("t_hot_max must exceed t_initial for a heating case")
        if total_time <= tau_heat:
            raise ValueError("total_time must exceed tau_heat to observe the post-pulse response")

        object.__setattr__(self, "t_initial", t_initial)
        object.__setattr__(self, "t_hot_max", t_hot_max)
        object.__setattr__(self, "tau_heat", tau_heat)
        object.__setattr__(self, "total_time", total_time)
        object.__setattr__(self, "t_back_max", t_back_max)
        object.__setattr__(self, "ablative_heat_flux", ablative_heat_flux)

        t_lo, t_hi = self.reusable_thickness_bounds
        t_lo = require_positive_finite(t_lo, "reusable_thickness_bounds[0]")
        t_hi = require_positive_finite(t_hi, "reusable_thickness_bounds[1]")
        if t_hi <= t_lo:
            raise ValueError("reusable_thickness_bounds upper bound must exceed lower bound")
        object.__setattr__(self, "reusable_thickness_bounds", (t_lo, t_hi))

        if not isinstance(self.reusable_n_nodes, int) or self.reusable_n_nodes < 3:
            raise ValueError(f"reusable_n_nodes must be an integer >= 3, got {self.reusable_n_nodes!r}")
        fourier_limit = require_positive_finite(self.reusable_fourier_limit, "reusable_fourier_limit")
        if fourier_limit > 0.5:
            raise ValueError(f"reusable_fourier_limit must be <= 0.5, got {fourier_limit!r}")
        object.__setattr__(self, "reusable_fourier_limit", fourier_limit)

    @property
    def reusable_heating_history(self) -> HeatingPulse:
        """The shared hot-side temperature history for every reusable candidate."""
        return square_pulse(t_initial=self.t_initial, t_hot=self.t_hot_max, tau_heat=self.tau_heat)

    @property
    def ablative_heat_flux_history(self) -> List[HeatFluxSegment]:
        """The shared net heat-flux history for every ablative candidate."""
        return [HeatFluxSegment(heat_flux=self.ablative_heat_flux, duration=self.tau_heat)]

    def ablative_total_heat_load(self) -> float:
        """Total heat load Q'' [J/m^2] implied by ``ablative_heat_flux_history``."""
        return integrated_heat_load(self.ablative_heat_flux_history)


# --- Structured trade result ---------------------------------------------------


@dataclass(frozen=True)
class ReusableTradeDetail:
    """Reusable-category-specific trade detail (see TradeResult)."""

    peak_backface_temperature: float
    thermal_diffusivity: float
    t_hot_max: float
    max_service_temperature: float


@dataclass(frozen=True)
class AblativeTradeDetail:
    """Ablative-category-specific trade detail (see TradeResult)."""

    total_heat_load: float
    effective_heat_of_ablation: float
    consumed_areal_mass: float
    remaining_areal_mass: float
    consumed_mass_fraction: float
    retained_thickness: float


@dataclass(frozen=True)
class TradeResult:
    """Common trade-comparison result for one candidate (either category).

    Common fields are meaningful across both categories; category-specific
    numbers live in exactly one of ``reusable_detail`` / ``ablative_detail``
    (whichever matches ``category``) so unlike quantities (e.g. a
    temperature margin vs. a recession margin) are never forced into a
    single misleadingly-generic field.

    ``governing_metric_name``/``governing_metric_value`` and
    ``design_margin`` are intentionally NOT the same physical quantity
    across categories -- see the class attributes below.
    """

    name: str
    category: str  # "reusable" or "ablative"
    feasible: bool
    required_thickness: Optional[float]  # m
    initial_areal_mass: Optional[float]  # kg/m^2
    governing_metric_name: str  # "peak_backface_temperature" or "recession_depth"
    governing_metric_value: Optional[float]
    design_margin: Optional[float]  # units given by margin_units; NOT a factor of safety
    margin_units: str  # "K" for reusable, "m" for ablative
    key_capability_limit: Optional[float]  # max_service_temperature [K], or max_recession [m]
    notes: Tuple[str, ...]
    reusable_detail: Optional[ReusableTradeDetail] = None
    ablative_detail: Optional[AblativeTradeDetail] = None


# --- Reusable candidate sizing ---------------------------------------------------


def size_reusable_candidate(material: TPSMaterial, study_case: StudyCase) -> TradeResult:
    """Size one reusable candidate against ``study_case`` using the verified
    transient conduction model (:func:`tps_trade.transient.size_thickness_transient`).

    Marked infeasible WITHOUT attempting to size a thickness if
    ``study_case.t_hot_max > material.max_service_temperature`` -- this
    model never silently sizes a material beyond its stated temperature
    capability. Also marked infeasible if the transient bisection sizing
    itself cannot find a feasible thickness within
    ``study_case.reusable_thickness_bounds``.
    """
    if study_case.t_hot_max > material.max_service_temperature:
        return TradeResult(
            name=material.name,
            category="reusable",
            feasible=False,
            required_thickness=None,
            initial_areal_mass=None,
            governing_metric_name="peak_backface_temperature",
            governing_metric_value=None,
            design_margin=None,
            margin_units="K",
            key_capability_limit=material.max_service_temperature,
            notes=(
                f"infeasible: study case t_hot_max={study_case.t_hot_max:.1f} K exceeds "
                f"material.max_service_temperature={material.max_service_temperature:.1f} K; "
                "not sized",
            ),
        )

    alpha = material.thermal_diffusivity()
    dx_min = study_case.reusable_thickness_bounds[0] / (study_case.reusable_n_nodes - 1)
    dt = max_stable_time_step(alpha, dx_min, study_case.reusable_fourier_limit)

    try:
        sizing = size_thickness_transient(
            material,
            study_case.reusable_heating_history,
            total_time=study_case.total_time,
            t_initial=study_case.t_initial,
            t_back_max=study_case.t_back_max,
            thickness_bounds=study_case.reusable_thickness_bounds,
            dt=dt,
            n_nodes=study_case.reusable_n_nodes,
        )
    except ValueError as exc:
        return TradeResult(
            name=material.name,
            category="reusable",
            feasible=False,
            required_thickness=None,
            initial_areal_mass=None,
            governing_metric_name="peak_backface_temperature",
            governing_metric_value=None,
            design_margin=None,
            margin_units="K",
            key_capability_limit=material.max_service_temperature,
            notes=(f"infeasible: transient sizing failed within thickness bounds ({exc})",),
        )

    detail = ReusableTradeDetail(
        peak_backface_temperature=sizing.peak_backface_temperature,
        thermal_diffusivity=alpha,
        t_hot_max=study_case.t_hot_max,
        max_service_temperature=material.max_service_temperature,
    )
    return TradeResult(
        name=material.name,
        category="reusable",
        feasible=True,
        required_thickness=sizing.thickness,
        initial_areal_mass=sizing.areal_mass,
        governing_metric_name="peak_backface_temperature",
        governing_metric_value=sizing.peak_backface_temperature,
        design_margin=sizing.margin_temperature,
        margin_units="K",
        key_capability_limit=material.max_service_temperature,
        notes=(),
        reusable_detail=detail,
    )


# --- Ablative candidate sizing ---------------------------------------------------


def size_ablative_candidate(candidate: AblativeCandidate, study_case: StudyCase) -> TradeResult:
    """Size one ablative candidate against ``study_case`` using the verified
    recession model (:func:`tps_trade.ablative.size_ablative_thickness`).

    Marked infeasible only if ``candidate.max_recession`` is supplied and
    the predicted recession exceeds it; otherwise this first-order model
    has no other intrinsic infeasibility mode (unlike the reusable model,
    it does not check a surface-temperature capability here, since this
    milestone's ablative model does not compute a surface temperature --
    see the module and README limitations).
    """
    total_heat_load = study_case.ablative_total_heat_load()
    sizing = size_ablative_thickness(
        candidate.material,
        total_heat_load,
        candidate.retained_thickness,
        max_recession=candidate.max_recession,
    )

    notes: List[str] = []
    feasible = True
    if candidate.max_recession is not None:
        if sizing.recession_margin is not None and sizing.recession_margin < 0.0:
            feasible = False
            notes.append(
                f"infeasible: predicted recession {sizing.recession_depth:.4f} m exceeds "
                f"max_recession={candidate.max_recession:.4f} m"
            )
    else:
        notes.append("no max_recession allowable supplied; design_margin is not evaluated (None)")

    design_margin = sizing.recession_margin

    detail = AblativeTradeDetail(
        total_heat_load=total_heat_load,
        effective_heat_of_ablation=candidate.material.effective_heat_of_ablation,
        consumed_areal_mass=sizing.consumed_areal_mass,
        remaining_areal_mass=sizing.remaining_areal_mass,
        consumed_mass_fraction=sizing.consumed_mass_fraction,
        retained_thickness=sizing.retained_thickness,
    )
    return TradeResult(
        name=candidate.material.name,
        category="ablative",
        feasible=feasible,
        required_thickness=sizing.initial_thickness,
        initial_areal_mass=sizing.initial_areal_mass,
        governing_metric_name="recession_depth",
        governing_metric_value=sizing.recession_depth,
        design_margin=design_margin,
        margin_units="m",
        key_capability_limit=candidate.max_recession,
        notes=tuple(notes),
        ablative_detail=detail,
    )


# --- Fairness / common-case enforcement -------------------------------------------


def validate_candidate_database(
    reusable_materials: Sequence[TPSMaterial], ablative_candidates: Sequence[AblativeCandidate]
) -> None:
    """Validate a candidate database before running a trade study.

    Checks:
    - every candidate name is unique across BOTH categories (so a trade
      table or ranking can never silently conflate two candidates);
    - every reusable entry is a ``TPSMaterial`` and every ablative entry is
      an ``AblativeCandidate`` (category consistency).
    """
    names: List[str] = []
    for material in reusable_materials:
        if not isinstance(material, TPSMaterial):
            raise TypeError(f"reusable candidate {material!r} must be a TPSMaterial")
        names.append(material.name)
    for candidate in ablative_candidates:
        if not isinstance(candidate, AblativeCandidate):
            raise TypeError(f"ablative candidate {candidate!r} must be an AblativeCandidate")
        names.append(candidate.material.name)

    duplicates = {name for name in names if names.count(name) > 1}
    if duplicates:
        raise ValueError(f"duplicate candidate names in database: {sorted(duplicates)}")


def run_trade_study(
    study_case: StudyCase,
    reusable_materials: Sequence[TPSMaterial],
    ablative_candidates: Sequence[AblativeCandidate],
) -> List[TradeResult]:
    """Size every candidate against the SAME ``study_case`` and return all results.

    Centralizing the sizing calls here (rather than callers building their
    own per-candidate boundary conditions) is what guarantees every
    reusable candidate sees the identical hot-side history/backface limit/
    thickness bounds, and every ablative candidate sees the identical
    heat-flux history/retained-thickness convention -- i.e. it is the
    apples-to-oranges-prevention mechanism described in the module
    docstring, not a separate runtime check bolted on afterward.
    """
    validate_candidate_database(reusable_materials, ablative_candidates)
    results: List[TradeResult] = [size_reusable_candidate(m, study_case) for m in reusable_materials]
    results += [size_ablative_candidate(c, study_case) for c in ablative_candidates]
    return results


# --- Ranking ------------------------------------------------------------------------


def rank_feasible_by_mass(results: Sequence[TradeResult]) -> List[TradeResult]:
    """Deterministic ranking of feasible candidates by initial areal mass.

    1. Infeasible candidates are excluded entirely -- a candidate can never
       be selected solely because it has lower mass if it is infeasible.
    2. Feasible candidates are ranked ascending by ``initial_areal_mass``.
    3. Ties (or near-ties) are broken by GREATER ``design_margin`` (a
       candidate with ``design_margin=None`` is treated as having the
       least margin for tie-break purposes).
    4. Any remaining tie is broken by candidate name, so the ordering is
       fully deterministic even for exactly equal mass and margin.
    """
    feasible = [r for r in results if r.feasible and r.initial_areal_mass is not None]

    def sort_key(result: TradeResult):
        margin = result.design_margin if result.design_margin is not None else float("-inf")
        return (result.initial_areal_mass, -margin, result.name)

    return sorted(feasible, key=sort_key)


@dataclass(frozen=True)
class TradeSummary:
    """Summary of a ranked trade study."""

    ranked_feasible: Tuple[TradeResult, ...]
    winner: Optional[TradeResult]
    mass_gap_to_next: Optional[float]  # kg/m^2; None if fewer than 2 feasible candidates


def summarize_trade(results: Sequence[TradeResult]) -> TradeSummary:
    """Rank ``results`` and summarize the lightest feasible candidate."""
    ranked = rank_feasible_by_mass(results)
    winner = ranked[0] if ranked else None
    gap = None
    if winner is not None and len(ranked) > 1:
        gap = ranked[1].initial_areal_mass - winner.initial_areal_mass
    return TradeSummary(ranked_feasible=tuple(ranked), winner=winner, mass_gap_to_next=gap)


# --- Preliminary recommendation -----------------------------------------------------


def generate_recommendation(study_case: StudyCase, summary: TradeSummary) -> str:
    """A preliminary, case-specific recommendation -- NOT a claim about the
    best real spacecraft TPS. See module docstring.
    """
    if summary.winner is None:
        return (
            f"No feasible candidate was found for study case '{study_case.name}' "
            "within the given candidate database and search bounds."
        )

    winner = summary.winner
    gap_text = (
        f", {summary.mass_gap_to_next:.2f} kg/m^2 lighter than the next feasible candidate"
        if summary.mass_gap_to_next is not None
        else " (no other feasible candidate to compare against)"
    )

    return (
        f"Minimum-areal-mass FEASIBLE candidate under this simplified model for "
        f"study case '{study_case.name}': '{winner.name}' ({winner.category}) at "
        f"{winner.initial_areal_mass:.2f} kg/m^2{gap_text}.\n"
        "\n"
        "This is the minimum-mass candidate UNDER THIS SIMPLIFIED MODEL for THIS "
        "SPECIFIC ILLUSTRATIVE STUDY CASE -- it is NOT a claim about the best real "
        "spacecraft TPS. In particular:\n"
        "  - Reusable candidates avoid modeled material consumption during the event.\n"
        "  - Ablative candidates consume material (recession/mass loss) during the event.\n"
        "  - Lifecycle and reusability (refurbishment, reuse-cycle degradation) have "
        "not been quantified anywhere in this project yet.\n"
        "  - Surface chemistry and the coupling between heating and the material's "
        "thermal response are both simplified in both models.\n"
        "  - This recommendation is therefore mission-case-specific and preliminary."
    )
