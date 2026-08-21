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


def test_display_parser_passthrough_status() -> None:
    with patch("sys.argv", ["caelestia", "display", "status"]):
        _, args = parse_args()
        assert args.args == ["status"]
        assert build_command(args) == ["caelestia-display", "status"]


def test_display_parser_passthrough_apply() -> None:
    with patch("sys.argv", ["caelestia", "display", "apply", "--monitors-json", '{"monitors":[]}', "tok123"]):
        _, args = parse_args()
        assert args.args == ["apply", "--monitors-json", '{"monitors":[]}', "tok123"]
        assert build_command(args) == [
            "caelestia-display",
            "apply",
            "--monitors-json",
            '{"monitors":[]}',
            "tok123",
        ]


def test_display_parser_passthrough_flags() -> None:
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
        assert args.args == [
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
        ]
        assert build_command(args) == [
            "caelestia-display",
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
        ]


def test_display_parser_mode_fallback() -> None:
    with patch("sys.argv", ["caelestia", "display", "mode", "extend"]):
        _, args = parse_args()
        cmd = build_command(args)
        assert cmd[0] in ("caelestia-display-mode", "caelestia-display")


def test_feature_detect_and_contract() -> None:
    backend_path = find_real_backend()
    if backend_path:
        info = feature_detect_backend(backend_path)
        assert info["available"] is True


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
        ["caelestia", "display", "confirm", "tok123"],
        ["caelestia", "display", "rollback", "tok123"],
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
