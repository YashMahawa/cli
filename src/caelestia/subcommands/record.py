import re
import shutil
import subprocess
import time
from argparse import Namespace
from datetime import datetime
from pathlib import Path

from caelestia.utils import hypr
from caelestia.utils.notify import close_notification, notify
from caelestia.utils.paths import get_config, recording_notif_path, recording_path, recordings_dir

RECORDER = "gpu-screen-recorder"

_STOPPED_NOTIF_HANDLER = r"""
path=$1
uri=$2
directory=$3

action=$(notify-send -a caelestia-cli \
    --action=watch=Watch \
    --action=open=Open \
    --action=delete=Delete \
    "Recording stopped" \
    "Recording saved in $path") || exit 0

case "$action" in
    watch)
        exec app2unit -O "$path"
        ;;
    open)
        dbus-send --session --dest=org.freedesktop.FileManager1 --type=method_call \
            /org/freedesktop/FileManager1 org.freedesktop.FileManager1.ShowItems \
            "array:string:$uri" "string:" || exec app2unit -O "$directory"
        ;;
    delete)
        rm -f -- "$path"
        ;;
esac
"""
QUALITY_DEFAULTS = (
    ("-k", "hevc"),
    ("-encoder", "gpu"),
    ("-fallback-cpu-encoding", "yes"),
    ("-q", "ultra"),
    ("-tune", "quality"),
    ("-fm", "cfr"),
)


def quality_args(extra_args: object) -> list[str]:
    """Add quality-first defaults while preserving explicit user choices."""
    args = [str(value) for value in extra_args] if isinstance(extra_args, list) else []
    for option, value in QUALITY_DEFAULTS:
        if option not in args:
            args.extend((option, value))
    return args


def monitor_refresh_rate(monitor: object, fallback: int = 60) -> int:
    if not isinstance(monitor, dict):
        return fallback
    try:
        return max(1, round(float(monitor.get("refreshRate", fallback))))
    except (TypeError, ValueError):
        return fallback


class Command:
    args: Namespace

    def __init__(self, args: Namespace) -> None:
        self.args = args

    def run(self) -> None:
        if self.args.pause:
            subprocess.run(["pkill", "-USR2", "-f", RECORDER], stdout=subprocess.DEVNULL)
        elif self.proc_running():
            self.stop()
        else:
            self.start()

    def proc_running(self) -> bool:
        return subprocess.run(["pidof", RECORDER], stdout=subprocess.DEVNULL).returncode == 0

    def intersects(self, a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
        return a[0] < b[0] + b[2] and a[0] + a[2] > b[0] and a[1] < b[1] + b[3] and a[1] + a[3] > b[1]

    def start(self) -> None:
        args = ["-w"]

        monitors = hypr.message("monitors")
        if self.args.region:
            if self.args.region == "slurp":
                region = subprocess.check_output(
                    ["slurp", "-f", "%wx%h+%x+%y"], text=True, stdin=subprocess.DEVNULL
                )
            else:
                region = self.args.region.strip()
            args += ["region", "-region", region]

            m = re.match(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", region)
            if not m:
                raise ValueError(f"Invalid region: {region}")

            w, h, x, y = map(int, m.groups())
            r = x, y, w, h
            max_rr = 60
            for monitor in monitors if isinstance(monitors, list) else []:
                if isinstance(monitor, dict) and self.intersects(
                    (monitor["x"], monitor["y"], monitor["width"], monitor["height"]), r
                ):
                    rr = monitor_refresh_rate(monitor)
                    max_rr = max(max_rr, rr)
            args += ["-f", str(max_rr)]
        else:
            focused_monitor = hypr.focused_monitor(monitors)
            if focused_monitor is None:
                notify("Recording failed", "No focused monitor is available to record")
                return
            args += [focused_monitor["name"], "-f", str(monitor_refresh_rate(focused_monitor))]

        audio = getattr(self.args, "audio", None) or ("system" if self.args.sound else "none")
        sources = {
            "system": "default_output",
            "mic": "default_input",
            # One mixed track, so players and editors get both without setup.
            "both": "default_output|default_input",
        }
        if audio in sources:
            args += ["-a", sources[audio]]

        config = get_config()
        try:
            extra_args = config.get("record", {}).get("extraArgs", [])
            args += quality_args(extra_args)
        except TypeError as e:
            raise ValueError(f"Config option 'record.extraArgs' should be an array: {e}")

        recording_path.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.Popen(
            [RECORDER, *args, "-o", str(recording_path)],
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        notif = notify("-p", "Recording started", "Recording...")
        recording_notif_path.write_text(notif)

        try:
            if proc.wait(1) != 0:
                close_notification(notif)
                notify(
                    "Recording failed",
                    "An error occurred attempting to start recorder. "
                    f"Command `{' '.join(proc.args)}` failed with exit code {proc.returncode}",
                )
        except subprocess.TimeoutExpired:
            pass

    def stop(self) -> None:
        # Start killing recording process
        subprocess.run(["pkill", "-f", RECORDER], stdout=subprocess.DEVNULL)

        # Wait for recording to finish to avoid corrupted video file
        while self.proc_running():
            time.sleep(0.1)

        # Move to recordings folder
        new_path = recordings_dir / f"recording_{datetime.now().strftime('%Y%m%d_%H-%M-%S')}.mp4"
        recordings_dir.mkdir(exist_ok=True, parents=True)
        shutil.move(recording_path, new_path)

        # Close start notification
        try:
            close_notification(recording_notif_path.read_text())
        except IOError:
            pass

        if self.args.clipboard:
            file_uri = Path(new_path).resolve().as_uri() + "\n"
            subprocess.run(["wl-copy", "--type", "text/uri-list"], input=file_uri.encode())

        # Handle the notification's actions in a detached process so this
        # command (and the shell's recorder state) is not held open until the
        # notification is clicked or dismissed.
        subprocess.Popen(
            ["sh", "-c", _STOPPED_NOTIF_HANDLER, "sh", str(new_path), new_path.resolve().as_uri(), str(new_path.parent)],
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
