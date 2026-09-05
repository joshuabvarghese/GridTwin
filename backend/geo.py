"""
GridTwin Synthetic Geography Layer

The IEEE 33-bus benchmark (see ieee33_data.py) only publishes branch
impedances and loads - no real-world coordinates. This module assigns
mock Lat/Lon positions to every bus so the feeder can be rendered on a
street map, without touching the CIM model, the pandapower conversion,
or the power-flow solver at all: it only reads `feeder.graph` (already
built by Feeder._build_graph()) and produces a bus_id -> (lat, lon) map.

Layout approach

Earlier versions of this module placed buses with pure trigonometry -
a fan radiating out from the substation by hop-count and angle. That's
topologically tidy but geographically blind: several buses landed
inside Mount Ainslie Nature Reserve, where no roads exist, so OSRM had
to detour ~5km around the mountain and the routed LineString no longer
touched the bus dot at either end.

compute_synthetic_coordinates() now instead looks each bus up in
ROAD_INTERSECTION_COORDS: a hardcoded table of real road-intersection
coordinates in North Canberra (Reid, Braddon, Turner, O'Connor,
Dickson), verified against real street data rather than computed. Every
bus sits exactly on a real corner or road-fronting address, so an OSRM
route between two adjacent buses starts and ends precisely on top of
their dots, and never needs to route around terrain that isn't there.

The table is laid out to loosely mirror the feeder's own radial
topology (see ieee33_data.BRANCHES): the 18-bus trunk (0-17) runs the
Reid -> Braddon -> Turner corridor along/near Northbourne Ave, and the
three laterals follow their own real corridors - Reid/Ainslie via
Limestone Ave (18-21), O'Connor via Miller St/Macpherson St (22-24),
and Dickson/Downer via Cowper St/Antill St (25-32) - but this is purely
cosmetic. It is not derived from hop-count or hop-count math, and does
not need to be: OSRM (see get_osrm_route()) does the real routing.

Cable routing: LineString features returned by build_geojson() don't
draw straight Euclidean lines between bus points either. Each segment
is routed along real street corridors via the public OSRM API, with
results cached in-process so the external HTTP call only happens once
per unique bus-pair, ever - not on every request, slider move, or
power-flow re-solve.
"""
from __future__ import annotations
import functools
import networkx as nx
import httpx

# City East Zone Substation, Coranderrk St, Reid - bus 0 / the feeder root.
DEFAULT_BASE_LAT = -35.2831
DEFAULT_BASE_LON = 149.1362

