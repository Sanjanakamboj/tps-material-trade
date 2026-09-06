# TPS Material Trade (STM-05)

## Objective

For a prescribed atmospheric-entry thermal environment, how do candidate
reusable and ablative TPS (thermal protection system) concepts compare in
thermal capability, required thickness/mass, reuse characteristics, and
design margin?

The final deliverable (later milestones) is an engineering trade table and a
recommended TPS material/system.

## Current scope: Milestone 1 + Milestone 2

**Milestone 1** built a verified, one-dimensional, **steady-state**
conduction model for a single homogeneous TPS slab (a simple analytical
reference case; see "Steady conduction (Milestone 1)" below).

**Milestone 2** adds a verified, one-dimensional, **transient**
(time-dependent) conduction model, so a slab can be sized against a
finite-duration hot-side heating pulse rather than only an indefinitely
sustained steady boundary condition (see "Transient conduction (Milestone
2)" below).

Neither milestone implements ablative recession, pyrolysis, material mass
loss, reusable-vs-ablative material trade scoring, a convective/radiative
surface energy balance, temperature-dependent conductivity, lifecycle/reuse
scoring, trajectory simulation, CFD, radiation transport, or a final
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

## Verification summary

69 automated tests in [tests/](tests/) cover both the steady model
(Milestone 1, 38 tests) and the transient model (Milestone 2, 31 tests):

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

All 69 tests currently pass.

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

## Install & test

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest -q
python examples/sanity_case.py
python examples/transient_heating_study.py
```

## License

No license has been chosen yet; no rights are granted to use this code
until a `LICENSE` file is added.
