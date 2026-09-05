"""
GridTwin CIM Network Instantiation

Builds the IEEE 33-bus radial feeder as real zepben.ewb CIM objects (EnergySource, ConnectivityNode, AcLineSegment + PerLengthSequenceImpedance, EnergyConsumer) from the standard Baran & Wu dataset in `ieee33_data.py`.

"""
from __future__ import annotations
import zepben.ewb as ewb

from ieee33_data import BRANCHES, LOADS, SUBSTATION_BUS


class InvalidCIMTopologyError(Exception):
    """Raised when the CIM object graph can't be built or traversed as expected."""


def _cn_mrid(bus: int) -> str:
    return f"cn-{bus}"


def build_cim_network() -> tuple[ewb.NetworkService, ewb.EnergySource]:
    """Full IEEE 33-bus radial feeder as zepben.ewb CIM objects.

    Each branch gets its own PerLengthSequenceImpedance rather than a shared one, since the published dataset gives one impedance per branch, not a per-km conductor spec. 
    Line length is fixed at 1 km so r_ohm_per_km/x_ohm_per_km equal the published per-branch ohm values directly.
    """
    ns = ewb.NetworkService()

    cn_by_bus = {}
    all_buses = {SUBSTATION_BUS}
    for a, b, _, _ in BRANCHES:
        all_buses.add(a)
        all_buses.add(b)

    for bus in sorted(all_buses):
        cn_by_bus[bus] = ns.add_connectivity_node(_cn_mrid(bus))

    source = ns.create_energy_source(
        cn_by_bus[SUBSTATION_BUS], mrid="src", name="Substation-Slack",
        active_power=0.0, reactive_power=0.0,
    )

    for a, b, r, x in BRANCHES:
        if a not in cn_by_bus or b not in cn_by_bus:
            raise InvalidCIMTopologyError(f"branch ({a}, {b}) references an unknown bus")
        mrid = f"line-{a}-{b}"
        plsi = ewb.PerLengthSequenceImpedance(mrid=f"plsi-{a}-{b}", r=r, x=x)
        ns.add(plsi)
        # NOTE (real library quirk, confirmed by testing on the toy feeder,
        # not a typo): create_ac_line_segment() *requires* an mrid kwarg
        # or it raises TypeError - but it then ignores the value and
        # assigns its own random UUID anyway. `name` is respected, so
        # that's the field the converter uses for line identification.
        line = ns.create_ac_line_segment(
            cn_by_bus[a], cn_by_bus[b], mrid=mrid, length=1000.0,
        )
        line.name = mrid
        line.per_length_sequence_impedance = plsi

    for bus, p_kw, q_kvar in LOADS:
        if bus not in cn_by_bus:
            raise InvalidCIMTopologyError(f"load references unknown bus {bus}")
        ns.create_energy_consumer(
            cn_by_bus[bus], mrid=f"load-{bus}", p=p_kw * 1000.0, q=q_kvar * 1000.0,
        )

    return ns, source
