"""TPS material property representation.

All properties are stored in SI units:

- density (rho): kg/m^3
- thermal conductivity (k): W/(m*K)
- max_service_temperature: K (absolute), a temperature *capability*, not a
  boundary condition for any particular analysis case
- specific_heat (cp), optional: J/(kg*K)

``specific_heat`` is accepted for forward compatibility with later transient
work, but Milestone 1's steady conduction model does not use it -- it is
validated if provided, and otherwise ignored.

Properties on any material shipped in this package are illustrative unless a
literature source is cited alongside them; they must not be treated as
authoritative design allowables.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ._validation import require_positive_finite, require_positive_absolute_temperature


@dataclass(frozen=True)
class TPSMaterial:
    """A homogeneous thermal-protection-system material.

    Attributes
    ----------
    name:
        Human-readable identifier, e.g. "Illustrative Reusable TPS (RCG-coated
        rigid tile), illustrative properties".
    density:
        Bulk density, rho [kg/m^3]. Must be positive and finite.
    conductivity:
        Thermal conductivity, k [W/(m*K)], assumed constant (no temperature
        dependence) in this milestone. Must be positive and finite.
    max_service_temperature:
        Absolute temperature capability of the material [K]. Must be
        positive and finite. This is a material property, not a boundary
        condition -- it is not automatically compared against any analysis
        case's T_hot in Milestone 1.
    specific_heat:
        Optional specific heat, cp [J/(kg*K)], for future transient work.
        Validated if provided; unused by the steady conduction model.
    """

    name: str
    density: float
    conductivity: float
    max_service_temperature: float
    specific_heat: Optional[float] = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string")

        # dataclass is frozen; use object.__setattr__ to normalize types
        # after validating them.
        density = require_positive_finite(self.density, "density")
        conductivity = require_positive_finite(self.conductivity, "conductivity")
        max_service_temperature = require_positive_absolute_temperature(
            self.max_service_temperature, "max_service_temperature"
        )
        object.__setattr__(self, "density", density)
        object.__setattr__(self, "conductivity", conductivity)
        object.__setattr__(self, "max_service_temperature", max_service_temperature)

        if self.specific_heat is not None:
            specific_heat = require_positive_finite(self.specific_heat, "specific_heat")
            object.__setattr__(self, "specific_heat", specific_heat)
