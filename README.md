# GridTwin
A CIM-flavoured distribution network simulator: load an IEEE 33-bus feeder, add rooftop solar / EV chargers to nodes, run AC power flow, and see the network turn from green to red as adoption climbs.

## Structure

```
gridtwin/
├── backend/
│    ├── tests/
│    │   ├──test_converter.py  # tests for the converter module
│    │   ├── test_cim_network.py  # tests for the cim_network module
│    │   ├── test_solver.py  # tests for the solver module
│    │   └── test_network.py  # tests for the network module
│    ├── ieee33_data.py  # published Baran & Wu 33-bus branch/load tables
│    ├── cim_network.py  # builds the feeder as real zepben.ewb CIM objects
│    ├── converter.py    # CIM NetworkService -> pandapower net
│    ├── solver.py       # per-node hosting-capacity search
│    ├── network.py      # Feeder class: graph model + DER logic, wraps the above
│    └── main.py          # FastAPI app exposing it over HTTP
├── frontend/
│   └── index.html        # main HTML page for the frontend
├── .gitignore            # git ignore file
└── README.md             # this file
└── requirements.txt      # list of dependencies


```

**Backend**
```bash
cd backend
# Activate the virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements cleanly
pip3 install -r requirements.txt

pip3 install pandapower fastapi uvicorn
uvicorn main:app --reload --port 8000
```

# test suite
pytest -v



**Frontend** 
```bash
cd frontend
python3 -m http.server 8080
# visit http://localhost:8080
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
