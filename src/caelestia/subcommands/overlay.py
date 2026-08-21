import subprocess
from argparse import Namespace

from caelestia.utils.io import error


class Command:
    args: Namespace

    def __init__(self, args: Namespace) -> None:
        self.args = args

    def run(self) -> None:
        action = getattr(self.args, "overlay_action", None)
        if not action or action in ["register", "float", "add"]:
            self.register()
        elif action in ["unregister", "remove", "unfloat", "unoverlay", "restore"]:
            self.unregister()
        elif action == "anchor":
            self.anchor()
        elif action == "pin":
            self.pin()
        elif action in ["clickthrough", "passthrough"]:
            self.clickthrough()
        elif action == "toggle":
            self.toggle()
        elif action in ["list", "get", "status"]:
            self.list_overlays()
        else:
            self.register()

    def send_ipc(self, method: str, *args: str) -> str:
        cmd = ["qs", "-c", "caelestia", "ipc", "call", "overlay", method]
        for arg in args:
            if arg is not None:
                cmd.append(str(arg))
        try:
            return subprocess.check_output(cmd, text=True).strip()
        except Exception as e:
            error(f"Failed to communicate with shell overlay service: {e}")
            return ""

    def register(self) -> None:
        window = getattr(self.args, "window", "active") or "active"
        anchor = getattr(self.args, "anchor", None) or ""
        pin = "true" if getattr(self.args, "pin", False) else ""
        clickthrough = "true" if getattr(self.args, "clickthrough", False) else ""
        res = self.send_ipc("register", window, anchor, pin, clickthrough)
        if res:
            print(res)

    def unregister(self) -> None:
        window = getattr(self.args, "window", "active") or "active"
        res = self.send_ipc("unregister", window)
        if res:
            print(res)

    def anchor(self) -> None:
        pos = getattr(self.args, "position", "center")
        window = getattr(self.args, "window", "active") or "active"
        margin = getattr(self.args, "margin", "10") or "10"
        res = self.send_ipc("anchor", pos, window, margin)
        if res:
            print(res)

    def pin(self) -> None:
        window = getattr(self.args, "window", "active") or "active"
        enable = getattr(self.args, "enable", False)
        disable = getattr(self.args, "disable", False)
        state_str = "true" if enable else ("false" if disable else "")
        res = self.send_ipc("pin", window, state_str)
        if res:
            print(res)

    def clickthrough(self) -> None:
        window = getattr(self.args, "window", "active") or "active"
        enable = getattr(self.args, "enable", False)
        disable = getattr(self.args, "disable", False)
        state_str = "true" if enable else ("false" if disable else "")
        res = self.send_ipc("clickthrough", window, state_str)
        if res:
            print(res)

    def toggle(self) -> None:
        window = getattr(self.args, "window", "active") or "active"
        res = self.send_ipc("toggle", window)
        if res:
            print(res)

    def list_overlays(self) -> None:
        res = self.send_ipc("list")
        if res:
            print(res)
