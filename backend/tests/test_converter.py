import pytest
import zepben.ewb as ewb
import pandapower as pp

from cim_network import build_cim_network, InvalidCIMTopologyError
from converter import cim_to_pandapower

VN_KV = 12.66
BASE_MVA = 10.0


@pytest.fixture
def cim_ns():
    ns, _source = build_cim_network()
    return ns


def test_converts_full_33_bus_topology(cim_ns):
    net = cim_to_pandapower(cim_ns, vn_kv=VN_KV, base_mva=BASE_MVA)
    assert len(net.bus) == 33
    assert len(net.line) == 32
    assert len(net.load) == 32
    assert len(net.ext_grid) == 1


def test_bus_voltage_level_matches_cim_input(cim_ns):
    net = cim_to_pandapower(cim_ns, vn_kv=VN_KV, base_mva=BASE_MVA)
    assert (net.bus.vn_kv == VN_KV).all()


def test_line_impedance_matches_published_branch_values(cim_ns):
    net = cim_to_pandapower(cim_ns, vn_kv=VN_KV, base_mva=BASE_MVA)
    line = net.line[net.line.name == "line-1-2"].iloc[0]
    assert line.r_ohm_per_km == pytest.approx(0.0922)
    assert line.x_ohm_per_km == pytest.approx(0.0470)
    assert line.length_km == pytest.approx(1.0)


def test_load_power_matches_published_kw_kvar(cim_ns):
    net = cim_to_pandapower(cim_ns, vn_kv=VN_KV, base_mva=BASE_MVA)
    load = net.load[net.load.name == "load-2"].iloc[0]
    assert load.p_mw == pytest.approx(0.100)
    assert load.q_mvar == pytest.approx(0.060)


def test_raises_on_missing_energy_source():
    ns = ewb.NetworkService()
    cn = ns.add_connectivity_node("cn-1")
    ns.create_energy_consumer(cn, mrid="load-1", p=1000.0, q=0.0)
    with pytest.raises(InvalidCIMTopologyError):
        cim_to_pandapower(ns, vn_kv=VN_KV, base_mva=BASE_MVA)


def test_powerflow_converges_on_converted_network(cim_ns):
    net = cim_to_pandapower(cim_ns, vn_kv=VN_KV, base_mva=BASE_MVA)
    pp.runpp(net, algorithm="nr")
    assert bool(net["converged"])
