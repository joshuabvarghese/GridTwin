# Limitations / Known Issues

## Power flow
- Runs a single-snapshot Newton-Raphson AC power flow (`pp.runpp`) per request. There's no time-series / load-profile simulation, so results reflect one static loading condition, not a day or year of operation.
- DER placement in `apply_uniform_solar_adoption` is uniform-by-load-bus (every load-carrying bus gets solar sized off its own peak demand). It doesn't model realistic clustering (e.g. adoption concentrated on one
  lateral), which is usually where hosting-capacity limits actually bite first in real feeders.
- No protection/thermal coordination checks (fuse/recloser limits, conductor thermal ratings beyond `loading_percent`) - `loading_percent` is pandapower's steady-state ampacity ratio, not a full protection study.

## Testing
- `tests/test_network.py` and `tests/test_api.py` cover the core power-flow/DER/API logic but don't cover convergence-failure paths (e.g. an intentionally pathological topology) beyond the generic `except Exception` fallback in `hosting_capacity_sweep`.
- `tests/test_converter.py` and `tests/test_solver.py` cover the new CIM-conversion and per-node hosting-capacity logic, including a couple of `InvalidCIMTopologyError`/`ValueError` edge cases.
