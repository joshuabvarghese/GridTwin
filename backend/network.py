"""
GridTwin - Network Topology Layer

Loads the IEEE 33-bus radial feeder from real zepben.ewb CIM objects into a pandapower model, and exposes it as a CIM-flavoured graph structure:
    Nodes  -> Bus / ConnectivityNode  (substations, houses/load points)
    Edges  -> ACLineSegment (power lines)
    Assets -> PowerTransformer, EnergyConsumer, PhotovoltaicUnit

Everything downstream (power flow engine, API, frontend) only talks to this module's `Feeder` class, so the CIM objects only need to be built once, here, at __init__ time. Swapping `cim_network.build_cim_network()` for a live EWB-server query is a drop-in replacement.
"""
from __future__ import annotations
import pandapower as pp
import networkx as nx
from dataclasses import dataclass, field

import cim_network
import converter
import ieee33_data
import solver
import geo


@dataclass
class DERAsset:
    node_id: int
    kind: str          # "solar" | "ev"
    kw: float          # positive = consumption (EV), will be negated for solar


class Feeder:
    """Wraps a pandapower network and exposes a NetworkX graph view."""

    def __init__(self, load_scale: float = 0.55):
        # The published IEEE 33-bus benchmark is a classic *stressed*
        # feeder (min ~0.90 pu at full load by design). We scale baseline
        # load down so the feeder starts healthy (green) and DER adoption
        # is what drives it into warning/violation territory - matches
        # how the demo should feel.
        ns, _source = cim_network.build_cim_network()
        self.net = converter.cim_to_pandapower(
            ns, vn_kv=ieee33_data.VN_KV, base_mva=ieee33_data.BASE_MVA,
        )
        self.net.load["p_mw"] *= load_scale
        self.net.load["q_mvar"] *= load_scale
        self._baseline_loads = self.net.load[["bus", "p_mw", "q_mvar"]].copy()
        self.ders: list[DERAsset] = []
        # Indices of load rows that add_der() created for buses with NO
        # baseline load (EV charger on an otherwise unloaded bus). reset_ders()
        # must drop these rows - restoring p/q from _baseline_loads only
        # touches the original rows, so without this list those rows would
        # leak past the reset.
        self._created_load_idx: list[int] = []
        self.graph = self._build_graph()
        # Synthetic Lat/Lon layout for the GIS/map view - purely cosmetic,
        # computed once from the (fixed) topology and never touches the
        # power-flow model. See geo.py.
        self._geo_coords = geo.compute_synthetic_coordinates(self.graph)

    #  CIM-ish graph construction 
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

    #  DER management
    def reset_ders(self):
        self.ders = []
        self.net.load.loc[self._baseline_loads.index, ["p_mw", "q_mvar"]] = self._baseline_loads[["p_mw", "q_mvar"]]
        # Drop load rows add_der() created on buses with no baseline load;
        # the restore above only touches baseline rows, so without this
        # those EV rows would survive the reset.
        if self._created_load_idx:
            self.net.load.drop(index=self._created_load_idx, inplace=True)
            self._created_load_idx = []
        # drop any sgen (solar) rows we've added
        self.net.sgen.drop(self.net.sgen.index, inplace=True)

    def add_der(self, node_id: int, kind: str, kw: float):
        if node_id not in self.net.bus.index:
            raise ValueError(f"Unknown bus/node id {node_id}")
        self.ders.append(DERAsset(node_id, kind, kw))
        mw = kw / 1000.0
        if kind == "ev":
            # EV charger = extra load at that bus
            existing = self.net.load[self.net.load.bus == node_id]
            if len(existing):
                self.net.load.loc[existing.index, "p_mw"] += mw
            else:
                new_idx = pp.create_load(
                    self.net, bus=node_id, p_mw=mw, q_mvar=0.0, name=f"ev_{node_id}",
                )
                self._created_load_idx.append(new_idx)
        elif kind == "solar":
            # Solar PV = static generator (injects real power, ~unity PF)
            pp.create_sgen(self.net, bus=node_id, p_mw=mw, q_mvar=0.0, name=f"pv_{node_id}")
        else:
            raise ValueError("kind must be 'ev' or 'solar'")

    def apply_uniform_adoption(self, kind: str, adoption_pct: float, oversize_ratio: float):
        """Slider hook: 0-100% adoption of `kind` ("solar" or "ev"). Each load bus represents a cluster of houses, so DER size scales with that node's own peak load rather than a flat kW figure - e.g. at 100% solar adoption every node's rooftop PV nameplate capacity eaches `oversize_ratio`x its local peak demand, which is what
        drives reverse power flow / over-voltage as adoption climbs.The same sizing rule applies to EV adoption, just with a smaller `oversize_ratio` since EV chargers add load rather than generation.
        """
        load_buses = sorted(self.net.load.bus.unique().tolist())
        for bus in load_buses:
            base_mw = self._baseline_loads.loc[self._baseline_loads.bus == bus, "p_mw"].sum()
            der_kw = base_mw * 1000 * oversize_ratio * (adoption_pct / 100.0)
            if der_kw > 0.01:
                self.add_der(bus, kind, der_kw)

    def apply_uniform_solar_adoption(self, adoption_pct: float, oversize_ratio: float = 4.5):
        """Solar-specific convenience wrapper around apply_uniform_adoption (kept for the sweep default and any existing callers)."""
        self.apply_uniform_adoption("solar", adoption_pct, oversize_ratio)

    # ---------- Power flow ----------
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
        """Ramp adoption 0->100% to find the % where the first violation occurs."""
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

    def hosting_capacity_for_node(self, node_id: int, max_solar_kw: float = 500.0, step_kw: float = 5.0) -> dict:
        """Per-node hosting capacity: how much solar can this one bus takebefore a voltage or thermal violation, holding every other bus at its current state (DERs already applied elsewhere are preserved)."""
        return solver.calculate_hosting_capacity(self.net, node_id, max_solar_kw, step_kw=step_kw)

    # GIS / map view
    def to_geojson(self, status_report: dict = None) -> dict:
        """Latest (or freshly-run) power-flow status serialized as GeoJSON for the map view. Doesn't touch power-flow logic itself - just reads the topology + a status report and hands off to geo.py."""
        if status_report is None:
            status_report = self.run_powerflow()
        return geo.build_geojson(self, status_report)



