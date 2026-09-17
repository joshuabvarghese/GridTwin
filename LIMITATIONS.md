# Limitations / Known Issues

## Network model
- Uses real `zepben.ewb` CIM objects for topology and impedances
  (`cim_network.py`, `converter.py`), built from the published Baran & Wu
  33-bus table (`ieee33_data.py`), not pandapower's bundled `case33bw()`.
- The dataset gives one aggregate impedance per branch, not a conductor
  spec + length, so each branch is modeled as its own
  `PerLengthSequenceImpedance` over a fixed 1 km length. The numbers come
  out right, but it isn't a real conductor catalogue.
- The 5 normally-open tie switches from the original paper aren't
  modeled - only the 32 normally-closed branches are built.
- Still a balanced single-phase-equivalent model; per-phase unbalance
  (relevant to single-phase rooftop solar) isn't represented.
- `cim_network.py` builds CIM objects from a hard-coded table rather than
  an ingested RDF/XML file or a live EWB-server query.

## Power flow
- Single-snapshot Newton-Raphson AC power flow per request - no
  time-series simulation, so results reflect one static loading
  condition.
- DER placement is uniform across every load bus, not clustered on one
  lateral (which is usually where hosting-capacity limits bite first in
  real feeders).
- No protection/thermal coordination checks beyond `loading_percent`
  (pandapower's steady-state ampacity ratio).

## API / state
- `main.py` holds a single module-level `Feeder` shared by all requests -
  fine for a single-user demo, not safe for concurrent multi-user
  sessions (one user's `/reset` clears everyone's DERs).
- CORS is locked to a fixed list of local dev origins; update
  `GRIDTWIN_CORS_ORIGINS` before deploying the frontend elsewhere.

## Testing
- `tests/test_network.py` and `tests/test_api.py` cover the core power
  flow/DER/API logic but not convergence-failure paths beyond the
  generic `except Exception` fallback in `hosting_capacity_sweep`.
- `tests/test_converter.py` covers CIM-conversion edge cases
  (`InvalidCIMTopologyError`, missing energy source, etc).
