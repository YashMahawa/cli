import argparse
import shutil
import subprocess
import sys

CANONICAL_BACKEND = "caelestia-display"

CONTRACT_SCHEMA = {
    "subcommands": ["apply", "confirm", "rollback", "status", "move-window", "profile"],
    "apply_options": [
        "--monitors-json",
        "--name",
        "--resolution",
        "--position",
        "--scale",
        "--transform",
        "--old-res",
        "--old-pos",
        "--old-scale",
    ],
    "profile_actions": ["list", "save", "load", "delete"],
    "modes": ["extend", "join", "mirror", "external", "laptop"],
}


def feature_detect_backend(executable: str = CANONICAL_BACKEND) -> dict:
    """Feature-detect and version the backend contract against the installed or PATH binary."""
    backend_binary = shutil.which(executable)
    detected = {
        "binary": executable,
        "path": backend_binary,
        "available": backend_binary is not None,
        "supports_mode_script": shutil.which("caelestia-display-mode") is not None,
        "subcommands": [],
        "apply_flags": [],
    }

    if not detected["available"]:
        return detected

    try:
        proc = subprocess.run([executable, "--help"], capture_output=True, text=True)
        help_out = proc.stdout + proc.stderr
        for sub in CONTRACT_SCHEMA["subcommands"]:
            if sub in help_out:
                detected["subcommands"].append(sub)

        apply_proc = subprocess.run([executable, "apply", "--help"], capture_output=True, text=True)
        apply_out = apply_proc.stdout + apply_proc.stderr
        for flag in CONTRACT_SCHEMA["apply_options"]:
            if flag in apply_out or flag.replace("--resolution", "--res").replace("--position", "--pos") in apply_out:
                detected["apply_flags"].append(flag)
    except Exception:
        pass

    return detected


def verify_backend_contract(executable: str = CANONICAL_BACKEND) -> bool:
    """Verify that the backend conforms to the canonical contract."""
    info = feature_detect_backend(executable)
    if not info["available"]:
        return False
    for sub in ["apply", "confirm", "rollback", "status", "profile"]:
        if sub not in info["subcommands"]:
            return False
    return True


def build_command(args: argparse.Namespace) -> list[str]:
    display_action = getattr(args, "display_action", None)

    if display_action == "mode":
        mode_name = getattr(args, "mode_name", None)
        if shutil.which("caelestia-display-mode"):
            cmd = ["caelestia-display-mode"]
            if mode_name:
                cmd.append(mode_name)
            return cmd

        cmd = ["caelestia-display", "apply"]
        mode_map = {
            "extend": '[{"name": "eDP-1", "res": "preferred", "pos": "0x0", "scale": "1"}, {"name": "HDMI-A-1", "res": "preferred", "pos": "1920x0", "scale": "1"}]',
            "join": '[{"name": "eDP-1", "res": "preferred", "pos": "0x0", "scale": "1"}, {"name": "HDMI-A-1", "res": "preferred", "pos": "1920x0", "scale": "1"}]',
            "mirror": '[{"name": "eDP-1", "res": "preferred", "pos": "0x0", "scale": "1"}, {"name": "HDMI-A-1", "res": "preferred", "pos": "0x0", "scale": "1"}]',
            "external": '[{"name": "eDP-1", "disabled": true}, {"name": "HDMI-A-1", "res": "preferred", "pos": "0x0", "scale": "1"}]',
            "laptop": '[{"name": "eDP-1", "res": "preferred", "pos": "0x0", "scale": "1"}, {"name": "HDMI-A-1", "disabled": true}]',
        }
        if mode_name in mode_map:
            cmd.extend(["--monitors-json", mode_map[mode_name]])
        return cmd

    cmd = ["caelestia-display"]
    if display_action:
        cmd.append(display_action)

    if display_action == "apply":
        name = getattr(args, "name", None)
        if name:
            cmd.extend(["--name", name])
        res = getattr(args, "res", None)
        if res:
            cmd.extend(["--resolution", res])
        pos = getattr(args, "pos", None)
        if pos:
            cmd.extend(["--position", pos])
        scale = getattr(args, "scale", None)
        if scale is not None:
            cmd.extend(["--scale", str(scale)])
        transform = getattr(args, "transform", None)
        if transform is not None:
            cmd.extend(["--transform", str(transform)])
        old_res = getattr(args, "old_res", None)
        if old_res:
            cmd.extend(["--old-res", old_res])
        old_pos = getattr(args, "old_pos", None)
        if old_pos:
            cmd.extend(["--old-pos", old_pos])
        old_scale = getattr(args, "old_scale", None)
        if old_scale is not None:
            cmd.extend(["--old-scale", str(old_scale)])
        monitors_json = getattr(args, "monitors_json", None)
        if monitors_json:
            cmd.extend(["--monitors-json", monitors_json])
        token = getattr(args, "token", None) or getattr(args, "token_opt", None)
        if token:
            cmd.append(token)

    elif display_action in ("confirm", "rollback"):
        token = getattr(args, "token", None) or getattr(args, "token_opt", None)
        if token:
            cmd.append(token)

    elif display_action == "move-window":
        target = getattr(args, "target", None)
        if target:
            cmd.append(target)

    elif display_action == "profile":
        profile_action = getattr(args, "profile_action", None)
        if profile_action:
            cmd.append(profile_action)
        name = getattr(args, "name", None)
        if name:
            cmd.append(name)
        monitors_json = getattr(args, "monitors_json", None)
        if monitors_json:
            cmd.extend(["--monitors-json", monitors_json])

    return cmd


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
