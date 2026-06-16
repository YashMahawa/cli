import json
import re
import socket
import time
from argparse import Namespace
from pathlib import Path
from typing import Any, Dict, Optional

from caelestia.utils import hypr
from caelestia.utils.io import error, fatal, info, log, warn, log_exception
from caelestia.utils.paths import get_config


class WindowRule:
    def __init__(self, name: str, match_type: str, width: str, height: str, actions: list[str]):
        self.name = name
        self.match_type = match_type
        self.width = width
        self.height = height
        self.actions = actions


class Command:
    def __init__(self, args: Namespace) -> None:
        self.args = args
        self.timeout_tracker: dict[str, float] = {}
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

    def _load_window_rules(self) -> list[WindowRule]:
        default_rules = [
            WindowRule("(Bitwarden", "initialTitleContains", "20%", "54%", ["float", "center"]),
            WindowRule("^[Pp]icture(-| )in(-| )[Pp]icture$", "initialTitleRegex", "", "", ["pip"]),
        ]

        config = get_config()
        try:
            if "resizer" in config and "rules" in config["resizer"]:
                rules = []
                for rule_config in config["resizer"]["rules"]:
                    rules.append(
                        WindowRule(
                            rule_config["name"],
                            rule_config["matchType"],
                            rule_config["width"],
                            rule_config["height"],
                            rule_config["actions"],
                        )
                    )
                return rules
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

    def _get_window_info(self, window_id: str) -> Optional[Dict[str, Any]]:
        try:
            clients = hypr.message("clients")
            if isinstance(clients, list):
                for client in clients:
                    if isinstance(client, dict) and client.get("address") == f"0x{window_id}":
                        return client
        except Exception:
            pass

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

    def _match_window_rule(
        self, window_title: str, initial_title: str, window_class: str = "", initial_class: str = ""
    ) -> WindowRule | None:
        for rule in self.window_rules:
            if rule.match_type == "initialTitle":
                if initial_title == rule.name:
                    return rule
            elif rule.match_type == "initialTitleContains":
                if rule.name in initial_title:
                    return rule
            elif rule.match_type == "initialTitleRegex":
                try:
                    if re.search(rule.name, initial_title):
                        return rule
                except re.error:
                    warn(f"invalid regex pattern in rule '{rule.name}'")
            elif rule.match_type == "initialClass":
                if initial_class == rule.name:
                    return rule
            elif rule.match_type == "titleContains":
                if rule.name in window_title:
                    return rule
            elif rule.match_type == "titleExact":
                if window_title == rule.name:
                    return rule
            elif rule.match_type == "titleRegex":
                try:
                    if re.search(rule.name, window_title):
                        return rule
                except re.error:
                    warn(f"invalid regex pattern in rule '{rule.name}'")
            elif rule.match_type == "class":
                if window_class == rule.name:
                    return rule

        return None

    def _handle_window_event(self, event: str) -> None:
        if event.startswith("windowtitle"):
            self._handle_title_event(event)
        elif event.startswith("openwindow"):
            self._handle_open_event(event)

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

            window_title = window_info.get("title", "")
            initial_title = window_info.get("initialTitle", "")
            window_class = window_info.get("class", "")
            initial_class = window_info.get("initialClass", "")

            log(f"Window 0x{window_id} - Title: '{window_title}' | Initial: '{initial_title}'")

            rule = self._match_window_rule(window_title, initial_title, window_class, initial_class)
            if rule:
                if self._is_rate_limited(window_id):
                    log(f"Rate limited: skipping window 0x{window_id}")
                    return

                info(f"Matched rule '{rule.name}' for window 0x{window_id}")
                self._apply_window_actions(window_id, rule.width, rule.height, rule.actions)

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

            window_info = self._get_window_info(window_id)
            initial_title = window_info.get("initialTitle", title) if window_info else title
            initial_class = window_info.get("initialClass", window_class) if window_info else window_class

            rule = self._match_window_rule(title, initial_title, window_class, initial_class)
            if rule:
                if self._is_rate_limited(window_id):
                    log(f"Rate limited: skipping window 0x{window_id}")
                    return

                info(f"Matched rule '{rule.name}' for new window 0x{window_id}")
                self._apply_window_actions(window_id, rule.width, rule.height, rule.actions)
                return

            if window_info:
                modal_state = window_info.get("modal", False)
                parent_addr = window_info.get("parent", "")
                xdg_parent = window_info.get("xdg_toplevel_parent", "")
                
                has_parent = bool(parent_addr) and parent_addr not in ("0x0", "", "0")
                has_xdg_parent = bool(xdg_parent) and xdg_parent not in ("0x0", "", "0")

                if modal_state or has_parent or has_xdg_parent:
                    if self._is_rate_limited(window_id):
                        return
                    info(f"Protocol signal detected (modal/parent) for 0x{window_id}. Floating automatically.")
                    self._apply_window_actions(window_id, "", "", ["float", "center"])
                    return

                size = window_info.get("size", [0, 0])
                if isinstance(size, list) and len(size) == 2:
                    w, h = size
                    if w > 0 and h > 0:
                        ratio = w / h
                        if 200 <= w <= 1000 and 100 <= h <= 800 and 0.5 <= ratio <= 2.5:
                            if self._is_rate_limited(window_id):
                                return
                            info(f"Fallback heuristic matched (size {w}x{h}) for 0x{window_id}. Floating automatically.")
                            self._apply_window_actions(window_id, "", "", ["float", "center"])
                            return

        except (IndexError, ValueError) as e:
            warn(f"failed to parse window open event: {e}")

    def run(self) -> None:
        if self.args.daemon:
            self._run_daemon()
        elif hasattr(self.args, "pattern") and self.args.pattern == "pip":
            self._run_pip_mode()
        elif all(
            hasattr(self.args, attr) and getattr(self.args, attr)
            for attr in ["pattern", "match_type", "width", "height", "actions"]
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
            temp_rule = WindowRule(self.args.pattern, self.args.match_type, self.args.width, self.args.height, actions)

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
                matches = False
                if temp_rule.match_type == "initialTitle":
                    matches = initial_title == temp_rule.name
                elif temp_rule.match_type == "initialTitleContains":
                    matches = temp_rule.name in initial_title
                elif temp_rule.match_type == "initialTitleRegex":
                    try:
                        matches = bool(re.search(temp_rule.name, initial_title))
                    except re.error:
                        warn(f"invalid regex pattern '{temp_rule.name}'")
                        return []
                elif temp_rule.match_type == "initialClass":
                    matches = initial_class == temp_rule.name
                elif temp_rule.match_type == "titleContains":
                    matches = temp_rule.name in window_title
                elif temp_rule.match_type == "titleExact":
                    matches = window_title == temp_rule.name
                elif temp_rule.match_type == "titleRegex":
                    try:
                        matches = bool(re.search(temp_rule.name, window_title))
                    except re.error:
                        warn(f"invalid regex pattern '{temp_rule.name}'")
                        return []
                elif temp_rule.match_type == "class":
                    matches = window_class == temp_rule.name

                if matches:
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
