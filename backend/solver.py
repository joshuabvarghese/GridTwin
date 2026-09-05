"""
GridTwin Hosting Capacity Engine

Ramps solar PV (or EV load) at a single target bus and finds the largest injection that keeps the feeder
within voltage and thermal limits.
"""
from __future__ import annotations
import copy
import pandapower as pp

V_MIN_PU = 0.95
V_MAX_PU = 1.05
MAX_LINE_LOADING_PCT = 100.0


class PowerFlowConvergenceError(Exception):
    """Raised when pp.runpp() fails to converge during a hosting-capacity step."""


def _run_and_check(net: pp.pandapowerNet) -> tuple[bool, bool]:
    try:
        pp.runpp(net, algorithm="nr")
    except Exception as e:
        raise PowerFlowConvergenceError(str(e)) from e
    overvoltage = bool((net.res_bus.vm_pu < V_MIN_PU).any() or (net.res_bus.vm_pu > V_MAX_PU).any())
    overloaded = bool((net.res_line.loading_percent > MAX_LINE_LOADING_PCT).any())
    return overvoltage, overloaded


def calculate_hosting_capacity(
    net: pp.pandapowerNet,
    target_node_id: int,
    max_solar_kw: float,
    step_kw: float = 5.0,
) -> dict:
    """Iteratively increase solar PV injection at `target_node_id` until a voltage or thermal violation appears, or `max_solar_kw` is reached.
    Operates on a private copy of `net` - the caller's network/state is untouched."""
    if target_node_id not in net.bus.index:
        raise ValueError(f"Unknown bus/node id {target_node_id}")
    if step_kw <= 0:
        raise ValueError("step_kw must be positive")

    working = copy.deepcopy(net)
    sgen_idx = pp.create_sgen(working, bus=target_node_id, p_mw=0.0, q_mvar=0.0, name="hc-probe")

    max_allowed_kw = 0.0
    overvoltage_flag = False
    overload_flag = False
    kw = step_kw
    while kw <= max_solar_kw:
        working.sgen.at[sgen_idx, "p_mw"] = kw / 1000.0
        overvoltage, overloaded = _run_and_check(working)
        if overvoltage or overloaded:
            overvoltage_flag, overload_flag = overvoltage, overloaded
            break
        max_allowed_kw = kw
        kw += step_kw

    return {
        "target_node_id": target_node_id,
        "max_allowable_kw": round(max_allowed_kw, 3),
        "reached_ceiling": max_allowed_kw >= max_solar_kw,
        "overvoltage": overvoltage_flag,
        "line_overload": overload_flag,
    }
