import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from caelestia.utils.theme import apply_chromium, sync_papirus_colors


def test_apply_chromium_user_space(tmp_path, monkeypatch):
    home_dir = tmp_path / "home"
    chrom_dir = home_dir / ".config/chromium/Default"
    chrom_dir.mkdir(parents=True)
    pref_file = chrom_dir / "Preferences"
    pref_file.write_text(json.dumps({"browser": {"theme": {}}}))

    brave_dir = home_dir / ".config/BraveSoftware/Brave-Browser/Profile 1"
    brave_dir.mkdir(parents=True)
    brave_pref = brave_dir / "Preferences"

    monkeypatch.setattr(Path, "home", lambda: home_dir)

    colours = {"surface": "1a1c1e"}
    apply_chromium(colours)

    # Check chromium Preferences
    data = json.loads(pref_file.read_text())
    assert "browser" in data
    assert "theme" in data["browser"]
    assert "user_color" in data["browser"]["theme"]
    assert data["browser"]["theme_color"] == data["browser"]["theme"]["user_color"]
    assert (chrom_dir / "Preferences.bak").exists()

    # Check brave Preferences
    data_brave = json.loads(brave_pref.read_text())
    assert "browser" in data_brave
    assert "theme" in data_brave["browser"]
    assert "user_color" in data_brave["browser"]["theme"]


def test_apply_chromium_skips_active_browser(tmp_path, monkeypatch):
    home_dir = tmp_path / "home"
    chrom_dir = home_dir / ".config/chromium/Default"
    chrom_dir.mkdir(parents=True)
    pref_file = chrom_dir / "Preferences"
    pref_file.write_text(json.dumps({"browser": {"theme": {}}}))

    # Create active SingletonLock
    lock_file = chrom_dir / "SingletonLock"
    lock_file.symlink_to(f"hostname-{Path(__file__).stat().st_ino}")

    monkeypatch.setattr(Path, "home", lambda: home_dir)

    with patch("caelestia.utils.theme._is_chromium_profile_active", return_value=True):
        apply_chromium({"surface": "1a1c1e"})

    data = json.loads(pref_file.read_text())
    assert "user_color" not in data["browser"]["theme"]


def test_apply_chromium_malformed_json_non_destructive(tmp_path, monkeypatch):
    home_dir = tmp_path / "home"
    chrom_dir = home_dir / ".config/chromium/Default"
    chrom_dir.mkdir(parents=True)
    pref_file = chrom_dir / "Preferences"
    malformed_content = "{ invalid json content"
    pref_file.write_text(malformed_content)

    monkeypatch.setattr(Path, "home", lambda: home_dir)

    apply_chromium({"surface": "1a1c1e"})

    # Content must remain intact and NOT replaced with empty object
    assert pref_file.read_text() == malformed_content


def test_apply_chromium_preserve_unknown_data(tmp_path, monkeypatch):
    home_dir = tmp_path / "home"
    chrom_dir = home_dir / ".config/chromium/Default"
    chrom_dir.mkdir(parents=True)
    pref_file = chrom_dir / "Preferences"
    initial_data = {
        "custom_user_key": "custom_user_value",
        "browser": {"custom_browser_setting": 123},
    }
    pref_file.write_text(json.dumps(initial_data))

    monkeypatch.setattr(Path, "home", lambda: home_dir)

    apply_chromium({"surface": "1a1c1e"})

    data = json.loads(pref_file.read_text())
    assert data["custom_user_key"] == "custom_user_value"
    assert data["browser"]["custom_browser_setting"] == 123
    assert "user_color" in data["browser"]["theme"]


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
