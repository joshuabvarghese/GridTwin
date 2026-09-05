import pytest
import pandapower as pp

from solver import calculate_hosting_capacity, PowerFlowConvergenceError


@pytest.fixture
def weak_radial_net():
    """A deliberately weak 3-bus radial feeder: long, high-impedance line
    to bus 2 so a modest solar injection there is enough to trip a
    voltage violation within a small max_solar_kw budget."""
    net = pp.create_empty_network()
    b0 = pp.create_bus(net, vn_kv=11.0, name="slack")
    b1 = pp.create_bus(net, vn_kv=11.0, name="n1")
    b2 = pp.create_bus(net, vn_kv=11.0, name="n2")
    pp.create_ext_grid(net, bus=b0, vm_pu=1.0)
    pp.create_line_from_parameters(
        net, from_bus=b0, to_bus=b1, length_km=5.0,
        r_ohm_per_km=1.2, x_ohm_per_km=0.9, c_nf_per_km=0.0, max_i_ka=0.2,
    )
    pp.create_line_from_parameters(
        net, from_bus=b1, to_bus=b2, length_km=5.0,
        r_ohm_per_km=1.2, x_ohm_per_km=0.9, c_nf_per_km=0.0, max_i_ka=0.2,
    )
    pp.create_load(net, bus=b1, p_mw=0.05, q_mvar=0.02)
    pp.create_load(net, bus=b2, p_mw=0.05, q_mvar=0.02)
    pp.runpp(net)
    return net, b2


def test_finds_a_breach_point_before_ceiling(weak_radial_net):
    net, target = weak_radial_net
    result = calculate_hosting_capacity(net, target, max_solar_kw=2000.0, step_kw=5.0)
    assert result["reached_ceiling"] is False
    assert result["overvoltage"] is True
    assert result["max_allowable_kw"] < 1000.0


def test_reaches_ceiling_when_budget_too_small(weak_radial_net):
    net, target = weak_radial_net
    result = calculate_hosting_capacity(net, target, max_solar_kw=1.0, step_kw=1.0)
    assert result["reached_ceiling"] is True
    assert result["overvoltage"] is False
    assert result["line_overload"] is False


def test_does_not_mutate_caller_network(weak_radial_net):
    net, target = weak_radial_net
    sgen_count_before = len(net.sgen)
    calculate_hosting_capacity(net, target, max_solar_kw=200.0, step_kw=10.0)
    assert len(net.sgen) == sgen_count_before


def test_unknown_bus_raises_value_error(weak_radial_net):
    net, _target = weak_radial_net
    with pytest.raises(ValueError):
        calculate_hosting_capacity(net, 9999, max_solar_kw=100.0)


def test_non_positive_step_kw_raises_value_error(weak_radial_net):
    net, target = weak_radial_net
    with pytest.raises(ValueError):
        calculate_hosting_capacity(net, target, max_solar_kw=100.0, step_kw=0)
