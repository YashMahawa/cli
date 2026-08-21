import json
import shutil
import subprocess
import sys
from argparse import Namespace

from caelestia.utils.io import error

MIN_SERVICE_VERSION = "1.0.0"


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

    def check_compatibility(self) -> bool:
        try:
            ver_output = self._raw_ipc("version")
            if not ver_output:
                return False
            try:
                data = json.loads(ver_output)
                if isinstance(data, dict):
                    if data.get("compatible") is False or data.get("error") == "incompatible_version":
                        error(f"Incompatible overlay service version: {data.get('message', 'Version mismatch')}")
                        sys.exit(1)
                    service_ver = data.get("version", "")
                else:
                    service_ver = str(data)
            except json.JSONDecodeError:
                service_ver = ver_output.strip()

            if service_ver and not self._is_version_compatible(service_ver):
                error(f"Incompatible overlay service version '{service_ver}': required >= {MIN_SERVICE_VERSION}")
                sys.exit(1)
            return True
        except Exception:
            return True

    def _is_version_compatible(self, version_str: str) -> bool:
        try:
            v_parts = [int(p) for p in version_str.split(".")]
            req_parts = [int(p) for p in MIN_SERVICE_VERSION.split(".")]
            return v_parts >= req_parts
        except ValueError:
            return True

    def _raw_ipc(self, method: str, *args: str) -> str:
        ipc_bin = shutil.which("caelestia-qs-ipc") or "caelestia-qs-ipc"
        cmd = [ipc_bin, "call", "overlay", method]
        for arg in args:
            if arg is not None:
                cmd.append(str(arg))

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except FileNotFoundError as e:
            error(f"Shell overlay service is not running or {ipc_bin} is missing: {e}")
            sys.exit(1)

        output = proc.stdout.strip()
        err_out = proc.stderr.strip()

        if proc.returncode != 0:
            err_msg = err_out or output or "IPC execution failed"
            try:
                err_json = json.loads(output or err_out)
                if isinstance(err_json, dict) and "error" in err_json:
                    err_type = err_json.get("error")
                    msg = err_json.get("message", err_type)
                    if err_type == "missing_shell":
                        err_msg = f"Shell overlay service is not running: {msg}"
                    elif err_type == "stale_window":
                        err_msg = f"Overlay window is stale or no longer exists: {msg}"
                    elif err_type == "incompatible_version":
                        err_msg = f"Incompatible overlay service version: {msg}"
                    elif err_type == "service_restarted":
                        err_msg = f"Shell overlay service was restarted: {msg}"
                    else:
                        err_msg = f"{err_type}: {msg}"
            except (json.JSONDecodeError, TypeError):
                pass

            error(f"Failed to communicate with shell overlay service: {err_msg}")
            sys.exit(proc.returncode if proc.returncode != 0 else 1)

        return output

    def send_ipc(self, method: str, *args: str, check_compat: bool = True) -> str:
        if check_compat and method != "version":
            self.check_compatibility()

        output = self._raw_ipc(method, *args)

        if output:
            try:
                data = json.loads(output)
                if isinstance(data, dict):
                    if data.get("success") is False or "error" in data:
                        err_type = data.get("error", "Unknown Error")
                        msg = data.get("message", err_type)
                        if err_type == "missing_shell":
                            err_msg = f"Shell overlay service is not running: {msg}"
                        elif err_type == "stale_window":
                            err_msg = f"Overlay window is stale or no longer exists: {msg}"
                        elif err_type == "incompatible_version":
                            err_msg = f"Incompatible overlay service version: {msg}"
                        elif err_type == "service_restarted":
                            err_msg = f"Shell overlay service was restarted: {msg}"
                        else:
                            err_msg = f"{err_type}: {msg}"

                        error(f"Overlay service error: {err_msg}")
                        sys.exit(1)
            except json.JSONDecodeError:
                pass

        return output

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
        margin = getattr(self.args, "margin", "10")
        if margin is None or margin == "":
            margin = "10"
        try:
            margin_val = int(margin)
            if margin_val < 0:
                raise ValueError("Margin must be a non-negative integer")
            margin_str = str(margin_val)
        except (ValueError, TypeError):
            error(f"Invalid numeric margin '{margin}': must be a non-negative integer")
            sys.exit(1)

        res = self.send_ipc("anchor", pos, window, margin_str)
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
