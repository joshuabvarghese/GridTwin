from unittest.mock import MagicMock, patch

import pytest
import ewb_client


def _mock_client(service, was_failure=False, thrown=None):
    result = MagicMock(was_failure=was_failure, thrown=thrown)
    client = MagicMock()
    client.get_equipment_container.return_value = result
    client.service = service
    return client


def test_uses_insecure_channel_when_no_token():
    fake_service = object()
    with patch("ewb_client.ewb.connect_insecure") as connect_insecure, \
         patch("ewb_client.ewb.connect_with_token") as connect_with_token, \
         patch("ewb_client.ewb.SyncNetworkConsumerClient", return_value=_mock_client(fake_service)):
        result = ewb_client.fetch_feeder("ewb.example.com", "feeder-1", port=50051)

    connect_insecure.assert_called_once_with(host="ewb.example.com", rpc_port=50051)
    connect_with_token.assert_not_called()
    assert result is fake_service


def test_uses_token_channel_when_token_given():
    fake_service = object()
    with patch("ewb_client.ewb.connect_insecure") as connect_insecure, \
         patch("ewb_client.ewb.connect_with_token") as connect_with_token, \
         patch("ewb_client.ewb.SyncNetworkConsumerClient", return_value=_mock_client(fake_service)):
        ewb_client.fetch_feeder("ewb.example.com", "feeder-1", port=443, token="secret")

    connect_with_token.assert_called_once_with(access_token="secret", host="ewb.example.com", rpc_port=443)
    connect_insecure.assert_not_called()


def test_fetches_the_requested_feeder_mrid():
    with patch("ewb_client.ewb.connect_insecure"), \
         patch("ewb_client.ewb.SyncNetworkConsumerClient") as sync_client_cls:
        mock_client = _mock_client(object())
        sync_client_cls.return_value = mock_client
        ewb_client.fetch_feeder("ewb.example.com", "feeder-42")

    args, _ = mock_client.get_equipment_container.call_args
    assert args[0] == "feeder-42"


def test_raises_on_grpc_failure():
    with patch("ewb_client.ewb.connect_insecure"), \
         patch("ewb_client.ewb.SyncNetworkConsumerClient",
               return_value=_mock_client(None, was_failure=True, thrown=ConnectionError("unreachable"))):
        with pytest.raises(ewb_client.EWBFetchError, match="unreachable"):
            ewb_client.fetch_feeder("ewb.example.com", "feeder-1")
