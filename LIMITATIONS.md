# Limitations / Known Issues


## Network model
- Uses real `zepben.ewb` CIM objects for the network topology and
  impedances (`cim_network.py`, `converter.py`) — `ConnectivityNode`,
  `EnergySource`, `AcLineSegment` + `PerLengthSequenceImpedance`,
  `EnergyConsumer` — built from the published Baran & Wu 33-bus table
  (`ieee33_data.py`), not `pandapower`'s bundled `case33bw()`. `converter.py`
  is the only place that walks the CIM object graph; everything else
  only ever sees the resulting pandapower net.
- The published 33-bus dataset gives one aggregate impedance per branch,
  not a conductor spec + length. Each branch is modeled as its own
  `PerLengthSequenceImpedance` with the published R/X applied over a
  fixed 1 km length, so the numbers come out right, but the per-branch
  `PerLengthSequenceImpedance` objects don't represent a real conductor
  catalogue the way a genuine CIM export would.
- The 5 normally-open tie switches from the original Baran & Wu paper
  aren't modeled — this codebase has no switch-state concept, so only
  the 32 normally-closed branches are built. (`pandapower`'s `case33bw()`
  includes all 37 as lines, 5 permanently open; the earlier version of
  this project inherited that count, current tests reflect the 32-line
  reality.)
- Still a balanced single-phase-equivalent representation — real LV
  networks are unbalanced across phases; per-phase unbalance (relevant
  to single-phase rooftop solar placement) isn't modeled.
- This is still not a live CIM RDF/XML or EWB-server import — `cim_network.py`
  builds the CIM objects from a hard-coded table rather than an ingested
  file/query. Swapping `build_cim_network()`'s body for either is the
  intended next step (see the NOTE at the bottom of `network.py`).

## Power flow
- Runs a single-snapshot Newton-Raphson AC power flow (`pp.runpp`) per
  request. There's no time-series / load-profile simulation, so results
  reflect one static loading condition, not a day or year of operation.
- DER placement in `apply_uniform_solar_adoption` is uniform-by-load-bus
  (every load-carrying bus gets solar sized off its own peak demand). It
  doesn't model realistic clustering (e.g. adoption concentrated on one
  lateral), which is usually where hosting-capacity limits actually bite
  first in real feeders.
- No protection/thermal coordination checks (fuse/recloser limits,
  conductor thermal ratings beyond `loading_percent`) - `loading_percent`
  is pandapower's steady-state ampacity ratio, not a full protection
  study.

## API / state
- `main.py` holds a single module-level `Feeder` instance shared by all
  requests - fine for a single-user demo, not safe for concurrent
  multi-user sessions (one user's `/reset` clears everyone's DERs).
- CORS is currently locked to a fixed list of local dev origins
  (`localhost`/`127.0.0.1` on `:8080` and `:3000`, see `main.py`); update
  that list before deploying the frontend anywhere else.

## Testing
- `tests/test_network.py` and `tests/test_api.py` cover the core
  power-flow/DER/API logic but don't cover convergence-failure paths
  (e.g. an intentionally pathological topology) beyond the generic
  `except Exception` fallback in `hosting_capacity_sweep`.
- `tests/test_converter.py` and `tests/test_solver.py` cover the new
  CIM-conversion and per-node hosting-capacity logic, including a couple
  of `InvalidCIMTopologyError`/`ValueError` edge cases.
