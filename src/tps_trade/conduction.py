"""Steady, one-dimensional conduction sizing for a single TPS slab.

Coordinate and sign convention
-------------------------------
The TPS is modeled as a uniform, homogeneous slab::

        hot surface (external environment)
        x = 0,  T = T_hot
        |
        |  TPS thickness t
        |
        x = t,  T = T_back   (cold / backface surface, e.g. bonded structure)

- x increases from the hot surface (x=0) into the material toward the
  backface (x=t).
- All temperatures (T_hot, T_back, max_service_temperature, ...) are
  ABSOLUTE temperatures in kelvin [K], and must be > 0.
- Heat flux q'' is defined POSITIVE when heat flows in the +x direction,
  i.e. from the hot surface toward the backface (T_hot > T_back for
  positive q'' under Fourier conduction). This package does not accept
  q'' <= 0 for inverse sizing (see size_thickness_for_backface_limit).
- Thickness t is in meters [m], t >= 0.

Governing relations (steady, constant k, no internal generation)
------------------------------------------------------------------
Thermal resistance per unit area::

    R'' = t / k                      [m^2*K/W]

Fourier conduction through the slab::

    q'' = k * (T_hot - T_back) / t   [W/m^2]

Solved for backface temperature::

    T_back = T_hot - q'' * t / k

Inverted for required thickness to meet a backface-temperature limit
T_back,max (see size_thickness_for_backface_limit for the full, deliberate
edge-case handling)::

    t_req = k * (T_hot - T_back,max) / q''

Areal mass::

    m_A = rho * t                    [kg/m^2]

IMPORTANT PHYSICAL CAVEAT
--------------------------
Prescribing T_hot and q'' simultaneously and independently is an
intentionally simplified MATHEMATICAL sizing case, not a complete physical
atmospheric-entry model. In a real entry problem, surface temperature and
heat flux are coupled through a surface energy balance (which can include
radiative reradiation and other terms), material properties vary with
temperature, heating is transient, and ablative TPS additionally undergo
pyrolysis and mass loss/recession -- none of which are represented here.
In particular, the counterintuitive-looking scalings t_req ~ k and
t_req ~ 1/q'' (see the test suite) are consequences of prescribing T_hot and
q'' independently in this simplified boundary-value problem; they are not
general statements about entry heating vs. TPS thickness.
"""

from __future__ import annotations

from dataclasses import dataclass

from .materials import TPSMaterial
from ._validation import (
    require_finite_number,
    require_positive_finite,
    require_nonnegative_finite,
    require_positive_absolute_temperature,
)


def thermal_resistance(thickness: float, conductivity: float) -> float:
    """Per-unit-area conductive thermal resistance R'' = t / k [m^2*K/W].

    thickness may be zero (R'' = 0); conductivity must be strictly positive.
    """
    thickness = require_nonnegative_finite(thickness, "thickness")
    conductivity = require_positive_finite(conductivity, "conductivity")
    return thickness / conductivity


def thickness_from_resistance(resistance: float, conductivity: float) -> float:
    """Inverse of thermal_resistance: t = R'' * k [m]."""
    resistance = require_nonnegative_finite(resistance, "resistance")
    conductivity = require_positive_finite(conductivity, "conductivity")
    return resistance * conductivity


def backface_temperature(
    t_hot: float, heat_flux: float, thickness: float, conductivity: float
) -> float:
    """Steady backface temperature: T_back = T_hot - q''*t/k [K].

    heat_flux may be positive, negative, or zero here (this is the forward
    conduction relation, not the inverse sizing case, which does restrict
    heat_flux to be positive -- see size_thickness_for_backface_limit).
    """
    t_hot = require_positive_absolute_temperature(t_hot, "t_hot")
    heat_flux = require_finite_number(heat_flux, "heat_flux")
    resistance = thermal_resistance(thickness, conductivity)
    return t_hot - heat_flux * resistance


def heat_flux_from_temperatures(
    t_hot: float, t_back: float, thickness: float, conductivity: float
) -> float:
    """Fourier conduction heat flux: q'' = k*(T_hot - T_back)/t [W/m^2].

    thickness must be strictly positive (a zero-thickness slab has no
    well-defined flux for a nonzero temperature drop, and an undefined 0/0
    for a zero drop).
    """
    t_hot = require_positive_absolute_temperature(t_hot, "t_hot")
    t_back = require_positive_absolute_temperature(t_back, "t_back")
    thickness = require_positive_finite(thickness, "thickness")
    conductivity = require_positive_finite(conductivity, "conductivity")
    return conductivity * (t_hot - t_back) / thickness


