import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from caelestia.utils.theme import apply_chromium, sync_papirus_colors


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
