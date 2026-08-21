from pathlib import Path
from unittest.mock import patch
import pytest

from caelestia.utils.notify import ensure_binary, notify
from caelestia.utils.dots.manifest import Manifest


def test_ensure_binary_present():
    with patch("shutil.which", return_value="/usr/bin/git"):
        assert ensure_binary("git") is True


def test_ensure_binary_missing():
    with patch("shutil.which", return_value=None), patch("caelestia.utils.notify.notify") as mock_notify:
        assert ensure_binary("nonexistent_utility_xyz") is False
        mock_notify.assert_called_once_with("Missing utility", "Required binary 'nonexistent_utility_xyz' is not installed.")


def test_manifest_sync_with_pkgbuild():
    pkgbuild_path = Path("/app/caelestia/PKGBUILD")
    manifest_path = Path("/app/caelestia/manifest.toml")
    assert pkgbuild_path.exists()
    assert manifest_path.exists()

    manifest = Manifest.parse(manifest_path.read_text())
    manifest_pkgs = manifest.enabled_packages()

    # Verify key runtime binaries in manifest
    key_deps = ["gnome-keyring", "polkit-gnome", "brightnessctl", "ddcutil", "networkmanager", "libnotify", "playerctl", "fuzzel"]
    for dep in key_deps:
        assert dep in manifest_pkgs, f"{dep} missing from manifest.toml"

    # Verify PKGBUILD contains manifest packages
    pkgbuild_text = pkgbuild_path.read_text()
    for dep in key_deps:
        assert dep in pkgbuild_text, f"{dep} missing from PKGBUILD"
