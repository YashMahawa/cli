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


if __name__ == "__main__":
    unittest.main()
