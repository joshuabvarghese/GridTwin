import pytest
from network import Feeder
import timeseries


@pytest.fixture
def feeder():
    return Feeder()


def test_returns_24_hours(feeder):
    result = timeseries.run_daily_profile(feeder, kind="solar", adoption_pct=50)
    assert len(result["hours"]) == 24
    assert [h["hour"] for h in result["hours"]] == list(range(24))


def test_solar_output_is_zero_overnight(feeder):
    result = timeseries.run_daily_profile(feeder, kind="solar", adoption_pct=100)
    midnight, midday = result["hours"][0], result["hours"][12]
    assert midnight["der_factor"] == 0.0
    assert midday["der_factor"] == pytest.approx(1.0, abs=0.05)
    assert midnight["der_count"] == 0
    assert midday["der_count"] > 0


def test_heavy_solar_adoption_stresses_midday_not_midnight(feeder):
    result = timeseries.run_daily_profile(feeder, kind="solar", adoption_pct=100)
    midnight, midday = result["hours"][0], result["hours"][12]
    assert midday["violations"] >= midnight["violations"]


def test_zero_adoption_has_no_violations_any_hour(feeder):
    result = timeseries.run_daily_profile(feeder, kind="solar", adoption_pct=0)
    assert all(h["violations"] == 0 for h in result["hours"])
    assert result["installed_der_count"] == 0


def test_invalid_kind_raises(feeder):
    with pytest.raises(ValueError):
        timeseries.run_daily_profile(feeder, kind="wind", adoption_pct=50)


def test_leaves_feeder_reset_afterward(feeder):
    timeseries.run_daily_profile(feeder, kind="solar", adoption_pct=100)
    assert len(feeder.net.sgen) == 0
    assert feeder.ders == []
    report = feeder.run_powerflow()
    assert report["der_count"] == 0


def test_annual_profile_returns_12_months(feeder):
    result = timeseries.run_annual_profile(feeder, kind="solar", adoption_pct=100)
    assert len(result["months"]) == 12
    assert [m["month"] for m in result["months"]] == list(range(1, 13))
    assert all(len(m["hours"]) == 24 for m in result["months"])
    assert result["representative_hours_simulated"] == 288


def test_annual_profile_summarizes_every_bus_and_line(feeder):
    result = timeseries.run_annual_profile(feeder, kind="solar", adoption_pct=100)
    assert len(result["buses"]) == len(feeder.graph.nodes)
    assert len(result["lines"]) == len(feeder.graph.edges)
    for b in result["buses"]:
        assert b["min_voltage"] <= b["avg_voltage"] <= b["max_voltage"]
        assert 1 <= b["min_voltage_month"] <= 12
        assert 0 <= b["min_voltage_hour"] <= 23


def test_annual_profile_flags_reverse_flow_under_heavy_solar(feeder):
    result = timeseries.run_annual_profile(feeder, kind="solar", adoption_pct=100)
    directions = {l["direction_at_max_loading"] for l in result["lines"]}
    assert "export" in directions  # heavy solar should push some line's flow backward


def test_annual_profile_zero_adoption_has_no_reverse_flow_or_violations(feeder):
    result = timeseries.run_annual_profile(feeder, kind="solar", adoption_pct=0)
    assert all(l["direction_at_max_loading"] == "import" for l in result["lines"])
    assert all(h["violations"] == 0 for m in result["months"] for h in m["hours"])


def test_annual_profile_leaves_feeder_reset_afterward(feeder):
    timeseries.run_annual_profile(feeder, kind="solar", adoption_pct=100)
    assert len(feeder.net.sgen) == 0
    assert feeder.ders == []


def test_annual_profile_invalid_kind_raises(feeder):
    with pytest.raises(ValueError):
        timeseries.run_annual_profile(feeder, kind="wind", adoption_pct=50)
