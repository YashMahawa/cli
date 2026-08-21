import argparse
import subprocess
import sys

class Command:
    def __init__(self, args: argparse.Namespace):
        self.args = args

    def run(self) -> None:
        cmd = ["caelestia-display"]
        display_action = getattr(self.args, "display_action", None)
        if display_action:
            cmd.append(display_action)
        if getattr(self.args, "token", None):
            cmd.append(self.args.token)
        if getattr(self.args, "profile_action", None):
            cmd.extend(["profile", self.args.profile_action])
        if getattr(self.args, "name", None):
            cmd.append(self.args.name)
        if getattr(self.args, "monitors_json", None):
            cmd.extend(["--monitors-json", self.args.monitors_json])

        res = subprocess.run(cmd, text=True)
        if res.returncode != 0:
            sys.exit(res.returncode)
