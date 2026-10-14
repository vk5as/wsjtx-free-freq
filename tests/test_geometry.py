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


def test_offset_at_the_ends_of_the_axis_is_the_axis_ends() -> None:
    assert AXIS.offset_at(40.0, step_hz=5, min_hz=200, max_hz=2800) == 200
    assert AXIS.offset_at(740.0, step_hz=5, min_hz=200, max_hz=2800) == 2800


def test_offset_at_inverts_x_of() -> None:
    assert AXIS.offset_at(AXIS.x_of(1500), step_hz=5, min_hz=200, max_hz=2800) == 1500


def test_offset_at_rounds_to_the_nearest_step() -> None:
    assert AXIS.offset_at(AXIS.x_of(1502), step_hz=5, min_hz=200, max_hz=2800) == 1500
    assert AXIS.offset_at(AXIS.x_of(1503), step_hz=5, min_hz=200, max_hz=2800) == 1505


def test_offset_at_rounds_a_half_step_up() -> None:
    assert AXIS.offset_at(AXIS.x_of(1502.5), step_hz=5, min_hz=200, max_hz=2800) == 1505


def test_offset_at_clamps_to_the_upper_limit_for_a_click_past_the_right_edge() -> None:
    assert AXIS.offset_at(AXIS.x_of(2800), step_hz=5, min_hz=200, max_hz=2750) == 2750
    assert AXIS.offset_at(900.0, step_hz=5, min_hz=200, max_hz=2750) == 2750


def test_offset_at_clamps_to_the_lower_limit_for_a_click_left_of_the_axis() -> None:
    assert AXIS.offset_at(0.0, step_hz=5, min_hz=200, max_hz=2750) == 200
    assert AXIS.offset_at(AXIS.x_of(210), step_hz=5, min_hz=300, max_hz=2750) == 300
