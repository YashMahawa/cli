import os
import shutil
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest
from caelestia.parser import parse_args
from caelestia.subcommands.display import (
    Command,
    build_command,
    feature_detect_backend,
    verify_backend_contract,
)


def find_real_backend() -> str | None:
    path = shutil.which("caelestia-display")
    if path and os.path.exists(path):
        return path
    candidates = [
        "/app/shell/modules/nexus/scripts/caelestia-display",
        "/app/shell/modules/nexus/scripts/manage_monitors.py",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def test_display_parser_status() -> None:
    with patch("sys.argv", ["caelestia", "display", "status"]):
        _, args = parse_args()
        assert args.display_action == "status"
        assert build_command(args) == ["caelestia-display", "status"]


def test_display_parser_apply_monitors_json() -> None:
    with patch("sys.argv", ["caelestia", "display", "apply", "--monitors-json", '{"monitors":[]}', "tok123"]):
        _, args = parse_args()
        assert args.display_action == "apply"
        assert args.monitors_json == '{"monitors":[]}'
        assert args.token == "tok123"
        assert build_command(args) == [
            "caelestia-display",
            "apply",
            "--monitors-json",
            '{"monitors":[]}',
            "tok123",
        ]


def test_display_parser_apply_individual_flags() -> None:
    with patch(
        "sys.argv",
        [
            "caelestia",
            "display",
            "apply",
            "--name",
            "eDP-1",
            "--res",
            "1920x1080@60",
            "--pos",
            "0x0",
            "--scale",
            "1.25",
            "--transform",
            "0",
        ],
    ):
        _, args = parse_args()
        assert args.display_action == "apply"
        assert args.name == "eDP-1"
        assert args.res == "1920x1080@60"
        assert args.pos == "0x0"
        assert args.scale == "1.25"
        assert args.transform == "0"
        assert build_command(args) == [
            "caelestia-display",
            "apply",
            "--name",
            "eDP-1",
            "--resolution",
            "1920x1080@60",
            "--position",
            "0x0",
            "--scale",
            "1.25",
            "--transform",
            "0",
        ]


def test_display_parser_mode() -> None:
    with patch("sys.argv", ["caelestia", "display", "mode", "extend"]):
        _, args = parse_args()
        assert args.display_action == "mode"
        assert args.mode_name == "extend"
        cmd = build_command(args)
        assert cmd[0] in ("caelestia-display-mode", "caelestia-display")


def test_display_parser_confirm() -> None:
    with patch("sys.argv", ["caelestia", "display", "confirm", "tok456"]):
        _, args = parse_args()
        assert args.display_action == "confirm"
        assert args.token == "tok456"
        assert build_command(args) == ["caelestia-display", "confirm", "tok456"]


def test_display_parser_confirm_token_opt() -> None:
    with patch("sys.argv", ["caelestia", "display", "confirm", "--token", "tok456"]):
        _, args = parse_args()
        assert args.display_action == "confirm"
        assert args.token_opt == "tok456"
        assert build_command(args) == ["caelestia-display", "confirm", "tok456"]


def test_display_parser_rollback() -> None:
    with patch("sys.argv", ["caelestia", "display", "rollback", "tok789"]):
        _, args = parse_args()
        assert args.display_action == "rollback"
        assert args.token == "tok789"
        assert build_command(args) == ["caelestia-display", "rollback", "tok789"]


def test_display_parser_move_window() -> None:
    with patch("sys.argv", ["caelestia", "display", "move-window", "HDMI-A-1"]):
        _, args = parse_args()
        assert args.display_action == "move-window"
        assert args.target == "HDMI-A-1"
        assert build_command(args) == ["caelestia-display", "move-window", "HDMI-A-1"]


def test_display_parser_profile_list() -> None:
    with patch("sys.argv", ["caelestia", "display", "profile", "list"]):
        _, args = parse_args()
        assert args.display_action == "profile"
        assert args.profile_action == "list"
        assert build_command(args) == ["caelestia-display", "profile", "list"]


def test_display_parser_profile_save() -> None:
    with patch("sys.argv", ["caelestia", "display", "profile", "save", "Desk", "--monitors-json", "[]"]):
        _, args = parse_args()
        assert args.display_action == "profile"
        assert args.profile_action == "save"
        assert args.name == "Desk"
        assert args.monitors_json == "[]"
        assert build_command(args) == ["caelestia-display", "profile", "save", "Desk", "--monitors-json", "[]"]


def test_display_parser_profile_load() -> None:
    with patch("sys.argv", ["caelestia", "display", "profile", "load", "Work"]):
        _, args = parse_args()
        assert args.display_action == "profile"
        assert args.profile_action == "load"
        assert args.name == "Work"
        assert build_command(args) == ["caelestia-display", "profile", "load", "Work"]


def test_display_parser_profile_delete() -> None:
    with patch("sys.argv", ["caelestia", "display", "profile", "delete", "OldProfile"]):
        _, args = parse_args()
        assert args.display_action == "profile"
        assert args.profile_action == "delete"
        assert args.name == "OldProfile"
        assert build_command(args) == ["caelestia-display", "profile", "delete", "OldProfile"]


def test_feature_detect_and_contract() -> None:
    backend_path = find_real_backend()
    if backend_path:
        info = feature_detect_backend(backend_path)
        assert info["available"] is True
        assert "apply" in info["subcommands"]
        assert "status" in info["subcommands"]


def test_integration_against_real_backend_parser() -> None:
    backend_path = find_real_backend()
    if not backend_path:
        pytest.skip("Real caelestia-display backend not found in workspace environment")

    test_cli_args = [
        ["caelestia", "display", "status"],
        [
            "caelestia",
            "display",
            "apply",
            "--name",
            "eDP-1",
            "--res",
            "1920x1080@60",
            "--pos",
            "0x0",
            "--scale",
            "1",
            "--transform",
            "0",
        ],
        ["caelestia", "display", "apply", "--monitors-json", '[{"name":"eDP-1"}]'],
        ["caelestia", "display", "confirm", "tok123"],
        ["caelestia", "display", "rollback", "tok123"],
        ["caelestia", "display", "move-window", "HDMI-A-1"],
        ["caelestia", "display", "profile", "list"],
        ["caelestia", "display", "profile", "save", "Desk", "--monitors-json", '[{"name":"eDP-1"}]'],
        ["caelestia", "display", "profile", "load", "Desk"],
        ["caelestia", "display", "profile", "delete", "Desk"],
    ]

    for cli_args in test_cli_args:
        with patch("sys.argv", cli_args):
            _, args = parse_args()
            cmd = build_command(args)
            backend_cmd_args = cmd[1:]

            proc_cmd = (
                [sys.executable, backend_path] + backend_cmd_args + ["--help"]
                if backend_path.endswith(".py")
                else [backend_path] + backend_cmd_args + ["--help"]
            )
            res = subprocess.run(proc_cmd, capture_output=True, text=True)
            assert (
                res.returncode == 0
            ), f"Backend parser failed for CLI command {cli_args}. Output: {res.stdout} {res.stderr}"


def test_display_command_runner() -> None:
    with patch("sys.argv", ["caelestia", "display", "status"]):
        _, args = parse_args()
        cmd_obj = Command(args)
        with patch("shutil.which", return_value="/usr/bin/caelestia-display"), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            cmd_obj.run()
            mock_run.assert_called_once_with(["caelestia-display", "status"], text=True)
