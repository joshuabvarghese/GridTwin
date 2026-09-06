# GridTwin

A CIM-flavoured distribution network simulator: load an IEEE 33-bus feeder,
add rooftop solar / EV chargers to nodes, run AC power flow, and see the
network turn from green to red as adoption climbs.

Live demo:- https://gridtwin-qql0.onrender.com

## Structure

```
gridtwin/
├── Dockerfile             # single-container image
├── docker-compose.yml      # local parity with that same container
├── backend/
│   ├── ieee33_data.py  # published Baran & Wu 33-bus branch/load tables
│   ├── cim_network.py  # builds the feeder as real zepben.ewb CIM objects
│   ├── converter.py    # CIM NetworkService -> pandapower net
│   ├── solver.py        # per-node hosting-capacity search
│   ├── network.py       # Feeder class: graph model + DER logic, wraps the above
│   └── main.py           # FastAPI app exposing it over HTTP (+ serves frontend/)
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
| `/simulate-der` | POST | add one DER: `{"node_id": 4, "kind": "ev", "kw": 22}` |
| `/adoption-slider` | POST | uniform adoption %: `{"adoption_pct": 60, "kind": "solar"}` |
| `/hosting-capacity` | GET | sweep 0→100% adoption, returns the breach point |
| `/reset` | POST | clear all DERs |
| `/api/grid/topology` | GET | same topology, as Cytoscape.js `elements` |
| `/api/grid/simulate` | POST | single-node solar injection: `{"node_id": 4, "solar_kw": 50}` |
| `/api/grid/hosting-capacity` | POST | per-node sweep: `{"node_id": 4, "max_solar_kw": 500, "step_kw": 5}` |

The frontend (`index.html`) currently talks to the first block of
endpoints only. The `/api/grid/*` block is additive — same `Feeder`
underneath, shaped to match the per-node hosting-capacity workflow
described in the project spec — and isn't wired into the UI yet.

## Design notes / what's real vs. simplified

- **Network**: the IEEE 33-bus radial feeder is built as real `zepben.ewb`
  CIM objects (`cim_network.py`) from the published Baran & Wu tables
  (`ieee33_data.py`) and converted to a pandapower model by `converter.py`.
  Baseline load is scaled down (0.55x) so the feeder starts healthy — the
  *stock* version of this benchmark is already voltage-stressed at full load,
  which makes for a bad demo (nothing to add before it goes red).
- **DER sizing**: each bus in a 33-bus feeder represents a whole
  neighborhood cluster (~60 kW average), not one house. So adoption % scales
  DER capacity relative to each node's own baseline load (a standard way
  hosting-capacity studies size DER), rather than a flat kW-per-house figure.
- **Voltage bands**: approximate ANSI C84.1 Range A/B (0.95–1.05 normal,
  down to 0.917/up to 1.058 warning, beyond that = violation).
- **CIM**: the feeder is built from real `zepben.ewb` CIM objects
  (`ConnectivityNode`, `EnergySource`, `AcLineSegment` +
  `PerLengthSequenceImpedance`, `EnergyConsumer` — see `cim_network.py`)
  rather than a graph that merely borrows CIM class names. It still
  doesn't parse a real IEC 61970 CIM RDF/XML file or query a live
  EWB server — the CIM objects are built from the published Baran & Wu
  33-bus table (`ieee33_data.py`) instead. Swapping that data source is
  the natural next step; see the NOTE at the bottom of `network.py`.
- **State**: there's one `Feeder` shared by every request (see
  `_feeder_lock` in `main.py`), not one per visitor/session. That's the
  right trade-off for a single-demo deployment — every viewer of the live
  link sees the same grid state, which is fine (arguably a feature) for a
  portfolio demo — but it means two people adjusting the slider at once
  will see each other's changes. Giving each request/session its own
  `Feeder` is the fix if that ever matters.
