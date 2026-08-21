import re
import socket
import time
from argparse import Namespace
from pathlib import Path
from typing import Any, Dict, Optional

from caelestia.utils import hypr
from caelestia.utils.io import error, fatal, info, log, warn, log_exception
from caelestia.utils.paths import get_config, user_config_path


def _get_prop_value(window_info: dict, prop: str) -> Any:
    normalized_prop = "class" if prop in ("window_class", "initialClass") and prop == "window_class" else prop

    if normalized_prop in ("width", "size.width", "size_width", "size.0"):
        if "width" in window_info and window_info["width"] is not None:
            return window_info["width"]
        size = window_info.get("size")
        if isinstance(size, (list, tuple)) and len(size) >= 1:
            return size[0]
        return 0
    elif normalized_prop in ("height", "size.height", "size_height", "size.1"):
        if "height" in window_info and window_info["height"] is not None:
            return window_info["height"]
        size = window_info.get("size")
        if isinstance(size, (list, tuple)) and len(size) >= 2:
            return size[1]
        return 0
    elif normalized_prop in ("initialWidth", "initial_width"):
        if "initialWidth" in window_info and window_info["initialWidth"] is not None:
            return window_info["initialWidth"]
        initial_size = window_info.get("initialSize")
        if isinstance(initial_size, (list, tuple)) and len(initial_size) >= 1:
            return initial_size[0]
        size = window_info.get("size")
        if isinstance(size, (list, tuple)) and len(size) >= 1:
            return size[0]
        return 0
    elif normalized_prop in ("initialHeight", "initial_height"):
        if "initialHeight" in window_info and window_info["initialHeight"] is not None:
            return window_info["initialHeight"]
        initial_size = window_info.get("initialSize")
        if isinstance(initial_size, (list, tuple)) and len(initial_size) >= 2:
            return initial_size[1]
        size = window_info.get("size")
        if isinstance(size, (list, tuple)) and len(size) >= 2:
            return size[1]
        return 0

    current_val = window_info
    for part in normalized_prop.split('.'):
        if isinstance(current_val, dict):
            current_val = current_val.get(part, "")
        elif isinstance(current_val, (list, tuple)):
            try:
                idx = int(part)
                current_val = current_val[idx] if 0 <= idx < len(current_val) else ""
            except ValueError:
                current_val = ""
                break
        else:
            current_val = ""
            break

    if prop == "workspace" and isinstance(current_val, dict):
        current_val = current_val.get("name", current_val.get("id", ""))

    return current_val


