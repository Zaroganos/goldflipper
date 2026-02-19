from __future__ import annotations

import argparse
import importlib
import logging
import os
import sys
from pathlib import Path

# Import exe-aware path utilities
from goldflipper.utils.exe_utils import (
    debug_paths,
    get_config_dir,
    get_executable_dir,
    get_settings_path,
    get_settings_template_path,
    is_frozen,
)

LOGGER = logging.getLogger("goldflipper.launcher")


def _print_startup_debug() -> None:
    """Print debug information about paths at startup."""
    # Always print critical path info for debugging first-run issues
    print("=" * 60)
    print("Goldflipper Startup Debug Info")
    print("=" * 60)
    try:
        # Always show these critical values
        frozen = is_frozen()
        print(f"  is_frozen: {frozen}")
        print(f"  sys.executable: {sys.executable}")
        print(f"  sys.argv[0]: {sys.argv[0] if sys.argv else 'N/A'}")

        settings_path = get_settings_path()
        print(f"  config_dir: {get_config_dir()}")
        print(f"  settings_path: {settings_path}")
        print(f"  settings_exists: {settings_path.exists()}")

        # Show full debug paths only if GOLDFLIPPER_DEBUG or frozen
        if os.environ.get("GOLDFLIPPER_DEBUG") or frozen:
            paths = debug_paths()
            print()
            print("  [Full Path Debug]")
            for key, value in paths.items():
                # Highlight critical issues
                if key.endswith("_exists") and value is False:
                    print(f"  {key}: {value}  <-- WARNING: File missing!")
                else:
                    print(f"  {key}: {value}")

        # Additional critical checks
        if not settings_path.exists():
            template_path = get_settings_template_path()
            print()
            print("  NOTICE: settings.yaml not found - first-run setup will launch")
            print(f"  Template path: {template_path}")
            print(f"  Template exists: {template_path.exists()}")
            if not template_path.exists():
                print("  ERROR: Cannot create settings - template file missing!")
                print("  This usually means the build didn't include the config data.")
    except Exception as e:
        print(f"  ERROR getting debug paths: {e}")
        import traceback

        traceback.print_exc()
    print("=" * 60)
    print()


def _settings_path() -> Path:
    """Return the canonical path to the primary settings file.

    In frozen (exe) mode: returns path NEXT TO the exe (persistent).
    In source mode: returns path in goldflipper/config/.
    """
    return get_settings_path()


def _get_setup_marker_path() -> Path:
    """Get path to the setup completion marker file."""
    return get_executable_dir() / ".setup_complete"


def _run_first_run_setup(force: bool) -> bool:
    """
    Launch the first-run wizard when required.

    The wizard shows on fresh installs (no .setup_complete marker) OR when forced.
    Settings file existence determines whether settings are pre-loaded as defaults.

    Returns True when a previously-missing settings file is created during this
    invocation. This allows the TUI to display the onboarding affordances.
    """
    settings_file = _settings_path()
    existed_before = settings_file.exists()
    marker_file = _get_setup_marker_path()
    setup_done_before = marker_file.exists()

    # Always print this check for debugging (visible in console)
    print(f"[Launcher] Settings file: {settings_file} (exists: {existed_before})")
    print(f"[Launcher] Setup marker: {marker_file} (exists: {setup_done_before})")
    print(f"[Launcher] force: {force}")

    # Show wizard if: forced OR setup hasn't been completed yet
    if not force and setup_done_before:
        print("[Launcher] Setup not needed - skipping wizard")
        return False

    print("[Launcher] Launching first-run setup wizard...")

    try:
        from goldflipper.first_run_setup import FirstRunSetup
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("First-run setup unavailable: %s", exc)
        print(f"[Launcher] ERROR: First-run setup import failed: {exc}")
        return False

    LOGGER.info(
        "Launching first-run setup (force=%s, setup_done_before=%s, settings_existed=%s)",
        force,
        setup_done_before,
        existed_before,
    )
    try:
        FirstRunSetup().run()
        # Mark setup as complete so wizard doesn't show on every launch
        marker_file.touch()
        print(f"[Launcher] Setup complete - marker created at {marker_file}")

        # Reload config after wizard creates/modifies settings
        from goldflipper.config.config import reload_config

        reload_config()
        print("[Launcher] Config reloaded after setup")
    except Exception as exc:  # pragma: no cover - GUI loop exceptions
        LOGGER.error("First-run setup terminated unexpectedly: %s", exc)
        print(f"[Launcher] ERROR: First-run setup crashed: {exc}")

    created_now = (not existed_before) and settings_file.exists()
    if created_now:
        LOGGER.info("Settings profile created at %s", settings_file)
    return created_now


