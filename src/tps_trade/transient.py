"""Transient (time-dependent) 1-D conduction through a TPS slab.

This module extends the Milestone 1 steady conduction model
(:mod:`tps_trade.conduction`) with a finite-difference solution of the
transient heat equation, so a slab can be sized against a finite-duration
heating pulse instead of only a steady prescribed hot-side
temperature/heat-flux pair.

Coordinate convention (same as Milestone 1)
--------------------------------------------
::

    hot surface (external environment)
    x = 0,  T = T_hot(t)     <- prescribed temperature history
    |
    |  TPS thickness t_slab
    |
    x = t_slab,  T = T_back(t)   <- insulated OR prescribed (see below)

- x increases from the hot surface (x=0) toward the backface (x=t_slab).
- All temperatures are absolute (K) and must be > 0.
- Thickness is in meters, > 0.

Governing equation
--------------------
Transient 1-D conduction with constant properties and no internal heat
generation::

    dT/dt = alpha * d^2T/dx^2

where the thermal diffusivity is::

    alpha = k / (rho * cp)      [m^2/s]

This requires ``specific_heat`` (cp) to be set on the material -- cp remains
optional on ``TPSMaterial`` for the steady model, but is mandatory here.

Numerical method
------------------
Explicit forward-time, centered-space (FTCS) finite differences on a uniform
grid of ``n_nodes`` nodes from x=0 to x=t_slab, chosen deliberately over
Crank-Nicolson for transparency: every update is a plain, inspectable
stencil with no linear solve.

Interior node update::

    T_new[i] = T[i] + Fo * (T[i+1] - 2*T[i] + T[i-1])

where the (mesh) Fourier number is::

    Fo = alpha * dt / dx^2

Stability (this module enforces this and raises rather than silently running
an unstable step)::

    Fo <= 0.5

Boundary conditions
----------------------
- Hot side (x=0): Dirichlet, prescribed temperature history T_hot(t), given
  either as a constant or as a callable ``t -> temperature`` (see
  ``square_pulse`` for a ready-made finite-duration pulse helper).
- Backface (x=t_slab): exactly one of://
    - ``"insulated"`` (primary/default): zero-gradient, dT/dx = 0, implemented
      via the standard ghost-node reflection for FTCS::

          T_new[-1] = T[-1] + 2*Fo*(T[-2] - T[-1])

    - ``"prescribed"``: Dirichlet, a second temperature history (constant or
      callable) supplied via ``backface_temperature``.

  These two semantics are never mixed: ``backface_temperature`` must be
  omitted for ``"insulated"`` and required for ``"prescribed"``.

Important physical caveat
----------------------------
As in Milestone 1, prescribing a hot-side TEMPERATURE history directly is a
simplified mathematical boundary condition, not a surface energy balance --
it does not represent convective or radiative heating, and material
properties are held constant (no temperature dependence). This module also
does not model ablation, pyrolysis, or mass loss. See the project README for
the full list of what is intentionally out of scope.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence, Union

from .materials import TPSMaterial
from ._validation import (
    require_finite_number,
    require_positive_finite,
    require_positive_absolute_temperature,
)

TemperatureHistory = Union[float, Callable[[float], float]]


def _as_temperature_function(value: TemperatureHistory, name: str) -> Callable[[float], float]:
    """Normalize a constant or callable temperature history to a callable.

    A plain number is validated once, up front, as a positive finite
    absolute temperature and wrapped in a constant function. A callable is
    trusted to be validated by the caller of the returned function (each
    solver time step feeds its output straight into node-temperature
    validation as part of the field itself).
    """
    if callable(value):
        return value
    value = require_positive_absolute_temperature(value, name)
    return lambda _t: value


def max_stable_time_step(alpha: float, dx: float, fourier_limit: float = 0.5) -> float:
    """Largest dt satisfying Fo = alpha*dt/dx^2 <= fourier_limit.

    A convenience helper for choosing dt; solve_transient_conduction still
    independently enforces the stability criterion on whatever dt it is
    actually given.
    """
    alpha = require_positive_finite(alpha, "alpha")
    dx = require_positive_finite(dx, "dx")
    fourier_limit = require_positive_finite(fourier_limit, "fourier_limit")
    return fourier_limit * dx * dx / alpha


@dataclass(frozen=True)
class HeatingPulse:
    """A square (on/off) hot-side temperature history.

    T_hot(t) = t_hot           for 0 <= t < tau_heat
             = t_soak          for t >= tau_heat   (defaults to t_initial)

    Callable directly as ``pulse(t)``. This is a deliberately simple,
    illustrative finite-duration heating case -- it is NOT a real
    atmospheric-entry heat-rate trajectory.
    """

    t_initial: float
    t_hot: float
    tau_heat: float
    t_soak: Optional[float] = None
    total_time: Optional[float] = None

    def __post_init__(self) -> None:
        t_initial = require_positive_absolute_temperature(self.t_initial, "t_initial")
        t_hot = require_positive_absolute_temperature(self.t_hot, "t_hot")
        tau_heat = require_positive_finite(self.tau_heat, "tau_heat")
        object.__setattr__(self, "t_initial", t_initial)
        object.__setattr__(self, "t_hot", t_hot)
        object.__setattr__(self, "tau_heat", tau_heat)
        if self.t_soak is not None:
            object.__setattr__(
                self, "t_soak", require_positive_absolute_temperature(self.t_soak, "t_soak")
            )
        if self.total_time is not None:
            object.__setattr__(
                self, "total_time", require_positive_finite(self.total_time, "total_time")
            )

    def __call__(self, t: float) -> float:
        return self.t_hot if t < self.tau_heat else (self.t_soak if self.t_soak is not None else self.t_initial)


def square_pulse(
    t_initial: float,
    t_hot: float,
    tau_heat: float,
    t_soak: Optional[float] = None,
    total_time: Optional[float] = None,
) -> HeatingPulse:
    """Build a simple square-wave hot-side heating pulse.

    See ``HeatingPulse`` for the exact temperature history definition. This
    is sufficient to compare a short pulse against a long pulse, but it is
    not a claim about any real entry heat-rate trajectory.
    """
    return HeatingPulse(t_initial=t_initial, t_hot=t_hot, tau_heat=tau_heat, t_soak=t_soak, total_time=total_time)


@dataclass(frozen=True)
class TransientResult:
    """Structured result of a transient conduction solve.

    ``temperature_field[k][i]`` is the temperature at time index k
    (``t[k]``) and spatial node index i (``x[i]``), i.e. field[time][space].

    ``hot_side_history[0]`` and ``backface_history[0]`` are the t=0 INITIAL
    CONDITION (uniform ``t_initial``), not the boundary condition -- the
    prescribed hot-side (and, if applicable, backface) boundary conditions
    are applied starting at time index 1 (``t[1]``) onward.
    """

    material: TPSMaterial
    thickness: float
    x: List[float]
    t: List[float]
    temperature_field: List[List[float]]
    hot_side_history: List[float]
    backface_history: List[float]
    peak_backface_temperature: float
    time_of_peak_backface_temperature: float
    fourier_number: float
    dx: float
    dt: float
    n_nodes: int
    n_steps: int
    backface_condition: str


def solve_transient_conduction(
    material: TPSMaterial,
    thickness: float,
    t_initial: float,
    hot_side_temperature: TemperatureHistory,
    total_time: float,
    dt: float,
    n_nodes: int = 21,
    backface: str = "insulated",
    backface_temperature: Optional[TemperatureHistory] = None,
) -> TransientResult:
    """Solve transient 1-D conduction through a uniform TPS slab via FTCS.

    Parameters
    ----------
    material:
        TPS material; must have ``specific_heat`` set.
    thickness:
        Slab thickness [m], > 0.
    t_initial:
        Uniform initial temperature T(x,0) [K], > 0.
    hot_side_temperature:
        Prescribed hot-side (x=0) temperature history: a constant [K], or a
        callable ``t -> T_hot(t)`` [K].
    total_time:
        Total simulated duration [s], > 0.
    dt:
        Time step [s], > 0. Chosen explicitly by the caller (see
        ``max_stable_time_step`` for a helper), and independently checked
        against the Fourier-number stability limit below.
    n_nodes:
        Number of spatial nodes (including both boundary nodes), >= 3.
    backface:
        ``"insulated"`` (default) for a zero-gradient backface, or
        ``"prescribed"`` for a Dirichlet backface temperature history
        (requires ``backface_temperature``).
    backface_temperature:
        Required (and only used) when ``backface="prescribed"``: a constant
        [K] or callable ``t -> T_back(t)``.

    Raises
    ------
    ValueError
        For invalid/non-finite inputs, a missing ``specific_heat``, an
        unrecognized ``backface`` value, mismatched ``backface_temperature``
        usage, or a Fourier number exceeding the 0.5 stability limit.
    """
    if material.specific_heat is None:
        raise ValueError(
            "solve_transient_conduction requires a material with specific_heat "
            f"(cp) set; material {material.name!r} has specific_heat=None"
        )

    thickness = require_positive_finite(thickness, "thickness")
    t_initial = require_positive_absolute_temperature(t_initial, "t_initial")
    total_time = require_positive_finite(total_time, "total_time")
    dt = require_positive_finite(dt, "dt")

    if not isinstance(n_nodes, int) or n_nodes < 3:
        raise ValueError(f"n_nodes must be an integer >= 3, got {n_nodes!r}")

    if backface not in ("insulated", "prescribed"):
        raise ValueError(f"backface must be 'insulated' or 'prescribed', got {backface!r}")
    if backface == "insulated" and backface_temperature is not None:
        raise ValueError("backface_temperature must not be given when backface='insulated'")
    if backface == "prescribed" and backface_temperature is None:
        raise ValueError("backface_temperature is required when backface='prescribed'")

    alpha = material.thermal_diffusivity()
    dx = thickness / (n_nodes - 1)
    fourier_number = alpha * dt / dx**2
    if fourier_number > 0.5:
        raise ValueError(
            "Explicit FTCS stability criterion violated: Fourier number "
            f"Fo = alpha*dt/dx^2 = {fourier_number:.4f} > 0.5. Reduce dt, "
            "increase n_nodes' spacing (dx), or otherwise adjust the "
            "discretization."
        )

    hot_func = _as_temperature_function(hot_side_temperature, "hot_side_temperature")
    back_func = (
        _as_temperature_function(backface_temperature, "backface_temperature")
        if backface == "prescribed"
        else None
    )

    n_steps = round(total_time / dt)
    if n_steps < 1:
        raise ValueError("total_time must correspond to at least one time step of size dt")

    x = [i * dx for i in range(n_nodes)]
    t_grid = [step * dt for step in range(n_steps + 1)]

    T: List[float] = [t_initial] * n_nodes
    field: List[List[float]] = [list(T)]
    hot_hist: List[float] = [T[0]]
    back_hist: List[float] = [T[-1]]

    for step in range(1, n_steps + 1):
        current_time = t_grid[step]
        T_new = list(T)
        for i in range(1, n_nodes - 1):
            T_new[i] = T[i] + fourier_number * (T[i + 1] - 2.0 * T[i] + T[i - 1])

        T_new[0] = require_positive_absolute_temperature(
            hot_func(current_time), "hot_side_temperature(t)"
        )

        if backface == "insulated":
            T_new[-1] = T[-1] + 2.0 * fourier_number * (T[-2] - T[-1])
        else:
            T_new[-1] = require_positive_absolute_temperature(
                back_func(current_time), "backface_temperature(t)"
            )

        T = T_new
        field.append(list(T))
        hot_hist.append(T[0])
        back_hist.append(T[-1])

    peak_backface_temperature = max(back_hist)
    peak_index = back_hist.index(peak_backface_temperature)
    time_of_peak = t_grid[peak_index]

    return TransientResult(
        material=material,
        thickness=thickness,
        x=x,
        t=t_grid,
        temperature_field=field,
        hot_side_history=hot_hist,
        backface_history=back_hist,
        peak_backface_temperature=peak_backface_temperature,
        time_of_peak_backface_temperature=time_of_peak,
        fourier_number=fourier_number,
        dx=dx,
        dt=dt,
        n_nodes=n_nodes,
        n_steps=n_steps,
        backface_condition=backface,
    )


@dataclass(frozen=True)
class TransientSizingResult:
    """Structured result of a bisection search for the minimum thickness
    satisfying max_t T_back(t) <= T_back,max under a prescribed heating
    history.
    """

    material: TPSMaterial
    t_initial: float
    t_back_max: float
    thickness: float
    peak_backface_temperature: float
    margin_temperature: float
    areal_mass: float
    thickness_bounds: tuple
    iterations: int
    converged: bool
    status: str


def size_thickness_transient(
    material: TPSMaterial,
    heating_history: TemperatureHistory,
    total_time: float,
    t_initial: float,
    t_back_max: float,
    thickness_bounds: Sequence[float],
    dt: float,
    n_nodes: int = 21,
    backface: str = "insulated",
    backface_temperature: Optional[TemperatureHistory] = None,
    thickness_tol: float = 1e-5,
    max_iterations: int = 50,
) -> TransientSizingResult:
    """Bisect for the minimum thickness satisfying max_t T_back(t) <= T_back,max.

    Assumes (and relies on, as verified by the test suite) that peak
    backface temperature decreases monotonically with thickness for a fixed
    heating history -- this holds for the diffusion problem solved here.

    Parameters
    ----------
    thickness_bounds:
        ``(t_min, t_max)`` search bracket [m], both > 0, t_max > t_min.
    max_iterations:
        Hard cap on bisection iterations; the search never expands the
        bracket on its own. If the upper bound cannot meet the backface
        limit, this raises a clear diagnostic rather than searching forever.

    Returns
    -------
    TransientSizingResult

    Raises
    ------
    ValueError
        For invalid inputs, or if no feasible thickness exists within
        ``thickness_bounds`` (i.e. even the thickest candidate still exceeds
        ``t_back_max``).
    """
    if len(thickness_bounds) != 2:
        raise ValueError("thickness_bounds must be a 2-tuple (t_min, t_max)")
    t_lo, t_hi = thickness_bounds
    t_lo = require_positive_finite(t_lo, "thickness_bounds[0]")
    t_hi = require_positive_finite(t_hi, "thickness_bounds[1]")
    if t_hi <= t_lo:
        raise ValueError(
            f"thickness_bounds upper bound ({t_hi}) must exceed lower bound ({t_lo})"
        )
    t_back_max = require_positive_absolute_temperature(t_back_max, "t_back_max")
    thickness_tol = require_positive_finite(thickness_tol, "thickness_tol")
    if not isinstance(max_iterations, int) or max_iterations < 1:
        raise ValueError(f"max_iterations must be a positive integer, got {max_iterations!r}")

    def peak_backface_at(thickness: float) -> float:
        result = solve_transient_conduction(
            material=material,
            thickness=thickness,
            t_initial=t_initial,
            hot_side_temperature=heating_history,
            total_time=total_time,
            dt=dt,
            n_nodes=n_nodes,
            backface=backface,
            backface_temperature=backface_temperature,
        )
        return result.peak_backface_temperature

    peak_lo = peak_backface_at(t_lo)
    peak_hi = peak_backface_at(t_hi)
    iterations = 0

    if peak_hi > t_back_max:
        raise ValueError(
            "No feasible thickness within thickness_bounds="
            f"{thickness_bounds}: even the upper bound {t_hi} m gives peak "
            f"backface temperature {peak_hi:.2f} K > t_back_max={t_back_max:.2f} K. "
            "Widen thickness_bounds."
        )

    if peak_lo <= t_back_max:
        thickness = t_lo
        peak = peak_lo
        converged = True
        status = "lower_bound_already_satisfies_limit"
    else:
        lo, hi = t_lo, t_hi
        peak = peak_hi
        converged = False
        status = "max_iterations_reached"
        for iterations in range(1, max_iterations + 1):
            mid = 0.5 * (lo + hi)
            peak_mid = peak_backface_at(mid)
            if peak_mid <= t_back_max:
                hi = mid
                peak = peak_mid
            else:
                lo = mid
            if (hi - lo) < thickness_tol:
                converged = True
                status = "converged"
                break
        thickness = hi

    m_areal = material.density * thickness
    margin = t_back_max - peak

    return TransientSizingResult(
        material=material,
        t_initial=t_initial,
        t_back_max=t_back_max,
        thickness=thickness,
        peak_backface_temperature=peak,
        margin_temperature=margin,
        areal_mass=m_areal,
        thickness_bounds=(t_lo, t_hi),
        iterations=iterations,
        converged=converged,
        status=status,
    )
