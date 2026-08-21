import argparse
import subprocess
import sys


def build_command(args: argparse.Namespace) -> list[str]:
    cmd = ["caelestia-display"]
    display_action = getattr(args, "display_action", None)
    if display_action:
        cmd.append(display_action)

    if display_action == "profile":
        profile_action = getattr(args, "profile_action", None)
        if profile_action:
            cmd.append(profile_action)
        name = getattr(args, "name", None)
        if name:
            cmd.append(name)
    else:
        monitors_json = getattr(args, "monitors_json", None)
        if monitors_json:
            cmd.extend(["--monitors-json", monitors_json])
        token = getattr(args, "token", None) or getattr(args, "token_opt", None)
        if token:
            cmd.append(token)

    return cmd


class Command:
    def __init__(self, args: argparse.Namespace):
        self.args = args

    def run(self) -> None:
        cmd = build_command(self.args)
        res = subprocess.run(cmd, text=True)
        if res.returncode != 0:
            sys.exit(res.returncode)

