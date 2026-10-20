from src.mouse_to_gyro import MouseGyroSource


def test_mouse_delta_maps_to_pitch_and_yaw_and_is_consumed_once():
    source = MouseGyroSource()
    source.feed_delta(10, -5)
    gyro = source.consume_gyro(0.01, sensitivity=0.1, max_dps=5000)
    assert gyro == (-800.0, 1600.0, 0.0)
    assert source.consume_gyro(0.01) == (0.0, 0.0, 0.0)


def test_mouse_gyro_inversion_and_magnitude_clamp():
    source = MouseGyroSource()
    source.feed_delta(1000, 1000)
    x, y, z = source.consume_gyro(
        0.001, sensitivity=2.0, invert_x=True, invert_y=True, max_dps=100
    )
    assert x < 0 and y < 0 and z == 0
    assert round((x * x + y * y) ** 0.5) == 1600


def test_cursor_warp_is_discarded_instead_of_throwing_gyro_sideways():
    source = MouseGyroSource()
    source._accept_position(100, 100)
    source._accept_position(110, 90)
    source._accept_position(1000, 1000)
    assert source.consume_delta() == (10.0, -10.0)
