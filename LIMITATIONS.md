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
- `cim_network.py` builds CIM objects from a hard-coded table by
  default. `ewb_client.py` adds an alternate path that fetches a feeder
  from a live EWB server instead (`GRIDTWIN_EWB_HOST`), using the real
  SDK client. Its request shape is confirmed against the public wire
  contract (`zepben/ewb-grpc`'s `nc-requests.proto`), but the round
  trip itself hasn't been run against an actual EWB server, since
  Zepben's server isn't publicly available to test against.
  `test_ewb_client.py` covers the client glue code (channel selection,
  error handling) against a mocked SDK client, not a real one.
- `converter.py` is a from-scratch traversal of a `NetworkService`, not
  a subclass of the SDK's own `BusBranchNetworkCreator` (a real,
  installed generic base class for building a bus-branch network from
  CIM - `zepben.ewb.BusBranchNetworkCreator`). Zepben's own example
  repo (`ewb-sdk-examples-python`) shows a concrete pandapower
  subclass of it (`BasicPandaPowerNetworkCreator`), but that class
  itself lives in a local, unpublished module the example imports and
  isn't installable, so there's nothing to actually inherit from
  outside their own repo. Subclassing the real base class properly (it
  has eight generic type parameters) would be a substantial rewrite for
  a converter that already works correctly at this project's scale;
  noted here rather than done, so it isn't quietly presented as more
  aligned with their architecture than it is.
- The synthetic map coordinates (`geo.py`) are hardcoded for the
  standard 33-bus topology. A feeder fetched from a live EWB server
  with a different shape won't crash - unknown buses just fall back to
  the substation's coordinates - but the map layout won't be
  meaningful for it.

## Power flow
- `/status`, `/adoption-slider` and `/hosting-capacity` run a single
  Newton-Raphson solve at whatever DER level is currently set.
  `/daily-profile` (`timeseries.py`) instead re-solves once per hour of
  a day with load and DER output scaled by profiles derived from real
  interval data - LOAD_PROFILE from the actual substation feeding this
  feeder, SOLAR_PROFILE from a different region entirely (the best real
  solar-generation shape available, not a genuine match). See
  `PROFILES.md` for the full derivation and what it does and doesn't
  get right.
- DER placement is uniform across every load bus, not clustered on one
  lateral (which is usually where hosting-capacity limits bite first in
  real feeders). Every bus also follows the same load/solar shape - no
  per-customer variation (there is now real per-month/seasonal
  variation for `/annual-profile` - see below).
- `/annual-profile` samples 288 representative hours (12 months x 24
  hours), not a full 8,760/17,520-point year - a deliberate trade-off
  for keeping a live request fast on this project's single shared
  feeder (see `timeseries.py`'s docstring for the actual measured
  cost). Its per-bus/per-line summary is modeled after Zepben's real
  `AssetLevelVoltageSummaryReport` / `AssetLevelThermalLoadingSummaryReport`
  proto messages, but doesn't reproduce every field: no per-phase
  results (this project is a balanced single-phase-equivalent model),
  no exact calendar timestamps (representative days stand in for real
  ones, so only month+hour is reported), and no energy/kWh
  accumulation fields.
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
- `tests/test_timeseries.py` covers the daily profile (shape, zero
  solar overnight, violations clustering at midday under heavy solar
  rather than at peak load, feeder left reset afterward) and the
  annual profile (12 months returned, every bus/line summarized,
  reverse power flow detected under heavy adoption and absent at zero
  adoption, feeder left reset afterward).
- `tests/test_ewb_client.py` covers the live-EWB-server glue code
  against a mocked SDK client (channel selection, mrid passed through,
  error handling) - see the network model caveat above.