class WindowRule:
    def __init__(self, name: str, match_type: str, width: str, height: str, actions: list[str], matches: Optional[list[tuple[str, str, str]]] = None):
        self.name = name
        self.match_type = match_type
        self.width = width
        self.height = height
        self.actions = actions
        
        if matches is not None:
            self.matches = matches
        else:
            self.matches = []
            if match_type == "initialTitle":
                self.matches.append(("initialTitle", "exact", name))
            elif match_type == "initialTitleContains":
                self.matches.append(("initialTitle", "contains", name))
            elif match_type == "initialTitleRegex":
                self.matches.append(("initialTitle", "regex", name))
            elif match_type == "initialClass":
                self.matches.append(("initialClass", "exact", name))
            elif match_type == "class":
                self.matches.append(("class", "exact", name))
            elif match_type == "titleContains":
                self.matches.append(("title", "contains", name))
            elif match_type == "titleExact":
                self.matches.append(("title", "exact", name))
            elif match_type == "titleRegex":
                self.matches.append(("title", "regex", name))

    def evaluate(self, window_info: dict) -> bool:
        if not self.matches:
            return False
            
        for prop, predicate, value in self.matches:
            actual_pred = predicate
            if prop in ("max_width", "max_height"):
                actual_prop = "initialWidth" if prop == "max_width" else "initialHeight"
                if actual_pred in ("exact", ""):
                    actual_pred = "lte"
            elif prop in ("min_width", "min_height"):
                actual_prop = "initialWidth" if prop == "min_width" else "initialHeight"
                if actual_pred in ("exact", ""):
                    actual_pred = "gte"
            else:
                actual_prop = prop

            window_val = _get_prop_value(window_info, actual_prop)

            if actual_pred in (
                "less_than", "lt", "<",
                "less_than_or_equal", "lte", "le", "<=", "max",
                "greater_than", "gt", ">",
                "greater_than_or_equal", "gte", "ge", ">=", "min",
            ):
                try:
                    num_win = float(window_val)
                    num_val = float(value)
                except (ValueError, TypeError):
                    return False

                if actual_prop in ("initialWidth", "initialHeight", "width", "height", "initial_width", "initial_height"):
                    if num_win <= 0:
                        return False

                if actual_pred in ("less_than", "lt", "<"):
                    if not (num_win < num_val):
                        return False
                elif actual_pred in ("less_than_or_equal", "lte", "le", "<=", "max"):
                    if not (num_win <= num_val):
                        return False
                elif actual_pred in ("greater_than", "gt", ">"):
                    if not (num_win > num_val):
                        return False
                elif actual_pred in ("greater_than_or_equal", "gte", "ge", ">=", "min"):
                    if not (num_win >= num_val):
                        return False
            elif actual_pred == "exact":
                if str(window_val) != str(value):
                    return False
            elif actual_pred == "contains":
                if str(value) not in str(window_val):
                    return False
            elif actual_pred == "regex":
                try:
                    if not re.search(value, str(window_val)):
                        return False
                except re.error:
                    warn(f"invalid regex pattern '{value}'")
                    return False
            else:
                if str(window_val) != str(value):
                    return False
                    
        return True

def _parse_match_arg(match_str: str) -> tuple[str, str, str]:
    if "=" not in match_str:
        return ("", "", "")
    
    key_part, value = match_str.split("=", 1)
    if ":" in key_part:
        prop, predicate = key_part.split(":", 1)
    else:
        prop = key_part
        predicate = "exact"
        
    return (prop, predicate, value)


