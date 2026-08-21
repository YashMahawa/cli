import json
import subprocess
from argparse import Namespace
from unittest.mock import MagicMock, patch

from caelestia.subcommands.clipboard import Command


def test_clipboard_copy_executes_daemon_copy(tmp_path: MagicMock) -> None:
    history_file = tmp_path / "clipboard-history.json"
    history_data = [
        {"id": 42, "kind": "text", "text": "Hello world\nSecond line"},
        {"id": 10, "kind": "image", "text": "Copied image"},
    ]
    history_file.write_text(json.dumps(history_data), encoding="utf-8")

    args = Namespace(delete=False)
    cmd = Command(args)

    with (
        patch("caelestia.subcommands.clipboard.c_state_dir", tmp_path),
        patch("shutil.which", return_value="/usr/bin/fuzzel"),
        patch("subprocess.check_output") as mock_check_output,
        patch("subprocess.run") as mock_run,
    ):
        mock_check_output.return_value = "42\tHello world Second line\n"

        cmd.run()

        mock_check_output.assert_called_once_with(
            ["fuzzel", "--dmenu", "--placeholder=Type to search clipboard"],
            input="42\tHello world Second line\n10\tCopied image",
            text=True,
        )
        mock_run.assert_called_once_with(["caelestia-clipboard", "copy", "42"], check=False)


def test_clipboard_delete_executes_daemon_delete(tmp_path: MagicMock) -> None:
    history_file = tmp_path / "clipboard-history.json"
    history_data = [{"id": 7, "kind": "text", "text": "Delete me"}]
    history_file.write_text(json.dumps(history_data), encoding="utf-8")

    args = Namespace(delete=True)
    cmd = Command(args)

    with (
        patch("caelestia.subcommands.clipboard.c_state_dir", tmp_path),
        patch("shutil.which", return_value="/usr/bin/fuzzel"),
        patch("subprocess.check_output") as mock_check_output,
        patch("subprocess.run") as mock_run,
    ):
        mock_check_output.return_value = "7\tDelete me\n"

        cmd.run()

        mock_check_output.assert_called_once_with(
            ["fuzzel", "--dmenu", "--prompt=del > ", "--placeholder=Delete from clipboard"],
            input="7\tDelete me",
            text=True,
        )
        mock_run.assert_called_once_with(["caelestia-clipboard", "delete", "7"], check=False)


def test_clipboard_missing_file_handles_gracefully(tmp_path: MagicMock) -> None:
    args = Namespace(delete=False)
    cmd = Command(args)

    with (
        patch("caelestia.subcommands.clipboard.c_state_dir", tmp_path),
        patch("shutil.which", return_value="/usr/bin/fuzzel"),
        patch("subprocess.check_output") as mock_check_output,
        patch("subprocess.run") as mock_run,
    ):
        mock_check_output.return_value = ""

        cmd.run()

        mock_check_output.assert_called_once_with(
            ["fuzzel", "--dmenu", "--placeholder=Type to search clipboard"],
            input="",
            text=True,
        )
        mock_run.assert_not_called()


def test_clipboard_fuzzel_cancelled(tmp_path: MagicMock) -> None:
    history_file = tmp_path / "clipboard-history.json"
    history_file.write_text(json.dumps([{"id": 1, "text": "test"}]), encoding="utf-8")

    args = Namespace(delete=False)
    cmd = Command(args)

    with (
        patch("caelestia.subcommands.clipboard.c_state_dir", tmp_path),
        patch("shutil.which", return_value="/usr/bin/fuzzel"),
        patch("subprocess.check_output", side_effect=subprocess.CalledProcessError(1, ["fuzzel"])),
        patch("subprocess.run") as mock_run,
    ):
        cmd.run()
        mock_run.assert_not_called()


def test_clipboard_empty_text_fallback(tmp_path: MagicMock) -> None:
    history_file = tmp_path / "clipboard-history.json"
    history_file.write_text(json.dumps([{"id": 15, "kind": "image", "text": ""}]), encoding="utf-8")

    args = Namespace(delete=False)
    cmd = Command(args)

    with (
        patch("caelestia.subcommands.clipboard.c_state_dir", tmp_path),
        patch("shutil.which", return_value="/usr/bin/fuzzel"),
        patch("subprocess.check_output") as mock_check_output,
        patch("subprocess.run") as mock_run,
    ):
        mock_check_output.return_value = "15\t[image]\n"

        cmd.run()

        mock_check_output.assert_called_once_with(
            ["fuzzel", "--dmenu", "--placeholder=Type to search clipboard"],
            input="15\t[image]",
            text=True,
        )
        mock_run.assert_called_once_with(["caelestia-clipboard", "copy", "15"], check=False)
