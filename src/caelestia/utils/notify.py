import re
import shutil
import subprocess


def notify(*args: str) -> str:
    if shutil.which("notify-send"):
        try:
            return subprocess.check_output(["notify-send", "-a", "caelestia-cli", *args], text=True).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    # DBus fallback if notify-send is absent or fails
    app_name = "caelestia-cli"
    app_icon = ""
    replaces_id = "0"
    expire_timeout = "-1"
    summary = ""
    body = ""
    actions: list[str] = []
    hints_dict: dict[str, str] = {}
    print_id = False

    positionals: list[str] = []
    i = 0
    n = len(args)
    while i < n:
        arg = args[i]
        if arg.startswith("-"):
            if arg in ("-p", "--print-id"):
                print_id = True
                i += 1
                continue
            if arg in ("-e", "--transient"):
                hints_dict["transient"] = "<true>"
                i += 1
                continue

            opt = arg
            val = None
            if "=" in opt:
                opt, val = opt.split("=", 1)

            if opt in ("-A", "--action"):
                if val is None and i + 1 < n and not args[i + 1].startswith("-"):
                    val = args[i + 1]
                    i += 1
                if val:
                    if "=" in val:
                        act_key, act_label = val.split("=", 1)
                    else:
                        act_key, act_label = val, val
                    actions.extend([act_key, act_label])
            elif opt in ("-a", "--app-name"):
                if val is None and i + 1 < n and not args[i + 1].startswith("-"):
                    val = args[i + 1]
                    i += 1
                if val:
                    app_name = val
            elif opt in ("-i", "--icon"):
                if val is None and i + 1 < n and not args[i + 1].startswith("-"):
                    val = args[i + 1]
                    i += 1
                if val:
                    app_icon = val
            elif opt in ("-r", "--replace-id"):
                if val is None and i + 1 < n and not args[i + 1].startswith("-"):
                    val = args[i + 1]
                    i += 1
                if val:
                    replaces_id = val
            elif opt in ("-t", "--expire-time"):
                if val is None and i + 1 < n and not args[i + 1].startswith("-"):
                    val = args[i + 1]
                    i += 1
                if val:
                    expire_timeout = val
            elif opt in ("-h", "--hint"):
                if val is None and i + 1 < n and not args[i + 1].startswith("-"):
                    val = args[i + 1]
                    i += 1
                if val:
                    parts = val.split(":", 2)
                    if len(parts) == 3:
                        h_type, h_key, h_val = parts[0].lower(), parts[1], parts[2]
                        if h_type in ("int", "int32", "uint32", "byte", "double", "boolean"):
                            hints_dict[h_key] = f"<{h_val}>"
                        else:
                            hints_dict[h_key] = f"<{repr(h_val)}>"
                    elif len(parts) == 2:
                        hints_dict[parts[0]] = f"<{repr(parts[1])}>"
            elif opt in ("-u", "--urgency", "-c", "--category"):
                if val is None and i + 1 < n and not args[i + 1].startswith("-"):
                    i += 1
            i += 1
        else:
            positionals.append(arg)
            i += 1

    if positionals:
        summary = positionals[0]
        if len(positionals) > 1:
            body = " ".join(positionals[1:])
    else:
        summary = "Notification"

    actions_dbus = "[" + ", ".join(repr(a) for a in actions) + "]" if actions else "[]"
    hints_dbus = "{" + ", ".join(f"{repr(k)}: {v}" for k, v in hints_dict.items()) + "}" if hints_dict else "{}"

    monitor_proc = None
    if actions and shutil.which("gdbus"):
        try:
            monitor_proc = subprocess.Popen(
                ["gdbus", "monitor", "--session", "--dest", "org.freedesktop.Notifications", "--object-path", "/org/freedesktop/Notifications"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except Exception:
            monitor_proc = None

    notif_id = None
    try:
        res = subprocess.check_output(
            [
                "gdbus",
                "call",
                "--session",
                "--dest=org.freedesktop.Notifications",
                "--object-path=/org/freedesktop/Notifications",
                "--method=org.freedesktop.Notifications.Notify",
                app_name,
                replaces_id,
                app_icon,
                summary,
                body,
                actions_dbus,
                hints_dbus,
                expire_timeout,
            ],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        match = re.search(r"uint32\s+(\d+)", res)
        if match:
            notif_id = match.group(1)
    except Exception:
        if monitor_proc:
            try:
                monitor_proc.terminate()
            except Exception:
                pass
            monitor_proc = None

    if monitor_proc and notif_id:
        try:
            assert monitor_proc.stdout is not None
            for line in monitor_proc.stdout:
                action_match = re.search(r"ActionInvoked.*?\b" + str(notif_id) + r"\b.*?['\"]([^'\"]+)['\"]", line)
                if action_match:
                    monitor_proc.terminate()
                    return action_match.group(1)

                closed_match = re.search(r"NotificationClosed.*?\b" + str(notif_id) + r"\b", line)
                if closed_match:
                    monitor_proc.terminate()
                    return ""
        except Exception:
            pass
        finally:
            if monitor_proc.poll() is None:
                try:
                    monitor_proc.terminate()
                except Exception:
                    pass
        return ""

    if print_id and notif_id:
        return str(notif_id)

    return ""


def open_path(path: object) -> bool:
    target = str(path)
    if shutil.which("app2unit"):
        subprocess.Popen(["app2unit", "-O", target], start_new_session=True)
        return True
    elif shutil.which("xdg-open"):
        subprocess.Popen(["xdg-open", target], start_new_session=True)
        return True
    elif shutil.which("gio"):
        subprocess.Popen(["gio", "open", target], start_new_session=True)
        return True
    else:
        notify("Missing opener", "No supported file opener (app2unit, xdg-open, or gio) is installed.")
        return False


def ensure_binary(binary: str, required: bool = True) -> bool:
    if not shutil.which(binary):
        if required:
            notify("Missing utility", f"Required binary '{binary}' is not installed.")
        return False
    return True


def close_notification(id: str) -> None:
    subprocess.run(
        [
            "gdbus",
            "call",
            "--session",
            "--dest=org.freedesktop.Notifications",
            "--object-path=/org/freedesktop/Notifications",
            "--method=org.freedesktop.Notifications.CloseNotification",
            str(id),
        ],
        stdout=subprocess.DEVNULL,
    )
