from caelestia.subcommands.record import monitor_refresh_rate, quality_args


def test_quality_defaults_are_added() -> None:
    args = quality_args(["-k", "h264"])

    assert args[:2] == ["-k", "h264"]
    assert args[args.index("-q") + 1] == "ultra"
    assert args[args.index("-tune") + 1] == "quality"
    assert args[args.index("-fm") + 1] == "cfr"
    assert args[args.index("-encoder") + 1] == "gpu"


def test_explicit_quality_choices_win() -> None:
    args = quality_args(["-q", "high", "-fm", "vfr", "-tune", "performance"])

    assert args.count("-q") == 1
    assert args[args.index("-q") + 1] == "high"
    assert args[args.index("-fm") + 1] == "vfr"
    assert args[args.index("-tune") + 1] == "performance"


def test_monitor_refresh_rate_tracks_the_active_mode() -> None:
    assert monitor_refresh_rate({"refreshRate": 59.951}) == 60
    assert monitor_refresh_rate({"refreshRate": 143.997}) == 144
    assert monitor_refresh_rate({"refreshRate": "invalid"}) == 60