class Command:
    def __init__(self, args: Namespace) -> None:
        self.args = args
        self.timeout_tracker: dict[str, float] = {}
        self.applied_rules: dict[str, str] = {}
        self.window_initial_props: dict[str, dict[str, Any]] = {}
        
        self.enable_fallback_heuristic = False
        self.window_rules = self._load_window_rules()

    def _make_resize_cmd(self, width: int | str, height: int | str, address: str) -> str:
        if hypr.is_lua_config():
            return f'dispatch hl.dsp.window.resize({{x = {width}, y = {height}, exact = true, window = "address:{address}"}})'
        return f"dispatch resizewindowpixel exact {width} {height},address:{address}"

    def _make_move_cmd(self, x: int, y: int, address: str) -> str:
        if hypr.is_lua_config():
            return f'dispatch hl.dsp.window.move({{x = {x}, y = {y}, window = "address:{address}"}})'
        return f"dispatch movewindowpixel exact {x} {y},address:{address}"

    def _make_float_cmd(self, address: str) -> str:
        if hypr.is_lua_config():
            return f'dispatch hl.dsp.window.float({{action = "toggle", window = "address:{address}"}})'
        return f"dispatch togglefloating address:{address}"

    def _make_center_cmd(self) -> str:
        if hypr.is_lua_config():
            return "dispatch hl.dsp.window.center()"
        return "dispatch centerwindow"

    def _record_initial_props(self, window_id: str, window_info: dict, fallback_title: str = "", fallback_class: str = "") -> None:
        initial_title = window_info.get("initialTitle") or window_info.get("title") or fallback_title
        initial_class = window_info.get("initialClass") or window_info.get("class") or fallback_class
        size = window_info.get("size")
        if not (isinstance(size, (list, tuple)) and len(size) >= 2):
            size = [0, 0]

        w = size[0] if isinstance(size[0], (int, float)) else 0
        h = size[1] if isinstance(size[1], (int, float)) else 0

        if window_id in self.window_initial_props:
            stored = self.window_initial_props[window_id]
            stored_w = stored.get("initialWidth", 0)
            stored_h = stored.get("initialHeight", 0)

            if (stored_w <= 0 or stored_h <= 0) and (w > 0 and h > 0):
                stored["initialSize"] = [w, h]
                stored["initialWidth"] = w
                stored["initialHeight"] = h

            if initial_title and (not stored.get("initialTitle") or stored.get("initialTitle") == fallback_title):
                stored["initialTitle"] = initial_title
            if initial_class and (not stored.get("initialClass") or stored.get("initialClass") == fallback_class):
                stored["initialClass"] = initial_class
            return

        self.window_initial_props[window_id] = {
            "initialTitle": initial_title,
            "initialClass": initial_class,
            "initialSize": [w, h],
            "initialWidth": w,
            "initialHeight": h,
        }

    def _enhance_window_info(self, window_id: str, window_info: dict) -> dict:
        if not isinstance(window_info, dict):
            return window_info

        initial_props = self.window_initial_props.get(window_id, {})
        for key, val in initial_props.items():
            if key not in window_info or window_info[key] is None or window_info[key] == "":
                window_info[key] = val

        if "initialTitle" not in window_info or not window_info["initialTitle"]:
            window_info["initialTitle"] = window_info.get("title", "")
        if "initialClass" not in window_info or not window_info["initialClass"]:
            window_info["initialClass"] = window_info.get("class", "")

        size = window_info.get("size")
        if isinstance(size, (list, tuple)) and len(size) >= 2:
            if "initialSize" not in window_info:
                window_info["initialSize"] = [size[0], size[1]]
            if "initialWidth" not in window_info:
                window_info["initialWidth"] = size[0]
            if "initialHeight" not in window_info:
                window_info["initialHeight"] = size[1]

        return window_info

    def _load_window_rules(self) -> list[WindowRule]:
        default_rules = [
            WindowRule("(Bitwarden", "titleContains", "20%", "54%", ["float", "center"]),
            WindowRule("^[Pp]icture(-| )in(-| )[Pp]icture$", "titleRegex", "", "", ["pip"]),
            WindowRule(
                "(?i)Sign In",
                "",
                "",
                "",
                ["float", "center"],
                matches=[
                    ("initialTitle", "regex", "(?i)Sign In"),
                    ("initialWidth", "lte", "1000"),
                    ("initialHeight", "lte", "800"),
                ],
            ),
            WindowRule(
                "(?i)Verification",
                "",
                "",
                "",
                ["float", "center"],
                matches=[
                    ("initialTitle", "regex", "(?i)Verification"),
                    ("initialWidth", "lte", "1000"),
                    ("initialHeight", "lte", "800"),
                ],
            ),
            WindowRule("(?i)Splash", "titleRegex", "", "", ["float", "center"]),
            WindowRule("(?i)^(?!.*The Updater).*Updater.*$", "titleRegex", "", "", ["float", "center"]),
        ]

        config = get_config()
        self.enable_fallback_heuristic = config.get("resizer", {}).get("enableFallbackHeuristic", False)

        try:
            if "resizer" in config and "rules" in config["resizer"]:
                rules = []
                for rule_config in config["resizer"]["rules"]:
                    matches = []
                    if "matches" in rule_config:
                        for match_item in rule_config["matches"]:
                            if isinstance(match_item, (list, tuple)) and len(match_item) == 3:
                                matches.append((str(match_item[0]), str(match_item[1]), str(match_item[2])))
                            elif isinstance(match_item, str):
                                p, pred, val = _parse_match_arg(match_item)
                                if p:
                                    matches.append((p, pred, val))
                    rules.append(
                        WindowRule(
                            rule_config.get("name", ""),
                            rule_config.get("matchType", ""),
                            rule_config.get("width", ""),
                            rule_config.get("height", ""),
                            rule_config.get("actions", []),
                            matches=matches if matches else None,
                        )
                    )
                return rules + default_rules
        except KeyError:
            warn("invalid config, falling back to default rules")
        except FileNotFoundError:
            pass

        return default_rules

    def _is_rate_limited(self, key: str) -> bool:
        current_time = time.time()
        last_time = self.timeout_tracker.get(key, 0)

        if current_time < last_time + 1:
            return True

        self.timeout_tracker[key] = current_time
        return False

    def _get_window_info(self, window_id: str, retries: int = 0) -> Optional[Dict[str, Any]]:
        attempts = 1 + max(0, retries)
        for attempt in range(attempts):
            try:
                clients = hypr.message("clients")
                if isinstance(clients, list):
                    for client in clients:
                        if isinstance(client, dict) and client.get("address") == f"0x{window_id}":
                            size = client.get("size")
                            w = size[0] if isinstance(size, (list, tuple)) and len(size) >= 1 and isinstance(size[0], (int, float)) else 0
                            h = size[1] if isinstance(size, (list, tuple)) and len(size) >= 2 and isinstance(size[1], (int, float)) else 0

                            self._record_initial_props(window_id, client)
                            if (w > 0 and h > 0) or attempt == attempts - 1:
                                return self._enhance_window_info(window_id, client)
            except Exception:
                pass

            if attempt < attempts - 1:
                time.sleep(0.02)

        return None

    def _apply_pip_action(self, window_id: str) -> None:
        try:
            address = f"0x{window_id}"
            clients_result = hypr.message("clients")
            if not isinstance(clients_result, list):
                return

            window = None
            for c in clients_result:
                if isinstance(c, dict) and c.get("address") == address:
                    window = c
                    break

            if not window or not isinstance(window, dict) or not window.get("floating", False):
                return

            workspaces_result = hypr.message("workspaces")
            if not isinstance(workspaces_result, list):
                return

            workspace_info = window.get("workspace")
            if not isinstance(workspace_info, dict):
                return

            workspace_name = workspace_info.get("name")
            workspace = None
            for w in workspaces_result:
                if isinstance(w, dict) and w.get("name") == workspace_name:
                    workspace = w
                    break

            if not workspace or not isinstance(workspace, dict):
                return

            monitors_result = hypr.message("monitors")
            if not isinstance(monitors_result, list):
                return

            monitor_id = workspace.get("monitorID")
            monitor = None
            for m in monitors_result:
                if isinstance(m, dict) and m.get("id") == monitor_id:
                    monitor = m
                    break

            if not monitor or not isinstance(monitor, dict):
                return

            window_size = window.get("size")
            if not isinstance(window_size, list) or len(window_size) < 2:
                return

            width, height = window_size[0], window_size[1]
            if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
                return

            monitor_height = monitor.get("height")
            monitor_width = monitor.get("width")
            monitor_scale = monitor.get("scale")
            monitor_x = monitor.get("x")
            monitor_y = monitor.get("y")

            if not all(
                isinstance(x, (int, float))
                for x in [monitor_height, monitor_width, monitor_scale, monitor_x, monitor_y]
            ):
                return

            monitor_height = monitor_height / monitor_scale
            monitor_width = monitor_width / monitor_scale

            scale_factor = monitor_height / 4 / height
            scaled_width = int(width * scale_factor)
            scaled_height = int(height * scale_factor)

            # Ensure minimum reasonable size
            min_width = 200
            min_height = 150
            scaled_width = max(scaled_width, min_width)
            scaled_height = max(scaled_height, min_height)

            # Use offset to ensure window stays on screen with some margin
            offset = min(monitor_width, monitor_height) * 0.03

            # Position in bottom-right corner with offset
            move_x = monitor_x + monitor_width - scaled_width - offset
            move_y = monitor_y + monitor_height - scaled_height - offset

            command1 = self._make_resize_cmd(scaled_width, scaled_height, address)
            command2 = self._make_move_cmd(int(move_x), int(move_y), address)
            hypr.batch(command1, command2)

            info(f"Applied PiP action to window {address}: {scaled_width}x{scaled_height} at ({move_x}, {move_y})")

        except Exception as e:
            error(f"failed to apply PiP action to window 0x{window_id}: {e}")

    def _apply_window_actions(self, window_id: str, width: str, height: str, actions: list[str]) -> bool:
        dispatch_commands = []

        if "float" in actions:
            window_info = self._get_window_info(window_id)
            if window_info and not window_info.get("floating", False):
                dispatch_commands.append(self._make_float_cmd(f"0x{window_id}"))

        if "pip" in actions:
            self._apply_pip_action(window_id)
            return True

        if width and height:
            dispatch_commands.append(self._make_resize_cmd(width, height, f"0x{window_id}"))

        if "center" in actions:
            dispatch_commands.append(self._make_center_cmd())

        try:
            hypr.batch(*dispatch_commands)
            info(f"Applied actions to window 0x{window_id}: {width} x {height} ({', '.join(actions)})")
            return True
        except Exception as e:
            error(f"failed to apply window actions for window 0x{window_id}: {e}")
            return False

    def _match_window_rule(self, window_info: dict) -> WindowRule | None:
        try:
            current_mtime = user_config_path.stat().st_mtime
        except FileNotFoundError:
            current_mtime = 0.0

        if getattr(self, "last_config_mtime", -1.0) != current_mtime:
            self.last_config_mtime = current_mtime
            self.window_rules = self._load_window_rules()

        for rule in self.window_rules:
            if rule.evaluate(window_info):
                return rule
        return None

    def _apply_matching_rule(self, window_id: str, window_info: dict) -> bool:
        rule = self._match_window_rule(window_info)
        if not rule:
            return False
        signature = f"{rule.name}|{rule.match_type}|{rule.width}|{rule.height}|{','.join(rule.actions)}"
        if self.applied_rules.get(window_id) == signature:
            return True
        if self._is_rate_limited(f"{window_id}:{signature}"):
            return True
        info(f"Matched rule '{rule.name}' for window 0x{window_id}")
        if self._apply_window_actions(window_id, rule.width, rule.height, rule.actions):
            self.applied_rules[window_id] = signature
        return True

    def _apply_protocol_popup(self, window_id: str, window_info: dict) -> bool:
        """Use compositor protocol metadata, independent of title language."""
        modal_state = window_info.get("modal", False)
        parent_addr = window_info.get("parent", "")
        xdg_parent = window_info.get("xdg_toplevel_parent", "")
        has_parent = bool(parent_addr) and parent_addr not in ("0x0", "", "0")
        has_xdg_parent = bool(xdg_parent) and xdg_parent not in ("0x0", "", "0")
        if not (modal_state or has_parent or has_xdg_parent):
            return False
        signature = "protocol-popup"
        if self.applied_rules.get(window_id) == signature:
            return True
        if self._is_rate_limited(f"{window_id}:{signature}"):
            return True
        info(f"Protocol popup detected for 0x{window_id}; floating automatically")
        if self._apply_window_actions(window_id, "", "", ["float", "center"]):
            self.applied_rules[window_id] = signature
        return True

    def _apply_unparented_popup_heuristic(self, window_id: str, window_info: dict) -> bool:
        """Evaluate unparented popups against creation geometry thresholds requiring strong popup evidence."""
        modal_state = window_info.get("modal", False)
        parent_addr = window_info.get("parent", "")
        xdg_parent = window_info.get("xdg_toplevel_parent", "")
        transient_for = window_info.get("transient_for", "")
        has_parent = (
            (bool(parent_addr) and parent_addr not in ("0x0", "", "0"))
            or (bool(xdg_parent) and xdg_parent not in ("0x0", "", "0"))
            or (bool(transient_for) and transient_for not in ("0x0", "", "0"))
        )
        if modal_state or has_parent:
            return False

        size = window_info.get("initialSize") or window_info.get("size", [0, 0])
        if not isinstance(size, (list, tuple)) or len(size) < 2:
            return False

        w, h = size[0], size[1]
        if not (isinstance(w, (int, float)) and isinstance(h, (int, float))):
            return False

        if w <= 0 or h <= 0:
            return False

        is_popup_geometry = 200 <= w <= 1000 and 100 <= h <= 800 and (w / h if h > 0 else 0) >= 0.3
        if not is_popup_geometry:
            return False

        title = (window_info.get("title", "") or window_info.get("initialTitle", "")).lower()
        role = str(
            window_info.get("role")
            or window_info.get("windowRole")
            or window_info.get("window_role")
            or window_info.get("type")
            or ""
        ).lower()

        is_auth_keywords = any(
            kw in title
            for kw in ("sign in", "verification", "log in", "login", "oauth", "auth", "sso", "accounts")
        )
        has_popup_role = any(
            r in role for r in ("popup", "pop-up", "dialog", "utility", "transient")
        )

        # Strong popup evidence is required: auth title or popup/transient role.
        # Browser class alone is NEVER sufficient.
        has_strong_evidence = is_auth_keywords or has_popup_role
        if not has_strong_evidence:
            return False

        signature = "unparented-popup"
        if self.applied_rules.get(window_id) == signature:
            return True
        if self._is_rate_limited(f"{window_id}:{signature}"):
            return True
        info(f"Unparented popup heuristic matched (size {w}x{h}) for 0x{window_id}; floating automatically")
        if self._apply_window_actions(window_id, "", "", ["float", "center"]):
            self.applied_rules[window_id] = signature
            return True

        return False

    def _handle_window_event(self, event: str) -> None:
        if event.startswith("windowtitle"):
            self._handle_title_event(event)
        elif event.startswith("openwindow"):
            self._handle_open_event(event)
        elif event.startswith("closewindow"):
            window_id = event.split(">>", 1)[-1].lstrip(">").split(",", 1)[0]
            self.applied_rules.pop(window_id, None)
            self.window_initial_props.pop(window_id, None)

    def _handle_title_event(self, event: str) -> None:
        try:
            # Handle both >> and >>> separators (different Hyprland versions)
            if ">>>" in event:
                window_id = event.split(">>>")[1].split(",")[0]
            else:
                window_id = event.split(">>")[1].split(",")[0]

            # Remove any leading > characters
            window_id = window_id.lstrip(">")

            if not all(c in "0123456789abcdefABCDEF" for c in window_id):
                warn(f"invalid window ID format: {window_id}")
                return

            window_info = self._get_window_info(window_id)
            if not window_info:
                return

            self._enhance_window_info(window_id, window_info)

            window_title = window_info.get("title", "")
            initial_title = window_info.get("initialTitle", "")
            window_class = window_info.get("class", "")
            initial_class = window_info.get("initialClass", "")

            log(f"Window 0x{window_id} - Title: '{window_title}' | Initial: '{initial_title}'")

            if self._apply_matching_rule(window_id, window_info):
                return
            self._apply_protocol_popup(window_id, window_info)

        except (IndexError, ValueError) as e:
            warn(f"failed to parse window title event: {e}")

    def _handle_open_event(self, event: str) -> None:
        try:
            # Handle both >> and >>> separators
            if "openwindow>>>" in event:
                data = event[13:]  # Remove "openwindow>>>"
            else:
                data = event[12:]  # Remove "openwindow>>"

            window_id, workspace, window_class, title = data.split(",", 3)

            # Remove any leading > characters
            window_id = window_id.lstrip(">")

            if not all(c in "0123456789abcdefABCDEF" for c in window_id):
                warn(f"invalid window ID format: {window_id}")
                return

            log(f"New window 0x{window_id} - Title: '{title}' | Class: '{window_class}'")

            window_info = self._get_window_info(window_id, retries=3)
            if not window_info:
                window_info = {
                    "address": f"0x{window_id}",
                    "title": title,
                    "initialTitle": title,
                    "class": window_class,
                    "initialClass": window_class,
                    "workspace": {"name": workspace},
                    "size": [0, 0],
                    "modal": False,
                    "parent": "0x0",
                    "xdg_toplevel_parent": "0x0",
                }

            self._record_initial_props(window_id, window_info, fallback_title=title, fallback_class=window_class)
            self._enhance_window_info(window_id, window_info)

            if self._apply_matching_rule(window_id, window_info):
                return

            if self._apply_protocol_popup(window_id, window_info):
                return

            if self._apply_unparented_popup_heuristic(window_id, window_info):
                return

        except (IndexError, ValueError) as e:
            warn(f"failed to parse window open event: {e}")

    def run(self) -> None:
        if self.args.daemon:
            self._run_daemon()
        elif hasattr(self.args, "pattern") and self.args.pattern == "pip":
            self._run_pip_mode()
        elif (
            all(hasattr(self.args, attr) and getattr(self.args, attr) for attr in ["pattern", "match_type", "width", "height", "actions"])
            or (hasattr(self.args, "match") and getattr(self.args, "match") and getattr(self.args, "width") and getattr(self.args, "height") and getattr(self.args, "actions"))
        ):
            self._run_active_mode()
        else:
            info(
                "Resizer daemon - use --daemon to start, 'pip' for quick pip mode, or provide pattern, match_type, width, height, and actions for active mode"
            )

    def _run_pip_mode(self) -> None:
        """Quick pip mode - applies pip action to the active window if it's floating"""
        try:
            active_window_result = hypr.message("activewindow")
            if not isinstance(active_window_result, dict) or not active_window_result.get("address"):
                error("no active window found")
                return

            address = active_window_result.get("address", "")
            if not isinstance(address, str) or not address.startswith("0x"):
                error("invalid window address")
                return

            window_id = address[2:]  # Remove "0x" prefix
            window_title = active_window_result.get("title", "")

            if not active_window_result.get("floating", False):
                warn(f"window '{window_title}' is not floating; PiP only works on floating windows.")
                return

            info(f"Applying PiP to active window: '{window_title}'")
            self._apply_pip_action(window_id)
            info("PiP applied successfully")

        except Exception as e:
            error(f"failed to apply PiP to active window: {e}")

    def _run_active_mode(self) -> None:
        try:
            # Create a temporary rule from command line arguments
            actions = self.args.actions.split(",") if self.args.actions else []
            matches = []
            
            if hasattr(self.args, "match") and getattr(self.args, "match"):
                for match_str in self.args.match:
                    prop, pred, val = _parse_match_arg(match_str)
                    if prop:
                        matches.append((prop, pred, val))
                        
            temp_rule = WindowRule(
                getattr(self.args, "pattern", "") or "",
                getattr(self.args, "match_type", "") or "",
                getattr(self.args, "width", "") or "",
                getattr(self.args, "height", "") or "",
                actions,
                matches=matches if matches else None
            )

            # Special case: "active" pattern means only target the currently active window
            if temp_rule.name.lower() == "active":
                self._apply_to_active_window(temp_rule)
                return

            # Find all windows that match the pattern
            matching_windows = self._find_matching_windows(temp_rule)

            if not matching_windows:
                warn(f"no windows found matching pattern '{temp_rule.name}' with match type '{temp_rule.match_type}'")
                return

            info(f"Found {len(matching_windows)} matching window(s)")

            # Apply rule to all matching windows
            success_count = 0
            for window in matching_windows:
                window_id = window["address"][2:]  # Remove "0x" prefix
                window_title = window.get("title", "")

                info(f"Applying rule to window 0x{window_id}: '{window_title}'")
                success = self._apply_window_actions(window_id, temp_rule.width, temp_rule.height, temp_rule.actions)
                if success:
                    success_count += 1

            info(f"Successfully applied rule to {success_count}/{len(matching_windows)} windows")

        except Exception as e:
            error(f"failed to apply rule: {e}")

    def _apply_to_active_window(self, temp_rule: WindowRule) -> None:
        """Apply rule only to the currently active window"""
        try:
            active_window_result = hypr.message("activewindow")
            if not isinstance(active_window_result, dict) or not active_window_result.get("address"):
                error("no active window found")
                return

            window_title = active_window_result.get("title", "")
            address = active_window_result.get("address", "")
            if not isinstance(address, str) or not address.startswith("0x"):
                error("invalid window address")
                return

            window_id = address[2:]  # Remove "0x" prefix

            info(f"Applying rule to active window 0x{window_id}: '{window_title}'")
            success = self._apply_window_actions(window_id, temp_rule.width, temp_rule.height, temp_rule.actions)
            if success:
                info("Rule applied successfully")
            else:
                error("failed to apply rule")

        except Exception as e:
            error(f"failed to apply rule to active window: {e}")

    def _find_matching_windows(self, temp_rule: WindowRule) -> list:
        """Find all windows that match the given rule pattern"""
        try:
            clients_result = hypr.message("clients")
            if not isinstance(clients_result, list):
                return []

            matching_windows = []
            for window in clients_result:
                if not isinstance(window, dict):
                    continue

                window_title = window.get("title", "")
                initial_title = window.get("initialTitle", "")
                window_class = window.get("class", "")
                initial_class = window.get("initialClass", "")

                # Check if window matches the pattern
                if temp_rule.evaluate(window):
                    matching_windows.append(window)

            return matching_windows

        except Exception as e:
            error(f"failed to find matching windows: {e}")
            return []

    @log_exception
    def _attempt_connection(self) -> bool:
        """Attempts to connect to socket and process events. Returns True if cleanly exited, False on EOF."""
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            sock.connect(hypr.socket2_path)
            
            info("Connected to Hyprland socket, listening for events...")
            self.connected = True

            while self.running:
                try:
                    data = sock.recv(4096).decode()
                    if not data:
                        warn("Hyprland socket closed (EOF)")
                        return False
                    for line in data.strip().split("\n"):
                        if line:
                            self._handle_window_event(line)
                except socket.timeout:
                    continue
                except BlockingIOError:
                    continue
            return True

    def _wait(self, duration: float) -> None:
        elapsed = 0.0
        while self.running and elapsed < duration:
            time.sleep(0.1)
            elapsed += 0.1

    def _run_daemon(self) -> None:
        import os
        import signal
        import tempfile

        pid_file = Path(tempfile.gettempdir()) / "caelestia-resizer.pid"
        
        if pid_file.exists():
            try:
                old_pid = int(pid_file.read_text().strip())
                os.kill(old_pid, 0)
                fatal(f"Daemon is already running with PID {old_pid}")
            except (ValueError, OSError):
                pass
                
        try:
            pid_file.write_text(str(os.getpid()))
        except Exception as e:
            fatal(f"Could not write PID file: {e}")

        self.running = True
        
        def handle_sig(signum, frame):
            self.running = False

        signal.signal(signal.SIGTERM, handle_sig)
        signal.signal(signal.SIGINT, handle_sig)

        info("Hyprland window resizer started")
        info(f"Loaded {len(self.window_rules)} window rules")

        backoff = 1.0
        max_backoff = 5.0

        try:
            while self.running:
                socket_path = Path(hypr.socket2_path)
                if not socket_path.exists():
                    warn(f"Hyprland socket not found at {socket_path}, retrying in {backoff}s...")
                    self._wait(backoff)
                    backoff = min(backoff * 2.0, max_backoff)
                    continue

                self.connected = False
                self._attempt_connection()
                
                if not self.running:
                    break

                if self.connected:
                    backoff = 1.0
                else:
                    warn(f"Connection attempt failed, retrying in {backoff}s...")
                    self._wait(backoff)
                    backoff = min(backoff * 2.0, max_backoff)
                
        except KeyboardInterrupt:
            pass
        except Exception as e:
            error(str(e))
        finally:
            info("Resizer daemon stopped")
            if pid_file.exists():
                try:
                    pid_file.unlink()
                except Exception:
                    pass
