import os
import socket
import tempfile
import unittest
from pathlib import Path

from caelestia.subcommands.install import _ignore_transient_nodes
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
