from caelestia.parser import parse_args
from unittest.mock import patch

def test_display_parser_status() -> None:
    with patch("sys.argv", ["caelestia", "display", "status"]):
        _, args = parse_args()
        assert args.display_action == "status"

def test_display_parser_profile_save() -> None:
    with patch("sys.argv", ["caelestia", "display", "profile", "save", "Desk"]):
        _, args = parse_args()
        assert args.display_action == "profile"
        assert args.profile_action == "save"
        assert args.name == "Desk"