# Real road-intersection / street-address coordinates in North Canberra,
# one per bus. Bus 0 is the substation itself; every other bus (1-32) is
# a verified real corner or road-fronting address, never a computed
# point, so it's guaranteed to sit on a road OSRM can actually route to.
#
# Layout (mirrors ieee33_data.BRANCHES, 0-indexed):
#   Trunk   0->1->2->...->17   Reid -> Braddon -> Turner (Northbourne Ave corridor)
#   Lateral 1->18->19->20->21  Reid/Braddon/Ainslie (Limestone Ave corridor)
#   Lateral 2->22->23->24      O'Connor (Miller St / Macpherson St corridor)
#   Lateral 5->25->...->32     Dickson/Downer (Cowper St / Antill St corridor)
ROAD_INTERSECTION_COORDS: dict[int, tuple[float, float]] = {
    0: (DEFAULT_BASE_LAT, DEFAULT_BASE_LON),  # City East Zone Substation, Coranderrk St, Reid

    # Trunk: Reid -> Braddon -> Turner (buses 1-17)
    1: (-35.281398, 149.138969),   # Coranderrk St & Currong St S, Reid
    2: (-35.279223, 149.135626),   # Ainslie Ave & Cooyong St, Reid/Braddon
    3: (-35.280812, 149.134034),   # Bunda St (Two24 Bunda), Reid/City
    4: (-35.275861, 149.129864),   # Northbourne Ave & Cooyong St
    5: (-35.275768, 149.135421),   # Donaldson St & Currong St N, Braddon
    6: (-35.279349, 149.128675),   # Northbourne Ave, City/Braddon border
    7: (-35.275112, 149.131387),   # Mort St, Braddon
    8: (-35.273046, 149.133149),   # Elouera St & Lonsdale St, Braddon
    9: (-35.270926, 149.134121),   # Girrahween St, Braddon
    10: (-35.270874, 149.132386),  # Girrahween St & Mort St, Braddon
    11: (-35.275404, 149.126834),  # Barry Dr & Marcus Clarke St, Turner/City
    12: (-35.274442, 149.127691),  # McKay Ln, Turner/Braddon border
    13: (-35.272617, 149.126128),  # Watson St, Turner
    14: (-35.263877, 149.125923),  # Condamine St, Turner
    15: (-35.260552, 149.131925),  # Northbourne Ave & MacArthur Ave, Turner
    16: (-35.261001, 149.136386),  # Limestone Ave & Wakefield Ave, Ainslie
    17: (-35.275836, 149.142737),  # Ainslie Ave & Limestone Ave, Braddon

    # Lateral off bus 1: Reid/Braddon/Ainslie, Limestone Ave corridor (18-21)
    18: (-35.279542, 149.141308),  # Elimatta St, Reid/Braddon
    19: (-35.271819, 149.141531),  # Limestone Ave nr Ainslie Ave, Braddon
    20: (-35.282462, 149.138024),  # Coranderrk St, Reid
    21: (-35.280227, 149.133256),  # Bunda St, Reid/City

    # Lateral off bus 2: O'Connor, Miller St/Macpherson St corridor (22-24)
    22: (-35.264242, 149.122232),  # Macpherson St, O'Connor
    23: (-35.264186, 149.122941),  # Sargood St, O'Connor
    24: (-35.268924, 149.113211),  # David St & Dryandra St, O'Connor

    # Lateral off bus 5: Dickson/Downer, Cowper St/Antill St corridor (25-32)
    25: (-35.257267, 149.139856),  # Majura Ave & Cowper St, Dickson
    26: (-35.250327, 149.136426),  # Woolley St, Dickson
    27: (-35.251360, 149.137571),  # Badham St & Cape St, Dickson
    28: (-35.251013, 149.136335),  # Woolley St, Dickson
    29: (-35.248925, 149.136044),  # Antill St, Dickson
    30: (-35.248180, 149.133963),  # Northbourne Ave & Antill St, Lyneham/Downer
    31: (-35.248792, 149.140935),  # Antill St & Cowper St, Downer
    32: (-35.244895, 149.144600),  # Frencham Pl, Downer
}


def compute_synthetic_coordinates(
    graph: nx.Graph,
    root: int = 0,
    base_lat: float = DEFAULT_BASE_LAT,
    base_lon: float = DEFAULT_BASE_LON,
) -> dict[int, tuple[float, float]]:
    """Return {node_id: (lat, lon)} for every node in `graph`.

    Looks each node up in ROAD_INTERSECTION_COORDS - real North Canberra
    road-intersection coordinates - rather than computing a position.
    `root` (bus 0) always resolves to `(base_lat, base_lon)`, so callers
    can still re-anchor the substation without touching the table.

    Any node not in the hardcoded table (shouldn't happen for the
    standard 33-bus feeder, but kept safe for custom topologies) falls
    back to the substation's own coordinates rather than raising.
    """
    if root not in graph:
        raise ValueError(f"root node {root} not present in graph")

    coords: dict[int, tuple[float, float]] = {}
    for n in graph.nodes:
        if n == root:
            coords[n] = (base_lat, base_lon)
        else:
            coords[n] = ROAD_INTERSECTION_COORDS.get(n, (base_lat, base_lon))

    return coords


OSRM_BASE_URL = "http://router.project-osrm.org/route/v1/driving"
OSRM_TIMEOUT_S = 5.0


