from wsjtx_free_freq.codec import Heartbeat, Status, decode, encode_heartbeat, encode_status


def test_heartbeat_round_trips_through_the_decoder() -> None:
    assert decode(encode_heartbeat("WSJT-X")) == Heartbeat("WSJT-X", 3, 3)


def test_status_round_trips_through_the_decoder() -> None:
    message = decode(encode_status("WSJT-X", dial_hz=14074000, mode="FT8", rx_df=1234, tx_df=987))
    assert message == Status("WSJT-X", 3, 14074000, "FT8", 1234, 987, False, 15)
