import os
import sys
import socket
import shutil
import webbrowser
from pathlib import Path
from datetime import datetime


def find_free_port(preferred_port: int = 8501, max_tries: int = 20) -> int:
    """Find an available TCP port, preferring a specific starting port.

    Tries sequentially from preferred_port up to preferred_port + max_tries - 1.
    Falls back to asking the OS for a free port if the preferred range is exhausted.
    """
    for port in range(preferred_port, preferred_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue

    # Fallback: let the OS allocate a free ephemeral port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def get_base_dir() -> Path:
    """Return the directory containing the bundled resources.

    - In PyInstaller onefile/onedir mode, files are extracted to sys._MEIPASS
    - In normal execution, use the directory of this file
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).parent


def resolve_paths() -> tuple[Path, Path, Path]:
    """Resolve important paths used by the app.

    Returns a tuple of:
    - base_dir: Where bundled resources live (may be a temp dir when frozen)
    - web_dir: Directory containing app.py and pages/
    - app_py: Full path to app.py
    """
    base_dir = get_base_dir()

    # When frozen, we bundle the web assets into a 'web' folder at the base
    # When running from source, this file is at goldflipper/web/entrypoint.py
    # so the web folder is the parent directory
    if (base_dir / "web").exists():
        web_dir = base_dir / "web"
    else:
        web_dir = Path(__file__).parent

    app_py = web_dir / "app.py"
    return base_dir, web_dir, app_py


def get_user_data_dir() -> Path:
    """Determine the user data directory for runtime files and DB.

    Priority:
    1) GOLDFLIPPER_DATA_DIR (if set)
    2) %APPDATA%/Goldflipper_Web on Windows, else ~/.config/Goldflipper_Web
    """
    override = os.environ.get("GOLDFLIPPER_DATA_DIR")
    if override:
        return Path(override)

    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Goldflipper_Web"

    # Non-Windows fallback
    return Path.home() / ".config" / "Goldflipper_Web"


def ensure_dirs(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def seed_database_if_needed(bundled_base: Path, user_data_dir: Path) -> None:
    """Copy a seeded DB to the user data dir if not already present.

    We bundle a seed DB at either:
    - base/web/data/db/goldflipper.db (preferred alongside app assets), or
    - base/goldflipper/data/db/goldflipper.db (fallback to package layout)
    """
    # Destination
    dest_db_dir = user_data_dir / "data" / "db"
    ensure_dirs(dest_db_dir)
    dest_db = dest_db_dir / "goldflipper.db"

    if dest_db.exists():
        return

    # Potential seed locations
    candidates = [
        bundled_base / "web" / "data" / "db" / "goldflipper.db",
        bundled_base / "goldflipper" / "data" / "db" / "goldflipper.db",
    ]

    for src in candidates:
        if src.exists():
            shutil.copy2(src, dest_db)
            return


def write_boot_log(user_data_dir: Path, text: str) -> None:
    try:
        logs_dir = user_data_dir / "logs"
        ensure_dirs(logs_dir)
        log_file = logs_dir / "launch_web.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {text}\n")
    except Exception:
        # Avoid raising on logging failures
        pass


def launch_streamlit(app_py: Path, port: int) -> int:
    """Launch Streamlit programmatically for the given script and port.

    Returns the exit code of the process. Note that this call is blocking until
    the Streamlit server terminates.
    """
    from streamlit.web import cli as streamlit_cli

    # Ensure argv is populated as if run from CLI
    sys.argv = [
        "streamlit",
        "run",
        str(app_py),
        "--server.headless=true",
        f"--server.port={port}",
        "--server.address=127.0.0.1",
        "--browser.gatherUsageStats=false",
    ]

    # Streamlit opens the default browser by default; we proactively open as well
    # to avoid cases where auto-open is disabled by user config.
    try:
        webbrowser.open(f"http://127.0.0.1:{port}")
    except Exception:
        pass

    return streamlit_cli.main()


def main() -> int:
    base_dir, web_dir, app_py = resolve_paths()

    # Prepare user data directory and environment
    user_data_dir = get_user_data_dir()
    ensure_dirs(user_data_dir)
    os.environ.setdefault("GOLDFLIPPER_DATA_DIR", str(user_data_dir))

    write_boot_log(user_data_dir, f"Starting entrypoint. base_dir={base_dir} web_dir={web_dir} app={app_py}")

    # First-run DB seed
    try:
        seed_database_if_needed(base_dir, user_data_dir)
    except Exception as exc:
        write_boot_log(user_data_dir, f"DB seed error: {exc}")

    # Pick a port and launch
    port = find_free_port(8501, 20)
    write_boot_log(user_data_dir, f"Launching Streamlit on 127.0.0.1:{port}")

    if not app_py.exists():
        write_boot_log(user_data_dir, f"ERROR: app.py not found at {app_py}")
        return 2

    try:
        return launch_streamlit(app_py, port)
    except SystemExit as sys_exit:
        # Streamlit may call sys.exit
        return int(getattr(sys_exit, "code", 0) or 0)
    except Exception as exc:
        write_boot_log(user_data_dir, f"Launch error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
