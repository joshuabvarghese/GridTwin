"""
Synthetic geography for the map view.

The IEEE 33-bus benchmark (ieee33_data.py) has no real-world
coordinates, so this module maps each bus to a real North Canberra
road-intersection instead of a computed layout - that keeps every bus
sitting on an actual road, so OSRM routing between adjacent buses lands
cleanly on both dots instead of detouring around terrain that isn't
really there. Purely cosmetic: never touches the CIM model, the
pandapower conversion, or the power-flow solver.
"""
from __future__ import annotations
import functools
import networkx as nx
import httpx

# City East Zone Substation, Coranderrk St, Reid - bus 0 / the feeder root.
DEFAULT_BASE_LAT = -35.2831
DEFAULT_BASE_LON = 149.1362

# One real intersection/address per bus (1-32), loosely following the
# feeder's own topology (see ieee33_data.BRANCHES):
#   Trunk   0->1->2->...->17   Reid -> Braddon -> Turner (Northbourne Ave)
#   Lateral 1->18->19->20->21  Reid/Braddon/Ainslie (Limestone Ave)
#   Lateral 2->22->23->24      O'Connor (Miller St / Macpherson St)
#   Lateral 5->25->...->32     Dickson/Downer (Cowper St / Antill St)
ROAD_INTERSECTION_COORDS: dict[int, tuple[float, float]] = {
    0: (DEFAULT_BASE_LAT, DEFAULT_BASE_LON),  # City East Zone Substation, Coranderrk St, Reid

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

    18: (-35.279542, 149.141308),  # Elimatta St, Reid/Braddon
    19: (-35.271819, 149.141531),  # Limestone Ave nr Ainslie Ave, Braddon
    20: (-35.282462, 149.138024),  # Coranderrk St, Reid
    21: (-35.280227, 149.133256),  # Bunda St, Reid/City

    22: (-35.264242, 149.122232),  # Macpherson St, O'Connor
    23: (-35.264186, 149.122941),  # Sargood St, O'Connor
    24: (-35.268924, 149.113211),  # David St & Dryandra St, O'Connor

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

    `root` always resolves to (base_lat, base_lon). Any node missing
    from ROAD_INTERSECTION_COORDS (shouldn't happen for the standard
    33-bus feeder) falls back to the substation's coordinates.
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
    """Street-following (lon, lat) route between two points via the
    public OSRM API. Cached per coordinate pair, so each line segment
    is only fetched once. Falls back to a straight line if OSRM is
    unreachable, slow, or returns something unexpected.
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

        return tuple((float(c[0]), float(c[1])) for c in coords)

    except (httpx.TimeoutException, httpx.HTTPError, KeyError, IndexError, ValueError):
        return fallback


def build_geojson(feeder, status_report: dict) -> dict:
    """Serialize a Feeder's topology + latest power-flow status as a
    GeoJSON FeatureCollection: buses -> Point features, lines ->
    LineString features (routed via OSRM). Read-only - never triggers
    a power-flow solve itself.
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
