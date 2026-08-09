from caelestia.utils.hypr import focused_monitor


def test_focused_monitor_returns_explicit_focus() -> None:
    monitors = [
        {"name": "eDP-1", "focused": False},
        {"name": "HDMI-A-1", "focused": True},
    ]

    assert focused_monitor(monitors) == monitors[1]


def test_focused_monitor_does_not_guess_during_transition() -> None:
    assert focused_monitor([{"name": "eDP-1", "focused": False}]) is None
    assert focused_monitor({"error": "compositor unavailable"}) is None
    assert focused_monitor(None) is None
