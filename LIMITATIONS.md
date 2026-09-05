# Limitations / Known Issues

## Testing
- `tests/test_network.py` and `tests/test_api.py` cover the core
  power-flow/DER/API logic but don't cover convergence-failure paths
  (e.g. an intentionally pathological topology) beyond the generic
  `except Exception` fallback in `hosting_capacity_sweep`.
- `tests/test_converter.py` and `tests/test_solver.py` cover the new
  CIM-conversion and per-node hosting-capacity logic, including a couple
  of `InvalidCIMTopologyError`/`ValueError` edge cases.
