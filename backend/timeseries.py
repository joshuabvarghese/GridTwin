
from __future__ import annotations
import pandapower as pp

HOURS_PER_DAY = 24
MONTHS_PER_YEAR = 12

# Real half-hourly demand (MW) for City East zone substation, Canberra
# - the actual substation this project already names as the feeder's
# root (geo.py) - Jul 2024-Jul 2025, median per hour of day, normalized
# to its own peak. data/derive_profiles.py + data/PROFILES.md.
LOAD_PROFILE = [
    0.622, 0.595, 0.593, 0.603, 0.643, 0.722, 0.830, 0.879,
    0.882, 0.863, 0.829, 0.812, 0.799, 0.814, 0.852, 0.906,
    0.956, 0.991, 1.000, 0.969, 0.878, 0.805, 0.737, 0.672,
]

# Real half-hourly rooftop solar generation from one Ausgrid customer
# (NSW, not ACT - the best available real shape, not a regional match).
SOLAR_PROFILE = [
    0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.066,
    0.219, 0.500, 0.740, 0.913, 1.000, 1.000, 0.868, 0.608,
    0.306, 0.045, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000,
]

# EV charging: light daytime top-ups, a strong peak in the
# evening-into-night window (home charging after work). Hand-shaped -
# no public EV charging interval dataset was used for this one.
EV_PROFILE = [
    0.55, 0.45, 0.35, 0.30, 0.28, 0.25, 0.20, 0.15,
    0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.20, 0.30,
    0.45, 0.70, 1.00, 0.95, 0.85, 0.75, 0.65, 0.60,
]

# The same two real data sources as above, grouped by (calendar month,
# hour) instead of blended into one year - index 0 = January, 11 =
# December. Normalized against ONE peak across all twelve months (not
# each month's own peak), so a genuinely quieter or stronger month
# stays genuinely quieter or stronger after normalizing - see
# data/derive_profiles.py's normalize_grid().
MONTHLY_LOAD_PROFILE = [
    [0.382, 0.372, 0.374, 0.383, 0.408, 0.463, 0.514, 0.517, 0.515, 0.514, 0.488, 0.533, 0.509, 0.529, 0.562, 0.600, 0.639, 0.615, 0.590, 0.562, 0.513, 0.473, 0.437, 0.401],
    [0.385, 0.373, 0.378, 0.385, 0.423, 0.506, 0.570, 0.570, 0.557, 0.562, 0.565, 0.569, 0.560, 0.547, 0.600, 0.644, 0.648, 0.631, 0.617, 0.581, 0.532, 0.484, 0.446, 0.404],
    [0.373, 0.364, 0.366, 0.378, 0.400, 0.477, 0.567, 0.554, 0.539, 0.524, 0.521, 0.517, 0.530, 0.548, 0.599, 0.648, 0.651, 0.628, 0.600, 0.557, 0.501, 0.460, 0.428, 0.391],
    [0.393, 0.370, 0.358, 0.354, 0.357, 0.372, 0.403, 0.475, 0.524, 0.491, 0.460, 0.439, 0.422, 0.449, 0.468, 0.497, 0.560, 0.603, 0.614, 0.590, 0.553, 0.513, 0.480, 0.440],
    [0.470, 0.436, 0.415, 0.407, 0.410, 0.427, 0.482, 0.595, 0.667, 0.637, 0.587, 0.545, 0.522, 0.503, 0.524, 0.565, 0.615, 0.685, 0.731, 0.719, 0.682, 0.649, 0.595, 0.537],
    [0.629, 0.573, 0.544, 0.535, 0.541, 0.582, 0.666, 0.814, 0.962, 0.913, 0.849, 0.795, 0.768, 0.733, 0.731, 0.751, 0.823, 0.933, 1.000, 0.977, 0.941, 0.876, 0.798, 0.722],
    [0.597, 0.544, 0.514, 0.501, 0.512, 0.539, 0.619, 0.780, 0.913, 0.866, 0.805, 0.751, 0.715, 0.702, 0.694, 0.707, 0.773, 0.871, 0.958, 0.930, 0.896, 0.841, 0.758, 0.686],
    [0.522, 0.472, 0.448, 0.441, 0.450, 0.484, 0.568, 0.696, 0.777, 0.741, 0.663, 0.606, 0.558, 0.561, 0.566, 0.590, 0.641, 0.729, 0.801, 0.795, 0.760, 0.721, 0.656, 0.598],
    [0.482, 0.446, 0.429, 0.420, 0.426, 0.451, 0.513, 0.623, 0.646, 0.564, 0.517, 0.481, 0.462, 0.453, 0.469, 0.506, 0.559, 0.655, 0.722, 0.729, 0.691, 0.655, 0.600, 0.550],
    [0.388, 0.379, 0.379, 0.388, 0.419, 0.485, 0.549, 0.522, 0.472, 0.445, 0.438, 0.434, 0.431, 0.441, 0.488, 0.543, 0.596, 0.605, 0.601, 0.575, 0.525, 0.481, 0.448, 0.407],
    [0.373, 0.364, 0.367, 0.377, 0.403, 0.467, 0.528, 0.531, 0.532, 0.520, 0.522, 0.505, 0.514, 0.543, 0.578, 0.611, 0.628, 0.608, 0.590, 0.568, 0.516, 0.466, 0.439, 0.395],
    [0.385, 0.374, 0.375, 0.390, 0.404, 0.450, 0.484, 0.501, 0.477, 0.476, 0.483, 0.487, 0.502, 0.526, 0.579, 0.619, 0.648, 0.620, 0.595, 0.572, 0.520, 0.477, 0.440, 0.403],
]

