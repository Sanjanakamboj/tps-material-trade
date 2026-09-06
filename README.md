# TPS Material Trade (STM-05)

## Objective

For a prescribed atmospheric-entry thermal environment, how do candidate
reusable and ablative TPS (thermal protection system) concepts compare in
thermal capability, required thickness/mass, reuse characteristics, and
design margin?

The final deliverable (later milestones) is an engineering trade table and a
recommended TPS material/system.

## Current scope: Milestone 1

This milestone builds **only** the thermal-sizing foundation: a verified,
one-dimensional, steady-state conduction model for a single homogeneous TPS
slab. It does **not** implement ablative recession, pyrolysis, material
optimization, multi-material trade scoring, lifecycle/reuse scoring,
trajectory simulation, CFD, radiation transport, transient finite-element
conduction, or a final material recommendation. Those are explicitly out of
scope until later milestones.

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

## Governing equations

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
- optional `specific_heat` (cp) [J/(kg*K)] for future transient work
  (validated if provided, unused by the steady model)

Boundary conditions (`T_hot`, `q''`, `T_back,max`) are **not** stored on the
material; they are supplied per analysis case, so the same material object
can be reused across sizing cases with different environments.

Only one illustrative material is included at this milestone, and its
properties are explicitly labeled illustrative (order-of-magnitude
representative of a low-density ceramic tile insulator) rather than sourced
design allowables.

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

## Verification summary

38 automated tests in [tests/](tests/) cover:

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

All 38 tests currently pass.

## Sanity-case result

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

## Install & test

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest -q
python examples/sanity_case.py
```

## License

No license has been chosen yet; no rights are granted to use this code
until a `LICENSE` file is added.