def _configure_terminal_for_textual() -> None:
    """Configure terminal environment for optimal Textual rendering.

    This helps with conhost (legacy Windows console) which has limited
    Unicode rendering compared to Windows Terminal.
    """
    import os

    # Force color output even if terminal detection fails
    os.environ.setdefault("FORCE_COLOR", "1")

    # Ensure proper color mode (truecolor if supported)
    os.environ.setdefault("COLORTERM", "truecolor")

    # On Windows, set PYTHONIOENCODING to UTF-8 for consistent encoding
    if os.name == "nt":
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")

        # Enable VT processing for ANSI escape codes in conhost
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            # Get stdout handle
            STD_OUTPUT_HANDLE = -11
            handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
            # Get current mode
            mode = ctypes.c_ulong()
            kernel32.GetConsoleMode(handle, ctypes.byref(mode))
            # Enable ENABLE_VIRTUAL_TERMINAL_PROCESSING (0x0004)
            ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
        except Exception:
            pass  # Ignore if this fails - not critical


def _launch_tui() -> None:
    """Start the Textual interface."""
    from goldflipper.goldflipper_tui import GoldflipperTUI, resize_terminal

    # Configure terminal for optimal Textual rendering (especially in conhost)
    _configure_terminal_for_textual()

    # Resize terminal window before Textual takes over (Windows only)
    # Note: launch_goldflipper.bat handles this more reliably for batch launches
    resize_terminal(120, 40)

    app = GoldflipperTUI()
    app.run()


def _run_tool(tool_name: str) -> int:
    """
    Run a specific tool directly.

    This allows the exe to be launched with --tool <name> to run a specific
    tool in its own process (essential for Tkinter GUI tools).

    Supported tools:
    - play_creator_gui: Tkinter GUI for creating plays
    - configuration: Settings editor
    - view_plays: Textual UI for viewing plays
    - system_status: System status checker
    - option_data_fetcher: Option data tool
    - auto_play_creator: Auto play creator
    - chart_viewer: Chart viewer
    - trade_logger: Trade logger UI
    - get_alpaca_info: Alpaca account info
    """
    print(f"[Launcher] Running tool: {tool_name}")

    # Map tool names to module paths and entry functions
    TOOL_MAP = {
        "play_creator_gui": ("goldflipper.tools.play_creator_gui", "main"),
        "configuration": ("goldflipper.tools.configuration", "main"),
        "view_plays": ("goldflipper.tools.view_plays", "main"),
        "system_status": ("goldflipper.tools.system_status", "check_system_status"),
        "option_data_fetcher": ("goldflipper.tools.option_data_fetcher", "main"),
        "auto_play_creator": ("goldflipper.tools.auto_play_creator", "main"),
        "play_creation_tool": ("goldflipper.tools.play_creation_tool", "main"),
        "chart_viewer": ("goldflipper.chart.chart_viewer", "main"),
        "trade_logger": ("goldflipper.trade_logging.trade_logger_ui", "main"),
        "get_alpaca_info": ("goldflipper.tools.get_alpaca_info", "main"),
    }

    if tool_name not in TOOL_MAP:
        print(f"[ERROR] Unknown tool: {tool_name}")
        print(f"[ERROR] Available tools: {', '.join(TOOL_MAP.keys())}")
        return 1

    module_path, entry_func = TOOL_MAP[tool_name]

    try:
        print(f"[Launcher] Importing {module_path}")
        module = importlib.import_module(module_path)

        if hasattr(module, entry_func):
            print(f"[Launcher] Calling {entry_func}()")
            getattr(module, entry_func)()
        elif hasattr(module, "run"):
            print("[Launcher] Calling run()")
            module.run()
        elif hasattr(module, "main"):
            print("[Launcher] Calling main()")
            module.main()
        else:
            print("[Launcher] No entry function found, module may run on import")

        return 0
    except Exception as e:
        import traceback

        print(f"\n{'=' * 60}")
        print(f"[ERROR] Failed to run tool: {tool_name}")
        print(f"[ERROR] Module: {module_path}")
        print(f"[ERROR] Exception: {e}")
        print(f"{'=' * 60}")
        traceback.print_exc()
        print(f"{'=' * 60}")
        input("\nPress Enter to exit...")
        return 1


