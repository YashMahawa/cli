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

    positionals: list[str] = []
    i = 0
    n = len(args)
    while i < n:
        arg = args[i]
        if arg.startswith("-"):
            if arg in ("-p", "--print-id", "-e", "--transient"):
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
            elif opt in ("-u", "--urgency", "-c", "--category", "-h", "--hint"):
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

    actions_dbus = "[" + ", ".join(f"'{a}'" for a in actions) + "]" if actions else "[]"

    try:
        subprocess.run(
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
                "{}",
                expire_timeout,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return ""


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
            id,
        ],
        stdout=subprocess.DEVNULL,
    )