MONTHLY_SOLAR_PROFILE = [
    [0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.016, 0.068, 0.172, 0.393, 0.514, 0.555, 0.802, 0.863, 0.904, 0.734, 0.623, 0.462, 0.172, 0.016, 0.000, 0.000, 0.000, 0.000],
    [0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.036, 0.120, 0.333, 0.495, 0.607, 0.846, 1.000, 0.803, 0.411, 0.317, 0.240, 0.085, 0.000, 0.000, 0.000, 0.000, 0.000],
    [0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.016, 0.085, 0.273, 0.478, 0.633, 0.675, 0.896, 0.811, 0.658, 0.607, 0.358, 0.052, 0.000, 0.000, 0.000, 0.000, 0.000],
    [0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.068, 0.257, 0.495, 0.631, 0.735, 0.667, 0.751, 0.641, 0.478, 0.163, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000],
    [0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.036, 0.197, 0.445, 0.667, 0.768, 0.836, 0.803, 0.650, 0.426, 0.036, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000],
    [0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.016, 0.104, 0.342, 0.470, 0.683, 0.667, 0.556, 0.436, 0.333, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000],
    [0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.016, 0.145, 0.377, 0.598, 0.735, 0.803, 0.768, 0.598, 0.410, 0.036, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000],
    [0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.052, 0.197, 0.402, 0.615, 0.665, 0.735, 0.709, 0.675, 0.436, 0.120, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000],
    [0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.016, 0.104, 0.325, 0.564, 0.751, 0.923, 0.948, 0.914, 0.820, 0.582, 0.290, 0.016, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000],
    [0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.068, 0.189, 0.426, 0.615, 0.691, 0.870, 0.922, 0.786, 0.828, 0.631, 0.309, 0.052, 0.000, 0.000, 0.000, 0.000, 0.000],
    [0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.016, 0.085, 0.221, 0.462, 0.598, 0.691, 0.769, 0.828, 0.727, 0.555, 0.452, 0.281, 0.068, 0.000, 0.000, 0.000, 0.000, 0.000],
    [0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.016, 0.104, 0.240, 0.377, 0.478, 0.607, 0.699, 0.727, 0.768, 0.735, 0.590, 0.317, 0.128, 0.016, 0.000, 0.000, 0.000, 0.000],
]

# No public EV charging dataset with monthly resolution was found -
# every month reuses the same hand-shaped EV_PROFILE. Unlike the two
# grids above, this one carries no real seasonal signal at all.
MONTHLY_EV_PROFILE = [EV_PROFILE for _ in range(MONTHS_PER_YEAR)]


def _installed_der(feeder, kind: str, adoption_pct: float, oversize_ratio: float) -> list[tuple[int, float]]:
    """Nameplate capacity per bus for `adoption_pct` adoption, sized
    the same way the adoption slider does it (Feeder.apply_uniform_adoption),
    read back rather than re-derived so the sizing rule only lives in
    one place. Installed once, then reset - callers apply their own
    scaled output per hour rather than this fixed kw."""
    feeder.reset_ders()
    feeder.apply_uniform_adoption(kind, adoption_pct, oversize_ratio)
    installed = [(d.node_id, d.kw) for d in feeder.ders]
    feeder.reset_ders()
    return installed


