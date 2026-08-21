import unittest
from unittest.mock import patch, MagicMock
from argparse import Namespace

from caelestia.parser import parse_args
from caelestia.subcommands.overlay import Command


class TestOverlayParser(unittest.TestCase):
    def test_register_args(self):
        with patch("sys.argv", ["caelestia", "overlay", "register", "0x1234", "-a", "top-right", "-p", "-c"]):
            _, args = parse_args()
            self.assertEqual(args.overlay_action, "register")
            self.assertEqual(args.window, "0x1234")
            self.assertEqual(args.anchor, "top-right")
            self.assertTrue(args.pin)
            self.assertTrue(args.clickthrough)

    def test_unregister_args(self):
        with patch("sys.argv", ["caelestia", "overlay", "unregister", "0x5678"]):
            _, args = parse_args()
            self.assertEqual(args.overlay_action, "unregister")
            self.assertEqual(args.window, "0x5678")

    def test_anchor_args(self):
        with patch("sys.argv", ["caelestia", "overlay", "anchor", "bottom-left", "active", "-m", "15"]):
            _, args = parse_args()
            self.assertEqual(args.overlay_action, "anchor")
            self.assertEqual(args.position, "bottom-left")
            self.assertEqual(args.window, "active")
            self.assertEqual(args.margin, "15")

    def test_pin_args(self):
        with patch("sys.argv", ["caelestia", "overlay", "pin", "active", "--enable"]):
            _, args = parse_args()
            self.assertEqual(args.overlay_action, "pin")
            self.assertEqual(args.window, "active")
            self.assertTrue(args.enable)
            self.assertFalse(args.disable)

    def test_clickthrough_args(self):
        with patch("sys.argv", ["caelestia", "overlay", "clickthrough", "active", "--disable"]):
            _, args = parse_args()
            self.assertEqual(args.overlay_action, "clickthrough")
            self.assertEqual(args.window, "active")
            self.assertTrue(args.disable)
            self.assertFalse(args.enable)

    def test_list_args(self):
        with patch("sys.argv", ["caelestia", "overlay", "list"]):
            _, args = parse_args()
            self.assertEqual(args.overlay_action, "list")


class TestOverlayCommand(unittest.TestCase):
    @patch("caelestia.subcommands.overlay.subprocess.check_output")
    def test_register_command_send_ipc(self, mock_check_output):
        mock_check_output.return_value = '{"success": true}'
        args = Namespace(overlay_action="register", window="active", anchor="top-left", pin=True, clickthrough=True)
        cmd = Command(args)

        with patch("builtins.print") as mock_print:
            cmd.run()
            mock_check_output.assert_called_once_with(
                ["qs", "-c", "caelestia", "ipc", "call", "overlay", "register", "active", "top-left", "true", "true"],
                text=True
            )
            mock_print.assert_called_once_with('{"success": true}')

    @patch("caelestia.subcommands.overlay.subprocess.check_output")
    def test_unregister_command_send_ipc(self, mock_check_output):
        mock_check_output.return_value = '{"success": true, "action": "unregistered"}'
        args = Namespace(overlay_action="unregister", window="0x1234")
        cmd = Command(args)

        with patch("builtins.print") as mock_print:
            cmd.run()
            mock_check_output.assert_called_once_with(
                ["qs", "-c", "caelestia", "ipc", "call", "overlay", "unregister", "0x1234"],
                text=True
            )
            mock_print.assert_called_once_with('{"success": true, "action": "unregistered"}')

    @patch("caelestia.subcommands.overlay.subprocess.check_output")
    def test_anchor_command_send_ipc(self, mock_check_output):
        mock_check_output.return_value = '{"success": true}'
        args = Namespace(overlay_action="anchor", position="top-right", window="active", margin="20")
        cmd = Command(args)

        with patch("builtins.print") as mock_print:
            cmd.run()
            mock_check_output.assert_called_once_with(
                ["qs", "-c", "caelestia", "ipc", "call", "overlay", "anchor", "top-right", "active", "20"],
                text=True
            )
            mock_print.assert_called_once_with('{"success": true}')

    @patch("caelestia.subcommands.overlay.subprocess.check_output")
    def test_ipc_error_handling(self, mock_check_output):
        mock_check_output.side_effect = Exception("IPC failure")
        args = Namespace(overlay_action="list")
        cmd = Command(args)

        with patch("caelestia.subcommands.overlay.error") as mock_error:
            cmd.run()
            mock_error.assert_called_once()
