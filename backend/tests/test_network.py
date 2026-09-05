import pytest
from network import Feeder


@pytest.fixture
def feeder():
    return Feeder()


def test_ieee33_loads_expected_topology(feeder):
    assert len(feeder.net.bus) == 33
    assert len(feeder.net.line) == 32
    assert feeder.graph.number_of_nodes() == 33


def test_baseline_converges_with_no_violations(feeder):
    report = feeder.run_powerflow()
    assert report["converged"] is True
    assert report["violations"] == 0
    assert report["der_count"] == 0


def test_add_solar_der_creates_sgen(feeder):
    feeder.add_der(node_id=17, kind="solar", kw=50.0)
    assert len(feeder.net.sgen) == 1
    assert feeder.net.sgen.iloc[0]["p_mw"] == pytest.approx(0.05)
    assert len(feeder.ders) == 1


def test_add_ev_der_increases_existing_load(feeder):
    bus_with_load = feeder.net.load.iloc[0]["bus"]
    before = feeder.net.load.loc[feeder.net.load.bus == bus_with_load, "p_mw"].sum()
    feeder.add_der(node_id=int(bus_with_load), kind="ev", kw=22.0)
    after = feeder.net.load.loc[feeder.net.load.bus == bus_with_load, "p_mw"].sum()
    assert after == pytest.approx(before + 0.022)


def test_add_der_unknown_bus_raises(feeder):
    with pytest.raises(ValueError):
        feeder.add_der(node_id=9999, kind="solar", kw=10.0)


def test_add_der_invalid_kind_raises(feeder):
    with pytest.raises(ValueError):
        feeder.add_der(node_id=5, kind="wind", kw=10.0)


def test_reset_ders_clears_solar_and_restores_baseline_load(feeder):
    bus_with_load = int(feeder.net.load.iloc[0]["bus"])
    baseline_p = feeder.net.load.loc[feeder.net.load.bus == bus_with_load, "p_mw"].sum()

    feeder.add_der(node_id=17, kind="solar", kw=100.0)
    feeder.add_der(node_id=bus_with_load, kind="ev", kw=22.0)
    feeder.reset_ders()

    assert len(feeder.net.sgen) == 0
    assert feeder.ders == []
    restored_p = feeder.net.load.loc[feeder.net.load.bus == bus_with_load, "p_mw"].sum()
    assert restored_p == pytest.approx(baseline_p)


def test_heavy_uniform_solar_adoption_triggers_overvoltage(feeder):
    feeder.apply_uniform_solar_adoption(100.0)
    report = feeder.run_powerflow()
    assert report["violations"] > 0
    over_or_warn = [b for b in report["buses"] if b["status"] != "normal"]
    assert len(over_or_warn) > 0


def test_hosting_capacity_sweep_is_monotonic_in_violations(feeder):
    result = feeder.hosting_capacity_sweep(kind="solar", step_pct=20)
    violations_by_pct = [row["violations"] for row in result["sweep"]]
    first_violation_idx = next(
        (i for i, v in enumerate(violations_by_pct) if v > 0), None
    )
    if first_violation_idx is not None:
        assert any(v > 0 for v in violations_by_pct[first_violation_idx:])


def test_hosting_capacity_sweep_resets_state_afterward(feeder):
    feeder.hosting_capacity_sweep(kind="solar", step_pct=25)
    assert len(feeder.net.sgen) == 0
    assert feeder.ders == []


def test_status_report_bands_match_ansi_c84_thresholds(feeder):
    feeder.run_powerflow()
    report = feeder.status_report()
    for bus in report["buses"]:
        vm = bus["vm_pu"]
        if vm < 0.917 or vm > 1.058:
            assert bus["status"] == "overloaded"
        elif vm < 0.95 or vm > 1.05:
            assert bus["status"] == "warning"
        else:
            assert bus["status"] == "normal"
