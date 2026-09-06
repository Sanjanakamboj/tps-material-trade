# TPS Material Trade (STM-05)

## Objective

For a prescribed atmospheric-entry thermal environment, how do candidate
reusable and ablative TPS (thermal protection system) concepts compare in
thermal capability, required thickness/mass, reuse characteristics, and
design margin?

The final deliverable (later milestones) is an engineering trade table and a
recommended TPS material/system.

## Current scope: Milestone 1 + Milestone 2 + Milestone 3 + Milestone 4 + Milestone 5

**Milestone 1** built a verified, one-dimensional, **steady-state**
conduction model for a single homogeneous reusable TPS slab (a simple
analytical reference case; see "Steady conduction (Milestone 1)" below).

**Milestone 2** added a verified, one-dimensional, **transient**
(time-dependent) conduction model, so a reusable-TPS slab can be sized
against a finite-duration hot-side heating pulse rather than only an
indefinitely sustained steady boundary condition (see "Transient conduction
(Milestone 2)" below).

**Milestone 3** added a first-order **ablative** TPS sizing model -- a
lumped surface energy-balance / recession model, independent of the
reusable-TPS conduction models above -- so the project could begin comparing
reusable insulation against a sacrificial ablative concept on a common
areal-mass basis (see "Ablative sizing (Milestone 3)" below).

**Milestone 4** performed the first actual **reusable-vs-ablative trade**:
a small, explicit candidate database, one canonical illustrative study
case, sizing of every candidate with the already-verified Milestone 1-3
models, a transparent trade table, deterministic ranking by areal mass, and
one preliminary, case-specific recommendation (see "Reusable-vs-ablative
trade (Milestone 4)" below).

**Milestone 5** extends that single-event trade into a simple, transparent
**mission-lifecycle** comparison: a reusable service-life/refurbishment
convention, an ablative replenishment convention, mission-count and
sensitivity studies, and a deterministic break-even search -- all built
strictly on top of the Milestone 4 single-event results, adding no new
thermal physics (see "Reusable-vs-ablative lifecycle trade (Milestone 5)"
below). It does **not** add monetary cost, maintenance labor, probabilistic
damage/degradation, material aging, coating erosion, or a final material
recommendation beyond the illustrative assumptions used here.

None of the five milestones implement pyrolysis kinetics, moving-boundary
finite-difference conduction, char-layer thermochemistry, surface
chemistry, a coupled convective/radiative surface energy balance,
temperature-dependent material properties, blowing correction, monetary
cost, maintenance labor accounting, probabilistic damage/degradation,
trajectory simulation, CFD, radiation transport, or a final, general
material recommendation. Those remain explicitly out of scope until later
milestones.

## Slab coordinate convention

```
hot surface (external environment)
x = 0,  T = T_hot
|
|  TPS thickness t
|
x = t,  T = T_back   (cold / backface surface, e.g. bonded structure)
```

- `x` increases from the hot surface (`x = 0`) into the material toward the
  backface (`x = t`).
- All temperatures are **absolute** (kelvin, K) and must be `> 0`.
- Heat flux `q''` is positive when heat flows in the `+x` direction (hot
  surface toward backface).
- Thickness `t` is in meters, `t >= 0`.

All internal units are SI: `kg/m^3` (density), `W/(m*K)` (conductivity),
`W/m^2` (heat flux), `m^2*K/W` (thermal resistance per unit area), `kg/m^2`
(areal mass).

## Steady conduction (Milestone 1)

Thermal resistance per unit area:

```
R'' = t / k
```

Steady 1-D conduction, constant `k`, no internal generation:

```
q'' = k (T_hot - T_back) / t
=>  T_back = T_hot - q'' t / k
```

Required thickness to meet a backface-temperature limit `T_back,max`
(inverting the relation above, for `q'' > 0`):

```
t_req = k (T_hot - T_back,max) / q''
```

Areal mass:

```
m_A = rho * t
```

`m_A` is mass per unit protected area; it is deliberately kept separate from
a total vehicle TPS mass, since no protected surface area has been defined
at this milestone.

## Temperature margin

```
Margin_T = T_back,max - T_back,predicted     [K]
```

At the exactly sized thickness, `Margin_T ≈ 0`. A normalized margin
(`Margin_T` divided by the available temperature drop `T_hot - T_back,max`)
is also exposed as a convenience, but the dimensional margin in K is the
primary result. This is a **temperature margin**, not a factor of safety.

## Material representation

`TPSMaterial` (see [src/tps_trade/materials.py](src/tps_trade/materials.py))
is a validated dataclass with:

- `name`
- `density` (rho) [kg/m^3], validated positive & finite
- `conductivity` (k) [W/(m*K)], validated positive & finite
- `max_service_temperature` [K], validated positive & finite
- optional `specific_heat` (cp) [J/(kg*K)]; validated if provided, unused by
  the steady model, but **required** for transient analysis (Milestone 2)

`TPSMaterial.thermal_diffusivity()` computes `alpha = k / (rho * cp)` and
raises `ValueError` if `cp` is not set -- the steady-state functions never
call it, so Milestone 1 behavior is unaffected by this addition.

Boundary conditions (`T_hot`, `q''`, `T_back,max`) are **not** stored on the
material; they are supplied per analysis case, so the same material object
can be reused across sizing cases with different environments.

Only one illustrative material is included at this milestone, and its
properties are explicitly labeled illustrative (order-of-magnitude
representative of a low-density ceramic tile insulator) rather than sourced
design allowables.

## Transient conduction (Milestone 2)

### Governing equation and thermal diffusivity

Transient 1-D conduction with constant properties and no internal heat
generation:

```
dT/dt = alpha * d^2T/dx^2
```

with thermal diffusivity:

```
alpha = k / (rho * cp)     [m^2/s]
```

`cp` (specific heat) is **required** for this model (see Material
representation above); the same coordinate convention as the steady model
applies (`x=0` hot surface, `x=t` backface).

### Finite-difference method

Explicit forward-time, centered-space (FTCS) finite differences on a
uniform grid of `n_nodes` nodes, chosen over Crank-Nicolson for
transparency (every update is a plain, inspectable stencil, no linear
solve). Interior node update:

```
T_new[i] = T[i] + Fo * (T[i+1] - 2*T[i] + T[i-1])
```

where the mesh Fourier number is `Fo = alpha * dt / dx^2`.

### Stability criterion

Explicit FTCS is only stable for:

```
Fo = alpha * dt / dx^2 <= 0.5
```

`solve_transient_conduction` checks this independently of how `dt` was
chosen and **raises `ValueError` rather than silently running an unstable
step** if it is violated. `max_stable_time_step(alpha, dx, fourier_limit)`
is provided as a convenience for picking `dt`.

### Boundary conditions

- **Hot side (`x=0`)**: Dirichlet, a prescribed temperature history
  `T_hot(t)` -- a constant, or a callable `t -> T_hot(t)`.
- **Backface (`x=t`)**: exactly one of:
  - `"insulated"` (default/primary): zero-gradient (`dT/dx = 0`), via the
    standard ghost-node reflection `T_new[-1] = T[-1] + 2*Fo*(T[-2] - T[-1])`.
  - `"prescribed"`: Dirichlet, a second temperature history supplied via
    `backface_temperature`.

  These semantics are never mixed: `backface_temperature` must be omitted
  for `"insulated"` and is required for `"prescribed"`.

### Finite-duration heating pulse

`square_pulse(t_initial, t_hot, tau_heat, t_soak=None)` builds a simple
square-wave hot-side history: `T_hot` for `0 <= t < tau_heat`, then
`t_soak` (or `t_initial` if not given) afterward. This is sufficient to
compare a short pulse against a long one; it is **not** a real
atmospheric-entry heat-rate trajectory.

### Transient thickness sizing

`size_thickness_transient(...)` finds the minimum thickness satisfying
`max_t T_back(t) <= T_back,max` for a given heating history, via bounded
bisection (never expanding the search bracket on its own). It returns a
structured `TransientSizingResult` (thickness, peak backface temperature,
temperature margin, areal mass, iteration count, and convergence
status/diagnostics), and raises a clear `ValueError` if no thickness within
the given bounds is feasible.

### Convergence / discretization controls

`n_nodes` (spatial) and `dt` (time step) are both explicit, caller-supplied
inputs -- nothing here is silently auto-refined. The test suite includes a
grid-refinement comparison showing the change in peak backface temperature
shrinking as `n_nodes` is refined at a fixed, stable `dt`, and an example
scaling of `dt` with `n_nodes` via `max_stable_time_step`.

## Ablative sizing (Milestone 3)

This is a **separate, first-order model** from the reusable-TPS conduction
models above -- it does not use `TPSMaterial` or the steady/transient
conduction relations, only its own `AblativeMaterial` and heat-load/
recession relations (see
[src/tps_trade/ablative.py](src/tps_trade/ablative.py) for the full
docstring).

### Model assumptions

A lumped surface energy-balance / recession model, assuming:

- an imposed **net** heat-flux history `q''(t)` reaching the ablating
  surface (this module does not compute a surface energy balance itself);
- all absorbed energy goes toward consuming material at a single, constant
  **effective heat of ablation** `H_eff` [J/kg];
- uniform, constant material density `rho`;
- **no** detailed internal conduction/pyrolysis coupling, **no** char-layer
  resistance, **no** radiative feedback, **no** surface chemistry, **no**
  blowing correction.

Heat flux is treated as **net-heating-only**: negative heat flux is
rejected (see "Heat-flux history representation" below).

### Ablative material representation

`AblativeMaterial` (see
[src/tps_trade/ablative.py](src/tps_trade/ablative.py)) is a validated
dataclass, chosen as a dedicated type (rather than extending `TPSMaterial`)
since its core parameter -- `H_eff` -- has no reusable-TPS analog:

- `name`
- `density` (rho) [kg/m^3], validated positive & finite
- `effective_heat_of_ablation` (H_eff) [J/kg], validated positive & finite
- optional `max_usable_temperature` [K], `conductivity` [W/(m*K)],
  `specific_heat` [J/(kg*K)] -- retained for possible future reuse with the
  conduction models, validated if provided, unused by this milestone's
  relations

### Heat-flux history representation

`HeatFluxSegment(heat_flux, duration)` represents one constant-flux segment
(`heat_flux >= 0`, `duration > 0`); a list of segments is a piecewise
history. `total_heat_load_sampled(times, heat_flux)` numerically integrates
an arbitrary sampled `(t, q'')` history via the trapezoidal rule (times
strictly increasing, flux `>= 0`, both finite). `integrated_heat_load(...)`
dispatches to the exact piecewise sum or the sampled trapezoidal
integration depending on what is passed.

### Heat-load and recession equations

Total (net) heat load:

```
Q'' = integral q''(t) dt          [J/m^2]
```

Consumed areal mass:

```
m''_consumed = Q'' / H_eff         [kg/m^2]
```

Recession depth (consumed thickness), equivalently consumed areal mass
divided by density:

```
delta = Q'' / (rho * H_eff)        [m]
```

### Retained thickness and initial sizing

`t_retained` is an **explicit engineering input** to this model -- the
thickness that must remain after the heating event for structural
integrity, insulation, uncertainty, and attachment protection. This module
does not invent or certify a value for it. Required initial thickness:

```
t_initial = delta + t_retained
```

### Mass decomposition

```
m''_initial   = rho * t_initial
m''_remaining = rho * t_retained
m''_consumed  = rho * delta
m''_initial = m''_remaining + m''_consumed     (verified within tolerance)
```

### Design margin

For a trial initial thickness `t_trial` (mirroring the Milestone 1/2
thickness-margin convention):

```
Margin_t = t_trial - delta - t_retained     [m]
```

At the exactly sized thickness, `Margin_t ~ 0`. This is a **dimensional
margin**, not a factor of safety. `evaluate_trial_thickness(...)` also
reports a pass/fail (`passed = Margin_t >= 0`). `size_ablative_thickness(...)`
additionally reports an optional recession margin
(`Margin_delta = max_recession - delta`) when a maximum allowable recession
depth is supplied.

## Reusable-vs-ablative trade (Milestone 4)

This section is the first place in the project that puts reusable and
ablative TPS candidates side by side. It adds **no new thermal physics** --
every sizing call delegates to the already-verified Milestone 1/2 transient
model and Milestone 3 ablative model (see
[src/tps_trade/trade.py](src/tps_trade/trade.py) and
[src/tps_trade/candidates.py](src/tps_trade/candidates.py)).

### The modeling mismatch (read this first)

The reusable model is driven by a prescribed **hot-side TEMPERATURE**
history (a Dirichlet boundary condition). The ablative model is driven by a
prescribed **net heat-FLUX** history (an energy input integrated directly
into consumed mass). The canonical study case below picks one illustrative
peak temperature and one illustrative heat flux intended to represent "the
same" qualitative entry-like event, but there is **no physical derivation**
here converting one into the other (that would require a surface energy
balance, out of scope through this milestone). Treat the correspondence as
illustrative and qualitative, not a derived equivalence. This is a
fundamental limitation of comparing these two model categories at this
stage of the project, not a hidden detail.

### Canonical study case

`STUDY_CASE` (`tps_trade.candidates.STUDY_CASE`), shared by every candidate:

| Quantity | Value |
|---|---|
| Initial temperature | 300.0 K |
| Peak hot-side temperature (reusable) | 1400.0 K |
| Heating pulse duration | 120.0 s |
| Total reusable simulation duration | 600.0 s |
| Backface temperature limit (reusable) | 450.0 K |
| Net heat flux (ablative) | 1.000e+06 W/m^2 |

An **illustrative, entry-like** case -- not a certified vehicle
trajectory. The heating pulse duration (120 s) is shared by both
categories: the reusable hot-side pulse and the ablative heat-flux pulse
both last exactly this long, so both models see an event of the same
duration (even though they describe its magnitude in incompatible units,
per the mismatch above).

### Candidate database

All properties below are **ILLUSTRATIVE / REPRESENTATIVE ONLY** -- none are
sourced from a specific material data sheet, and none represent a real,
named TPS material (e.g. Shuttle tile, PICA, Avcoat) or certified
allowable.

**Reusable candidates** (`tps_trade.candidates.REUSABLE_CANDIDATES`):

| Name | rho [kg/m^3] | k [W/(m*K)] | cp [J/(kg*K)] | Max service temp [K] |
|---|---|---|---|---|
| Reusable low-density tile (illustrative) | 350.0 | 0.060 | 1050.0 | 1650.0 |
| Reusable fibrous blanket (illustrative) | 150.0 | 0.045 | 1200.0 | 1250.0 |

The fibrous blanket's max service temperature (1250 K) is **deliberately
below** the study case's peak hot-side temperature (1400 K), so the
candidate database itself demonstrates the service-temperature feasibility
gate (see below) rather than only exercising it in a synthetic unit test.

**Ablative candidates** (`tps_trade.candidates.ABLATIVE_CANDIDATES`), each
an `AblativeCandidate` pairing an `AblativeMaterial` with its own
`retained_thickness` and an illustrative `max_recession` structural
allowable:

| Name | rho [kg/m^3] | H_eff [J/kg] | Retained thickness [mm] | Max recession [mm] |
|---|---|---|---|---|
| Lightweight charring ablator (illustrative) | 280.0 | 6.000e+06 | 6.0 | 90.0 |
| Dense high-H_eff ablator (illustrative) | 1400.0 | 1.000e+07 | 5.0 | 20.0 |

`retained_thickness` and `max_recession` are trade-specific **engineering
inputs**, not material properties -- this project never invents or
certifies them.

### Reusable sizing workflow

For each reusable candidate: if `STUDY_CASE.t_hot_max > material.max_service_temperature`,
the candidate is marked **infeasible without attempting to size a
thickness** -- this project never silently sizes a material beyond its
stated temperature capability. Otherwise, `size_thickness_transient(...)`
(Milestone 2) is called with the study case's shared hot-side history,
backface limit, thickness search bounds, and node count, and the result's
thickness, areal mass, peak backface temperature, and temperature margin
are carried into the common trade result.

### Ablative sizing workflow

For each ablative candidate: the study case's shared heat-flux history is
integrated once (`Q'' = q''*tau_heat`), and `size_ablative_thickness(...)`
(Milestone 3) is called with the candidate's material, that heat load,
`retained_thickness`, and `max_recession`. A candidate is marked
**infeasible** only if `max_recession` is supplied and the predicted
recession exceeds it -- unlike the reusable model, this ablative model has
no surface-temperature capability check here (it never computes a surface
temperature in this milestone).

### Common trade result

`TradeResult` (see [src/tps_trade/trade.py](src/tps_trade/trade.py))
exposes common fields (`name`, `category`, `feasible`, `required_thickness`,
`initial_areal_mass`, `governing_metric_name`/`value`, `design_margin`,
`margin_units`, `key_capability_limit`, `notes`) plus exactly one of
`reusable_detail` / `ablative_detail` populated per instance -- unlike
quantities (a temperature margin in K vs. a recession margin in m) are
never forced into a single misleadingly-generic field.

### Ranking

`rank_feasible_by_mass(...)` is deterministic: (1) infeasible candidates
are excluded entirely -- a candidate is never selected for having lower
mass if it is infeasible; (2) feasible candidates are ranked ascending by
`initial_areal_mass`; (3) ties are broken by greater `design_margin`; (4)
any remaining tie is broken by name. No arbitrary weighted score is
introduced -- this is a transparent, single-criterion (mass) ranking with
an explicit tie-break, not a qualitative scoring rubric.

### Comparison-fairness guarantee

`run_trade_study(study_case, reusable_materials, ablative_candidates)`
centralizes every sizing call against the **same** `StudyCase` instance
(validating unique candidate names first), which is what guarantees every
reusable candidate sees the identical hot-side history/backface limit/
thickness bounds, and every ablative candidate sees the identical
heat-flux history/retained-thickness convention -- fairness by
construction, not a separate check bolted on afterward. All quantities
throughout remain SI internally.

## Reusable-vs-ablative lifecycle trade (Milestone 5)

This section extends the Milestone 4 single-event trade into a
**mission-lifecycle** comparison. It introduces **no new thermal physics**
-- every lifecycle number starts from an already-sized Milestone 4
`TradeResult` (thermal feasibility and initial areal mass) with an
explicit mass-accounting convention layered on top (see
[src/tps_trade/lifecycle.py](src/tps_trade/lifecycle.py)). Call this what
it is: an **illustrative lifecycle mass-equivalent trade**, not a real
operations-cost or reliability model.

**The Milestone 4 single-event result is preserved, not replaced** -- see
"Trade study result (Milestone 4)" above, still reproducible via
`examples/tps_material_trade.py`. Milestone 5 adds lifecycle context on
top of it via a separate ranking (`rank_lifecycle_by_burden`), never by
overwriting `rank_feasible_by_mass`.

### Lifecycle philosophy

- **Reusable TPS**: the installed TPS is retained between missions. It may
  incur a small refurbishment-equivalent mass penalty each mission
  (inspection, minor repair, coating touch-up, handling), and has a finite
  service life in missions, after which the entire installation is
  replaced.
- **Ablative TPS**: the modeled sacrificial (consumed) material is
  replenished before each subsequent mission; the retained substrate
  thickness is not treated as newly consumed each mission.

Neither category is assumed superior in advance.

### Lifecycle configuration (`LifecycleConfig`)

All assumptions are explicit, validated fields -- never buried inside a
candidate's material properties:

- `mission_count` (M >= 1)
- `reusable_service_life_missions` (N_service >= 1) -- illustrative (e.g.
  25/50/100 missions), **not** a claim about any real vehicle's tile
  lifetime unless separately sourced
- `reusable_refurbishment_fraction` (f_refurb >= 0) -- an illustrative
  **mass-equivalent** penalty per mission (fraction of installed mass),
  representing inspection/minor repair/coating touch-up/handling, **not**
  actual removed-and-replaced material
- `reusable_replace_at_end_of_service_life` (default `True`) -- if `False`,
  flying past the service life is not modeled; that case is reported as
  lifecycle-infeasible instead
- `ablative_replenishment_convention` -- documentation-only tag; only
  `"consumed_mass_only"` (below) is implemented in this milestone

### Reusable lifecycle equation

For installed areal mass `m''_installed`, service life `N_service`, and
refurbishment fraction `f_refurb`, over `M >= 1` missions:

```
installation_count = ceil(M / N_service)
replacement_count   = installation_count - 1

installation_burden  = installation_count * m''_installed
refurbishment_burden = f_refurb * m''_installed * M

cumulative_burden = installation_burden + refurbishment_burden
```

**Replacement-timing convention**: one installation is good for *exactly*
`N_service` missions (missions `1..N_service` fly on installation #1,
`N_service+1..2*N_service` on installation #2, etc.) -- so the first
replacement is required *before* mission `N_service + 1`, not at mission
`N_service` itself. At `M == N_service` there are 0 replacements; at
`M == N_service + 1` there is 1.

### Ablative lifecycle equation

For initial areal mass `m''_initial` and consumed areal mass per mission
`m''_consumed` (both from the Milestone 3 single-event sizing), assuming
mission 1 requires the full initial mass and every subsequent mission
requires replenishing only the consumed mass, over `M >= 1` missions:

```
replenishment_count  = M - 1
replenishment_burden = (M - 1) * m''_consumed

cumulative_burden = m''_initial + replenishment_burden
```

No additional ablative refurbishment penalty is introduced. Both
conventions reduce to the Milestone 4 single-event result at `M=1` with
zero refurbishment: `cumulative_burden == initial_areal_mass`.

### Common lifecycle result and ranking

`LifecycleResult` exposes common fields (`name`, `category`,
`mission_count`, `feasible`, `initial_areal_mass`,
`cumulative_lifecycle_burden`, `mission_averaged_burden`, `replacements`,
`notes`) plus exactly one of `reusable_detail` / `ablative_detail`. The
`replacements` field counts a **different physical event per category**
(full installation replacements for reusable; replenishment top-ups for
ablative, always `M-1`) -- documented explicitly rather than pretending the
two are the same quantity.

`rank_lifecycle_by_burden(...)` excludes thermally infeasible candidates
(the fibrous blanket stays excluded here too -- lifecycle assumptions
never make a thermally infeasible candidate feasible) and ranks the rest
ascending by `cumulative_lifecycle_burden`, tie-broken by name. This
ranking is deliberately kept **separate** from Milestone 4's
`rank_feasible_by_mass`.

### Break-even / crossover search

`find_breakeven_mission_count(candidate_a, candidate_b, base_config,
mission_range)` deterministically scans a finite, explicit mission-count
range for the first mission count at which the lower-burden candidate
changes, returning a clear "no crossover found within this range"
diagnostic rather than extrapolating beyond the searched bound.

## Important limitation

Prescribing `T_hot` and `q''` simultaneously and independently is an
**intentionally simplified mathematical sizing case**, not a complete
physical atmospheric-entry model. In a real entry problem:

- surface temperature and heat flux are coupled through a surface energy
  balance (which can include radiative reradiation),
- material properties vary strongly with temperature,
- heating is transient, and
- ablative TPS additionally undergo pyrolysis, recession, and mass loss.

None of this is represented here. In particular, this simplified
boundary-value formulation produces two results that can look
counterintuitive out of context:

- `t_req` scales **proportionally** with `k` (not inversely) at fixed
  `T_hot`, `q''`, and `T_back,max` — a higher-conductivity material needs
  *more* thickness to produce the same temperature drop at a fixed
  prescribed heat flux.
- `t_req` scales **inversely** with `q''` at fixed temperatures — doubling
  the prescribed heat flux halves the required thickness in *this specific*
  formulation, because `T_hot` is held fixed rather than driven by the
  heating itself.

These are consequences of prescribing `T_hot` and `q''` independently, not
general statements that higher entry heating requires less TPS. See the
docstring in
[src/tps_trade/conduction.py](src/tps_trade/conduction.py) for the full
discussion.

The transient model (Milestone 2) removes the "indefinitely sustained
boundary condition" assumption, but keeps the same kind of simplification:
prescribing a hot-side **temperature** history directly is still not a
surface energy balance (no convection or radiation coupling), material
properties (`k`, `rho`, `cp`) are still held constant (no temperature
dependence), and there is still no ablation, pyrolysis, or mass loss. See
the docstring in
[src/tps_trade/transient.py](src/tps_trade/transient.py) for the full
discussion.

The ablative model (Milestone 3) is a first-order, lumped "energy in, mass
out" bookkeeping model, **not** a high-fidelity ablation solver: it does
not represent pyrolysis kinetics, a moving-boundary conduction solution
through a receding/charring layer, char-layer thermochemistry, surface
chemistry, a coupled surface energy balance, or blowing (mass-injection)
correction. The imposed heat-flux history is assumed net-of-surface-effects
already; the model does not compute how that net flux itself would change
as the surface recedes or chars. See the docstring in
[src/tps_trade/ablative.py](src/tps_trade/ablative.py) for the full
discussion.

The trade (Milestone 4) inherits every limitation of both models above
(prescribed, not coupled, boundary conditions; constant material
properties; no ablative surface temperature computed; no pyrolysis/char/
chemistry/blowing) **plus** trade-level limitations of its own: no
lifecycle/reuse accounting (refurbishment, reuse-cycle degradation,
turnaround time), no attachment/substructure mass, no waterproofing or
coatings, no integration penalties, no structural durability assessment,
and no cost accounting. **This is a preliminary model comparison, not a
certified TPS selection.** See the docstring in
[src/tps_trade/trade.py](src/tps_trade/trade.py) for the full discussion.

The lifecycle trade (Milestone 5) adds the mission-lifecycle mass
accounting described above, but is explicitly **not**: a monetary cost
model, a maintenance-labor-hours model, a probabilistic damage/degradation
model, a reusable material-aging model, a coating-erosion model, an
impact-damage model, an oxidation-kinetics model, or an ablative chemistry
model. It also does not model rain/weather/environmental exposure between
missions, attachment/substructure replacement, or thermal-property aging
with cycle count, and it simplifies ablative replenishment to consumed
material only (no additional ablative refurbishment penalty). Call this
model what it is: an **illustrative lifecycle mass-equivalent trade**, not
a real operations-cost model. See the docstring in
[src/tps_trade/lifecycle.py](src/tps_trade/lifecycle.py) for the full
discussion.

## Engineering interpretation (Milestone 2)

- **Thermal diffusivity, not conductivity alone, controls transient
  penetration rate.** `alpha = k/(rho*cp)` sets how fast a temperature
  disturbance propagates through the slab; conductivity by itself only
  says how much heat flows for a given gradient, not how quickly the
  interior responds.
- **Density and specific heat provide thermal inertia.** Higher `rho` or
  `cp` (higher volumetric heat capacity `rho*cp`) slows the temperature
  rise for the same absorbed heat -- this is why tests H and I show higher
  `cp` and higher `rho` each reducing peak backface temperature for the
  same pulse.
- **Finite heating duration matters strongly.** A short pulse may barely
  penetrate a slab that would eventually reach a much higher backface
  temperature under sustained heating (see test E and the "short-time
  penetration" verification).
- **Steady-state sizing can be conservative for short heating events.**
  The representative study below shows the Milestone 1 steady-sized
  thickness exceeding the Milestone 2 transient-sized thickness for the
  same finite pulse -- because steady sizing implicitly assumes the
  boundary condition is sustained forever.
- **Numerical convergence matters.** A transient finite-difference result
  is only meaningful once spatial/time discretization sensitivity has been
  checked (see "Convergence / discretization controls" above) -- an
  arbitrary single grid is not treated as exact here.

This does not change the fact that the model is a simplified mathematical
sizing tool, not a certified thermal analysis.

## Engineering interpretation (Milestone 3)

- **Heat flux integrated over time determines total heat load.** `Q''` is
  what drives ablation, not the instantaneous heat flux -- a short, intense
  pulse and a longer, gentler one can deliver the same `Q''` and therefore
  the same recession under this model.
- **Effective heat of ablation determines how much mass must be sacrificed
  per unit energy.** `H_eff` is the single lumped parameter standing in for
  pyrolysis, phase change, and reradiation losses combined; it sets
  `m''_consumed = Q''/H_eff` directly.
- **Density converts consumed areal mass into recession depth.** The same
  consumed mass produces less recession in a denser material
  (`delta = m''_consumed/rho`).
- **Retained thickness is a separate design requirement**, not something
  this model derives -- it is supplied as an explicit engineering input
  and added directly to the recession depth to get the required initial
  thickness.
- **High `H_eff` is favorable for recession but does not by itself
  determine TPS system quality** -- it says nothing about retained-
  thickness insulation performance, structural behavior, or manufacturing/
  attachment considerations.
- **This model ignores internal temperature gradients and surface
  thermochemistry** -- there is no conduction calculation into the
  ablator's retained thickness in this milestone, and no surface energy
  balance computing `q''(t)` itself.

This is a first-order sizing/bookkeeping tool, not a complete ablative TPS
design model.

## Engineering interpretation (Milestone 4)

- **Reusable systems** are often low density, rely on low thermal
  diffusivity (good insulation, not necessarily high or low conductivity
  alone -- see the Milestone 2 interpretation), and retain their full mass
  after the heating event -- attractive for repeated missions, though this
  project has not yet quantified any reuse/lifecycle benefit.
- **Ablative systems** reject heat by consuming material: effective heat
  of ablation directly sets how much sacrificial mass is required for a
  given heat load. They may tolerate more severe or longer heating in
  practice, but under this model they are always mission-consumable --
  mass is spent, not retained.
- **Lowest areal mass for one event is not automatically "best lifecycle
  TPS."** A reusable candidate that wins this single-event mass comparison
  still needs no replacement between flights (a real advantage this trade
  does not credit numerically), while an ablative candidate that loses the
  single-event mass comparison might still be preferable for a
  single-use mission where reuse is irrelevant. Milestone 4 answers "which
  candidate is lightest for this one modeled event," not "which system is
  best over a program's lifecycle."
- The trade's ranking is driven entirely by `initial_areal_mass` among
  feasible candidates -- it does not (and, per this project's stated
  approach, should not) collapse thermal capability, reuse potential, and
  manufacturability into a single arbitrary weighted score.

## Engineering interpretation (Milestone 5)

- **Reusable TPS pays an initial installation "penalty" but can amortize
  it over many missions** -- a reusable candidate's cumulative burden grows
  only through refurbishment and (infrequent) replacement, not per-mission
  consumption.
- **Ablative TPS incurs a recurring sacrificial-mass demand** -- every
  mission after the first requires replenishing the consumed mass, so
  cumulative burden grows roughly linearly with mission count.
- **A finite reusable service life introduces replacement penalties** --
  once a reusable installation exceeds its service life, a full
  replacement is required, which can noticeably increase cumulative burden
  (see the service-life sensitivity result below).
- **Refurbishment can materially affect lifecycle ranking** -- a nonzero
  `f_refurb` compounds with mission count, so it is worth checking even
  though it is "just" an illustrative mass-equivalent penalty.
- **Lifecycle burden is not actual monetary cost.** It is a mass-equivalent
  bookkeeping quantity, useful for comparing categories on a like-for-like
  basis, not a stand-in for dollars or labor hours.
- **Lower initial mass does not automatically mean lower long-term
  operational burden** -- in general a candidate that wins the Milestone 4
  single-event comparison need not win the Milestone 5 lifecycle
  comparison (see the ranking test in the verification suite for a
  constructed counter-example); it happens to remain the same candidate in
  this project's specific canonical study case and candidate set.
- **No meaningful lifecycle conclusion is possible without explicit
  mission-count assumptions.** "How many missions?" changes the answer, as
  the mission-count sensitivity below shows directly.

## Verification summary

156 automated tests in [tests/](tests/) cover the steady model
(Milestone 1, 38 tests), the transient model (Milestone 2, 31 tests), the
ablative sizing model (Milestone 3, 36 tests), the reusable-vs-ablative
trade (Milestone 4, 27 tests), and the lifecycle trade (Milestone 5, 24
tests):

### Steady model (Milestone 1)

- **A.** Thermal resistance hand calculation (`R'' = t/k`)
- **B.** Conductive heat-flux identity (`q'' = k(T_hot - T_back)/t`)
- **C.** Backface-temperature calculation (`T_back = T_hot - q''t/k`)
- **D.** Thickness-inversion round trip (size from a known thickness,
  recover it)
- **E.** Conductivity scaling (`t_req ∝ k`)
- **F.** Heat-flux scaling (`t_req ∝ 1/q''`)
- **G.** Areal-mass scaling (linear in both `rho` and `t`)
- **H.** Exact-boundary margin (`Margin_T ≈ 0` at the sized thickness)
- **I.** Over-thickness (lower predicted `T_back`, positive margin)
- **J.** Under-thickness (higher predicted `T_back`, negative margin)
- **K.** Invalid-input rejection (`k <= 0`, `rho <= 0`, negative thickness,
  `q'' <= 0` for inverse sizing, NaN/inf, non-physical absolute
  temperatures)
- **L.** Zero-required-thickness case (`T_hot <= T_back,max`)
- Material validation (`TPSMaterial` field checks)

### Transient model (Milestone 2)

- **A.** Thermal diffusivity hand calculation (`alpha = k/(rho*cp)`) and
  rejection when `cp` is missing
- **B.** Uniform-temperature equilibrium (`T_hot = T_initial` + insulated
  backface stays exactly uniform)
- **C.** Stability rejection (`Fo > 0.5` raises `ValueError`; `Fo = 0.5`
  exactly is accepted)
- **D.** Constant boundary behavior (hot node holds its prescribed value,
  backface never exceeds `T_hot`, monotonic approach to the boundary value)
- **E.** Short-time penetration (thick slab, short pulse -> backface stays
  near `T_initial`)
- **F.** Thickness effect (greater thickness -> lower peak backface temp)
- **G.** Conductivity effect (higher `k` -> higher peak backface temp for a
  finite pulse)
- **H.** Heat-capacity effect (higher `cp` -> lower transient rise)
- **I.** Density effect (higher `rho` -> lower transient rise)
- **J.** Bounded-temperature sanity (field stays within `[T_initial, T_hot]`)
- **K.** Insulated-backface zero-gradient check (numerical gradient at the
  backface much smaller than near the hot side)
- **L.** Pulse-duration effect (longer pulse -> higher peak backface temp)
- **M.** Thickness-sizing boundary (peak `T_back` at or below the limit
  within tolerance)
- **N.** Over-thickness (positive margin)
- **O.** Under-thickness (reduced/violated margin)
- **P.** Bisection determinism (repeated sizing calls agree exactly)
- Infeasible-bounds diagnostic (clear `ValueError`, no bound expansion)
- **Q.** Missing-`cp` rejection by the transient solver
- **R.** Invalid-input rejection (thickness, node count, `dt`, total time,
  temperatures, NaN/inf, mixed/unknown backface semantics)
- Prescribed-backface boundary condition check
- Semi-infinite step-temperature analytical reference (`erf` solution)
  comparison at an interior point, before backface effects matter
- Grid-refinement convergence check (change in peak backface temperature
  shrinks as `n_nodes` is refined at a fixed, stable `dt`)

### Ablative sizing model (Milestone 3)

- **A.** Constant heat-flux heat load (`Q'' = q''*tau`, exact)
- **B.** Piecewise heat-load hand calculation (multi-segment history,
  exact sum), plus a sampled-history trapezoidal hand calculation
- **C.** Consumed areal mass (`m''_consumed = Q''/H_eff`)
- **D.** Recession depth (`delta = Q''/(rho*H_eff)`)
- **E.** Density scaling (`delta ∝ 1/rho`)
- **F.** Heat-of-ablation scaling (`delta ∝ 1/H_eff`)
- **G.** Heat-load scaling (doubling `Q''` doubles consumed mass and
  recession)
- **H.** Initial-thickness identity (`t_initial = delta + t_retained`)
- **I.** Mass decomposition (`m''_initial = m''_remaining + m''_consumed`)
- **J.** Trial-thickness exact boundary (`Margin_t ~ 0` at
  `t_trial = delta + t_retained`)
- **K.** Over-thickness (positive margin, passes)
- **L.** Under-thickness (negative margin, fails)
- **M.** Zero heat load (`delta = 0`, consumed mass `= 0`,
  `t_initial = t_retained`)
- **N.** Invalid-material-input rejection (`rho <= 0`, `H_eff <= 0`,
  NaN/inf)
- **O.** Invalid-heat-history rejection (negative duration, non-monotonic
  times, NaN/inf, negative heat flux, mismatched/too-few samples, empty
  segment list)
- **P.** Sampled-integration determinism (repeated calls agree exactly)
- Recession-margin reporting when `max_recession` is supplied (and `None`
  by default)
- Invalid sizing/trial-evaluation input rejection

### Reusable-vs-ablative trade (Milestone 4)

- **A.** Candidate database validation (unique names, valid properties,
  category consistency, rejection of duplicate names / wrong types)
- **B.** Reusable sizing consistency (trade result matches an independent
  direct call to `size_thickness_transient`)
- **C.** Ablative sizing consistency (trade result matches an independent
  direct call to `size_ablative_thickness`)
- **D.** Service-temperature rejection (a candidate below the study case's
  hot-side maximum is infeasible; the canonical fibrous-blanket candidate
  demonstrates this for real)
- **E.** Common study-case enforcement (sizing candidates never mutates
  the shared `StudyCase`; every candidate draws from the same heating
  history / heat load)
- **F.** Areal-mass ranking (lightest feasible synthetic candidate is
  selected)
- **G.** Infeasible exclusion (an infeasible candidate is never selected
  for having lower mass)
- **H.** Deterministic tie-break (equal-mass candidates ranked
  consistently by margin, then by name, regardless of input order)
- **J.** Reusable model trend (higher `rho*cp` / lower `alpha` reduces
  required transient thickness for the trade's own study case)
- **K.** Ablative model trend (higher `H_eff` reduces consumed mass and
  recession for equal heat load)
- **L.** Mass identity (`initial = remaining + consumed`) verified through
  the trade result
- End-to-end `run_trade_study` / `summarize_trade` / `generate_recommendation`
  checks, including the no-feasible-candidate diagnostic
- `StudyCase` input validation (hot max vs. initial, total time vs. pulse
  duration, thickness bounds, Fourier limit)

### Lifecycle trade (Milestone 5)

- **A.** One-mission reusable identity (`M=1`, zero refurbishment ->
  cumulative burden = installed areal mass)
- **B.** One-mission ablative identity (`M=1` -> cumulative burden =
  initial areal mass)
- **C.** Ablative repeated-mission formula hand calculation
  (`m_initial + (M-1)*m_consumed`)
- **D.** Reusable refurbishment scaling (doubling `f_refurb` doubles the
  refurbishment contribution; installation burden unaffected)
- **E.** Reusable replacement-count convention, parametrized across
  `M < N_service`, `M == N_service`, `M == N_service+1`, and multiple
  replacement intervals
- **F.** Zero refurbishment with a long service life (cumulative burden
  stays equal to installed mass)
- **G.** Mission-averaged burden identity (`average = cumulative/M`)
- **H.** Thermally infeasible exclusion (a synthetic infeasible candidate,
  and the canonical fibrous blanket, both stay excluded from lifecycle
  ranking)
- **I.** Lifecycle ranking can differ from the single-event mass ranking
  (constructed candidates where the single-event winner loses the
  multi-mission comparison)
- **J.** Break-even helper finds a known analytical crossover mission
  count for a synthetic constant-vs-linear-burden pair
- **K.** No-crossover behavior, both for a synthetic pair and for the
  canonical reusable tile vs. dense ablator over a 500-mission search
- **L.** Determinism (repeated lifecycle and break-even calls agree
  exactly)
- `LifecycleConfig` input validation; `reusable_replace_at_end_of_service_life=False`
  behavior; category-mismatch rejection in the dispatch functions
- End-to-end `run_lifecycle_study` / `summarize_lifecycle` check on the
  canonical candidate database

All 156 tests currently pass.

## Sanity-case result (Milestone 1, steady)

Illustrative reusable-TPS-style tile, run via
[examples/sanity_case.py](examples/sanity_case.py):

| Quantity | Value |
|---|---|
| Material | Illustrative Reusable TPS Tile (rigid ceramic insulator, illustrative properties) |
| Density (rho) | 350.0 kg/m^3 |
| Conductivity (k) | 0.0600 W/(m*K) |
| T_hot | 1400.0 K |
| Heat flux (q'') | 3000.0 W/m^2 |
| T_back,max | 450.0 K |
| Required thickness | 1.90 cm (0.0190 m) |
| Thermal resistance (R'') | 0.3167 m^2*K/W |
| Areal mass (m_A) | 6.65 kg/m^2 |
| Predicted T_back at sized thickness | 450.00 K |
| Temperature margin | +0.0000 K |

Off-nominal checks at the same boundary conditions:

- **80% of required thickness** (1.52 cm): predicted `T_back` = 640.00 K,
  which **exceeds** the 450 K limit (margin = -190.00 K), as expected for an
  undersized TPS.
- **120% of required thickness** (2.28 cm): predicted `T_back` = 260.00 K,
  giving a **positive** margin of +190.00 K, as expected for an oversized
  TPS.

This case is explicitly illustrative; it is not tuned to represent any
specific real spacecraft.

## Transient heating study result (Milestone 2)

Same illustrative reusable-TPS-style tile (now with `cp` added), run via
[examples/transient_heating_study.py](examples/transient_heating_study.py),
exposed to a 120 s square hot-side pulse to `T_hot = 1400 K` from
`T_initial = 300 K`, against the same `T_back,max = 450 K` limit:

| Quantity | Value |
|---|---|
| Diffusivity (alpha) | 1.633e-07 m^2/s |
| Pulse duration | 120.0 s |
| Spatial nodes | 21 |
| Time step (dt) | 0.0245 s |
| Fourier number (Fo) | 0.400 |
| Transient-sized thickness | 1.619 cm |
| Peak backface temperature | 449.94 K |
| Time of peak backface temperature | 335.6 s |
| Temperature margin | +0.0552 K |
| Areal mass | 5.67 kg/m^2 |

### Steady- vs. transient-sized thickness comparison

| Sizing approach | Thickness |
|---|---|
| Milestone 1, steady (`q'' = 3000 W/m^2`, sustained indefinitely) | 1.900 cm |
| Milestone 2, transient (120 s pulse) | 1.619 cm |

The transient-sized thickness is thinner here because the pulse is finite:
the backface never has time to reach the temperature it would eventually
reach under sustained heating, so a thinner slab still keeps its **peak**
transient temperature under the limit. This is a consequence of the pulse
being short relative to the slab's thermal response time -- it is **not** a
general claim that transient sizing is always less conservative than
steady sizing (a sufficiently long pulse converges toward the steady
result). This comparison is illustrative only, not a real reentry
certification load case.

## Ablative sanity-study result (Milestone 3)

One illustrative charring-ablator-style material, run via
[examples/ablative_sanity_case.py](examples/ablative_sanity_case.py),
exposed to a constant 2.0e6 W/m^2 heat-flux pulse for 60 s
(`Q'' = 1.2e8 J/m^2`), with an explicit `t_retained = 5.0 mm`:

| Quantity | Value |
|---|---|
| Density (rho) | 1400.0 kg/m^3 |
| Effective heat of ablation (H_eff) | 1.000e+07 J/kg |
| Total heat load (Q'') | 1.200e+08 J/m^2 |
| Consumed areal mass | 12.000 kg/m^2 |
| Recession depth | 8.57 mm |
| Retained thickness requirement | 5.00 mm |
| Initial required thickness | 13.57 mm |
| Initial areal mass | 19.000 kg/m^2 |
| Remaining areal mass | 7.000 kg/m^2 |
| Consumed mass fraction | 0.632 |

Mass check: `19.000 = 7.000 + 12.000` (initial = remaining + consumed).

Off-nominal checks at the same heat load:

- **80% of required initial thickness** (10.86 mm): remaining after
  recession = 2.29 mm, margin = **-2.71 mm** -- **FAILS** the
  retained-thickness requirement, as expected for an undersized ablator.
- **120% of required initial thickness** (16.29 mm): remaining after
  recession = 7.71 mm, margin = **+2.71 mm** -- **PASSES**, as expected for
  an oversized ablator.

### Sensitivity: effective heat of ablation (H_eff)

| H_eff variant | H_eff [J/kg] | Recession [mm] | t_initial [mm] | Areal mass [kg/m^2] |
|---|---|---|---|---|
| -25% | 7.500e+06 | 11.43 | 16.43 | 23.000 |
| baseline | 1.000e+07 | 8.57 | 13.57 | 19.000 |
| +25% | 1.250e+07 | 6.86 | 11.86 | 16.600 |

Recession depth (and therefore required initial thickness and areal mass)
scales **inversely** with `H_eff` at fixed heat load and density: a
higher-`H_eff` material sacrifices less mass for the same absorbed energy.
This is a property of the lumped model's parameters, not a statement that
`H_eff` alone determines overall TPS system quality.

This case is explicitly illustrative; it is not tuned to represent any
specific real ablative material or entry environment, and is not compared
against the Milestone 1/2 reusable-TPS results here.

## Trade study result (Milestone 4)

Run via [examples/tps_material_trade.py](examples/tps_material_trade.py)
against the canonical `STUDY_CASE`:

**Reusable candidates:**

| Name | Feasible | Thickness [mm] | Areal mass [kg/m^2] | Peak T_back [K] | Margin [K] | alpha [m^2/s] |
|---|---|---|---|---|---|---|
| Reusable low-density tile (illustrative) | True | 16.20 | 5.67 | 449.9 | +0.148 | 1.633e-07 |
| Reusable fibrous blanket (illustrative) | **False** | -- | -- | -- | -- | -- |

The fibrous blanket is infeasible: the study case's 1400 K peak hot-side
temperature exceeds its 1250 K `max_service_temperature`, so it is never
sized.

**Ablative candidates:**

| Name | Feasible | Initial thickness [mm] | Areal mass [kg/m^2] | Recession [mm] | Consumed mass [%] | Retained thickness [mm] |
|---|---|---|---|---|---|---|
| Lightweight charring ablator (illustrative) | True | 77.43 | 21.68 | 71.43 | 92.3 | 6.00 |
| Dense high-H_eff ablator (illustrative) | True | 13.57 | 19.00 | 8.57 | 63.2 | 5.00 |

**Ranking (feasible candidates, lightest first):**

1. Reusable low-density tile (illustrative) -- reusable -- 5.67 kg/m^2
2. Dense high-H_eff ablator (illustrative) -- ablative -- 19.00 kg/m^2
3. Lightweight charring ablator (illustrative) -- ablative -- 21.68 kg/m^2

**Preliminary recommendation:** the minimum-areal-mass FEASIBLE candidate
under this simplified model for this study case is the **Reusable
low-density tile (illustrative)**, 13.33 kg/m^2 lighter than the next
feasible candidate. This is the minimum-mass candidate **under this
simplified model for this specific illustrative study case** -- it is
**not** a claim about the best real spacecraft TPS (see "Engineering
interpretation (Milestone 4)" above for why).

### Heating-duration sensitivity

Holding the peak hot-side temperature and heat flux fixed and varying only
the heating-pulse duration:

| Duration | Reusable tile mass [kg/m^2] | Lightweight ablator mass [kg/m^2] | Dense ablator mass [kg/m^2] | Winner |
|---|---|---|---|---|
| 60 s (shorter) | 4.01 | 11.68 (feasible) | 13.00 | Reusable tile |
| 120 s (baseline) | 5.67 | 21.68 (feasible) | 19.00 | Reusable tile |
| 240 s (longer) | 8.01 | 41.68 (**infeasible**: exceeds 90 mm recession allowable) | 31.00 | Reusable tile |

The reusable candidate's required mass grows relatively slowly with
duration (transient penetration scales with the square root of time),
while each ablative candidate's consumed mass grows linearly with the
constant heat flux held over a longer time. In this study case **the
ranking does not cross over** -- the reusable tile remains the
minimum-mass feasible candidate at every duration tested -- but the
lightweight charring ablator becomes infeasible at the longest duration
because its recession exceeds its illustrative structural allowable,
independent of the mass ranking itself. No crossover was forced; this is
simply what the numbers show for this candidate set and case.

## Lifecycle trade result (Milestone 5)

Run via [examples/tps_lifecycle_trade.py](examples/tps_lifecycle_trade.py),
using the SAME candidates and study case as Milestone 4, with baseline
illustrative lifecycle assumptions: reusable service life = 50 missions,
refurbishment-equivalent fraction = 1% of installed mass per mission.

**Mission-count sensitivity** (cumulative lifecycle burden, kg/m^2-equivalent):

| Missions | Reusable low-density tile | Lightweight charring ablator | Dense high-H_eff ablator | Winner |
|---|---|---|---|---|
| 1 | 5.73 | 21.68 | 19.00 | Reusable tile |
| 5 | 5.95 | 101.68 | 67.00 | Reusable tile |
| 10 | 6.24 | 201.68 | 127.00 | Reusable tile |
| 25 | 7.09 | 501.68 | 307.00 | Reusable tile |
| 50 | 8.50 | 1001.68 | 607.00 | Reusable tile |
| 100 | 17.01 | 2001.68 | 1207.00 | Reusable tile |

(The fibrous blanket remains excluded throughout -- it never becomes
lifecycle-feasible; thermal infeasibility is never overridden by lifecycle
assumptions.)

**Single-event vs. lifecycle winners**: the single-event (Milestone 4)
winner, the 50-mission lifecycle winner, and the 100-mission lifecycle
winner are all the **Reusable low-density tile (illustrative)** in this
study case -- the two kinds of conclusion happen to agree here, but
Milestone 5's own verification tests include a constructed counter-example
showing they do not have to.

**Break-even analysis** (reusable tile vs. dense high-H_eff ablator, 1-500
missions): **no crossover found** -- the tile leads throughout the searched
range (burden at 500 missions: tile = 85.03 kg/m^2-equivalent vs. dense
ablator = 6007.00 kg/m^2-equivalent). This is a real result of this
candidate set's parameters, not a forced outcome.

**Service-life sensitivity** (reusable tile, 100 missions, f_refurb = 1%):

| N_service | Cumulative burden | Replacements |
|---|---|---|
| 10 | 62.36 | 9 |
| 25 | 28.34 | 3 |
| 50 | 17.01 | 1 |
| 100 | 11.34 | 0 |

Even at the shortest illustrative service life tested (10 missions), the
tile's burden (62.36) stays far below the dense ablator's 100-mission
burden (1207.00) -- the ranking does not change.

**Refurbishment-fraction sensitivity** (reusable tile, 50 missions):

| f_refurb | Cumulative burden |
|---|---|
| 0% | 5.67 |
| 1% | 8.50 |
| 2% | 11.34 |
| 5% | 19.84 |

Again far below the dense ablator's 50-mission burden (607.00) across the
whole sensitivity range tested.

**Takeaway for this study case**: neither service-life nor
refurbishment-fraction sensitivity changes the ranking, because these
ablative candidates' per-mission consumed mass is large relative to the
reusable tile's installation/refurbishment burden. This is a property of
*these* illustrative candidates and assumptions -- a different candidate
set (e.g. a much lower-consumption ablator, or a very short reusable
service life) could show a different, or crossing, result. All lifecycle
parameters here are illustrative; this is not a claim about real
operational cost.

## Install & test

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest -q
python examples/sanity_case.py
python examples/transient_heating_study.py
python examples/ablative_sanity_case.py
python examples/tps_material_trade.py
python examples/tps_lifecycle_trade.py
```

## License

No license has been chosen yet; no rights are granted to use this code
until a `LICENSE` file is added.