def main(argv: list[str] | None = None) -> int:
    """
    Entry point for the packaged Goldflipper desktop experience.

    - Runs the onboarding wizard on the very first launch.
    - Falls back to the existing configuration afterwards.
    - Starts the Textual TUI by default.

    Special exe-mode arguments:
    - --trading-mode: Run the trading system directly (for spawned processes)
    - --service-install: Install the Windows service
    - --service-remove: Remove the Windows service
    """
    # Print debug info at startup (always in frozen mode, or when GOLDFLIPPER_DEBUG is set)
    _print_startup_debug()

    parser = argparse.ArgumentParser(description="Goldflipper Desktop Launcher")
    parser.add_argument(
        "--force-setup",
        action="store_true",
        help="Always run the configuration wizard before launching the TUI.",
    )
    parser.add_argument(
        "--skip-setup",
        action="store_true",
        help="Never launch the configuration wizard (even on first run).",
    )
    parser.add_argument(
        "--setup-only",
        action="store_true",
        help="Run the configuration wizard and exit without launching the TUI.",
    )
    # Exe-mode special arguments
    parser.add_argument(
        "--trading-mode",
        action="store_true",
        help="Run the trading system directly (used when launching from exe TUI).",
    )
    parser.add_argument(
        "--service-install",
        action="store_true",
        help="Install the Windows service (requires admin privileges).",
    )
    parser.add_argument(
        "--service-remove",
        action="store_true",
        help="Remove the Windows service (requires admin privileges).",
    )
    parser.add_argument(
        "--tool",
        type=str,
        help="Launch a specific tool directly (e.g., --tool play_creator_gui).",
    )
    args = parser.parse_args(argv)

    # Handle special exe-mode arguments
    if args.tool:
        return _run_tool(args.tool)

    if args.trading_mode:
        # CRITICAL DEBUG: Print sys.argv and is_frozen BEFORE importing run module
        # This helps diagnose path resolution issues in subprocess
        print("\n[TRADING MODE DEBUG]")
        print(f"  sys.argv = {sys.argv}")
        print(f"  sys.argv[0] = {sys.argv[0] if sys.argv else 'EMPTY'}")
        print(f"  is_frozen() = {is_frozen()}")
        print(f"  get_settings_path() = {get_settings_path()}")
        print(f"  settings exists = {get_settings_path().exists()}")
        print()

        LOGGER.info("Trading mode requested; launching trading system directly.")
        try:
            from goldflipper.run import run_trading_system

            run_trading_system(console_mode=True)
            return 0
        except Exception as e:
            import traceback

            print(f"\n{'=' * 60}")
            print("[ERROR] Trading system suffered a fatal error!")
            print(f"[ERROR] Exception: {e}")
            print(f"{'=' * 60}")
            traceback.print_exc()
            print(f"{'=' * 60}")
            input("\nPress Enter to exit...")
            return 1

    if args.service_install:
        LOGGER.info("Service installation requested.")
        import win32serviceutil

        from goldflipper.run import GoldflipperService

        win32serviceutil.HandleCommandLine(GoldflipperService, argv=["", "--startup", "auto", "install"])
        return 0

    if args.service_remove:
        LOGGER.info("Service removal requested.")
        import win32serviceutil

        from goldflipper.run import GoldflipperService

        win32serviceutil.HandleCommandLine(GoldflipperService, argv=["", "remove"])
        return 0

    # Normal TUI launch flow
    settings_created = False
    if not args.skip_setup:
        settings_created = _run_first_run_setup(force=args.force_setup)

    config_module = importlib.import_module("goldflipper.config.config")
    if settings_created:
        # Signal to the TUI that the onboarding workflow just completed so it
        # can highlight the configuration button and show notifications.
        config_module.settings_just_created = True

    if args.setup_only:
        LOGGER.info("Setup-only mode requested; exiting before launching TUI.")
        return 0

    _launch_tui()
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry point
    raise SystemExit(main())
