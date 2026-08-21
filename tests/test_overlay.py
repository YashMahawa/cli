import unittest
from unittest.mock import patch, MagicMock
from argparse import Namespace

from caelestia.parser import parse_args
from caelestia.subcommands.overlay import Command, MIN_SERVICE_VERSION


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
    def setUp(self):
        which_patcher = patch("caelestia.subcommands.overlay.shutil.which", return_value="caelestia-qs-ipc")
        self.mock_which = which_patcher.start()
        self.addCleanup(which_patcher.stop)

    def _make_proc(self, returncode=0, stdout='{"success": true}', stderr=""):
        proc = MagicMock()
        proc.returncode = returncode
        proc.stdout = stdout
        proc.stderr = stderr
        return proc

    @patch("caelestia.subcommands.overlay.subprocess.run")
    def test_register_command_send_ipc(self, mock_run):
        mock_run.return_value = self._make_proc(stdout='{"success": true}')
        args = Namespace(overlay_action="register", window="active", anchor="top-left", pin=True, clickthrough=True)
        cmd = Command(args)

        with patch("builtins.print") as mock_print, patch.object(cmd, "check_compatibility", return_value=True):
            cmd.run()
            mock_run.assert_called_with(
                ["caelestia-qs-ipc", "call", "overlay", "register", "active", "top-left", "true", "true"],
                capture_output=True,
                text=True,
                check=False,
            )
            mock_print.assert_called_once_with('{"success": true}')

    @patch("caelestia.subcommands.overlay.subprocess.run")
    def test_unregister_command_send_ipc(self, mock_run):
        mock_run.return_value = self._make_proc(stdout='{"success": true, "action": "unregistered"}')
        args = Namespace(overlay_action="unregister", window="0x1234")
        cmd = Command(args)

        with patch("builtins.print") as mock_print, patch.object(cmd, "check_compatibility", return_value=True):
            cmd.run()
            mock_run.assert_called_with(
                ["caelestia-qs-ipc", "call", "overlay", "unregister", "0x1234"],
                capture_output=True,
                text=True,
                check=False,
            )
            mock_print.assert_called_once_with('{"success": true, "action": "unregistered"}')

    @patch("caelestia.subcommands.overlay.subprocess.run")
    def test_anchor_command_send_ipc(self, mock_run):
        mock_run.return_value = self._make_proc(stdout='{"success": true}')
        args = Namespace(overlay_action="anchor", position="top-right", window="active", margin="20")
        cmd = Command(args)

        with patch("builtins.print") as mock_print, patch.object(cmd, "check_compatibility", return_value=True):
            cmd.run()
            mock_run.assert_called_with(
                ["caelestia-qs-ipc", "call", "overlay", "anchor", "top-right", "active", "20"],
                capture_output=True,
                text=True,
                check=False,
            )
            mock_print.assert_called_once_with('{"success": true}')

    @patch("caelestia.subcommands.overlay.subprocess.run")
    def test_ipc_uses_resolved_binary_path(self, mock_run):
        self.mock_which.return_value = "/usr/bin/caelestia-qs-ipc"
        mock_run.return_value = self._make_proc(stdout='{"success": true}')
        args = Namespace(overlay_action="list")
        cmd = Command(args)

        with patch("builtins.print") as mock_print, patch.object(cmd, "check_compatibility", return_value=True):
            cmd.run()
            mock_run.assert_called_with(
                ["/usr/bin/caelestia-qs-ipc", "call", "overlay", "list"],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_anchor_invalid_numeric_margin(self):
        args_non_numeric = Namespace(overlay_action="anchor", position="top-right", window="active", margin="abc")
        cmd = Command(args_non_numeric)
        with patch("caelestia.subcommands.overlay.error") as mock_error, self.assertRaises(SystemExit) as ctx:
            cmd.run()
        self.assertEqual(ctx.exception.code, 1)
        mock_error.assert_called_once()
        self.assertIn("Invalid numeric margin", mock_error.call_args[0][0])

        args_negative = Namespace(overlay_action="anchor", position="top-right", window="active", margin="-5")
        cmd2 = Command(args_negative)
        with patch("caelestia.subcommands.overlay.error") as mock_error2, self.assertRaises(SystemExit) as ctx2:
            cmd2.run()
        self.assertEqual(ctx2.exception.code, 1)
        mock_error2.assert_called_once()
        self.assertIn("Invalid numeric margin", mock_error2.call_args[0][0])

    @patch("caelestia.subcommands.overlay.subprocess.run")
    def test_missing_shell(self, mock_run):
        mock_run.side_effect = FileNotFoundError("caelestia-qs-ipc not found")
        args = Namespace(overlay_action="list")
        cmd = Command(args)

        with patch("caelestia.subcommands.overlay.error") as mock_error, patch.object(cmd, "check_compatibility", return_value=True), self.assertRaises(SystemExit) as ctx:
            cmd.run()
        self.assertEqual(ctx.exception.code, 1)
        mock_error.assert_called_once()
        self.assertIn("Shell overlay service is not running", mock_error.call_args[0][0])

    @patch("caelestia.subcommands.overlay.subprocess.run")
    def test_stale_window(self, mock_run):
        mock_run.return_value = self._make_proc(
            returncode=1,
            stdout='{"error": "stale_window", "message": "Window 0xdeadbeef no longer exists"}'
        )
        args = Namespace(overlay_action="pin", window="0xdeadbeef", enable=True, disable=False)
        cmd = Command(args)

        with patch("caelestia.subcommands.overlay.error") as mock_error, patch.object(cmd, "check_compatibility", return_value=True), self.assertRaises(SystemExit) as ctx:
            cmd.run()
        self.assertEqual(ctx.exception.code, 1)
        mock_error.assert_called_once()
        self.assertIn("Overlay window is stale or no longer exists", mock_error.call_args[0][0])

    @patch("caelestia.subcommands.overlay.subprocess.run")
    def test_restart_recovery(self, mock_run):
        mock_run.return_value = self._make_proc(
            returncode=1,
            stdout='{"error": "service_restarted", "message": "Overlay service restarted, state lost"}'
        )
        args = Namespace(overlay_action="toggle", window="active")
        cmd = Command(args)

        with patch("caelestia.subcommands.overlay.error") as mock_error, patch.object(cmd, "check_compatibility", return_value=True), self.assertRaises(SystemExit) as ctx:
            cmd.run()
        self.assertEqual(ctx.exception.code, 1)
        mock_error.assert_called_once()
        self.assertIn("Shell overlay service was restarted", mock_error.call_args[0][0])

    @patch("caelestia.subcommands.overlay.subprocess.run")
    def test_incompatible_service_versions(self, mock_run):
        mock_run.return_value = self._make_proc(
            returncode=0,
            stdout='{"version": "0.5.0", "compatible": false}'
        )
        args = Namespace(overlay_action="list")
        cmd = Command(args)

        with patch("caelestia.subcommands.overlay.error") as mock_error, self.assertRaises(SystemExit) as ctx:
            cmd.run()
        self.assertEqual(ctx.exception.code, 1)
        mock_error.assert_called_once()
        self.assertIn("Incompatible overlay service version", mock_error.call_args[0][0])

    @patch("caelestia.subcommands.overlay.subprocess.run")
    def test_compatibility_legacy_service_unknown_method(self, mock_run):
        mock_run.return_value = self._make_proc(
            returncode=1,
            stdout='{"error": "unknown_method", "message": "Unknown method: version"}'
        )
        args = Namespace(overlay_action="list")
        cmd = Command(args)

        # Legacy service without version endpoint returns unknown method
        # check_compatibility should return True (supported legacy service)
        self.assertTrue(cmd.check_compatibility())

    @patch("caelestia.subcommands.overlay.subprocess.run")
    def test_compatibility_service_not_running_genuine_failure(self, mock_run):
        mock_run.return_value = self._make_proc(
            returncode=1,
            stdout='{"error": "missing_shell", "message": "Shell service unavailable"}'
        )
        args = Namespace(overlay_action="list")
        cmd = Command(args)

        # Genuine IPC failure during check_compatibility should NOT be swallowed
        with patch("caelestia.subcommands.overlay.error") as mock_error, self.assertRaises(SystemExit) as ctx:
            cmd.check_compatibility()
        self.assertEqual(ctx.exception.code, 1)
        mock_error.assert_called_once()
        self.assertIn("Shell overlay service is not running", mock_error.call_args[0][0])

    @patch("caelestia.subcommands.overlay.subprocess.run")
    def test_real_command_execution_with_legacy_service(self, mock_run):
        # First call is check_compatibility -> version -> unknown_method
        # Second call is register -> success
        mock_run.side_effect = [
            self._make_proc(returncode=1, stdout='{"error": "unknown_method", "message": "Unknown method: version"}'),
            self._make_proc(returncode=0, stdout='{"success": true}')
        ]
        args = Namespace(overlay_action="register", window="active", anchor="top-left", pin=True, clickthrough=False)
        cmd = Command(args)

        with patch("builtins.print") as mock_print:
            # cmd.run() executes without patching check_compatibility
            cmd.run()
            self.assertEqual(mock_run.call_count, 2)
            mock_print.assert_called_once_with('{"success": true}')

