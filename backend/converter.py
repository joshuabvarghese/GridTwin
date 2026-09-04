"""
GridTwin CIM -> pandapower Converter

Traverses a zepben.ewb NetworkService's CIM objects (ConnectivityNode,
EnergySource, AcLineSegment, EnergyConsumer) and builds an equivalent
pandapower network. This is the layer that lets everything downstream
(power flow, hosting-capacity sweeps, the API) stay CIM-agnostic: swap
`cim_network.build_cim_network()` for a live EWB-server query and this
function's input type doesn't change.
"""
from __future__ import annotations
import zepben.ewb as ewb
import pandapower as pp

from cim_network import InvalidCIMTopologyError

DEFAULT_MAX_I_KA = 0.4


def _terminal_cn_mrid(conducting_equipment, sequence_number: int, context: str) -> str:
    terminal = conducting_equipment.get_terminal_by_sn(sequence_number)
    if terminal is None or terminal.connectivity_node is None:
        raise InvalidCIMTopologyError(
            f"{context} is missing terminal {sequence_number} or its connectivity node"
        )
    return terminal.connectivity_node.mrid


def cim_to_pandapower(
    ns: ewb.NetworkService, vn_kv: float, base_mva: float, max_i_ka: float = DEFAULT_MAX_I_KA,
) -> pp.pandapowerNet:
    net = pp.create_empty_network(sn_mva=base_mva, f_hz=50.0)

    cn_to_bus: dict[str, int] = {}
    for cn in ns.objects(ewb.ConnectivityNode):
        cn_to_bus[cn.mrid] = pp.create_bus(net, vn_kv=vn_kv, name=cn.mrid)

    sources = list(ns.objects(ewb.EnergySource))
    if not sources:
        raise InvalidCIMTopologyError("CIM network has no EnergySource (slack bus)")
    for es in sources:
        cn_mrid = _terminal_cn_mrid(es, 1, f"EnergySource {es.mrid}")
        pp.create_ext_grid(net, bus=cn_to_bus[cn_mrid], vm_pu=1.0, name=es.mrid)

    for line in ns.objects(ewb.AcLineSegment):
        if line.per_length_sequence_impedance is None:
            raise InvalidCIMTopologyError(f"AcLineSegment {line.name} has no impedance")
        cn_a = _terminal_cn_mrid(line, 1, f"AcLineSegment {line.name}")
        cn_b = _terminal_cn_mrid(line, 2, f"AcLineSegment {line.name}")
        plsi = line.per_length_sequence_impedance
        length_km = line.length / 1000.0
        pp.create_line_from_parameters(
            net,
            from_bus=cn_to_bus[cn_a], to_bus=cn_to_bus[cn_b],
            length_km=length_km,
            r_ohm_per_km=plsi.r, x_ohm_per_km=plsi.x,
            c_nf_per_km=0.0, max_i_ka=max_i_ka,
            name=line.name,
        )

    for load in ns.objects(ewb.EnergyConsumer):
        cn_mrid = _terminal_cn_mrid(load, 1, f"EnergyConsumer {load.mrid}")
        pp.create_load(
            net, bus=cn_to_bus[cn_mrid],
            p_mw=load.p / 1e6, q_mvar=load.q / 1e6,
            name=load.mrid,
        )

    return net
