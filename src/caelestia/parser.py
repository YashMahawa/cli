import argparse
import sys

from caelestia.subcommands import (
    clipboard,
    display,
    emoji,
    install,
    record,
    resizer,
    scheme,
    screenshot,
    shell,
    toggle,
    update,
    wallpaper,
)
from caelestia.utils.dots.manifest import Manifest
from caelestia.utils.dots.packages import AUR_HELPERS
from caelestia.utils.dots.source import DotsSource
from caelestia.utils.io import warn
from caelestia.utils.paths import wallpapers_dir
from caelestia.utils.scheme import get_scheme_names, scheme_variants
from caelestia.utils.wallpaper import get_wallpaper


def parse_args() -> tuple[argparse.ArgumentParser, argparse.Namespace]:
    parser = argparse.ArgumentParser(prog="caelestia", description="Main control script for the Caelestia dotfiles")
    parser.add_argument("-v", "--version", action="store_true", help="print the current version")

    # Add subcommand parsers
    command_parser = parser.add_subparsers(
        title="subcommands", description="valid subcommands", metavar="COMMAND", help="the subcommand to run"
    )

    # Create parser for shell opts
    shell_parser = command_parser.add_parser("shell", help="start or message the shell")
    shell_parser.set_defaults(cls=shell.Command)
    shell_parser.add_argument("message", nargs="*", help="a message to send to the shell")
    shell_parser.add_argument("-d", "--daemon", action="store_true", help="start the shell detached")
    shell_parser.add_argument("-s", "--show", action="store_true", help="print all shell IPC commands")
    shell_parser.add_argument("-l", "--log", action="store_true", help="print the shell log")
    shell_parser.add_argument("-k", "--kill", action="store_true", help="kill the shell")
    shell_parser.add_argument("--log-rules", metavar="RULES", help="log rules to apply")

    # Create parser for toggle opts
    toggle_parser = command_parser.add_parser("toggle", help="toggle a special workspace")
    toggle_parser.set_defaults(cls=toggle.Command)
    toggle_parser.add_argument("workspace", help="the workspace to toggle")

    # Create parser for scheme opts
    scheme_parser = command_parser.add_parser("scheme", help="manage the colour scheme")
    scheme_command_parser = scheme_parser.add_subparsers(title="subcommands")

    list_parser = scheme_command_parser.add_parser("list", help="list available schemes")
    list_parser.set_defaults(cls=scheme.List)
    list_parser.add_argument("-n", "--names", action="store_true", help="list scheme names")
    list_parser.add_argument("-f", "--flavours", action="store_true", help="list scheme flavours")
    list_parser.add_argument("-m", "--modes", action="store_true", help="list scheme modes")
    list_parser.add_argument("-v", "--variants", action="store_true", help="list scheme variants")

    get_parser = scheme_command_parser.add_parser("get", help="get scheme properties")
    get_parser.set_defaults(cls=scheme.Get)
    get_parser.add_argument("-n", "--name", action="store_true", help="print the current scheme name")
    get_parser.add_argument("-f", "--flavour", action="store_true", help="print the current scheme flavour")
    get_parser.add_argument("-m", "--mode", action="store_true", help="print the current scheme mode")
    get_parser.add_argument("-v", "--variant", action="store_true", help="print the current scheme variant")

    set_parser = scheme_command_parser.add_parser("set", help="set the current scheme")
    set_parser.set_defaults(cls=scheme.Set)
    set_parser.add_argument("--notify", action="store_true", help="send a notification on error")
    set_parser.add_argument("-r", "--random", action="store_true", help="switch to a random scheme")
    set_parser.add_argument("-n", "--name", choices=get_scheme_names(), help="the name of the scheme to switch to")
    set_parser.add_argument("-f", "--flavour", help="the flavour to switch to")
    set_parser.add_argument("-m", "--mode", choices=["dark", "light"], help="the mode to switch to")
    set_parser.add_argument("-v", "--variant", choices=scheme_variants, help="the variant to switch to")
    set_parser.add_argument("--sync", action="store_true", help="run theme application synchronously for validation")

    # Create parser for screenshot opts
    screenshot_parser = command_parser.add_parser("screenshot", help="take a screenshot")
    screenshot_parser.set_defaults(cls=screenshot.Command)
    screenshot_parser.add_argument("-r", "--region", nargs="?", const="slurp", help="take a screenshot of a region")
    screenshot_parser.add_argument(
        "-f", "--freeze", action="store_true", help="freeze the screen while selecting a region"
    )

    # Create parser for record opts
    record_parser = command_parser.add_parser("record", help="start a screen recording")
    record_parser.set_defaults(cls=record.Command)
    record_parser.add_argument("-r", "--region", nargs="?", const="slurp", help="record a region")
    record_parser.add_argument("-s", "--sound", action="store_true", help="record audio")
    record_parser.add_argument("-p", "--pause", action="store_true", help="pause/resume the recording")
    record_parser.add_argument("-c", "--clipboard", action="store_true", help="copy recording path to clipboard")

    # Create parser for clipboard opts
    clipboard_parser = command_parser.add_parser("clipboard", help="open clipboard history")
    clipboard_parser.set_defaults(cls=clipboard.Command)
    clipboard_parser.add_argument("-d", "--delete", action="store_true", help="delete from clipboard history")

    # Create parser for display opts
    display_parser = command_parser.add_parser("display", help="interactive visual monitor manager controls")
    display_parser.set_defaults(cls=display.Command)
    display_subparsers = display_parser.add_subparsers(dest="display_action", help="display action to execute")

    # apply subcommand
    apply_parser = display_subparsers.add_parser("apply", help="apply display configuration")
    apply_parser.add_argument("token", nargs="?", help="apply confirmation token")
    apply_parser.add_argument("--token", dest="token_opt", help="apply confirmation token")
    apply_parser.add_argument("--monitors-json", help="JSON payload for monitor arrangements")
    apply_parser.add_argument("--name", help="Monitor name")
    apply_parser.add_argument("--resolution", "--res", dest="res", help="Resolution e.g. 1920x1080@60")
    apply_parser.add_argument("--position", "--pos", dest="pos", help="Position e.g. 0x0")
    apply_parser.add_argument("--scale", help="Scale factor e.g. 1.25")
    apply_parser.add_argument("--transform", help="Transform index 0-7")
    apply_parser.add_argument("--old-res", help="Previous resolution")
    apply_parser.add_argument("--old-pos", help="Previous position")
    apply_parser.add_argument("--old-scale", help="Previous scale factor")

    # mode subcommand
    mode_parser = display_subparsers.add_parser("mode", help="set display mode preset")
    mode_parser.add_argument(
        "mode_name", choices=["extend", "join", "mirror", "external", "laptop"], help="display mode preset"
    )

    # confirm subcommand
    confirm_parser = display_subparsers.add_parser("confirm", help="confirm display configuration")
    confirm_parser.add_argument("token", nargs="?", help="confirmation token")
    confirm_parser.add_argument("--token", dest="token_opt", help="confirmation token")

    # rollback subcommand
    rollback_parser = display_subparsers.add_parser("rollback", help="rollback display configuration")
    rollback_parser.add_argument("token", nargs="?", help="rollback token")
    rollback_parser.add_argument("--token", dest="token_opt", help="rollback token")

    # status subcommand
    display_subparsers.add_parser("status", help="show display status")

    # move-window subcommand
    move_parser = display_subparsers.add_parser("move-window", help="move active window to target display")
    move_parser.add_argument("target", help="target monitor name")

    # profile subcommand
    profile_parser = display_subparsers.add_parser("profile", help="manage display profiles")
    profile_subparsers = profile_parser.add_subparsers(dest="profile_action", help="profile action")
    profile_subparsers.add_parser("list", help="list saved profiles")

    profile_save = profile_subparsers.add_parser("save", help="save current display profile")
    profile_save.add_argument("name", help="profile name")
    profile_save.add_argument("--monitors-json", help="Monitors JSON for saving profile")

    profile_load = profile_subparsers.add_parser("load", help="load a display profile")
    profile_load.add_argument("name", help="profile name")

    profile_delete = profile_subparsers.add_parser("delete", help="delete a display profile")
    profile_delete.add_argument("name", help="profile name")

    # Create parser for emoji-picker opts
    emoji_parser = command_parser.add_parser("emoji", help="emoji/glyph utilities")
    emoji_parser.set_defaults(cls=emoji.Command)
    emoji_parser.add_argument("-p", "--picker", action="store_true", help="open the emoji/glyph picker")
    emoji_parser.add_argument("-f", "--fetch", action="store_true", help="fetch emoji/glyph data from remote")

    # Create parser for wallpaper opts
    wallpaper_parser = command_parser.add_parser("wallpaper", help="manage the wallpaper")
    wallpaper_parser.set_defaults(cls=wallpaper.Command)
    wallpaper_parser.add_argument(
        "-p", "--print", nargs="?", const=get_wallpaper(), metavar="PATH", help="print the scheme for a wallpaper"
    )
    wallpaper_parser.add_argument(
        "-r", "--random", nargs="?", const=wallpapers_dir, metavar="DIR", help="switch to a random wallpaper"
    )
    wallpaper_parser.add_argument("-f", "--file", help="the path to the wallpaper to switch to")
    wallpaper_parser.add_argument("-n", "--no-filter", action="store_true", help="do not filter by size")
    wallpaper_parser.add_argument("--sync", action="store_true", help="run theme application synchronously for validation")
    wallpaper_parser.add_argument(
        "-t",
        "--threshold",
        default=0.8,
        help="the minimum percentage of the largest monitor size the image must be greater than to be selected",
    )
    wallpaper_parser.add_argument(
        "-N",
        "--no-smart",
        action="store_true",
        help="do not automatically change the scheme mode based on wallpaper colour",
    )

    # Create parser for resizer opts
    resizer_parser = command_parser.add_parser("resizer", help="window resizer daemon")
    resizer_parser.set_defaults(cls=resizer.Command)
    resizer_parser.add_argument("-d", "--daemon", action="store_true", help="start the resizer daemon")
    resizer_parser.add_argument(
        "pattern",
        nargs="?",
        help="pattern to match against windows ('active' for current window only, 'pip' for quick pip mode)",
    )
    resizer_parser.add_argument(
        "match_type",
        nargs="?",
        metavar="match_type",
        choices=["titleContains", "titleExact", "titleRegex", "initialTitle", "initialTitleContains", "initialTitleRegex", "initialClass", "class"],
        help="type of pattern matching (titleContains,titleExact,titleRegex,initialTitle,initialTitleContains,initialTitleRegex,initialClass,class)",
    )
    resizer_parser.add_argument("width", nargs="?", help="width to resize to")
    resizer_parser.add_argument("height", nargs="?", help="height to resize to")
    resizer_parser.add_argument("actions", nargs="?", help="comma-separated actions to apply (float,center,pip)")
    resizer_parser.add_argument(
        "--match",
        action="append",
        metavar="RULE",
        help="match criteria in the format key[:predicate]=value (e.g., class=Gimp, title:regex=^Foo)",
    )

    # Create parser for install opts
    install_parser = command_parser.add_parser(
        "install",
        help="install the Caelestia dotfiles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    install_parser.set_defaults(cls=install.Command)
    install_parser.add_argument("--aur-helper", choices=AUR_HELPERS, help="the AUR helper to use")
    install_parser.add_argument(
        "--enable-components", metavar="LIST", help="comma-separated list of components to enable"
    )
    install_parser.add_argument(
        "--disable-components", metavar="LIST", help="comma-separated list of components to disable"
    )
    install_parser.add_argument("--noconfirm", action="store_true", help="use defaults for all prompts")
    _set_install_epilog(install_parser)

    # Create parser for update opts
    update_parser = command_parser.add_parser("update", help="update the Caelestia dotfiles")
    update_parser.set_defaults(cls=update.Command)
    update_parser.add_argument("--aur-helper", choices=AUR_HELPERS, help="the AUR helper to use")
    update_parser.add_argument("--noconfirm", action="store_true", help="use defaults for all prompts")

    return parser, parser.parse_args()


def _set_install_epilog(install_parser: argparse.ArgumentParser) -> None:
    """Add components if using install subcommand"""

    if len(sys.argv) > 1 and sys.argv[1] == "install":
        manifest = _load_install_manifest()
        if manifest is not None and manifest.components:
            install_parser.epilog = _components_epilog(manifest)


def _load_install_manifest() -> Manifest | None:
    source = DotsSource()
    try:
        source.ensure()
        return source.manifest_at(source.remote_ref)
    except Exception as e:
        warn(f"failed to load manifest from dots repo ({e})\n", prefix=False)
        return None


def _components_epilog(manifest: Manifest) -> str:
    def e(*v: int) -> str:
        return f"\033[{';'.join(str(c) for c in v)}m"

    def b(c: int) -> str:
        return e(1, c)

    reset = e(0)

    width = max(len(name) for name in manifest.components)
    lines = [f"{b(34)}available components (for --enable-components / --disable-components):{reset}"]
    for name, comp in manifest.components.items():
        lines.append(f"  {b(32)}{name:<{width}}{reset}\t{'(default)' if comp.default else '(off)'}")
    return "\n".join(lines)
