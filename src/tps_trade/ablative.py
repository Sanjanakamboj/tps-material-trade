"""First-order ablative TPS sizing: a lumped surface energy-balance model.

Milestone 3 scope and assumptions
------------------------------------
This module implements a deliberately simple, **lumped** ablation model. It
assumes:

- an imposed NET heat-flux history ``q''(t)`` [W/m^2] reaching the ablating
  surface (net of whatever surface processes already balanced away --
  this model does not compute a surface energy balance itself);
- all of the absorbed energy over the event goes toward consuming
  ("ablating") material at a single, constant **effective heat of
  ablation** ``H_eff`` [J/kg] -- i.e. it costs ``H_eff`` joules of net
  absorbed heat to remove one kilogram of material per unit area;
- a uniform, constant material density ``rho``;
- **no** detailed internal conduction or pyrolysis-zone coupling;
- **no** char-layer thermal resistance;
- **no** radiative feedback / reradiation modeling;
- **no** surface chemistry;
- **no** blowing (mass-injection) correction to the heat transfer.

This is a first-order, "energy in, mass out" bookkeeping model -- it is
explicitly NOT a high-fidelity ablation solver, and does not represent
pyrolysis kinetics, a moving-boundary conduction solution, char-layer
thermochemistry, or a coupled surface energy balance. Those remain out of
scope for this milestone (and are not necessarily in scope for the project
at all).

Core relations
----------------
Total (net) heat load absorbed at the surface over the event::

    Q'' = integral q''(t) dt        [J/m^2]

Consumed (ablated) areal mass::

    m''_consumed = Q'' / H_eff       [kg/m^2]

Recession depth (thickness consumed)::

    delta = m''_consumed / rho = Q'' / (rho * H_eff)      [m]

Required initial thickness, given an explicit retained-thickness
requirement ``t_retained`` (an engineering input to this model, not a
value this module invents or derives)::

    t_initial = delta + t_retained

Mass decomposition (verified in the test suite to hold within numerical
tolerance)::

    m''_initial = rho * t_initial
    m''_remaining = rho * t_retained
    m''_consumed = rho * delta
    m''_initial = m''_remaining + m''_consumed

Design margin (dimensional, NOT a factor of safety) for a trial initial
thickness ``t_trial``, mirroring the Milestone 1/2 thickness-margin
convention::

    Margin_t = t_trial - delta - t_retained

At the exactly sized thickness (``t_trial = delta + t_retained``),
``Margin_t ~ 0``.

Heat-flux sign convention
----------------------------
Heat flux in this model is net heating flowing INTO the ablating surface,
and this module rejects negative heat flux: for this preliminary model, the
heating history is treated as net-heating-only (see ``HeatFluxSegment`` and
``total_heat_load_sampled``). A history that goes net-cooling for part of
an event is out of scope here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple, Union

from ._validation import (
    require_finite_number,
    require_positive_finite,
    require_nonnegative_finite,
    require_positive_absolute_temperature,
)


@dataclass(frozen=True)
class AblativeMaterial:
    """A homogeneous ablative TPS material for the first-order model.

    Attributes
    ----------
    name:
        Human-readable identifier.
    density:
        Bulk (virgin) density, rho [kg/m^3]. Must be positive and finite.
    effective_heat_of_ablation:
        H_eff [J/kg]: net absorbed energy per unit area consumed to remove
        one unit of areal mass, i.e. the single lumped parameter standing
        in for pyrolysis, phase change, and reradiation losses combined.
        Must be positive and finite.
    max_usable_temperature:
        Optional temperature capability [K] (e.g. a virgin-material
        decomposition-onset temperature), for future use. Validated if
        provided.
    conductivity, specific_heat:
        Optional retained thermal properties [W/(m*K)], [J/(kg*K)], so an
        ablative material could later be reused with the Milestone 1/2
        conduction models. Not used by this milestone's ablation
        relations; validated if provided.

    As with ``TPSMaterial``, any properties not traceable to a literature
    source are illustrative, not authoritative design allowables.
    """

    name: str
    density: float
    effective_heat_of_ablation: float
    max_usable_temperature: Optional[float] = None
    conductivity: Optional[float] = None
    specific_heat: Optional[float] = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string")

        density = require_positive_finite(self.density, "density")
        h_eff = require_positive_finite(
            self.effective_heat_of_ablation, "effective_heat_of_ablation"
        )
        object.__setattr__(self, "density", density)
        object.__setattr__(self, "effective_heat_of_ablation", h_eff)

        if self.max_usable_temperature is not None:
            object.__setattr__(
                self,
                "max_usable_temperature",
                require_positive_absolute_temperature(
                    self.max_usable_temperature, "max_usable_temperature"
                ),
            )
        if self.conductivity is not None:
            object.__setattr__(
                self, "conductivity", require_positive_finite(self.conductivity, "conductivity")
            )
        if self.specific_heat is not None:
            object.__setattr__(
                self, "specific_heat", require_positive_finite(self.specific_heat, "specific_heat")
            )


# --- Heat-flux history representation ---------------------------------------


@dataclass(frozen=True)
class HeatFluxSegment:
    """One constant-heat-flux segment of a piecewise heating history.

    heat_flux: net heat flux [W/m^2] during this segment. Must be >= 0 --
    this preliminary model treats the history as net-heating-only and
    rejects negative heat flux (see module docstring).
    duration: segment duration [s]. Must be > 0.
    """

    heat_flux: float
    duration: float

    def __post_init__(self) -> None:
        heat_flux = require_nonnegative_finite(self.heat_flux, "heat_flux")
        duration = require_positive_finite(self.duration, "duration")
        object.__setattr__(self, "heat_flux", heat_flux)
        object.__setattr__(self, "duration", duration)


def total_heat_load_constant(heat_flux: float, duration: float) -> float:
    """Exact heat load for a single constant heat flux over a duration.

    Q'' = q'' * tau     [J/m^2]
    """
    segment = HeatFluxSegment(heat_flux=heat_flux, duration=duration)
    return segment.heat_flux * segment.duration


def total_heat_load_piecewise(segments: Sequence[HeatFluxSegment]) -> float:
    """Exact heat load for a piecewise-constant heat-flux history.

    Q'' = sum_i q''_i * tau_i     [J/m^2]
    """
    if len(segments) == 0:
        raise ValueError("segments must be a non-empty sequence of HeatFluxSegment")
    for i, segment in enumerate(segments):
        if not isinstance(segment, HeatFluxSegment):
            raise TypeError(f"segments[{i}] must be a HeatFluxSegment, got {type(segment)!r}")
    return sum(segment.heat_flux * segment.duration for segment in segments)


def total_heat_load_sampled(times: Sequence[float], heat_flux: Sequence[float]) -> float:
    """Heat load from a sampled history via the trapezoidal rule.

    Q'' ~= sum_i 0.5*(q''[i] + q''[i+1]) * (t[i+1] - t[i])     [J/m^2]

    ``times`` must be strictly increasing, finite, and the same length as
    ``heat_flux`` (>= 2 samples). ``heat_flux`` values must be finite and
    >= 0 (see module docstring on the net-heating-only convention).
    Deterministic: repeated calls with the same inputs return the same
    result (plain arithmetic, no randomness or mutable state).
    """
    if len(times) != len(heat_flux):
        raise ValueError(
            f"times and heat_flux must be the same length, got {len(times)} and {len(heat_flux)}"
        )
    if len(times) < 2:
        raise ValueError("times/heat_flux must have at least 2 samples to integrate")

    validated_times: List[float] = []
    for i, t in enumerate(times):
        t = require_finite_number(t, f"times[{i}]")
        if i > 0 and t <= validated_times[i - 1]:
            raise ValueError(
                f"times must be strictly increasing; times[{i}]={t!r} <= times[{i-1}]={validated_times[i-1]!r}"
            )
        validated_times.append(t)

    validated_flux: List[float] = [
        require_nonnegative_finite(q, f"heat_flux[{i}]") for i, q in enumerate(heat_flux)
    ]

    total = 0.0
    for i in range(len(validated_times) - 1):
        dt = validated_times[i + 1] - validated_times[i]
        total += 0.5 * (validated_flux[i] + validated_flux[i + 1]) * dt
    return total


HeatFluxHistory = Union[Sequence[HeatFluxSegment], Tuple[Sequence[float], Sequence[float]]]


def integrated_heat_load(history: HeatFluxHistory) -> float:
    """Dispatch to the appropriate exact/numerical heat-load integration.

    Accepts either:
    - a sequence of ``HeatFluxSegment`` (piecewise-constant, exact), or
    - a ``(times, heat_flux)`` pair of equal-length sequences (sampled,
      trapezoidal).
    """
    if isinstance(history, tuple) and len(history) == 2 and not isinstance(history[0], HeatFluxSegment):
        times, heat_flux = history
        return total_heat_load_sampled(times, heat_flux)
    if isinstance(history, (list, tuple)) and len(history) > 0 and isinstance(history[0], HeatFluxSegment):
        return total_heat_load_piecewise(history)
    raise TypeError(
        "history must be a non-empty sequence of HeatFluxSegment, or a "
        "(times, heat_flux) pair of equal-length sequences"
    )


# --- Core ablation relations --------------------------------------------------


def consumed_areal_mass(total_heat_load: float, effective_heat_of_ablation: float) -> float:
    """Consumed areal mass: m''_consumed = Q'' / H_eff     [kg/m^2]."""
    total_heat_load = require_nonnegative_finite(total_heat_load, "total_heat_load")
    h_eff = require_positive_finite(effective_heat_of_ablation, "effective_heat_of_ablation")
    return total_heat_load / h_eff


def recession_depth(total_heat_load: float, density: float, effective_heat_of_ablation: float) -> float:
    """Recession (consumed thickness): delta = Q'' / (rho * H_eff)     [m].

    Equivalent to consumed_areal_mass(...) / density.
    """
    density = require_positive_finite(density, "density")
    m_consumed = consumed_areal_mass(total_heat_load, effective_heat_of_ablation)
    return m_consumed / density


# --- Structured results -------------------------------------------------------


@dataclass(frozen=True)
class AblativeSizingResult:
    """Structured result of sizing an ablative TPS initial thickness."""

    material: AblativeMaterial
    total_heat_load: float
    effective_heat_of_ablation: float
    consumed_areal_mass: float
    recession_depth: float
    retained_thickness: float
    initial_thickness: float
    initial_areal_mass: float
    remaining_areal_mass: float
    consumed_mass_fraction: float
    recession_margin: Optional[float] = None


def size_ablative_thickness(
    material: AblativeMaterial,
    total_heat_load: float,
    retained_thickness: float,
    max_recession: Optional[float] = None,
) -> AblativeSizingResult:
    """Size the required initial ablative thickness for a given heat load.

    t_initial = delta + t_retained, with the full mass decomposition
    (initial/remaining/consumed areal mass) and consumed-mass fraction.

    Parameters
    ----------
    material:
        Ablative material (supplies rho and H_eff).
    total_heat_load:
        Q'' [J/m^2], the total net heat load for the event. Must be >= 0.
    retained_thickness:
        t_retained [m], an explicit engineering input (structural margin,
        insulation, uncertainty, attachment protection) -- this module
        does not invent or certify this value. Must be >= 0.
    max_recession:
        Optional maximum allowable recession depth [m]. If given, a
        recession margin ``Margin_delta = max_recession - delta`` is
        reported (dimensional, not a factor of safety).
    """
    total_heat_load = require_nonnegative_finite(total_heat_load, "total_heat_load")
    retained_thickness = require_nonnegative_finite(retained_thickness, "retained_thickness")

    delta = recession_depth(total_heat_load, material.density, material.effective_heat_of_ablation)
    m_consumed = consumed_areal_mass(total_heat_load, material.effective_heat_of_ablation)

    t_initial = delta + retained_thickness
    m_initial = material.density * t_initial
    m_remaining = material.density * retained_thickness
    consumed_fraction = (m_consumed / m_initial) if m_initial > 0.0 else 0.0

    recession_margin = None
    if max_recession is not None:
        max_recession = require_nonnegative_finite(max_recession, "max_recession")
        recession_margin = max_recession - delta

    return AblativeSizingResult(
        material=material,
        total_heat_load=total_heat_load,
        effective_heat_of_ablation=material.effective_heat_of_ablation,
        consumed_areal_mass=m_consumed,
        recession_depth=delta,
        retained_thickness=retained_thickness,
        initial_thickness=t_initial,
        initial_areal_mass=m_initial,
        remaining_areal_mass=m_remaining,
        consumed_mass_fraction=consumed_fraction,
        recession_margin=recession_margin,
    )


@dataclass(frozen=True)
class AblativeTrialResult:
    """Structured result of evaluating a specified trial initial thickness
    against a heat-load case (see ``evaluate_trial_thickness``)."""

    material: AblativeMaterial
    trial_thickness: float
    total_heat_load: float
    consumed_thickness: float
    remaining_thickness: float
    retained_thickness: float
    margin_thickness: float
    passed: bool


def evaluate_trial_thickness(
    material: AblativeMaterial,
    trial_thickness: float,
    total_heat_load: float,
    retained_thickness: float,
) -> AblativeTrialResult:
    """Evaluate a specified initial ablative thickness under a heat-load case.

    Margin_t = t_trial - delta - t_retained

    Passes (``passed=True``) iff t_trial - delta >= t_retained, i.e.
    Margin_t >= 0.
    """
    trial_thickness = require_positive_finite(trial_thickness, "trial_thickness")
    total_heat_load = require_nonnegative_finite(total_heat_load, "total_heat_load")
    retained_thickness = require_nonnegative_finite(retained_thickness, "retained_thickness")

    delta = recession_depth(total_heat_load, material.density, material.effective_heat_of_ablation)
    remaining_thickness = trial_thickness - delta
    margin_thickness = trial_thickness - delta - retained_thickness
    passed = margin_thickness >= 0.0

    return AblativeTrialResult(
        material=material,
        trial_thickness=trial_thickness,
        total_heat_load=total_heat_load,
        consumed_thickness=delta,
        remaining_thickness=remaining_thickness,
        retained_thickness=retained_thickness,
        margin_thickness=margin_thickness,
        passed=passed,
    )
