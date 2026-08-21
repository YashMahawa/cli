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

    # Check brave Preferences
    data_brave = json.loads(brave_pref.read_text())
    assert "browser" in data_brave
    assert "theme" in data_brave["browser"]
    assert "user_color" in data_brave["browser"]["theme"]


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
