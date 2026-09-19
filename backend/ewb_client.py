
from __future__ import annotations
import zepben.ewb as ewb


class EWBFetchError(Exception):
    """Raised when a live EWB server is configured but the fetch fails
    (unreachable, auth rejected, feeder mrid not found, etc)."""


def fetch_feeder(host: str, feeder_mrid: str, port: int = 50051, token: str = None) -> ewb.NetworkService:
    """Pull one feeder's network model from a live EWB server via gRPC."""
    channel = ewb.connect_with_token(access_token=token, host=host, rpc_port=port) if token \
        else ewb.connect_insecure(host=host, rpc_port=port)
    client = ewb.SyncNetworkConsumerClient(channel)

    result = client.get_equipment_container(feeder_mrid, ewb.Feeder)
    if result.was_failure:
        raise EWBFetchError(f"fetching feeder {feeder_mrid!r} from {host}:{port} failed: {result.thrown}")
    return client.service