@functools.lru_cache(maxsize=None)
def get_osrm_route(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[tuple[float, float], ...]:
    """Return a street-following route (lon, lat) coordinate sequence
    between two points, via the public OSRM demo server.

    Cached with lru_cache keyed on the four coordinates, so each unique
    line segment is only ever fetched once (e.g. at startup / first
    /api/network/geojson call). Every later call - including slider
    moves and power-flow re-solves, which don't change bus positions -
    hits the in-memory cache and returns instantly with zero HTTP calls.

    Falls back to a straight two-point line if OSRM can't be reached,
    times out, or returns something unexpected, so the endpoint never
    breaks just because the public demo server is slow/unavailable.
    """
    fallback = ((lon1, lat1), (lon2, lat2))

    url = f"{OSRM_BASE_URL}/{lon1},{lat1};{lon2},{lat2}"
    params = {"overview": "full", "geometries": "geojson"}

    try:
        resp = httpx.get(url, params=params, timeout=OSRM_TIMEOUT_S)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != "Ok" or not data.get("routes"):
            return fallback

        coords = data["routes"][0]["geometry"]["coordinates"]
        if not coords or len(coords) < 2:
            return fallback

        # Tuple-of-tuples: hashable/immutable, safe to hand out from a
        # shared lru_cache entry without callers accidentally mutating it.
        return tuple((float(c[0]), float(c[1])) for c in coords)

    except (httpx.TimeoutException, httpx.HTTPError, KeyError, IndexError, ValueError):
        return fallback


def build_geojson(feeder, status_report: dict) -> dict:
    """Serialize a Feeder's topology + latest power-flow status into a
    standard GeoJSON FeatureCollection.

    Nodes (ConnectivityNode) -> Point features: bus_id, voltage_pu, violation_status.
    Lines (AcLineSegment)    -> LineString features: loading_percent, r_ohm, x_ohm.

    Reads-only: takes an already-built Feeder + an already-computed
    status report (e.g. from feeder.run_powerflow()), so it never
    triggers a power flow solve itself.
    """
    coords = getattr(feeder, "_geo_coords", None)
    if coords is None:
        coords = compute_synthetic_coordinates(feeder.graph)

    bus_status = {b["node_id"]: b for b in status_report.get("buses", [])}
    line_status = {}
    for l in status_report.get("lines", []):
        line_status[(l["from_bus"], l["to_bus"])] = l
        line_status[(l["to_bus"], l["from_bus"])] = l

    features = []

    for node_id, data in feeder.graph.nodes(data=True):
        lat, lon = coords.get(node_id, (DEFAULT_BASE_LAT, DEFAULT_BASE_LON))
        bstat = bus_status.get(node_id, {})
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "cim_class": "ConnectivityNode",
                "bus_id": node_id,
                "voltage_pu": bstat.get("vm_pu"),
                "violation_status": bstat.get("status", "unknown"),
                "is_substation": node_id == 0,
            },
        })

    for u, v, edata in feeder.graph.edges(data=True):
        lat_u, lon_u = coords.get(u, (DEFAULT_BASE_LAT, DEFAULT_BASE_LON))
        lat_v, lon_v = coords.get(v, (DEFAULT_BASE_LAT, DEFAULT_BASE_LON))
        lstat = line_status.get((u, v), {})

        r_ohm = x_ohm = None
        line_id = edata.get("line_id")
        if line_id is not None and line_id in feeder.net.line.index:
            row = feeder.net.line.loc[line_id]
            r_ohm = round(float(row.r_ohm_per_km * row.length_km), 5)
            x_ohm = round(float(row.x_ohm_per_km * row.length_km), 5)

        # Street-snapped route via OSRM (cached - see get_osrm_route). Only
        # the two bus endpoints determine the route, so this is an instant
        # cache hit on every call after the very first one for this pair.
        route_coords = get_osrm_route(lat_u, lon_u, lat_v, lon_v)

        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [list(pt) for pt in route_coords]},
            "properties": {
                "cim_class": "AcLineSegment",
                "from_bus": u,
                "to_bus": v,
                "loading_percent": lstat.get("loading_percent"),
                "status": lstat.get("status", "unknown"),
                "r_ohm": r_ohm,
                "x_ohm": x_ohm,
            },
        })

    return {"type": "FeatureCollection", "features": features}