def areal_mass(density: float, thickness: float) -> float:
    """TPS areal mass: m_A = rho * t [kg/m^2].

    This is mass per unit protected area, not total vehicle TPS mass --
    no protected surface area has been defined at this milestone.
    """
    density = require_positive_finite(density, "density")
    thickness = require_nonnegative_finite(thickness, "thickness")
    return density * thickness


@dataclass(frozen=True)
class SizingResult:
    """Structured result of a required-thickness sizing calculation.

    All boundary conditions (t_hot, heat_flux, t_back_max) are carried on
    the result itself, deliberately kept separate from the TPS material
    property object.
    """

    material: TPSMaterial
    t_hot: float
    heat_flux: float
    t_back_max: float
    thickness: float
    thermal_resistance: float
    t_back_predicted: float
    areal_mass: float
    margin_temperature: float

    @property
    def normalized_margin(self) -> float:
        """Margin_T normalized by the available temperature drop (T_hot -
        T_back_max). Dimensionless; provided for convenience only -- the
        dimensional margin_temperature [K] is the primary result.

        Returns 0.0 in the degenerate case T_hot == T_back_max (no available
        temperature drop to normalize by).
        """
        drop = self.t_hot - self.t_back_max
        if drop == 0.0:
            return 0.0
        return self.margin_temperature / drop


def size_thickness_for_backface_limit(
    material: TPSMaterial,
    t_hot: float,
    heat_flux: float,
    t_back_max: float,
) -> SizingResult:
    """Size the required TPS thickness to meet a backface-temperature limit.

    Inverts the steady conduction relation for the required thickness::

        t_req = k * (T_hot - T_back,max) / q''

    Parameters
    ----------
    material:
        TPS material (supplies conductivity k and density rho).
    t_hot:
        Prescribed hot-surface absolute temperature [K]. Must be > 0.
    heat_flux:
        Prescribed steady heat flux through the slab [W/m^2], positive from
        hot surface toward backface. Must be > 0 -- see "Edge cases" below.
    t_back_max:
        Maximum allowable backface absolute temperature [K]. Must be > 0.

    Edge cases (deliberate)
    ------------------------
    - If T_hot <= T_back_max, the prescribed hot-side temperature already
      satisfies the backface limit with no conduction path needed under
      this simplified criterion, so the required thickness is exactly
      0.0 m (not negative, not undefined).
    - heat_flux <= 0 is rejected outright: with q'' <= 0, the forward
      relation T_back = T_hot - q''*t/k does not raise the backface
      temperature above T_hot as thickness increases (q''=0), or actively
      lowers it (q''<0), so "required thickness to avoid exceeding
      T_back_max" is not a meaningful sizing question in either case here.
    - Non-finite or non-physical (<=0 K) absolute temperatures are rejected
      by the shared validation helpers.

    Returns
    -------
    SizingResult
        Structured result including the sized thickness, resulting thermal
        resistance, predicted backface temperature at that thickness,
        areal mass, and temperature margin.
    """
    t_hot = require_positive_absolute_temperature(t_hot, "t_hot")
    t_back_max = require_positive_absolute_temperature(t_back_max, "t_back_max")
    heat_flux = require_positive_finite(heat_flux, "heat_flux")

    if t_hot <= t_back_max:
        thickness = 0.0
    else:
        thickness = material.conductivity * (t_hot - t_back_max) / heat_flux

    resistance = thermal_resistance(thickness, material.conductivity)
    t_back_predicted = backface_temperature(
        t_hot, heat_flux, thickness, material.conductivity
    )
    m_areal = areal_mass(material.density, thickness)
    margin = t_back_max - t_back_predicted

    return SizingResult(
        material=material,
        t_hot=t_hot,
        heat_flux=heat_flux,
        t_back_max=t_back_max,
        thickness=thickness,
        thermal_resistance=resistance,
        t_back_predicted=t_back_predicted,
        areal_mass=m_areal,
        margin_temperature=margin,
    )
