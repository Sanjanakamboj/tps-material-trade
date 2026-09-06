"""Canonical Milestone 4 study case and illustrative candidate database.

Every property in this module is ILLUSTRATIVE / REPRESENTATIVE ONLY. None
of it is traceable to a specific sourced material data sheet, and none of
it should be read as claiming to represent a real, named TPS material
(e.g. actual Shuttle tile, PICA, or Avcoat properties) or a certified
vehicle trajectory. Generic descriptive names are used deliberately for
this reason.

This module exists so the trade study (Milestone 4) has one canonical,
shared study case and a small, explicit candidate set that every example
and test in this project references -- rather than each caller inventing
its own slightly different numbers.
"""

from __future__ import annotations

from .materials import TPSMaterial
from .ablative import AblativeMaterial
from .trade import StudyCase, AblativeCandidate

# --- Canonical study case ----------------------------------------------------

STUDY_CASE = StudyCase(
    name="Illustrative 120 s entry-like heat pulse",
    t_initial=300.0,  # K
    t_hot_max=1400.0,  # K, peak reusable hot-side temperature
    tau_heat=120.0,  # s, heating pulse duration (shared by both categories)
    total_time=600.0,  # s, total reusable transient simulation duration
    t_back_max=450.0,  # K, reusable backface-temperature limit
    ablative_heat_flux=1.0e6,  # W/m^2, net heat flux imposed on ablative candidates
)
"""The one canonical, illustrative study case used by every candidate in
this trade. See the ``StudyCase`` docstring in tps_trade.trade for the
important caveat that ``t_hot_max`` (reusable) and ``ablative_heat_flux``
(ablative) are two different simplified boundary-condition descriptions,
not a physically derived equivalence.
"""

# --- Reusable candidates ------------------------------------------------------

REUSABLE_CANDIDATES = [
    TPSMaterial(
        name="Reusable low-density tile (illustrative)",
        density=350.0,  # kg/m^3
        conductivity=0.06,  # W/(m*K)
        max_service_temperature=1650.0,  # K
        specific_heat=1050.0,  # J/(kg*K)
    ),
    TPSMaterial(
        name="Reusable fibrous blanket (illustrative)",
        density=150.0,  # kg/m^3
        conductivity=0.045,  # W/(m*K)
        max_service_temperature=1250.0,  # K -- deliberately BELOW the study
        # case's t_hot_max=1400 K, so this candidate demonstrates the
        # service-temperature feasibility gate in the trade study itself.
        specific_heat=1200.0,  # J/(kg*K)
    ),
]

# --- Ablative candidates -------------------------------------------------------

ABLATIVE_CANDIDATES = [
    AblativeCandidate(
        material=AblativeMaterial(
            name="Lightweight charring ablator (illustrative)",
            density=280.0,  # kg/m^3
            effective_heat_of_ablation=6.0e6,  # J/kg
        ),
        retained_thickness=0.006,  # m, explicit engineering input
        max_recession=0.09,  # m, illustrative structural/char-layer allowable
    ),
    AblativeCandidate(
        material=AblativeMaterial(
            name="Dense high-H_eff ablator (illustrative)",
            density=1400.0,  # kg/m^3
            effective_heat_of_ablation=1.0e7,  # J/kg
        ),
        retained_thickness=0.005,  # m, explicit engineering input
        max_recession=0.02,  # m, illustrative structural/char-layer allowable
    ),
]
