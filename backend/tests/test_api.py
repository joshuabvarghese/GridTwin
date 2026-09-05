import pytest
from fastapi.testclient import TestClient
from main import app, feeder


@pytest.fixture(autouse=True)
def _reset_feeder_state():
    feeder.reset_ders()
    yield
    feeder.reset_ders()


client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"ok": True}


def test_network_topology_shape():
    body = client.get("/network").json()
    assert len(body["nodes"]) == 33
    assert len(body["edges"]) == 32
    assert body["nodes"][0]["cim_class"] == "ConnectivityNode"


def test_status_matches_baseline():
    body = client.get("/status").json()
    assert body["converged"] is True
    assert body["violations"] == 0


def test_simulate_der_valid_request():
    resp = client.post("/simulate-der", json={"node_id": 17, "kind": "solar", "kw": 50})
    assert resp.status_code == 200
    assert resp.json()["der_count"] == 1


def test_simulate_der_unknown_bus_returns_400():
    resp = client.post("/simulate-der", json={"node_id": 9999, "kind": "solar", "kw": 50})
    assert resp.status_code == 400


def test_reset_clears_previous_ders():
    client.post("/simulate-der", json={"node_id": 17, "kind": "solar", "kw": 50})
    resp = client.post("/reset")
    assert resp.json()["der_count"] == 0


def test_adoption_slider_solar():
    resp = client.post("/adoption-slider", json={"adoption_pct": 100, "kind": "solar"})
    assert resp.status_code == 200
    assert resp.json()["der_count"] > 0


def test_hosting_capacity_endpoint_returns_curve():
    body = client.get("/hosting-capacity", params={"kind": "solar", "step_pct": 25}).json()
    assert "sweep" in body
    assert "hosting_capacity_pct" in body
    assert len(body["sweep"]) == 5  # 0, 25, 50, 75, 100
