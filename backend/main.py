"""
GridTwin API
"""
import os
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from network import Feeder

app = FastAPI(title="GridTwin API", version="0.1.0")

_default_origins = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
_extra_origins = [o.strip() for o in os.environ.get("GRIDTWIN_CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins + _extra_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

feeder = Feeder()

# FastAPI executes *sync* endpoints in a threadpool, so two requests can touch the shared `feeder` object concurrently (e.g. a slider drag firing rapid /adoption-slider POSTs). pandapower solves mutate net.res_* in place, so any endpoint that mutates DER state or runs a solve must hold this lock.
# single-feeder app; to scale out, give each request its own Feeder (or a deepcopy of the net) instead of sharing one instance.
_feeder_lock = threading.Lock()


def _safe(fn):
    """Run `fn()`, translating a bad input into 400 and anything else most commonly a non-convergent power flow) into 500. Centralizes the
    try/except pattern that used to be copy-pasted into every endpoint below that mutates DER state or runs a solve."""
    try:
        return fn()
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Power flow did not converge: {e}")


class DERRequest(BaseModel):
    node_id: int
    kind: str = "ev"     # "ev" | "solar"
    kw: float = 22.0


class AdoptionRequest(BaseModel):
    adoption_pct: float
    kind: str = "solar"  # "solar" | "ev"


class GridSimulateRequest(BaseModel):
    node_id: int
    solar_kw: float


class HostingCapacityRequest(BaseModel):
    node_id: int
    max_solar_kw: float = 500.0
    step_kw: float = 5.0


@app.get("/network")
def get_network():
    # Read-only view of the topology; no lock needed.
    return {
        "nodes": [{"id": n, **d} for n, d in feeder.graph.nodes(data=True)],
        "edges": [{"source": u, "target": v, **d} for u, v, d in feeder.graph.edges(data=True)],
    }


@app.get("/status")
def get_status():
    """Current power-flow state without adding anything new."""
    with _feeder_lock:
        return _safe(feeder.run_powerflow)


def _simulate(node_id: int, kind: str, kw: float) -> dict:
    feeder.add_der(node_id, kind, kw)
    return feeder.run_powerflow()


@app.post("/simulate-der")
def simulate_der(req: DERRequest):
    with _feeder_lock:
        return _safe(lambda: _simulate(req.node_id, req.kind, req.kw))


@app.post("/reset")
def reset():
    with _feeder_lock:
        feeder.reset_ders()
        return feeder.run_powerflow()


@app.post("/adoption-slider")
def adoption_slider(req: AdoptionRequest):
    oversize_ratio = 4.5 if req.kind == "solar" else 1.5

    def go():
        feeder.reset_ders()
        feeder.apply_uniform_adoption(req.kind, req.adoption_pct, oversize_ratio)
        return feeder.run_powerflow()

    with _feeder_lock:
        return _safe(go)


@app.get("/hosting-capacity")
def hosting_capacity(kind: str = "solar", step_pct: int = 5):
    # Holds the lock for the whole sweep (21 solves) so no other request can perturb feeder state mid-sweep. Blocks other callers for ~1-2s.
    with _feeder_lock:
        return feeder.hosting_capacity_sweep(kind=kind, step_pct=step_pct)


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/api/network/geojson")
def api_network_geojson():
    """GeoJSON view of the current feeder state for the map/GIS frontend.

    Nodes (ConnectivityNode) -> Point features: bus_id, voltage_pu, violation_status.
    Lines (AcLineSegment)    -> LineString features: loading_percent, r_ohm, x_ohm.
    Uses the feeder's current DER/loading state (same state /status reflects) -
    call /reset or /adoption-slider first if you want a different scenario.
    """
    with _feeder_lock:
        return _safe(feeder.to_geojson)


@app.get("/api/grid/topology")
def api_grid_topology():
    elements = [
        {"data": {"id": str(n), **d}} for n, d in feeder.graph.nodes(data=True)
    ] + [
        {"data": {"source": str(u), "target": str(v), **d}}
        for u, v, d in feeder.graph.edges(data=True)
    ]
    return {"elements": elements}


@app.post("/api/grid/simulate")
def api_grid_simulate(req: GridSimulateRequest):
    def go():
        report = _simulate(req.node_id, "solar", req.solar_kw)
        return {
            "bus_voltages": report["buses"],
            "line_loading": report["lines"],
            "violations": report["violations"],
        }

    with _feeder_lock:
        return _safe(go)


@app.post("/api/grid/hosting-capacity")
def api_grid_hosting_capacity(req: HostingCapacityRequest):
    def go():
        return feeder.hosting_capacity_for_node(
            req.node_id, max_solar_kw=req.max_solar_kw, step_kw=req.step_kw,
        )

    with _feeder_lock:
        return _safe(go)
_frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if _frontend_dir.is_dir():
    print(f"[gridtwin] serving frontend from {_frontend_dir}")
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
else:
    print(f"[gridtwin] WARNING: frontend dir not found at {_frontend_dir} - API only, no UI mounted")
