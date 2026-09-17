# GridTwin

A CIM-flavoured distribution network simulator: load an IEEE 33-bus feeder,
add rooftop solar / EV chargers to nodes, run AC power flow, and see the
network turn from green to red as adoption climbs.

<p align="center">
  <img src="assets/demo.gif" alt="GridTwin Dashboard" width="100%" />
</p>

Live demo: https://gridtwin-qql0.onrender.com

## Structure

```
gridtwin/
├── Dockerfile
├── docker-compose.yml
├── backend/
│   ├── ieee33_data.py   # Baran & Wu 33-bus branch/load tables
│   ├── cim_network.py   # builds the feeder as zepben.ewb CIM objects
│   ├── converter.py     # CIM NetworkService -> pandapower net
│   ├── network.py       # Feeder class: graph model + DER logic
│   ├── geo.py            # synthetic bus coordinates + OSRM routing for the map view
│   └── main.py            # FastAPI app (also serves frontend/)
└── frontend/
    ├── config.js          # runtime API base URL
    └── index.html         # React + Cytoscape.js dashboard
```

## Run it

**Docker (single container, backend + frontend, no CORS setup needed)**
```bash
docker compose up --build
# visit http://localhost:8000
```

**Manual**
```bash
# Backend
cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && uvicorn main:app --reload --port 8000

# Frontend - first uncomment the GRIDTWIN_API_BASE line in frontend/config.js
cd frontend && python3 -m http.server 8080
# visit http://localhost:8080
```

**Tests**
```bash
cd backend && source venv/bin/activate && pytest -v
```

## API

| Endpoint | Method | Purpose |
|---|---|---|
| `/network` | GET | topology (nodes + edges) for the graph view |
| `/status` | GET | current power-flow result, no changes |
| `/adoption-slider` | POST | uniform adoption %: `{"adoption_pct": 60, "kind": "solar"}` |
| `/hosting-capacity` | GET | sweep 0→100% adoption, returns the breach point |
| `/reset` | POST | clear all DERs |
| `/api/network/geojson` | GET | topology + status as GeoJSON, for the map view |
| `/api/grid/simulate` | POST | single-node solar injection: `{"node_id": 4, "solar_kw": 50}` |

## Design notes

- **Network**: the 33-bus feeder is built as real `zepben.ewb` CIM objects
  (`cim_network.py`) from the published Baran & Wu tables
  (`ieee33_data.py`), then converted to a pandapower model by
  `converter.py`. It's built from the published table rather than a live
  EWB-server query or a real CIM RDF/XML file - swapping that source is
  the natural next step.
- **Baseline load** is scaled down (0.55x) so the feeder starts healthy;
  the stock benchmark is already voltage-stressed at full load, leaving
  nothing to add before it goes red.
- **DER sizing**: each bus represents a neighborhood cluster (~60 kW
  average), not one house, so adoption % scales DER capacity relative to
  that node's own baseline load rather than a flat kW-per-house figure.
- **Voltage bands**: approximate ANSI C84.1 Range A/B (0.95–1.05 normal,
  down to 0.917/up to 1.058 warning, beyond that a violation).
- **State**: one `Feeder` is shared by every request (see `_feeder_lock`
  in `main.py`) rather than one per session - every viewer of the live
  demo sees the same grid state. Fine for a single-demo deployment; two
  people adjusting the slider at once will see each other's changes.

See `LIMITATIONS.md` for what's simplified vs. a real utility model.
