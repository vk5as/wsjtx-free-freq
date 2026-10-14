from wsjtx_free_freq.geometry import Axis

AXIS = Axis(low_hz=200, high_hz=2800, left_px=40.0, width_px=700.0)


def test_low_and_high_offsets_sit_at_the_ends_of_the_axis() -> None:
    assert AXIS.x_of(200) == 40.0
    assert AXIS.x_of(2800) == 740.0


def test_midpoint_offset_sits_in_the_middle() -> None:
    assert AXIS.x_of(1500) == 390.0


def test_x_increases_with_offset() -> None:
    xs = [AXIS.x_of(hz) for hz in range(200, 2801, 100)]
    assert xs == sorted(xs)
    assert len(set(xs)) == len(xs)


def test_ticks_every_500_hz_across_the_search_range() -> None:
    assert AXIS.ticks(500) == [500, 1000, 1500, 2000, 2500]


def test_ticks_start_at_the_first_step_inside_an_unaligned_range() -> None:
    assert Axis(low_hz=230, high_hz=1100, left_px=0.0, width_px=1.0).ticks(500) == [500, 1000]


def test_no_ticks_when_the_range_holds_no_step() -> None:
    assert Axis(low_hz=210, high_hz=290, left_px=0.0, width_px=1.0).ticks(500) == []
