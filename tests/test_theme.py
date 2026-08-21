import os
import pty
import time
from unittest.mock import patch
from pathlib import Path

from caelestia.utils.theme import apply_terms

real_os_open = os.open


def test_apply_terms_successful_write(tmp_path: Path) -> None:
    master, slave = pty.openpty()
    slave_dup = os.dup(slave)
    os.set_blocking(master, False)
    os.set_blocking(slave, False)

    dummy_pt = Path("/dev/pts/0")

    def mock_open(path, flags, *args):
        if str(path).startswith("/dev/pts/"):
            return slave
        return real_os_open(path, flags, *args)

    with patch("caelestia.utils.theme.c_state_dir", new=tmp_path), \
         patch.object(Path, "exists", return_value=True), \
         patch.object(Path, "is_dir", return_value=True), \
         patch.object(Path, "iterdir", return_value=[dummy_pt]), \
         patch("caelestia.utils.theme.os.open", side_effect=mock_open):

        test_seq = "\x1b]10;rgb:ff/ff/ff\x1b\\"
        apply_terms(test_seq, timeout=0.1)

        written_data = os.read(master, 1024).decode("utf-8")
        assert written_data == test_seq

    os.close(master)
    os.close(slave_dup)


def test_apply_terms_partial_write_retry(tmp_path: Path) -> None:
    master, slave = pty.openpty()
    slave_dup = os.dup(slave)
    os.set_blocking(master, False)
    os.set_blocking(slave, False)

    dummy_pt = Path("/dev/pts/1")
    write_calls = 0
    real_os_write = os.write

    def mock_open(path, flags, *args):
        if str(path).startswith("/dev/pts/"):
            return slave
        return real_os_open(path, flags, *args)

    def mock_write(fd, buf):
        nonlocal write_calls
        if fd == slave:
            write_calls += 1
            if write_calls == 1:
                # Partial write of first 5 bytes
                return real_os_write(fd, buf[:5])
            elif write_calls == 2:
                # Transient write block
                raise BlockingIOError()
            else:
                # Complete write of remaining bytes
                return real_os_write(fd, buf)
        return real_os_write(fd, buf)

    with patch("caelestia.utils.theme.c_state_dir", new=tmp_path), \
         patch.object(Path, "exists", return_value=True), \
         patch.object(Path, "is_dir", return_value=True), \
         patch.object(Path, "iterdir", return_value=[dummy_pt]), \
         patch("caelestia.utils.theme.os.open", side_effect=mock_open), \
         patch("caelestia.utils.theme.os.write", side_effect=mock_write), \
         patch("caelestia.utils.theme.select.select", return_value=([], [slave], [])) as mock_select:

        test_seq = "\x1b]10;rgb:11/22/33\x1b\\\x1b]11;rgb:44/55/66\x1b\\"
        apply_terms(test_seq, timeout=1.0)

        assert mock_select.called
        read_bytes = b""
        while len(read_bytes) < len(test_seq.encode("utf-8")):
            try:
                chunk = os.read(master, 1024)
                if not chunk:
                    break
                read_bytes += chunk
            except BlockingIOError:
                time.sleep(0.01)
        read_data = read_bytes.decode("utf-8")
        assert read_data == test_seq

    os.close(master)
    os.close(slave_dup)


def test_apply_terms_stalled_terminal_timeout(tmp_path: Path) -> None:
    dummy_pt = Path("/dev/pts/2")
    dummy_fd = 999

    def mock_open(path, flags, *args):
        if str(path).startswith("/dev/pts/"):
            return dummy_fd
        return real_os_open(path, flags, *args)

    with patch("caelestia.utils.theme.c_state_dir", new=tmp_path), \
         patch.object(Path, "exists", return_value=True), \
         patch.object(Path, "is_dir", return_value=True), \
         patch.object(Path, "iterdir", return_value=[dummy_pt]), \
         patch("caelestia.utils.theme.os.open", side_effect=mock_open), \
         patch("caelestia.utils.theme.os.close") as mock_close, \
         patch("caelestia.utils.theme.os.write", side_effect=BlockingIOError()), \
         patch("caelestia.utils.theme.select.select", return_value=([], [], [])) as mock_select:

        apply_terms("\x1b]10;rgb:00/00/00\x1b\\", timeout=0.01)

        assert mock_select.called
        mock_close.assert_called_with(dummy_fd)


def test_apply_terms_handles_inaccessible_pts(tmp_path: Path) -> None:
    dummy_pt = Path("/dev/pts/3")

    def mock_open(path, flags, *args):
        if str(path).startswith("/dev/pts/"):
            raise PermissionError("Permission denied")
        return real_os_open(path, flags, *args)

    with patch("caelestia.utils.theme.c_state_dir", new=tmp_path), \
         patch.object(Path, "exists", return_value=True), \
         patch.object(Path, "is_dir", return_value=True), \
         patch.object(Path, "iterdir", return_value=[dummy_pt]), \
         patch("caelestia.utils.theme.os.open", side_effect=mock_open):

        apply_terms("\x1b]10;rgb:11/11/11\x1b\\", timeout=0.05)
