import argparse
import getpass
import logging
import os
import sys

from Agent.config import APP_TYPE, BACKEND_URL, LOG_LEVEL
from Agent.sender import check_backend, set_credentials
from Agent.watcher import SourceManager

_VALID_APP_TYPES = ("python", "node", "windows")


def _input_path(prompt: str) -> str:
    """Path input with Tab completion using msvcrt."""
    import glob as _glob
    import msvcrt

    buf: list[str] = []
    sys.stdout.write(prompt)
    sys.stdout.flush()

    while True:
        ch = msvcrt.getwch()

        if ch in ("\r", "\n"):
            sys.stdout.write("\n")
            sys.stdout.flush()
            return "".join(buf)

        elif ch == "\t":
            current = "".join(buf)
            matches = sorted(_glob.glob(current + "*"))
            if not matches:
                pass
            elif len(matches) == 1:
                completed = matches[0].replace("\\", "/")
                if os.path.isdir(completed) and not completed.endswith("/"):
                    completed += "/"
                buf = list(completed)
                text = "".join(buf)
                sys.stdout.write(f"\r{prompt}{text}  \r{prompt}{text}")
                sys.stdout.flush()
            else:
                common = os.path.commonprefix(matches).replace("\\", "/")
                if len(common) > len(current):
                    buf = list(common)
                sys.stdout.write("\n")
                for m in matches[:10]:
                    sys.stdout.write(f"  {m.replace(chr(92), '/')}\n")
                if len(matches) > 10:
                    sys.stdout.write(f"  ... ({len(matches) - 10} more)\n")
                sys.stdout.write(f"{prompt}{''.join(buf)}")
                sys.stdout.flush()

        elif ch == "\x08":  # Backspace
            if buf:
                buf.pop()
                text = "".join(buf)
                sys.stdout.write(f"\r{prompt}{text}  \r{prompt}{text}")
                sys.stdout.flush()

        elif ch == "\xe0":  # Arrow / special key prefix — consume and ignore
            msvcrt.getwch()

        elif ord(ch) >= 32:
            buf.append(ch)
            sys.stdout.write(ch)
            sys.stdout.flush()


def _pick(options: list[str], prompt: str) -> str:
    """Arrow-key selection menu. Up/Down to move, Enter to select."""
    os.system("")  # enable ANSI on Windows

    import msvcrt

    idx = 0
    n = len(options)

    def _draw():
        for i, opt in enumerate(options):
            marker = "\x1b[1;36m>\x1b[0m" if i == idx else " "
            sys.stdout.write(f"\r {marker} {opt}               \n")
        sys.stdout.write(f"\x1b[{n}A")
        sys.stdout.flush()

    print(prompt)
    _draw()

    while True:
        ch = msvcrt.getwch()
        if ch == "\xe0":
            arrow = msvcrt.getwch()
            if arrow == "H":
                idx = (idx - 1) % n
            elif arrow == "P":
                idx = (idx + 1) % n
        elif ch in ("\r", "\n"):
            chosen = options[idx]
            for _ in range(n):
                sys.stdout.write(f"\r\x1b[K\n")
            sys.stdout.write(f"\x1b[{n}A\r  \x1b[32m✓\x1b[0m {chosen}\n")
            sys.stdout.flush()
            return chosen
        _draw()

HELP = """\
Commands:
  add <path>   Start watching a directory for .log files
  rm  <path>   Stop watching a directory
  list         Show all active watch paths
  help         Show this message
  quit         Exit the agent\
"""


def setup_logging():
    level = getattr(logging, LOG_LEVEL, logging.INFO)
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        level=level,
        stream=sys.stderr,
    )


def run_cli(manager: SourceManager):
    print(HELP)
    while True:
        try:
            raw = input("agent> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not raw:
            continue

        parts = raw.split(None, 1)
        cmd = parts[0].lower()

        if cmd in ("quit", "exit"):
            break
        elif cmd == "add":
            if len(parts) < 2:
                print("usage: add <path>")
            else:
                print(manager.add(parts[1]))
        elif cmd in ("rm", "remove"):
            if len(parts) < 2:
                print("usage: rm <path>")
            else:
                print(manager.remove(parts[1]))
        elif cmd == "list":
            sources = manager.list()
            if sources:
                for s in sources:
                    print(f"  {s}")
            else:
                print("  (no sources watched)")
        elif cmd == "help":
            print(HELP)
        else:
            print(f"unknown command '{cmd}'. Type 'help' for available commands.")


def prompt_credentials() -> tuple[str, str]:
    print("Mini-Splunk Agent — Login")
    username = input("Username: ").strip()
    password = getpass.getpass("Password: ")
    return username, password


def prompt_init() -> tuple[str, str]:
    print("\n--- Agent Init ---")

    while True:
        path = _input_path("Watch path (Tab to complete): ").strip()
        if path:
            break
        print("  Path cannot be empty.")

    app_type = _pick(list(_VALID_APP_TYPES), "App type (use arrow keys):")
    print(f"  Watching: {path}\n")
    return path, app_type


def main():
    setup_logging()
    log = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description="Mini-Splunk log agent")
    parser.add_argument(
        "--watch",
        nargs="*",
        default=[],
        metavar="PATH",
        help="Directories to watch at startup (skips init prompt)",
    )
    args = parser.parse_args()

    username, password = prompt_credentials()
    set_credentials(username, password)

    if check_backend():
        log.info("backend reachable at %s", BACKEND_URL)
    else:
        log.warning("backend unreachable at %s — logs will be retried or dead-lettered", BACKEND_URL)

    # If no paths supplied via CLI/env, run the interactive init prompt
    pre_configured = [p for p in args.watch if p]
    if pre_configured:
        app_type = APP_TYPE
        init_paths = pre_configured
    else:
        init_path, app_type = prompt_init()
        init_paths = [init_path]

    log.info("starting | app_type=%s | backend=%s", app_type, BACKEND_URL)
    manager = SourceManager(app_type=app_type)

    for path in init_paths:
        print(manager.add(path))

    try:
        run_cli(manager)
    finally:
        log.info("shutting down, flushing buffer...")
        manager.stop()
        log.info("stopped")


if __name__ == "__main__":
    main()