def _prepare_der_rows(feeder, installed: list[tuple[int, float]], kind: str) -> list[tuple[int, float, int]]:
    """Create one sgen (solar) or dedicated load (ev) row per installed
    DER, once, with p_mw=0 - then every hour just updates that row's
    p_mw instead of dropping and recreating it. Electrically identical
    to add_der()'s persistent-adoption path (pandapower sums all load
    rows at a bus regardless of how many there are), but ~5x faster
    over a long sweep: creating/dropping a pandas row per DER per hour
    costs far more than the power-flow solve itself does (measured -
    23s of a 29s, 288-hour sweep was row churn, not Newton-Raphson).
    Returns (bus, kw, row_index) triples; row cleanup is reset_ders()'s
    job, same as the persistent path - see network.py."""
    rows = []
    for bus, kw in installed:
        if kind == "solar":
            idx = pp.create_sgen(feeder.net, bus=bus, p_mw=0.0, q_mvar=0.0, name=f"pv_{bus}")
        else:
            idx = pp.create_load(feeder.net, bus=bus, p_mw=0.0, q_mvar=0.0, name=f"ev_{bus}")
            feeder._created_load_idx.append(idx)
        rows.append((bus, kw, idx))
    return rows


def _solve_hour(feeder, der_rows: list[tuple[int, float, int]], kind: str, load_factor: float, der_factor: float):
    """Mutate the feeder to one hour's load/DER output level (updating
    der_rows' pre-allocated p_mw, not creating/dropping rows) and solve
    once. Returns (status_report, line_directions), where
    line_directions maps line_id -> "import" | "export": "export" means
    power is flowing backward through that line - DER output exceeding
    local demand, pushed back toward the substation - the direct
    wire-level signature of a hosting-capacity problem."""
    baseline = feeder._baseline_loads
    feeder.net.load.loc[baseline.index, ["p_mw", "q_mvar"]] = baseline[["p_mw", "q_mvar"]] * load_factor

    table = feeder.net.sgen if kind == "solar" else feeder.net.load
    der_count = 0
    for bus, kw, idx in der_rows:
        mw = (kw * der_factor) / 1000.0
        table.at[idx, "p_mw"] = mw
        if mw > 0:
            der_count += 1

    try:
        pp.runpp(feeder.net, algorithm="nr")
        report = feeder.status_report()
        # In this radial tree, from_bus is always the upstream (closer
        # to the substation) end - see Feeder._build_graph(). Negative
        # p_from_mw means the line is carrying power the other way.
        line_directions = {
            int(idx): ("export" if row.p_from_mw < 0 else "import")
            for idx, row in feeder.net.res_line.iterrows()
        }
    except Exception:
        report = {"buses": [], "lines": [], "violations": 999, "converged": False}
        line_directions = {}
    report["der_count"] = der_count
    return report, line_directions


def run_daily_profile(feeder, kind: str = "solar", adoption_pct: float = 100.0, oversize_ratio: float = None) -> dict:
    """Install `adoption_pct` worth of `kind` DER, then re-solve once
    per hour of one blended day (the whole year folded into a single
    day - see run_annual_profile() for the seasonal version) with load
    and DER output scaled by LOAD_PROFILE / (SOLAR_PROFILE or
    EV_PROFILE) instead of held fixed. Leaves the feeder reset to
    baseline (no DERs) when done, so it's safe to call on the shared
    feeder alongside other endpoints.
    """
    if kind not in ("solar", "ev"):
        raise ValueError("kind must be 'ev' or 'solar'")
    if oversize_ratio is None:
        oversize_ratio = 4.5 if kind == "solar" else 1.5

    installed = _installed_der(feeder, kind, adoption_pct, oversize_ratio)
    der_rows = _prepare_der_rows(feeder, installed, kind)
    der_profile = SOLAR_PROFILE if kind == "solar" else EV_PROFILE

    hours = []
    worst_hour = None
    worst_violations = -1
    for hour in range(HOURS_PER_DAY):
        report, _ = _solve_hour(feeder, der_rows, kind, LOAD_PROFILE[hour], der_profile[hour])
        hours.append({"hour": hour, "load_factor": LOAD_PROFILE[hour], "der_factor": der_profile[hour], **report})
        if report["violations"] > worst_violations:
            worst_violations = report["violations"]
            worst_hour = hour

    feeder.reset_ders()
    return {
        "kind": kind,
        "adoption_pct": adoption_pct,
        "installed_der_count": len(installed),
        "worst_hour": worst_hour,
        "hours": hours,
    }


