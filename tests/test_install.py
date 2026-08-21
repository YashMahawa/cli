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
    @patch("caelestia.subcommands.install.Path.exists")
    def test_enable_power_services_skipped_when_not_systemd(
        self, mock_exists: MagicMock, mock_run: MagicMock
    ) -> None:
        mock_exists.return_value = False
        cmd = Command(Namespace())
        cmd.enable_power_services()
        mock_run.assert_not_called()

    @patch("caelestia.subcommands.install.subprocess.run")
    @patch("caelestia.subcommands.install.os.geteuid", return_value=0)
    @patch("caelestia.subcommands.install.Path.exists", return_value=True)
    def test_enable_power_services_root(
        self, mock_exists: MagicMock, mock_geteuid: MagicMock, mock_run: MagicMock
    ) -> None:
        cmd = Command(Namespace())
        cmd.enable_power_services()
        mock_run.assert_called_once_with(
            ["systemctl", "enable", "--now", "upower.service", "power-profiles-daemon.service"],
            check=True,
        )

    @patch("caelestia.subcommands.install.subprocess.run")
    @patch("caelestia.subcommands.install.shutil.which", return_value="/usr/bin/sudo")
    @patch("caelestia.subcommands.install.os.geteuid", return_value=1000)
    @patch("caelestia.subcommands.install.Path.exists", return_value=True)
    def test_enable_power_services_sudo(
        self,
        mock_exists: MagicMock,
        mock_geteuid: MagicMock,
        mock_which: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        cmd = Command(Namespace())
        cmd.enable_power_services()
        mock_run.assert_called_once_with(
            ["sudo", "systemctl", "enable", "--now", "upower.service", "power-profiles-daemon.service"],
            check=True,
        )


if __name__ == "__main__":
    unittest.main()
