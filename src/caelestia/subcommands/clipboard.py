import json
import subprocess
from argparse import Namespace

from caelestia.utils.paths import c_state_dir


class Command:
    args: Namespace

    def __init__(self, args: Namespace) -> None:
        self.args = args

    def run(self) -> None:
        history_file = c_state_dir / "clipboard-history.json"
        entries = []
        if history_file.is_file():
            try:
                entries = json.loads(history_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                entries = []

        lines = []
        if isinstance(entries, list):
            for item in entries:
                if not isinstance(item, dict):
                    continue
                item_id = item.get("id")
                if item_id is None:
                    continue
                text = item.get("text", "")
                if not text or not str(text).strip():
                    text = f"[{item.get('kind', 'item')}]"
                text_single_line = " ".join(str(text).splitlines())
                lines.append(f"{item_id}\t{text_single_line}")

        clip = "\n".join(lines)

        if self.args.delete:
            args = ["--prompt=del > ", "--placeholder=Delete from clipboard"]
        else:
            args = ["--placeholder=Type to search clipboard"]

        try:
            chosen = subprocess.check_output(
                ["fuzzel", "--dmenu", *args], input=clip, text=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return

        if not chosen or not chosen.strip():
            return

        try:
            chosen_id = int(chosen.strip().split("\t")[0])
        except (ValueError, IndexError):
            return

        if self.args.delete:
            subprocess.run(["caelestia-clipboard", "delete", str(chosen_id)], check=False)
        else:
            subprocess.run(["caelestia-clipboard", "copy", str(chosen_id)], check=False)
