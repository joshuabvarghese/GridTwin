"""
Feeder: graph + DER model on top of a pandapower network.

Builds the IEEE 33-bus feeder from CIM objects (cim_network.py) and
converts it to pandapower (converter.py), then exposes it as a NetworkX
graph with helpers for adding DERs and running power flow. Everything
else (API, frontend) only talks to this class.

The CIM model itself comes from either source, chosen by
_load_cim_network(): a hardcoded local build by default, or a live EWB
server if GRIDTWIN_EWB_HOST is set (ewb_client.py). converter.py can't
tell the two apart - it only ever reads a NetworkService.
"""
from __future__ import annotations
import os
import pandapower as pp
import networkx as nx
from dataclasses import dataclass

import cim_network
import converter
import ewb_client
import ieee33_data
import geo


@dataclass
class DERAsset:
    node_id: int
    kind: str          # "solar" | "ev"
    kw: float          # positive = consumption (EV), will be negated for solar


class Feeder:
    """Wraps a pandapower network and exposes a NetworkX graph view."""

    def __init__(self, load_scale: float = 0.55):
        # The published 33-bus benchmark is stressed even at baseline
        # (~0.90 pu at full load), so we scale load down to start the
        # feeder healthy - DER adoption is what pushes it into warning
        # /violation territory.
        ns, _source = self._load_cim_network()
        vn_kv = float(os.environ.get("GRIDTWIN_EWB_VN_KV", ieee33_data.VN_KV))
        base_mva = float(os.environ.get("GRIDTWIN_EWB_BASE_MVA", ieee33_data.BASE_MVA))
        self.net = converter.cim_to_pandapower(ns, vn_kv=vn_kv, base_mva=base_mva)
        self.net.load["p_mw"] *= load_scale
        self.net.load["q_mvar"] *= load_scale
        self._baseline_loads = self.net.load[["bus", "p_mw", "q_mvar"]].copy()
        self.ders: list[DERAsset] = []
        # Load rows add_der() created for buses with no baseline load
        # (e.g. an EV charger on an otherwise unloaded bus). reset_ders()
        # drops these explicitly since they have nothing to restore.
        self._created_load_idx: list[int] = []
        self.graph = self._build_graph()
        # Cosmetic lat/lon layout for the map view, computed once from
        # the (fixed) topology. Never touches the power-flow model.
        self._geo_coords = geo.compute_synthetic_coordinates(self.graph)

    @staticmethod
    def _load_cim_network():
        """Build the IEEE 33-bus CIM model locally (default), or fetch
        a feeder from a live EWB server if GRIDTWIN_EWB_HOST is set -
        see ewb_client.py and README.md."""
        host = os.environ.get("GRIDTWIN_EWB_HOST")
        if not host:
            return cim_network.build_cim_network()
        feeder_mrid = os.environ.get("GRIDTWIN_EWB_FEEDER_MRID", "gridtwin-feeder")
        port = int(os.environ.get("GRIDTWIN_EWB_PORT", "50051"))
        token = os.environ.get("GRIDTWIN_EWB_TOKEN")
        return ewb_client.fetch_feeder(host, feeder_mrid, port=port, token=token), None

    def _build_graph(self) -> nx.Graph:
        g = nx.Graph()
        for _, row in self.net.bus.iterrows():
            g.add_node(int(row.name), vn_kv=row.vn_kv, cim_class="ConnectivityNode")
        for _, row in self.net.line.iterrows():
            g.add_edge(
                int(row.from_bus), int(row.to_bus),
                cim_class="ACLineSegment",
                length_km=row.length_km,
                line_id=int(row.name),
            )
        return g

    # DER management
    def reset_ders(self):
        self.ders = []
        self.net.load.loc[self._baseline_loads.index, ["p_mw", "q_mvar"]] = self._baseline_loads[["p_mw", "q_mvar"]]
        if self._created_load_idx:
            self.net.load.drop(index=self._created_load_idx, inplace=True)
            self._created_load_idx = []
        self.net.sgen.drop(self.net.sgen.index, inplace=True)

    def add_der(self, node_id: int, kind: str, kw: float):
        if node_id not in self.net.bus.index:
            raise ValueError(f"Unknown bus/node id {node_id}")
        self.ders.append(DERAsset(node_id, kind, kw))
        mw = kw / 1000.0
        if kind == "ev":
            # EV charger = extra load at that bus.
            existing = self.net.load[self.net.load.bus == node_id]
            if len(existing):
                self.net.load.loc[existing.index, "p_mw"] += mw
            else:
                new_idx = pp.create_load(
                    self.net, bus=node_id, p_mw=mw, q_mvar=0.0, name=f"ev_{node_id}",
                )
                self._created_load_idx.append(new_idx)
        elif kind == "solar":
            # Solar PV = static generator, ~unity power factor.
            pp.create_sgen(self.net, bus=node_id, p_mw=mw, q_mvar=0.0, name=f"pv_{node_id}")
        else:
            raise ValueError("kind must be 'ev' or 'solar'")

    def apply_uniform_adoption(self, kind: str, adoption_pct: float, oversize_ratio: float):
        """Apply `adoption_pct` (0-100) of `kind` to every load bus.

        Each bus represents a cluster of houses, so DER size scales with
        that bus's own peak load rather than a flat kW figure: at 100%
        solar adoption, every bus's PV nameplate reaches `oversize_ratio`x
        its peak demand, which is what drives over-voltage as adoption
        climbs. EV adoption uses the same rule with a smaller ratio,
        since chargers add load instead of generation.
        """
        load_buses = sorted(self.net.load.bus.unique().tolist())
        for bus in load_buses:
            base_mw = self._baseline_loads.loc[self._baseline_loads.bus == bus, "p_mw"].sum()
            der_kw = base_mw * 1000 * oversize_ratio * (adoption_pct / 100.0)
            if der_kw > 0.01:
                self.add_der(bus, kind, der_kw)

    def apply_uniform_solar_adoption(self, adoption_pct: float, oversize_ratio: float = 4.5):
        self.apply_uniform_adoption("solar", adoption_pct, oversize_ratio)

    # Power flow
    def run_powerflow(self):
        pp.runpp(self.net, algorithm="nr")
        return self.status_report()

    def status_report(self) -> dict:
        buses = []
        for idx, row in self.net.res_bus.iterrows():
            # ANSI C84.1-ish bands: Range A (normal) 0.95-1.05,
            # Range B (warning) down to 0.917 / up to 1.058, else violation.
            vm = row.vm_pu
            status = "normal"
            if vm < 0.917 or vm > 1.058:
                status = "overloaded"
            elif vm < 0.95 or vm > 1.05:
                status = "warning"
            buses.append({
                "node_id": int(idx),
                "vm_pu": round(float(vm), 4),
                "va_degree": round(float(row.va_degree), 3),
                "status": status,
            })

        lines = []
        for idx, row in self.net.res_line.iterrows():
            loading = row.loading_percent
            status = "normal"
            if loading > 100:
                status = "overloaded"
            elif loading > 80:
                status = "warning"
            src = self.net.line.at[idx, "from_bus"]
            dst = self.net.line.at[idx, "to_bus"]
            lines.append({
                "line_id": int(idx),
                "from_bus": int(src),
                "to_bus": int(dst),
                "loading_percent": round(float(loading), 2),
                "status": status,
            })

        n_overload = sum(1 for b in buses if b["status"] == "overloaded") + \
                     sum(1 for l in lines if l["status"] == "overloaded")

        return {
            "buses": buses,
            "lines": lines,
            "der_count": len(self.ders),
            "violations": n_overload,
            "converged": bool(self.net["converged"]) if "converged" in self.net else True,
        }

    def hosting_capacity_sweep(self, kind: str = "solar", step_pct: int = 5, oversize_ratio: float = None):
        """Ramp adoption 0->100% and report the % where the first violation occurs."""
        if oversize_ratio is None:
            oversize_ratio = 4.5 if kind == "solar" else 1.5
        results = []
        breach_pct = None
        for pct in range(0, 101, step_pct):
            self.reset_ders()
            self.apply_uniform_adoption(kind, pct, oversize_ratio)
            try:
                report = self.run_powerflow()
            except Exception:
                report = {"violations": 999, "converged": False}
            violations = report.get("violations", 0)
            results.append({"adoption_pct": pct, "violations": violations})
            if violations > 0 and breach_pct is None:
                breach_pct = pct
        self.reset_ders()
        return {"sweep": results, "hosting_capacity_pct": breach_pct if breach_pct is not None else 100}

    # GIS / map view
    def to_geojson(self, status_report: dict = None) -> dict:
        if status_report is None:
            status_report = self.run_powerflow()
        return geo.build_geojson(self, status_report)
