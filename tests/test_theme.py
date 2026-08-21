import json
import os
import pty
from pathlib import Path
from unittest.mock import MagicMock, patch

from caelestia.utils.theme import apply_chromium, apply_terms, sync_papirus_colors

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
        apply_terms(test_seq, timeout=0.2)

        assert mock_select.called
        read_data = os.read(master, 1024).decode("utf-8")
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


def test_apply_chromium_user_space_theme_asset(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr("caelestia.utils.theme.c_data_dir", data_dir / "caelestia")

    # Create dummy browser directory and Preferences file to verify it is NOT mutated
    pref_file = tmp_path / "home/.config/chromium/Default/Preferences"
    pref_file.parent.mkdir(parents=True)
    initial_pref_content = '{"browser": {}}'
    pref_file.write_text(initial_pref_content)

    colours = {"surface": "1a1c1e", "on_surface": "e1e2e5"}
    apply_chromium(colours)

    # Verify generated user theme asset
    manifest_path = data_dir / "caelestia/chromium/manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text())
    assert manifest["manifest_version"] == 3
    assert manifest["theme"]["colors"]["frame"] == [26, 28, 30]

    # Verify browser profile Preferences was NOT mutated or backed up
    assert pref_file.read_text() == initial_pref_content
    assert not (pref_file.parent / "Preferences.bak").exists()


def test_package_installer_no_packages_path():
    from caelestia.utils.dots.packages import NoopInstaller, PackageInstaller

    installer = PackageInstaller.get(no_packages=True)
    assert isinstance(installer, NoopInstaller)


def test_sync_papirus_colors_user_space(tmp_path, monkeypatch):
    home_dir = tmp_path / "home"
    icon_dir = home_dir / ".local/share/icons/Papirus"
    icon_dir.mkdir(parents=True)

    monkeypatch.setattr(Path, "home", lambda: home_dir)

    with patch("subprocess.run") as mock_run, patch("subprocess.Popen") as mock_popen:
        mock_run.return_value = MagicMock(returncode=0)
        sync_papirus_colors("ff0000")

        mock_popen.assert_called_once()
        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == "papirus-folders"
        assert "-u" in cmd
        assert "sudo" not in cmd
