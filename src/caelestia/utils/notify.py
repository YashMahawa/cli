import shutil
import subprocess


def notify(*args: str) -> str:
    if shutil.which("notify-send"):
        try:
            return subprocess.check_output(["notify-send", "-a", "caelestia-cli", *args], text=True).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    # DBus fallback if notify-send is absent or fails
    summary = args[-2] if len(args) >= 2 else (args[0] if args else "Notification")
    body = args[-1] if len(args) >= 2 else ""
    try:
        subprocess.run(
            [
                "gdbus",
                "call",
                "--session",
                "--dest=org.freedesktop.Notifications",
                "--object-path=/org/freedesktop/Notifications",
                "--method=org.freedesktop.Notifications.Notify",
                "caelestia-cli",
                "0",
                "",
                summary,
                body,
                "[]",
                "{}",
                "-1",
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
