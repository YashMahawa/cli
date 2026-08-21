import os
import socket
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch

from caelestia.subcommands.install import Command, _ignore_transient_nodes
from caelestia.utils.dots.deployer import Deployer


class TestInstallSafety(unittest.TestCase):
    def test_backup_ignores_runtime_socket_and_fifo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            regular = root / "settings.json"
            regular.write_text("{}")
            fifo = root / "agent.fifo"
            os.mkfifo(fifo)
            sock = socket.socket(socket.AF_UNIX)
            try:
                sock.bind(str(root / "agent.sock"))
                ignored = _ignore_transient_nodes(str(root), [entry.name for entry in root.iterdir()])
            finally:
                sock.close()

            self.assertEqual(ignored, {"agent.fifo", "agent.sock"})

    def test_deployer_installs_a_copy_not_a_repository_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "checkout" / "config.ini"
            destination = root / "installed" / "config.ini"
            source.parent.mkdir()
            source.write_text("first")

            Deployer().place_file(source, destination, record=False)
            source.write_text("second")

            self.assertFalse(destination.is_symlink())
            self.assertEqual(destination.read_text(), "first")

    @patch("caelestia.subcommands.install.subprocess.run")
    @patch("caelestia.subcommands.install.Path.exists", return_value=False)
    def test_enable_power_services_opt_in_default_false(
        self, mock_exists: MagicMock, mock_run: MagicMock
    ) -> None:
        cmd = Command(Namespace(enable_power_profiles_daemon=False))
        cmd.enable_power_services()
        mock_run.assert_not_called()

    @patch("caelestia.subcommands.install.Path.exists", return_value=False)
    def test_enable_power_services_non_systemd_context_error(
        self, mock_exists: MagicMock
    ) -> None:
        cmd = Command(Namespace(enable_power_profiles_daemon=True))
        with self.assertRaises(RuntimeError) as cm:
            cmd.enable_power_services()
        self.assertIn("Systemd is not running", str(cm.exception))

    @patch("caelestia.subcommands.install.shutil.which", return_value=None)
    @patch("caelestia.subcommands.install.os.geteuid", return_value=1000)
    @patch("caelestia.subcommands.install.Path.exists", return_value=True)
    def test_enable_power_services_user_space_no_privileges(
        self, mock_exists: MagicMock, mock_geteuid: MagicMock, mock_which: MagicMock
    ) -> None:
        cmd = Command(Namespace(enable_power_profiles_daemon=True))
        with self.assertRaises(RuntimeError) as cm:
            cmd.enable_power_services()
        self.assertIn("Root or sudo privileges are required", str(cm.exception))

    @patch("caelestia.subcommands.install._get_active_power_manager", return_value="tlp.service")
    @patch("caelestia.subcommands.install.subprocess.run")
    @patch("caelestia.subcommands.install.os.geteuid", return_value=0)
    @patch("caelestia.subcommands.install.Path.exists", return_value=True)
    def test_enable_power_services_conflicting_manager(
        self,
        mock_exists: MagicMock,
        mock_geteuid: MagicMock,
        mock_run: MagicMock,
        mock_active_mgr: MagicMock,
    ) -> None:
        cmd = Command(Namespace(enable_power_profiles_daemon=True))
        cmd.enable_power_services()
        mock_run.assert_not_called()

    @patch("caelestia.subcommands.install._get_active_power_manager", return_value=None)
    @patch("caelestia.subcommands.install.subprocess.run")
    @patch("caelestia.subcommands.install.os.geteuid", return_value=0)
    @patch("caelestia.subcommands.install.Path.exists", return_value=True)
    def test_enable_power_services_root_success(
        self,
        mock_exists: MagicMock,
        mock_geteuid: MagicMock,
        mock_run: MagicMock,
        mock_active_mgr: MagicMock,
    ) -> None:
        cmd = Command(Namespace(enable_power_profiles_daemon=True))
        cmd.enable_power_services()
        mock_run.assert_called_once_with(
            ["systemctl", "enable", "--now", "power-profiles-daemon.service"],
            check=True,
        )

    @patch("caelestia.subcommands.install._get_active_power_manager", return_value=None)
    @patch("caelestia.subcommands.install.subprocess.run")
    @patch("caelestia.subcommands.install.shutil.which", return_value="/usr/bin/sudo")
    @patch("caelestia.subcommands.install.os.geteuid", return_value=1000)
    @patch("caelestia.subcommands.install.Path.exists", return_value=True)
    def test_enable_power_services_sudo_success(
        self,
        mock_exists: MagicMock,
        mock_geteuid: MagicMock,
        mock_which: MagicMock,
        mock_run: MagicMock,
        mock_active_mgr: MagicMock,
    ) -> None:
        cmd = Command(Namespace(enable_power_profiles_daemon=True))
        cmd.enable_power_services()
        mock_run.assert_called_once_with(
            ["sudo", "systemctl", "enable", "--now", "power-profiles-daemon.service"],
            check=True,
        )

    @patch("caelestia.subcommands.install._get_active_power_manager", return_value=None)
    @patch("caelestia.subcommands.install.subprocess.run")
    @patch("caelestia.subcommands.install.os.geteuid", return_value=0)
    @patch("caelestia.subcommands.install.Path.exists", return_value=True)
    def test_enable_power_services_propagates_failure(
        self,
        mock_exists: MagicMock,
        mock_geteuid: MagicMock,
        mock_run: MagicMock,
        mock_active_mgr: MagicMock,
    ) -> None:
        import subprocess

        mock_run.side_effect = subprocess.CalledProcessError(1, ["systemctl"])
        cmd = Command(Namespace(enable_power_profiles_daemon=True))
        with self.assertRaises(subprocess.CalledProcessError):
            cmd.enable_power_services()

    @patch("caelestia.subcommands.install.subprocess.run")
    def test_get_active_power_manager_finds_active(self, mock_run: MagicMock) -> None:
        def side_effect(cmd, **kwargs):
            res = MagicMock()
            if "tlp" in cmd or "tlp.service" in cmd:
                res.returncode = 0
            else:
                res.returncode = 1
            return res

        mock_run.side_effect = side_effect
        from caelestia.subcommands.install import _get_active_power_manager

        self.assertEqual(_get_active_power_manager(), "tlp")

    def test_deployer_deploys_portal_mapping_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            src_portal_dir = root / "xdg-desktop-portal"
            src_portal_dir.mkdir()
            conf_file = src_portal_dir / "hyprland-portals.conf"
            conf_content = (
                "[preferred]\n"
                "default=gtk;hyprland;\n"
                "org.freedesktop.impl.portal.ScreenCast=hyprland\n"
                "org.freedesktop.impl.portal.FileChooser=gtk\n"
                "org.freedesktop.impl.portal.Secret=gnome-keyring;gtk;\n"
            )
            conf_file.write_text(conf_content)

            dest_portal_dir = root / ".config" / "xdg-desktop-portal"
            dest_portal_dir.mkdir(parents=True)
            Deployer().place_file(conf_file, dest_portal_dir / "hyprland-portals.conf", record=False)

            dest_conf = dest_portal_dir / "hyprland-portals.conf"
            self.assertTrue(dest_conf.exists())
            self.assertEqual(dest_conf.read_text(), conf_content)


if __name__ == "__main__":
    unittest.main()
