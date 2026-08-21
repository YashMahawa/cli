import os
import subprocess
from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from caelestia.subcommands.toggle import Command as ToggleCommand, validate_desktop_id
from caelestia.utils.notify import ensure_binary, notify
from caelestia.utils.dots.manifest import Manifest


def resolve_manifest_and_pkgbuild() -> tuple[Path, Path]:
    """Explicitly resolve manifest.toml and PKGBUILD paths without assuming container layout."""
    env_dir = os.environ.get("CAELESTIA_DIR")
    if env_dir:
        base = Path(env_dir)
        if (base / "PKGBUILD").exists() and (base / "manifest.toml").exists():
            return base / "PKGBUILD", base / "manifest.toml"

    sibling = Path(__file__).resolve().parents[2] / "caelestia"
    if (sibling / "PKGBUILD").exists() and (sibling / "manifest.toml").exists():
        return sibling / "PKGBUILD", sibling / "manifest.toml"

    fixture_dir = Path(__file__).resolve().parent / "fixtures"
    return fixture_dir / "PKGBUILD", fixture_dir / "manifest.toml"


def test_ensure_binary_present():
    with patch("shutil.which", return_value="/usr/bin/git"):
        assert ensure_binary("git") is True


def test_ensure_binary_missing_required():
    with patch("shutil.which", return_value=None), patch("caelestia.utils.notify.notify") as mock_notify:
        assert ensure_binary("nonexistent_utility_xyz", required=True) is False
        mock_notify.assert_called_once_with("Missing utility", "Required binary 'nonexistent_utility_xyz' is not installed.")


def test_ensure_binary_missing_optional():
    with patch("shutil.which", return_value=None), patch("caelestia.utils.notify.notify") as mock_notify:
        assert ensure_binary("optional_utility_xyz", required=False) is False
        mock_notify.assert_not_called()


def test_notify_dbus_fallback():
    with patch("shutil.which", return_value=None), patch("subprocess.run") as mock_run:
        notify("Title", "Body text")
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        assert args[0][0] == "gdbus"
        assert any("org.freedesktop.Notifications" in arg for arg in args[0])


def test_notify_dbus_fallback_options_and_actions():
    with patch("shutil.which", return_value=None), patch("subprocess.run") as mock_run:
        notify("-A", "open=Open", "-A", "save=Save", "-p", "Screenshot taken", "Saved to cache")
        mock_run.assert_called_once()
        cmd_args = mock_run.call_args[0][0]
        assert cmd_args[0] == "gdbus"
        # Summary (index 9), Body (index 10), Actions (index 11)
        assert cmd_args[9] == "Screenshot taken"
        assert cmd_args[10] == "Saved to cache"
        assert cmd_args[11] == "['open', 'Open', 'save', 'Save']"


def test_toggle_app2unit_optional_fallback():
    cmd = ToggleCommand(Namespace(workspace="sysmon"))
    cmd.get_clients = MagicMock(return_value=[])

    with patch("shutil.which", side_effect=lambda x: "/usr/bin/app2unit" if x == "app2unit" else "/usr/bin/foot"), patch(
        "caelestia.utils.hypr.dispatch"
    ) as mock_dispatch:
        spawned = cmd.spawn_client(lambda c: False, ["foot"])
        assert spawned is True
        mock_dispatch.assert_called_once_with("exec", "[workspace special:sysmon] app2unit -- foot")

    with patch("shutil.which", side_effect=lambda x: "/usr/bin/foot" if x == "foot" else None), patch(
        "caelestia.utils.hypr.dispatch"
    ) as mock_dispatch:
        spawned = cmd.spawn_client(lambda c: False, ["foot"])
        assert spawned is True
        mock_dispatch.assert_called_once_with("exec", "[workspace special:sysmon] foot")


def test_toggle_desktop_file_launchers():
    cmd = ToggleCommand(Namespace(workspace="communication"))
    cmd.get_clients = MagicMock(return_value=[])

    # Case 1: app2unit available with valid desktop entry
    with patch("caelestia.subcommands.toggle.validate_desktop_id", return_value=True), patch(
        "shutil.which", side_effect=lambda x: "/usr/bin/app2unit" if x == "app2unit" else None
    ), patch("caelestia.utils.hypr.dispatch") as mock_dispatch:
        spawned = cmd.spawn_client(lambda c: False, ["spotify.desktop"])
        assert spawned is True
        mock_dispatch.assert_called_once_with("exec", "[workspace special:communication] app2unit -- spotify.desktop")

    # Case 2: gtk-launch available when app2unit is absent
    with patch("caelestia.subcommands.toggle.validate_desktop_id", return_value=True), patch(
        "shutil.which", side_effect=lambda x: "/usr/bin/gtk-launch" if x == "gtk-launch" else None
    ), patch("caelestia.utils.hypr.dispatch") as mock_dispatch:
        spawned = cmd.spawn_client(lambda c: False, ["spotify.desktop"])
        assert spawned is True
        mock_dispatch.assert_called_once_with("exec", "[workspace special:communication] gtk-launch spotify")

    # Case 3: gio launch available when app2unit and gtk-launch are absent
    with patch("caelestia.subcommands.toggle.validate_desktop_id", return_value=True), patch(
        "shutil.which", side_effect=lambda x: "/usr/bin/gio" if x == "gio" else None
    ), patch("caelestia.utils.hypr.dispatch") as mock_dispatch:
        spawned = cmd.spawn_client(lambda c: False, ["spotify.desktop"])
        assert spawned is True
        mock_dispatch.assert_called_once_with("exec", "[workspace special:communication] gio launch spotify.desktop")

    # Case 4: No launcher available
    with patch("caelestia.subcommands.toggle.validate_desktop_id", return_value=True), patch(
        "shutil.which", return_value=None
    ), patch("caelestia.subcommands.toggle.notify") as mock_notify:
        spawned = cmd.spawn_client(lambda c: False, ["spotify.desktop"])
        assert spawned is False
        mock_notify.assert_called_once_with(
            "Missing launcher", "No supported desktop launcher (app2unit, gtk-launch, or gio) is installed."
        )

    # Case 5: Invalid desktop ID
    with patch("caelestia.subcommands.toggle.validate_desktop_id", return_value=False), patch(
        "caelestia.subcommands.toggle.notify"
    ) as mock_notify:
        spawned = cmd.spawn_client(lambda c: False, ["nonexistent.desktop"])
        assert spawned is False
        mock_notify.assert_called_once_with("Missing desktop file", "Desktop entry 'nonexistent.desktop' not found.")


def test_manifest_sync_with_pkgbuild():
    pkgbuild_path, manifest_path = resolve_manifest_and_pkgbuild()
    assert pkgbuild_path.exists(), f"PKGBUILD not found at {pkgbuild_path}"
    assert manifest_path.exists(), f"manifest.toml not found at {manifest_path}"

    manifest = Manifest.parse(manifest_path.read_text())
    manifest.resolve_components()
    manifest_pkgs = manifest.enabled_packages()

    pkgbuild_text = pkgbuild_path.read_text()

    # Validate CLI runtime package parity across manifest and PKGBUILD
    cli_runtime_deps = ["fuzzel", "libnotify", "swappy", "grim", "slurp", "cliphist", "gpu-screen-recorder", "wl-clipboard"]
    for dep in cli_runtime_deps:
        if dep in manifest_pkgs:
            assert dep in pkgbuild_text, f"{dep} is in manifest.toml but missing from PKGBUILD"
