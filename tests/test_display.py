from unittest.mock import MagicMock, patch

from caelestia.parser import parse_args
from caelestia.subcommands.display import Command, build_command


def test_display_parser_status() -> None:
    with patch("sys.argv", ["caelestia", "display", "status"]):
        _, args = parse_args()
        assert args.display_action == "status"
        assert build_command(args) == ["caelestia-display", "status"]


def test_display_parser_apply() -> None:
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


def test_display_parser_profile_list() -> None:
    with patch("sys.argv", ["caelestia", "display", "profile", "list"]):
        _, args = parse_args()
        assert args.display_action == "profile"
        assert args.profile_action == "list"
        assert build_command(args) == ["caelestia-display", "profile", "list"]


def test_display_parser_profile_save() -> None:
    with patch("sys.argv", ["caelestia", "display", "profile", "save", "Desk"]):
        _, args = parse_args()
        assert args.display_action == "profile"
        assert args.profile_action == "save"
        assert args.name == "Desk"
        assert build_command(args) == ["caelestia-display", "profile", "save", "Desk"]


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


def test_display_command_runner() -> None:
    with patch("sys.argv", ["caelestia", "display", "status"]):
        _, args = parse_args()
        cmd_obj = Command(args)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            cmd_obj.run()
            mock_run.assert_called_once_with(["caelestia-display", "status"], text=True)

