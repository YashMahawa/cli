import argparse
import shutil
import subprocess
import sys

CANONICAL_BACKEND = "caelestia-display"


def build_command(args: argparse.Namespace) -> list[str]:
    raw_args = list(getattr(args, "args", []) or [])
    if raw_args and raw_args[0] == "mode":
        mode_args = raw_args[1:]
        if shutil.which("caelestia-display-mode"):
            return ["caelestia-display-mode"] + mode_args

        cmd = ["caelestia-display", "apply"]
        if mode_args:
            mode_name = mode_args[0]
            mode_map = {
                "extend": '[{"name": "eDP-1", "res": "preferred", "pos": "0x0", "scale": "1"}, {"name": "HDMI-A-1", "res": "preferred", "pos": "1920x0", "scale": "1"}]',
                "join": '[{"name": "eDP-1", "res": "preferred", "pos": "0x0", "scale": "1"}, {"name": "HDMI-A-1", "res": "preferred", "pos": "1920x0", "scale": "1"}]',
                "mirror": '[{"name": "eDP-1", "res": "preferred", "pos": "0x0", "scale": "1"}, {"name": "HDMI-A-1", "res": "0x0", "scale": "1"}]',
                "external": '[{"name": "eDP-1", "disabled": true}, {"name": "HDMI-A-1", "res": "preferred", "pos": "0x0", "scale": "1"}]',
                "laptop": '[{"name": "eDP-1", "res": "preferred", "pos": "0x0", "scale": "1"}, {"name": "HDMI-A-1", "disabled": true}]',
            }
            if mode_name in mode_map:
                cmd.extend(["--monitors-json", mode_map[mode_name]])
        return cmd

    return ["caelestia-display"] + raw_args


def feature_detect_backend(executable: str = CANONICAL_BACKEND) -> dict:
    """Feature-detect the installed backend capabilities by querying backend help output."""
    backend_binary = shutil.which(executable)
    detected = {
        "binary": executable,
        "path": backend_binary,
        "available": backend_binary is not None,
        "supports_mode_script": shutil.which("caelestia-display-mode") is not None,
    }

    if not detected["available"]:
        return detected

    try:
        proc = subprocess.run([executable, "--help"], capture_output=True, text=True)
        help_out = proc.stdout + proc.stderr
        detected["help_output"] = help_out
    except Exception:
        pass

    return detected


def verify_backend_contract(executable: str = CANONICAL_BACKEND) -> bool:
    """Verify that the backend executable is available in PATH."""
    info = feature_detect_backend(executable)
    return info["available"]


class Command:
    def __init__(self, args: argparse.Namespace):
        self.args = args

    def run(self) -> None:
        cmd = build_command(self.args)
        executable = cmd[0]
        if not shutil.which(executable):
            print(f"Error: Required display backend binary '{executable}' not found in PATH.", file=sys.stderr)
            sys.exit(1)
        res = subprocess.run(cmd, text=True)
        if res.returncode != 0:
            sys.exit(res.returncode)