def run_annual_profile(feeder, kind: str = "solar", adoption_pct: float = 100.0, oversize_ratio: float = None) -> dict:
    if kind not in ("solar", "ev"):
        raise ValueError("kind must be 'ev' or 'solar'")
    if oversize_ratio is None:
        oversize_ratio = 4.5 if kind == "solar" else 1.5

    installed = _installed_der(feeder, kind, adoption_pct, oversize_ratio)
    der_rows = _prepare_der_rows(feeder, installed, kind)
    monthly_load = MONTHLY_LOAD_PROFILE
    monthly_der = MONTHLY_SOLAR_PROFILE if kind == "solar" else MONTHLY_EV_PROFILE

    per_bus: dict[int, dict] = {}
    per_line: dict[int, dict] = {}
    months = []

    for month in range(1, MONTHS_PER_YEAR + 1):
        month_hours = []
        for hour in range(HOURS_PER_DAY):
            report, line_directions = _solve_hour(
                feeder, der_rows, kind, monthly_load[month - 1][hour], monthly_der[month - 1][hour],
            )
            month_hours.append({"hour": hour, "violations": report["violations"], "converged": report["converged"]})

            for b in report["buses"]:
                acc = per_bus.setdefault(b["node_id"], {
                    "min": b["vm_pu"], "min_at": (month, hour),
                    "max": b["vm_pu"], "max_at": (month, hour),
                    "sum": 0.0, "n": 0,
                })
                if b["vm_pu"] < acc["min"]:
                    acc["min"], acc["min_at"] = b["vm_pu"], (month, hour)
                if b["vm_pu"] > acc["max"]:
                    acc["max"], acc["max_at"] = b["vm_pu"], (month, hour)
                acc["sum"] += b["vm_pu"]
                acc["n"] += 1

            for l in report["lines"]:
                acc = per_line.setdefault(l["line_id"], {
                    "from_bus": l["from_bus"], "to_bus": l["to_bus"],
                    "max_loading_pct": l["loading_percent"], "max_at": (month, hour),
                    "direction_at_max": line_directions.get(l["line_id"], "import"),
                    "hours_over_normal": 0,
                })
                if l["loading_percent"] > acc["max_loading_pct"]:
                    acc["max_loading_pct"] = l["loading_percent"]
                    acc["max_at"] = (month, hour)
                    acc["direction_at_max"] = line_directions.get(l["line_id"], "import")
                if l["loading_percent"] > 100:
                    acc["hours_over_normal"] += 1

        months.append({"month": month, "hours": month_hours})

    feeder.reset_ders()

    buses = [
        {
            "bus_id": bus_id,
            "min_voltage": round(acc["min"], 4), "min_voltage_month": acc["min_at"][0], "min_voltage_hour": acc["min_at"][1],
            "max_voltage": round(acc["max"], 4), "max_voltage_month": acc["max_at"][0], "max_voltage_hour": acc["max_at"][1],
            "avg_voltage": round(acc["sum"] / acc["n"], 4),
        }
        for bus_id, acc in per_bus.items()
    ]
    lines = [
        {
            "line_id": line_id, "from_bus": acc["from_bus"], "to_bus": acc["to_bus"],
            "max_loading_pct": round(acc["max_loading_pct"], 2),
            "max_loading_month": acc["max_at"][0], "max_loading_hour": acc["max_at"][1],
            "direction_at_max_loading": acc["direction_at_max"],
            "representative_hours_over_normal": acc["hours_over_normal"],
        }
        for line_id, acc in per_line.items()
    ]
    worst_month = max(months, key=lambda m: sum(h["violations"] for h in m["hours"]))["month"]

    return {
        "kind": kind,
        "adoption_pct": adoption_pct,
        "installed_der_count": len(installed),
        "representative_hours_simulated": MONTHS_PER_YEAR * HOURS_PER_DAY,
        "worst_month": worst_month,
        "months": months,
        "buses": buses,
        "lines": lines,
    }
